"""
MarketPulse Core — Rasmiy Uzum Market Seller OpenAPI moduli (Read + Admin Write).

Xususiyatlari:
- Hech qanday kalit kod ichida saqlanmaydi — faqat .env dagi `UZUM_API_KEY`
  (va ixtiyoriy `UZUM_SHOP_ID`) ishlatiladi.
- Rasmiy Uzum Seller OpenAPI (`https://api-seller.uzum.uz/api/seller-openapi`):
  1. GET  /v1/shops                       — do'konlar ro'yxatini olish
  2. GET  /v1/product/shop/{shopId}       — mahsulotlar, SKU, narx, qoldiq, sotuv, vozvrat, komissiya
  3. POST /v1/product/{shopId}/sendPriceData — tasdiqlangan yangi narxni Uzum'ga yuborish
- `Authorization: <UZUM_API_KEY>` sarlavhasi (Bearer prefiksisiz).
- 3 martalik retry (5 soniya pauza), timeout=60, `so'm` valyutasi va kalitni loglardan yashirish.
"""

import os
import time
from typing import Any

from dotenv import load_dotenv
import requests

from parsers.universal import narxni_tozalash, reytingni_aniqlash
from utils import loggerni_olish


logger = loggerni_olish("parsers.uzum_api")

UZUM_API_BASE = "https://api-seller.uzum.uz/api/seller-openapi"
SO_ROV_TIMEOUT = 60
MAKS_URINISHLAR = 3
QAYTA_URINISH_PAUZA = 5
SAHIFA_HAJMI = 100


def uzum_kalitlarini_olish() -> tuple[str, str]:
    """`.env` faylidan UZUM_API_KEY va ixtiyoriy UZUM_SHOP_ID qiymatlarini o'qiydi."""
    load_dotenv(override=True)
    api_key = os.getenv("UZUM_API_KEY", "").strip()
    shop_id = os.getenv("UZUM_SHOP_ID", "").strip()
    return api_key, shop_id


def uzum_sozlanganmi() -> bool:
    """Uzum Seller OpenAPI kaliti `.env` da to'ldirilganligini tekshiradi."""
    api_key, _ = uzum_kalitlarini_olish()
    return bool(api_key)


def _proksi_olish() -> dict[str, str] | None:
    """Ixtiyoriy PROXY_URL sozlamasini qaytaradi."""
    proksi_url = os.getenv("PROXY_URL", "").strip()
    return {"http": proksi_url, "https": proksi_url} if proksi_url else None


def _uzum_sorov_yuborish(
    endpoint: str,
    api_key: str,
    metod: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    proksi: dict[str, str] | None = None,
) -> Any:
    """Uzum Seller OpenAPI ga GET/POST so'rov yuboradi (timeout=60, 3x retry, 5s pauza)."""
    url = f"{UZUM_API_BASE}{endpoint}"
    sarlavhalar = {
        "Authorization": api_key,
        "Accept": "application/json",
    }
    if json_body is not None:
        sarlavhalar["Content-Type"] = "application/json"

    for urinish in range(1, MAKS_URINISHLAR + 1):
        try:
            javob = requests.request(
                method=metod,
                url=url,
                params=params,
                json=json_body,
                headers=sarlavhalar,
                proxies=proksi,
                timeout=SO_ROV_TIMEOUT,
            )

            if javob.status_code in (401, 403):
                raise requests.HTTPError(
                    f"Uzum API ruxsat xatosi ({javob.status_code}): "
                    "UZUM_API_KEY noto'g'ri yoki ushbu amal uchun huquqi yetarli emas.",
                    response=javob,
                )

            if (javob.status_code == 429 or 500 <= javob.status_code < 600) and urinish < MAKS_URINISHLAR:
                logger.warning(
                    "Uzum API vaqtinchalik holat (%d, %s), %d soniya kutilmoqda (%d/%d)...",
                    javob.status_code,
                    endpoint,
                    QAYTA_URINISH_PAUZA,
                    urinish,
                    MAKS_URINISHLAR,
                )
                time.sleep(QAYTA_URINISH_PAUZA)
                continue

            javob.raise_for_status()
            return javob.json() if javob.content else {}

        except (requests.ConnectionError, requests.Timeout) as xato:
            xavfsiz = str(xato).replace(api_key, "***")
            if urinish < MAKS_URINISHLAR:
                logger.warning(
                    "Uzum API ulanish xatosi (%s, %d/%d): %s. %d soniya kutilmoqda...",
                    endpoint,
                    urinish,
                    MAKS_URINISHLAR,
                    xavfsiz,
                    QAYTA_URINISH_PAUZA,
                )
                time.sleep(QAYTA_URINISH_PAUZA)
                continue
            raise

    raise requests.RequestException(f"Uzum API ({endpoint}) barcha qayta urinishlardan so'ng javob bermadi.")


