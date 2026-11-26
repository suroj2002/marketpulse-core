"""
MarketPulse Core — Universal Fallback, valyuta aniqlash va konfiguratsiya yuklovchi modul.

1. `sites_config.json` faylidan domenga mos CSS selektorlarni topadi.
2. Agar domen `sites_config.json` da topilmasa, **Universal Fallback** ishga tushadi:
   - `JSON-LD` (`application/ld+json`) ichidan `Product` ma'lumotlarini ajratadi;
   - `meta` teglardan (`og:title`, `product:price:amount`, `product:price:currency`) qidiradi;
   - DOM ichidagi narxga o'xshash elementlardan (class/id/itemprop) narx, valyuta va sarlavhani topadi.
"""

import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from utils import loggerni_olish


logger = loggerni_olish("parsers.universal")

KONFIG_FAYL_YOLLARI = (
    Path("sites_config.json"),
    Path(__file__).resolve().parent / "sites_config.json",
)

REYTING_XARITASI = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}

SOTUVDA_YOQ_IBORALAR = (
    "sotuvda yo'q",
    "sotuvda yoq",
    "mavjud emas",
    "out of stock",
    "unavailable",
    "нет в наличии",
)

NARX_DOM_SELEKTORLARI = (
    '[itemprop="price"]',
    '[data-testid*="price" i]',
    '[class*="price" i]',
    '[id*="price" i]',
    '[class*="narx" i]',
    '[class*="cost" i]',
    '[class*="amount" i]',
)

VALYUTA_BELGILARI: tuple[tuple[tuple[str, ...], str], ...] = (
    (("so'm", "som", "сўм", "сум", "uzs"), "so'm"),
    (("£", "gbp"), "£"),
    (("$", "usd"), "$"),
    (("€", "eur"), "€"),
    (("₽", "руб", "rub"), "₽"),
)


def domenni_olish(url: str) -> str:
    """URL manzilidan toza domen nomini (www. siz, kichik harfda) ajratadi."""
    tahlil = urlparse(url.strip())
    domen = (tahlil.netloc or "").lower().strip()
    if ":" in domen:
        domen = domen.split(":", 1)[0]
    if domen.startswith("www."):
        domen = domen[4:]
    return domen


