"""
MarketPulse Core — Rasmiy Ozon Seller API moduli.

Xususiyatlari:
- Hech qanday kalit kod ichida saqlanmaydi — faqat .env dagi `OZON_CLIENT_ID`
  va `OZON_API_KEY` ishlatiladi.
- Anti-bot va CAPTCHA cheklovlarisiz 100% rasmiy API orqali ishlaydi:
  1. POST /v3/product/list       — barcha product_id larni olish (sahifalash bilan)
  2. POST /v3/product/info/list  — mahsulot nomi, SKU/havola va asosiy narxlari
  3. POST /v5/product/info/prices — eng yangi joriy narx va valyuta
- 3 martalik retry (5 soniya pauza), timeout=60 va kalitlarni loglardan yashirish himoyasi.
"""

import os
import time
from typing import Any

from dotenv import load_dotenv
import requests

from parsers.universal import narxni_tozalash, valyutani_aniqlash
from utils import loggerni_olish


logger = loggerni_olish("parsers.ozon_api")

OZON_API_BASE = "https://api-seller.ozon.ru"
SO_ROV_TIMEOUT = 60
MAKS_URINISHLAR = 3
QAYTA_URINISH_PAUZA = 5
PARTIYA_HAJMI = 100


def ozon_kalitlarini_olish() -> tuple[str, str]:
    """`.env` faylidan OZON_CLIENT_ID va OZON_API_KEY qiymatlarini o'qiydi."""
    load_dotenv(override=True)
    client_id = os.getenv("OZON_CLIENT_ID", "").strip()
    api_key = os.getenv("OZON_API_KEY", "").strip()
    return client_id, api_key


def ozon_sozlanganmi() -> bool:
    """Ozon Seller API kalitlari `.env` da to'ldirilganligini tekshiradi."""
    client_id, api_key = ozon_kalitlarini_olish()
    return bool(client_id and api_key)