def _dokon_idlarini_ajratish(javob: Any) -> list[int]:
    """`/v1/shops` javobidan do'kon ID lari ro'yxatini xavfsiz ajratadi."""
    if isinstance(javob, list):
        royxat = javob
    elif isinstance(javob, dict):
        royxat = javob.get("payload") or javob.get("shops") or javob.get("items") or []
    else:
        royxat = []

    idlar: list[int] = []
    for item in royxat:
        if isinstance(item, dict):
            sid = item.get("id") or item.get("shopId")
            if sid is not None:
                idlar.append(int(sid))
    return idlar


def _mahsulotlar_royxatini_ajratish(javob: Any) -> list[dict[str, Any]]:
    """`/v1/product/shop/{shopId}` javobidan mahsulotlar ro'yxatini xavfsiz ajratadi."""
    if isinstance(javob, list):
        return javob
    if isinstance(javob, dict):
        if isinstance(javob.get("productList"), list):
            return javob["productList"]
        if isinstance(javob.get("items"), list):
            return javob["items"]
        payload = javob.get("payload")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for kalit in ("productList", "items", "products", "content"):
                if isinstance(payload.get(kalit), list):
                    return payload[kalit]
    return []


def _mahsulot_narxini_olish(mahsulot: dict[str, Any]) -> float:
    """Uzum mahsulot obyektidan (yoki uning birinchi faol SKU sidan) narxni oladi."""
    for kalit in ("price", "sellPrice", "purchasePrice", "minSellPrice"):
        qiymat = mahsulot.get(kalit)
        if qiymat is not None:
            narx = narxni_tozalash(qiymat)
            if narx > 0:
                return narx

    sku_royxat = mahsulot.get("skuList") or mahsulot.get("skus") or []
    if isinstance(sku_royxat, list):
        for sku in sku_royxat:
            if not isinstance(sku, dict):
                continue
            for kalit in ("price", "sellPrice", "purchasePrice", "fullPrice"):
                qiymat = sku.get(kalit)
                if qiymat is not None:
                    narx = narxni_tozalash(qiymat)
                    if narx > 0:
                        return narx
    return 0.0


def _komissiyani_olish(item: dict[str, Any], asosiy_sku: dict[str, Any]) -> float:
    """Mahsulotning Uzum komissiya foizini xavfsiz ajratadi."""
    kom_dto = item.get("commissionDto")
    if isinstance(kom_dto, dict):
        qiymat = kom_dto.get("maxCommission") or kom_dto.get("minCommission")
        if qiymat is not None:
            return round(float(qiymat), 2)
    for manba in (item.get("commission"), asosiy_sku.get("commission")):
        if manba is not None:
            try:
                return round(float(manba), 2)
            except (TypeError, ValueError):
                pass
    return 0.0


def _logistika_tolovini_olish(item: dict[str, Any], asosiy_sku: dict[str, Any]) -> float:
    """Agar Uzum API logistika to'lovini bersa ajratadi, bermasa 0.0 qaytaradi."""
    kalitlar = ("logisticFee", "logisticsFee", "deliveryFee", "logisticsCost", "logisticPrice")
    for obyekt in (item, asosiy_sku):
        if not isinstance(obyekt, dict):
            continue
        for kalit in kalitlar:
            qiymat = obyekt.get(kalit)
            if qiymat is not None:
                try:
                    son = float(qiymat)
                    if son > 0:
                        return round(son, 2)
                except (TypeError, ValueError):
                    pass
    return 0.0