def konfiguratsiyani_yuklash(konfig_yoli: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """`sites_config.json` faylini o'qib, domen -> selektorlar lug'atini qaytaradi."""
    yollari = (Path(konfig_yoli),) if konfig_yoli else KONFIG_FAYL_YOLLARI
    for yol in yollari:
        if yol.exists():
            try:
                malumot = json.loads(yol.read_text(encoding="utf-8"))
                if isinstance(malumot, dict):
                    return {k.lower().removeprefix("www."): v for k, v in malumot.items()}
            except (OSError, json.JSONDecodeError) as xato:
                logger.error("sites_config.json o'qishda xatolik (%s): %s", yol, xato)
                return {}
    logger.warning("sites_config.json topilmadi — barcha saytlar Universal Fallback bilan ishlaydi.")
    return {}


def sayt_konfiguratsiyasini_topish(
    url: str,
    konfig_yoli: str | Path | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """
    URL domeniga mos konfiguratsiyani `sites_config.json` dan qidiradi.
    Subdomenlarni ham qo'llab-quvvatlaydi (masalan: shop.example.com -> example.com).
    """
    domen = domenni_olish(url)
    konfig = konfiguratsiyani_yuklash(konfig_yoli)

    if domen in konfig:
        return domen, konfig[domen]

    for kalit, qiymat in konfig.items():
        if domen.endswith(f".{kalit}"):
            return kalit, qiymat

    return domen, None


def valyutani_aniqlash(matn: str | None, standart: str = "") -> str:
    """Narx matni yoki ISO kodidan (UZS, USD, GBP, EUR, RUB) valyuta belgisini aniqlaydi."""
    if not matn:
        return standart
    kichik = str(matn).strip().lower()
    for kalitlar, belgi in VALYUTA_BELGILARI:
        if any(k in kichik for k in kalitlar):
            return belgi
    return standart


def narxni_formatlash(narx: float, valyuta: str = "") -> str:
    """Narxni o'z valyutasiga mos chiroyli ko'rinishda formatlaydi."""
    belgi = (valyuta or "").strip()
    if belgi in ("£", "$", "€"):
        return f"{belgi}{narx:,.2f}"
    if belgi in ("so'm", "сум", "₽"):
        if float(narx).is_integer():
            return f"{narx:,.0f} {belgi}".replace(",", " ")
        return f"{narx:,.2f} {belgi}".replace(",", " ")
    if belgi:
        return f"{narx:,.2f} {belgi}"
    return f"{narx:,.2f}"


def narxni_tozalash(narx_matni: str | float | int | None) -> float:
    """
    Narx matnidan valyuta belgilari va ortiqcha simvollarni regex (re)
    yordamida tozalab, float turiga o'tkazadi.

    Agar narx topilmasa yoki mahsulot "Sotuvda yo'q" bo'lsa,
    dastur sinmasdan 0.0 qaytaradi.
    """
    if narx_matni is None:
        logger.warning("Narx qiymati bo'sh — 0.0 qiymati berildi.")
        return 0.0

    if isinstance(narx_matni, (int, float)):
        return float(narx_matni) if narx_matni >= 0 else 0.0

    matn = str(narx_matni).strip()
    if not matn:
        logger.warning("Narx matni bo'sh — 0.0 qiymati berildi.")
        return 0.0

    kichik_matn = matn.lower()
    if any(ibora in kichik_matn for ibora in SOTUVDA_YOQ_IBORALAR):
        logger.warning("Mahsulot sotuvda yo'q (%r) — 0.0 qiymati berildi.", matn)
        return 0.0

    # Bo'shliqlar bilan ajratilgan mingliklarni birlashtiramiz (masalan: "1 250 000 so'm")
    birlashtirilgan = re.sub(r"(?<=\d)[\s\u00a0](?=\d{3}\b)", "", matn)
    tozalangan = re.sub(r"[^\d.,]", "", birlashtirilgan)
    if not tozalangan:
        logger.warning("Narx matnidan raqam topilmadi (%r) — 0.0 qiymati berildi.", matn)
        return 0.0

    # Vergul o'nlik ajratuvchi bo'lsa nuqtaga almashtiramiz
    if "," in tozalangan and "." not in tozalangan:
        qismlar = tozalangan.split(",")
        if len(qismlar) == 2 and len(qismlar[1]) in (1, 2):
            tozalangan = tozalangan.replace(",", ".")
        else:
            tozalangan = tozalangan.replace(",", "")
    elif "," in tozalangan and "." in tozalangan:
        tozalangan = tozalangan.replace(",", "")

    moslik = re.search(r"\d+(?:\.\d+)?", tozalangan)
    if not moslik:
        logger.warning("Narxni raqamga aylantirib bo'lmadi (%r) — 0.0 qiymati berildi.", matn)
        return 0.0

    return float(moslik.group(0))


def reytingni_aniqlash(qiymat: Any) -> int:
    """HTML klass nomi yoki raqamli reytingdan 0..5 oralig'idagi butun reytingni aniqlaydi."""
    if qiymat is None:
        return 0

    if isinstance(qiymat, (int, float)):
        return max(0, min(5, int(round(float(qiymat)))))

    matn = str(qiymat).strip()
    if not matn:
        return 0

    for soz, son in REYTING_XARITASI.items():
        if soz in matn.split():
            return son

    moslik = re.search(r"(\d+(?:[.,]\d+)?)", matn)
    if moslik:
        try:
            son_qiymat = float(moslik.group(1).replace(",", "."))
            if 0 <= son_qiymat <= 5:
                return int(round(son_qiymat))
        except ValueError:
            pass
    return 0


def _json_ld_dan_mahsulot_topish(obyekt: Any) -> dict[str, Any] | None:
    """JSON-LD ichidan rekursiv ravishda `@type: Product` obyektini topadi."""
    if isinstance(obyekt, list):
        for element in obyekt:
            topilgan = _json_ld_dan_mahsulot_topish(element)
            if topilgan:
                return topilgan
        return None

    if not isinstance(obyekt, dict):
        return None

    turi = obyekt.get("@type")
    turlar = turi if isinstance(turi, list) else [turi]
    if any(isinstance(t, str) and t.lower() == "product" for t in turlar):
        nomi = str(obyekt.get("name", "")).strip()
        narx: float = 0.0
        valyuta = ""
        reyting: int = 0

        offers = obyekt.get("offers")
        if isinstance(offers, list) and offers:
            offers = offers[0]
        if isinstance(offers, dict):
            xom_narx = (
                offers.get("price")
                or offers.get("lowPrice")
                or offers.get("highPrice")
            )
            if xom_narx is not None:
                narx = narxni_tozalash(xom_narx)
                valyuta = valyutani_aniqlash(str(xom_narx))
            if not valyuta and offers.get("priceCurrency"):
                valyuta = valyutani_aniqlash(str(offers.get("priceCurrency")))

        agg_rating = obyekt.get("aggregateRating")
        if isinstance(agg_rating, dict):
            reyting = reytingni_aniqlash(agg_rating.get("ratingValue"))

        if nomi:
            return {"nomi": nomi, "narx": narx, "valyuta": valyuta, "reyting": reyting}

    if "@graph" in obyekt:
        return _json_ld_dan_mahsulot_topish(obyekt["@graph"])

    return None


def _meta_qiymat_olish(sahifa, selektorlar: tuple[str, ...]) -> str:
    """Sahifadagi meta teglardan birinchi bo'sh bo'lmagan `content` qiymatini oladi."""
    for selektor in selektorlar:
        try:
            element = sahifa.locator(selektor)
            if element.count() > 0:
                qiymat = element.first.get_attribute("content")
                if qiymat and qiymat.strip():
                    return qiymat.strip()
        except Exception:
            continue
    return ""


def universal_fallback_ajratish(sahifa, joriy_url: str) -> list[dict[str, Any]]:
    """
    Noma'lum saytlar uchun Universal Fallback mexanizmi:
    1. JSON-LD (`application/ld+json`) -> `Product`
    2. Meta teglar (`og:title`, `product:price:amount`, `product:price:currency`)
    3. DOM ichidagi sarlavha (`h1`/`title`) va narxga o'xshash elementlar
    """
    logger.info("Universal Fallback ishga tushdi: %s", joriy_url)

    nomi = ""
    narx = 0.0
    valyuta = ""
    reyting = 0

    # 1-bosqich: JSON-LD (application/ld+json)
    try:
        skriptlar = sahifa.locator('script[type="application/ld+json"]')
        for i in range(skriptlar.count()):
            xom_json = skriptlar.nth(i).inner_text().strip()
            if not xom_json:
                continue
            try:
                malumot = json.loads(xom_json)
            except json.JSONDecodeError:
                continue

            topilgan = _json_ld_dan_mahsulot_topish(malumot)
            if topilgan:
                nomi = topilgan["nomi"]
                narx = topilgan["narx"]
                valyuta = topilgan.get("valyuta", "")
                reyting = topilgan["reyting"]
                logger.info(
                    "Universal Fallback (JSON-LD) orqali topildi: nomi=%r, narx=%.2f (%s)",
                    nomi,
                    narx,
                    valyuta or "—",
                )
                break
    except Exception as xato:
        logger.warning("JSON-LD o'qishda xatolik: %s", xato)

    # 2-bosqich: Meta teglar (og:title, product:price:amount, product:price:currency)
    if not nomi:
        nomi = _meta_qiymat_olish(
            sahifa,
            (
                'meta[property="og:title"]',
                'meta[name="twitter:title"]',
                'meta[name="title"]',
            ),
        )
    if narx == 0.0:
        meta_narx = _meta_qiymat_olish(
            sahifa,
            (
                'meta[property="product:price:amount"]',
                'meta[property="og:price:amount"]',
                'meta[itemprop="price"]',
                'meta[name="price"]',
            ),
        )
        if meta_narx:
            narx = narxni_tozalash(meta_narx)
            if not valyuta:
                valyuta = valyutani_aniqlash(meta_narx)
            logger.info("Universal Fallback (meta) orqali narx topildi: %.2f", narx)

    if not valyuta:
        meta_valyuta = _meta_qiymat_olish(
            sahifa,
            (
                'meta[property="product:price:currency"]',
                'meta[property="og:price:currency"]',
                'meta[itemprop="priceCurrency"]',
            ),
        )
        if meta_valyuta:
            valyuta = valyutani_aniqlash(meta_valyuta)

    if reyting == 0:
        meta_reyting = _meta_qiymat_olish(sahifa, ('meta[itemprop="ratingValue"]',))
        if meta_reyting:
            reyting = reytingni_aniqlash(meta_reyting)

    # 3-bosqich: DOM elementlaridan (h1 / title va narxga o'xshash elementlar)
    if not nomi:
        try:
            h1 = sahifa.locator("h1")
            if h1.count() > 0:
                nomi = h1.first.inner_text().strip()
        except Exception:
            pass

    if not nomi:
        try:
            nomi = (sahifa.title() or "").strip()
        except Exception:
            nomi = ""

    if narx == 0.0:
        for selektor in NARX_DOM_SELEKTORLARI:
            try:
                elementlar = sahifa.locator(selektor)
                chegara = min(elementlar.count(), 5)
                for idx in range(chegara):
                    el = elementlar.nth(idx)
                    matn = el.get_attribute("content") or el.inner_text().strip()
                    if not matn or len(matn) > 80:
                        continue
                    ehtimoliy = narxni_tozalash(matn)
                    if ehtimoliy > 0:
                        narx = ehtimoliy
                        if not valyuta:
                            valyuta = valyutani_aniqlash(matn)
                        logger.info(
                            "Universal Fallback (DOM %s) orqali narx topildi: %.2f (%s)",
                            selektor,
                            narx,
                            valyuta or "—",
                        )
                        break
                if narx > 0:
                    break
            except Exception:
                continue

    if not nomi:
        logger.warning("Universal Fallback sahifadan mahsulot nomini topa olmadi: %s", joriy_url)
        return []

    return [
        {
            "nomi": nomi,
            "narx": narx,
            "valyuta": valyuta,
            "reyting": reyting,
            "url": joriy_url,
        }
    ]