def _ozon_sorov_yuborish(
    endpoint: str,
    payload: dict[str, Any],
    client_id: str,
    api_key: str,
    proksi: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Ozon Seller API ga POST so'rov yuboradi (timeout=60, 3x retry, 5s pauza)."""
    url = f"{OZON_API_BASE}{endpoint}"
    sarlavhalar = {
        "Client-Id": client_id,
        "Api-Key": api_key,
        "Content-Type": "application/json",
    }

    for urinish in range(1, MAKS_URINISHLAR + 1):
        try:
            javob = requests.post(
                url,
                json=payload,
                headers=sarlavhalar,
                proxies=proksi,
                timeout=SO_ROV_TIMEOUT,
            )

            if javob.status_code in (401, 403):
                raise requests.HTTPError(
                    f"Ozon API ruxsat xatosi ({javob.status_code}): "
                    "OZON_CLIENT_ID yoki OZON_API_KEY noto'g'ri yoki huquqi yetarli emas.",
                    response=javob,
                )

            if (javob.status_code == 429 or 500 <= javob.status_code < 600) and urinish < MAKS_URINISHLAR:
                logger.warning(
                    "Ozon API vaqtinchalik holat (%d, %s), %d soniya kutilmoqda (%d/%d)...",
                    javob.status_code,
                    endpoint,
                    QAYTA_URINISH_PAUZA,
                    urinish,
                    MAKS_URINISHLAR,
                )
                time.sleep(QAYTA_URINISH_PAUZA)
                continue

            javob.raise_for_status()
            return javob.json()

        except (requests.ConnectionError, requests.Timeout) as xato:
            xavfsiz = str(xato).replace(api_key, "***")
            if urinish < MAKS_URINISHLAR:
                logger.warning(
                    "Ozon API ulanish xatosi (%s, %d/%d): %s. %d soniya kutilmoqda...",
                    endpoint,
                    urinish,
                    MAKS_URINISHLAR,
                    xavfsiz,
                    QAYTA_URINISH_PAUZA,
                )
                time.sleep(QAYTA_URINISH_PAUZA)
                continue
            raise

    raise requests.RequestException(f"Ozon API ({endpoint}) barcha qayta urinishlardan so'ng javob bermadi.")


def _ozon_mahsulot_havolasi(info: dict[str, Any], product_id: int) -> str:
    """Ozon mahsuloti uchun bosiladigan rasmiy havolani shakllantiradi."""
    sku = info.get("sku") or info.get("fbs_sku") or info.get("fbo_sku")
    if not sku and isinstance(info.get("sources"), list):
        for manba in info["sources"]:
            if isinstance(manba, dict) and manba.get("sku"):
                sku = manba["sku"]
                break
    identifikator = sku or product_id
    return f"https://www.ozon.ru/product/{identifikator}/"


def _royxatni_ajratish(javob: dict[str, Any]) -> list[dict[str, Any]]:
    """Ozon API javobidan (`items` yoki `result.items` yoki `result`) ro'yxatni xavfsiz oladi."""
    if isinstance(javob.get("items"), list):
        return javob["items"]
    natija = javob.get("result")
    if isinstance(natija, list):
        return natija
    if isinstance(natija, dict) and isinstance(natija.get("items"), list):
        return natija["items"]
    return []


def ozon_mahsulotlarini_olish(maks_soni: int = 200) -> list[dict[str, Any]]:
    """
    Rasmiy Ozon Seller API orqali do'kondagi mahsulotlar (nomi, joriy narxi,
    valyutasi, reytingi va havolasi) ro'yxatini yig'ib qaytaradi.
    """
    client_id, api_key = ozon_kalitlarini_olish()
    if not client_id or not api_key:
        logger.info("Ozon Seller API sozlanmagan (OZON_CLIENT_ID / OZON_API_KEY bo'sh).")
        return []

    proksi_url = os.getenv("PROXY_URL", "").strip()
    proksi = {"http": proksi_url, "https": proksi_url} if proksi_url else None

    print("[Ozon API] Rasmiy Ozon Seller API orqali mahsulotlar yuklanmoqda...")
    logger.info("Ozon Seller API yuklash boshlandi (maks_soni=%d)...", maks_soni)

    try:
        # 1. Barcha product_id larni /v3/product/list dan olish
        product_idlar: list[int] = []
        last_id = ""

        while len(product_idlar) < maks_soni:
            qolgan = min(PARTIYA_HAJMI, maks_soni - len(product_idlar))
            list_javob = _ozon_sorov_yuborish(
                "/v3/product/list",
                payload={
                    "filter": {"visibility": "ALL"},
                    "last_id": last_id,
                    "limit": qolgan,
                },
                client_id=client_id,
                api_key=api_key,
                proksi=proksi,
            )
            elementlar = _royxatni_ajratish(list_javob)
            if not elementlar:
                break

            for el in elementlar:
                pid = el.get("product_id")
                if pid is not None:
                    product_idlar.append(int(pid))

            yangi_last_id = ""
            if isinstance(list_javob.get("result"), dict):
                yangi_last_id = str(list_javob["result"].get("last_id", "") or "")
            else:
                yangi_last_id = str(list_javob.get("last_id", "") or "")

            if not yangi_last_id or yangi_last_id == last_id or len(elementlar) < qolgan:
                break
            last_id = yangi_last_id

        if not product_idlar:
            print("[Ozon API] OGOHLANTIRISH: Ozon kabinetida mahsulotlar topilmadi (0 ta).")
            logger.warning("Ozon Seller API 0 ta mahsulot qaytardi.")
            return []

        # 2. /v3/product/info/list orqali nom, SKU va asosiy narxlarni olish
        info_xarita: dict[int, dict[str, Any]] = {}
        for bosh in range(0, len(product_idlar), PARTIYA_HAJMI):
            partiya = product_idlar[bosh : bosh + PARTIYA_HAJMI]
            info_javob = _ozon_sorov_yuborish(
                "/v3/product/info/list",
                payload={"product_id": partiya},
                client_id=client_id,
                api_key=api_key,
                proksi=proksi,
            )
            for info in _royxatni_ajratish(info_javob):
                pid = info.get("id") or info.get("product_id")
                if pid is not None:
                    info_xarita[int(pid)] = info

        # 3. /v5/product/info/prices orqali eng aniq joriy narxlarni olish
        narx_xarita: dict[int, dict[str, Any]] = {}
        for bosh in range(0, len(product_idlar), PARTIYA_HAJMI):
            partiya = product_idlar[bosh : bosh + PARTIYA_HAJMI]
            try:
                narx_javob = _ozon_sorov_yuborish(
                    "/v5/product/info/prices",
                    payload={
                        "filter": {"product_id": partiya, "visibility": "ALL"},
                        "limit": len(partiya),
                    },
                    client_id=client_id,
                    api_key=api_key,
                    proksi=proksi,
                )
                for item in _royxatni_ajratish(narx_javob):
                    pid = item.get("product_id")
                    if pid is not None:
                        narx_xarita[int(pid)] = item
            except requests.RequestException as narx_xatosi:
                logger.warning(
                    "Ozon /v5/product/info/prices qisman xato berdi — /v3 narxlari ishlatiladi: %s",
                    str(narx_xatosi).replace(api_key, "***"),
                )

        # 4. MarketPulse standart formatiga birlashtirish
        mahsulotlar: list[dict[str, Any]] = []
        for pid in product_idlar:
            info = info_xarita.get(pid, {})
            narx_item = narx_xarita.get(pid, {})
            narx_obyekt = narx_item.get("price") if isinstance(narx_item.get("price"), dict) else {}

            nomi = str(info.get("name") or info.get("offer_id") or f"Ozon mahsulot #{pid}").strip()

            xom_narx = (
                narx_obyekt.get("price")
                or narx_obyekt.get("marketing_seller_price")
                or info.get("price")
            )
            narx = narxni_tozalash(xom_narx)

            xom_valyuta = (
                narx_obyekt.get("currency_code")
                or info.get("currency_code")
                or "RUB"
            )
            valyuta = valyutani_aniqlash(str(xom_valyuta), standart="₽")

            havola = _ozon_mahsulot_havolasi(info, pid)

            mahsulotlar.append(
                {
                    "nomi": nomi,
                    "narx": narx,
                    "valyuta": valyuta,
                    "reyting": 0,
                    "url": havola,
                }
            )

        print(f"[Ozon API] Muvaffaqiyatli yakunlandi: {len(mahsulotlar)} ta mahsulot olindi.")
        logger.info("Ozon Seller API muvaffaqiyatli yakunlandi: %d ta mahsulot.", len(mahsulotlar))
        return mahsulotlar

    except requests.RequestException as xato:
        xavfsiz = str(xato).replace(api_key, "***")
        print(f"[Ozon API] XATOLIK: {xavfsiz}")
        logger.error("Ozon Seller API xatoligi: %s", xavfsiz)
        return []