def uzum_mahsulotlarini_olish(maks_soni: int = 200) -> list[dict[str, Any]]:
    """
    Rasmiy Uzum Seller OpenAPI orqali do'kondagi barcha mahsulotlarni
    (narx, qoldiq, sotuv, vozvrat %, komissiya %, SKU ID va havola) yig'ib qaytaradi.
    """
    api_key, belgilangan_shop_id = uzum_kalitlarini_olish()
    if not api_key:
        logger.info("Uzum Seller OpenAPI sozlanmagan (UZUM_API_KEY bo'sh).")
        return []

    proksi = _proksi_olish()
    print("[Uzum API] Rasmiy Uzum Market Seller OpenAPI orqali mahsulotlar yuklanmoqda...")
    logger.info("Uzum Seller OpenAPI yuklash boshlandi (maks_soni=%d)...", maks_soni)

    try:
        if belgilangan_shop_id and belgilangan_shop_id.isdigit():
            dokon_idlar = [int(belgilangan_shop_id)]
        else:
            dokonlar_javobi = _uzum_sorov_yuborish("/v1/shops", api_key=api_key, proksi=proksi)
            dokon_idlar = _dokon_idlarini_ajratish(dokonlar_javobi)

        if not dokon_idlar:
            print("[Uzum API] OGOHLANTIRISH: API kalitga bog'langan do'kon topilmadi.")
            logger.warning("Uzum Seller OpenAPI: 0 ta do'kon topildi.")
            return []

        mahsulotlar: list[dict[str, Any]] = []
        for shop_id in dokon_idlar:
            sahifa = 0
            while len(mahsulotlar) < maks_soni:
                qolgan = min(SAHIFA_HAJMI, maks_soni - len(mahsulotlar))
                javob = _uzum_sorov_yuborish(
                    f"/v1/product/shop/{shop_id}",
                    api_key=api_key,
                    params={"size": qolgan, "page": sahifa},
                    proksi=proksi,
                )
                elementlar = _mahsulotlar_royxatini_ajratish(javob)
                if not elementlar:
                    break

                for item in elementlar:
                    if len(mahsulotlar) >= maks_soni:
                        break
                    pid = item.get("productId") or item.get("id")
                    if pid is None:
                        continue

                    sku_royxat = item.get("skuList") or []
                    asosiy_sku = (
                        sku_royxat[0]
                        if isinstance(sku_royxat, list) and sku_royxat and isinstance(sku_royxat[0], dict)
                        else {}
                    )

                    status_obyekt = item.get("status")
                    holat_matni = (
                        str(status_obyekt.get("title", "")).strip()
                        if isinstance(status_obyekt, dict)
                        else ""
                    )

                    nomi = str(item.get("title") or item.get("name") or f"Uzum mahsulot #{pid}").strip()
                    narx = _mahsulot_narxini_olish(item)
                    reyting = reytingni_aniqlash(item.get("rating"))
                    havola = f"https://uzum.uz/uz/product/{pid}"

                    qoldiq = int(item.get("quantityAvailable") or asosiy_sku.get("quantityAvailable") or 0)
                    sotilgan = int(item.get("quantitySold") or asosiy_sku.get("quantitySold") or 0)
                    qaytgan = int(item.get("quantityReturned") or asosiy_sku.get("quantityReturned") or 0)
                    vozvrat_foiz = round(
                        float(item.get("returnedPercentage") or asosiy_sku.get("returnedPercentage") or 0.0),
                        2,
                    )
                    komissiya_foiz = _komissiyani_olish(item, asosiy_sku)
                    logistika_tolovi = _logistika_tolovini_olish(item, asosiy_sku)
                    sku_id = asosiy_sku.get("skuId")
                    sku_title = str(asosiy_sku.get("skuTitle") or item.get("skuTitle") or "").strip()
                    sku_kodi = str(
                        asosiy_sku.get("skuFullTitle")
                        or sku_title
                        or (str(sku_id) if sku_id is not None else "")
                    ).strip()

                    mahsulotlar.append(
                        {
                            "nomi": nomi,
                            "narx": narx,
                            "valyuta": "so'm",
                            "reyting": reyting,
                            "url": havola,
                            "shop_id": int(shop_id),
                            "product_id": int(pid),
                            "sku_id": int(sku_id) if sku_id is not None else None,
                            "sku": sku_kodi,
                            "sku_title": sku_title,
                            "qoldiq": qoldiq,
                            "sotilgan": sotilgan,
                            "qaytgan": qaytgan,
                            "vozvrat_foiz": vozvrat_foiz,
                            "komissiya_foiz": komissiya_foiz,
                            "logistika_tolovi": logistika_tolovi,
                            "holat_matni": holat_matni,
                        }
                    )

                if len(elementlar) < qolgan:
                    break
                sahifa += 1

        if not mahsulotlar:
            print("[Uzum API] OGOHLANTIRISH: Uzum kabinetida mahsulotlar topilmadi (0 ta).")
            logger.warning("Uzum Seller OpenAPI 0 ta mahsulot qaytardi.")
        else:
            print(f"[Uzum API] Muvaffaqiyatli yakunlandi: {len(mahsulotlar)} ta mahsulot olindi.")
            logger.info("Uzum Seller OpenAPI muvaffaqiyatli yakunlandi: %d ta mahsulot.", len(mahsulotlar))

        return mahsulotlar

    except requests.RequestException as xato:
        xavfsiz = str(xato).replace(api_key, "***")
        print(f"[Uzum API] XATOLIK: {xavfsiz}")
        logger.error("Uzum Seller OpenAPI xatoligi: %s", xavfsiz)
        return []


def uzum_narx_ozgartirish(
    shop_id: int,
    product_id: int,
    sku_id: int,
    yangi_narx: int,
    eski_narx: int | None = None,
    sku_title: str = "",
) -> tuple[bool, str]:
    """
    Tasdiqlangan yangi narxni Uzum Seller OpenAPI (`POST /v1/product/{shopId}/sendPriceData`)
    orqali yangilaydi.

    Qaytaradi:
        (muvaffaqiyatli, o'zbekcha_xabar)
    """
    api_key, _ = uzum_kalitlarini_olish()
    if not api_key:
        return False, "❌ .env faylida UZUM_API_KEY sozlanmagan."

    if yangi_narx < 1 or yangi_narx > 999_999_000:
        return False, "❌ Narx 1 dan 999 999 000 so'm oralig'ida bo'lishi kerak."

    toliq_narx = max(int(yangi_narx), int(eski_narx)) if eski_narx and eski_narx > 0 else int(yangi_narx)
    payload: dict[str, Any] = {
        "productId": int(product_id),
        "skuList": [
            {
                "skuId": int(sku_id),
                "sellPrice": int(yangi_narx),
                "fullPrice": toliq_narx,
                "skuTitle": sku_title or "",
            }
        ],
    }

    logger.info(
        "Uzum narx yangilanmoqda: shop_id=%d, product_id=%d, sku_id=%d, sellPrice=%d, fullPrice=%d",
        shop_id,
        product_id,
        sku_id,
        yangi_narx,
        toliq_narx,
    )

    try:
        _uzum_sorov_yuborish(
            f"/v1/product/{shop_id}/sendPriceData",
            api_key=api_key,
            metod="POST",
            json_body=payload,
            proksi=_proksi_olish(),
        )
        logger.info(
            "Uzum narxi muvaffaqiyatli yangilandi: product_id=%d -> %d so'm",
            product_id,
            yangi_narx,
        )
        return True, f"✅ Uzum Market'dagi narx muvaffaqiyatli yangilandi: {yangi_narx:,} so'm".replace(",", " ")

    except requests.HTTPError as http_xato:
        status = http_xato.response.status_code if http_xato.response is not None else 0
        if status in (401, 403):
            xabar = (
                "❌ API kalitingizda narx o'zgartirish (Admin/Write) huquqi yo'q.\n"
                "Uzum Seller kabineti → API Keys bo'limidan mahsulot narxini tahrirlash "
                "huquqiga ega kalit olib `.env` dagi `UZUM_API_KEY` ni yangilang."
            )
            logger.error("Uzum sendPriceData ruxsat xatosi (%d): product_id=%d", status, product_id)
            return False, xabar

        tafsilot = ""
        if http_xato.response is not None:
            tafsilot = http_xato.response.text[:250].replace(api_key, "***")
        logger.error("Uzum sendPriceData HTTP xatosi (%d): %s", status, tafsilot)
        return False, f"❌ Uzum API xatosi ({status}): {tafsilot or 'Narxni yangilab bo‘lmadi.'}"

    except requests.RequestException as xato:
        xavfsiz = str(xato).replace(api_key, "***")
        logger.error("Uzum sendPriceData tarmoq xatosi: %s", xavfsiz)
        return False, f"❌ Tarmoq xatosi: {xavfsiz}"
