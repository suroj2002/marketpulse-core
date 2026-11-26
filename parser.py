"""
MarketPulse Core — Universal Playwright aqlli parser moduli.

Xususiyatlari:
- Bir nechta URL uchun bitta umumiy Chromium sessiyasidan foydalanadi (`kop_manbadan_yigish`) —
  RAM va vaqtni 3–5 barobar tejaydi.
- Avval URL domenini `sites_config.json` dan tekshirib mos CSS selektor bilan yig'adi.
- Noma'lum saytlar uchun JS/SPA yuklanishini (`networkidle`) kutib, **Universal Fallback**
  (JSON-LD, meta teglar, DOM narx qidiruvi) orqali narx va valyutani avtomatik aniqlaydi.
- `.env` da `PROXY_URL` ko'rsatilgan bo'lsa Playwright shu proksi orqali ochadi.
- Headless rejim, real User-Agent, 2–4 soniya tasodifiy pauza va narx topilmasa 0.0 himoyasi.
"""

import os
import random
import time
from typing import Any
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from parsers.universal import (
    narxni_tozalash,
    reytingni_aniqlash,
    sayt_konfiguratsiyasini_topish,
    universal_fallback_ajratish,
    valyutani_aniqlash,
)
from utils import loggerni_olish


logger = loggerni_olish("parser")

MANBA_URL = "https://books.toscrape.com/"
HAQIQIY_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def proksi_sozlamasini_olish() -> dict[str, str] | None:
    """
    .env faylidagi `PROXY_URL` o'zgaruvchisidan Playwright uchun proksi
    lug'atini tayyorlaydi. Bo'sh bo'lsa None qaytaradi (to'g'ridan-to'g'ri ulanish).
    """
    load_dotenv()
    proksi_url = os.getenv("PROXY_URL", "").strip()
    if not proksi_url:
        return None

    tahlil = urlparse(proksi_url)
    if not tahlil.scheme or not tahlil.hostname:
        logger.warning("PROXY_URL noto'g'ri formatda — proksisiz davom ettiriladi.")
        return None

    port_qismi = f":{tahlil.port}" if tahlil.port else ""
    sozlama: dict[str, str] = {"server": f"{tahlil.scheme}://{tahlil.hostname}{port_qismi}"}
    if tahlil.username:
        sozlama["username"] = tahlil.username
    if tahlil.password:
        sozlama["password"] = tahlil.password

    logger.info("Playwright proksi faollashtirildi: %s", sozlama["server"])
    return sozlama


def _spa_yuklanishini_kutish(sahifa) -> None:
    """React/Vue/Next.js kabi SPA sahifalarda JS narxlari yuklanishini qisqa kutadi."""
    try:
        sahifa.wait_for_load_state("networkidle", timeout=7000)
    except PlaywrightTimeoutError:
        # Ba'zi saytlarda fon analitik so'rovlar to'xtamaydi — bu normal holat
        pass


def _katalogdan_yigish(
    sahifa,
    konfig: dict[str, Any],
    sahifa_raqami: int,
    qolgan_limit: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """`sites_config.json` dagi katalog selektorlari yordamida mahsulotlarni yig'adi."""
    natijalar: list[dict[str, Any]] = []
    kartochka_selektor = konfig["kartochka"]
    nomi_selektor = konfig.get("nomi", "h3 a")
    nomi_atribut = konfig.get("nomi_atribut")
    havola_selektor = konfig.get("havola", nomi_selektor)
    narx_selektor = konfig.get("narxi", "")
    reyting_selektor = konfig.get("reytingi", "")
    keyingi_selektor = konfig.get("keyingi_sahifa", "")
    standart_valyuta = konfig.get("valyuta", "")

    sahifa.wait_for_selector(kartochka_selektor, timeout=15000)
    kartochkalar = sahifa.locator(kartochka_selektor)
    kartochka_soni = kartochkalar.count()

    for indeks in range(kartochka_soni):
        if len(natijalar) >= qolgan_limit:
            break

        try:
            kartochka = kartochkalar.nth(indeks)

            nomi_el = kartochka.locator(nomi_selektor).first
            nomi = ""
            if nomi_atribut:
                nomi = nomi_el.get_attribute(nomi_atribut) or ""
            if not nomi:
                nomi = nomi_el.inner_text().strip()

            havola_el = kartochka.locator(havola_selektor).first
            nisbiy_havola = havola_el.get_attribute("href")
            toliq_havola = urljoin(sahifa.url, nisbiy_havola) if nisbiy_havola else sahifa.url

            narx = 0.0
            valyuta = standart_valyuta
            if narx_selektor:
                narx_el = kartochka.locator(narx_selektor)
                if narx_el.count() > 0:
                    narx_matni = narx_el.first.inner_text().strip()
                    narx = narxni_tozalash(narx_matni)
                    valyuta = valyutani_aniqlash(narx_matni, standart=standart_valyuta)
                else:
                    logger.warning("%s mahsulotida narx topilmadi — 0.0 yozildi.", nomi.strip())

            reyting = 0
            if reyting_selektor:
                reyting_el = kartochka.locator(reyting_selektor)
                if reyting_el.count() > 0:
                    reyting_manba = (
                        reyting_el.first.get_attribute("class")
                        or reyting_el.first.inner_text().strip()
                    )
                    reyting = reytingni_aniqlash(reyting_manba)

            if nomi.strip():
                natijalar.append(
                    {
                        "nomi": nomi.strip(),
                        "narx": narx,
                        "valyuta": valyuta,
                        "reyting": reyting,
                        "url": toliq_havola,
                    }
                )
        except Exception as xato:
            xato_xabari = (
                f"Xatolik ({sahifa_raqami}-sahifa, "
                f"{indeks + 1}-mahsulot o'tkazib yuborildi): {xato}"
            )
            print(f"[Parser] {xato_xabari}")
            logger.warning(xato_xabari)
            continue

    keyingi_url: str | None = None
    if len(natijalar) < qolgan_limit and keyingi_selektor:
        keyingi_tugma = sahifa.locator(keyingi_selektor)
        if keyingi_tugma.count() > 0:
            keyingi_href = keyingi_tugma.first.get_attribute("href")
            if keyingi_href:
                keyingi_url = urljoin(sahifa.url, keyingi_href)

    return natijalar, keyingi_url


def _yakka_mahsulot_yigish(sahifa, konfig: dict[str, Any]) -> list[dict[str, Any]]:
    """`sites_config.json` dagi yakka mahsulot sahifasi selektorlari bilan yig'adi."""
    nomi_selektor = konfig.get("nomi", "h1")
    narx_selektor = konfig.get("narxi", "")
    reyting_selektor = konfig.get("reytingi", "")
    standart_valyuta = konfig.get("valyuta", "")

    nomi = ""
    if nomi_selektor:
        nomi_el = sahifa.locator(nomi_selektor)
        if nomi_el.count() > 0:
            nomi = nomi_el.first.inner_text().strip()

    narx = 0.0
    valyuta = standart_valyuta
    if narx_selektor:
        narx_el = sahifa.locator(narx_selektor)
        if narx_el.count() > 0:
            narx_matni = narx_el.first.get_attribute("content") or narx_el.first.inner_text().strip()
            narx = narxni_tozalash(narx_matni)
            valyuta = valyutani_aniqlash(narx_matni, standart=standart_valyuta)

    reyting = 0
    if reyting_selektor:
        reyting_el = sahifa.locator(reyting_selektor)
        if reyting_el.count() > 0:
            reyting_manba = (
                reyting_el.first.get_attribute("class")
                or reyting_el.first.inner_text().strip()
            )
            reyting = reytingni_aniqlash(reyting_manba)

    if not nomi or narx <= 0:
        logger.info(
            "Konfiguratsiya selektori to'liq natija bermadi (nomi=%r, narx=%.2f) — "
            "Universal Fallback (JSON-LD / meta / DOM) ishga tushirilmoqda.",
            nomi,
            narx,
        )
        zaxira = universal_fallback_ajratish(sahifa, sahifa.url)
        if zaxira:
            if not nomi:
                nomi = zaxira[0].get("nomi", "")
            if narx <= 0:
                narx = float(zaxira[0].get("narx") or 0.0)
            if not valyuta:
                valyuta = str(zaxira[0].get("valyuta") or standart_valyuta)
            if reyting == 0:
                reyting = int(zaxira[0].get("reyting") or 0)

    if not nomi:
        return []

    return [
        {
            "nomi": nomi,
            "narx": narx,
            "valyuta": valyuta,
            "reyting": reyting,
            "url": sahifa.url,
        }
    ]


def _bitta_manbadan_yigish(sahifa, manba_url: str, limit: int) -> list[dict[str, Any]]:
    """Ochiq Playwright `sahifa` obyekti orqali bitta manba URL'idan ma'lumot yig'adi."""
    mahsulotlar: list[dict[str, Any]] = []
    joriy_url: str | None = manba_url
    sahifa_raqami = 1

    domen, sayt_konfigi = sayt_konfiguratsiyasini_topish(manba_url)
    rejim = f"sites_config.json ({domen})" if sayt_konfigi else f"Universal Fallback ({domen})"
    boshlanish_xabari = (
        f"Ma'lumot yig'ish boshlandi: {manba_url} | Rejim: {rejim} (limit: {limit})"
    )
    print(f"[Parser] {boshlanish_xabari}")
    logger.info(boshlanish_xabari)

    while joriy_url and len(mahsulotlar) < limit:
        # Anti-bot himoyasi: sahifalar/so'rovlar orasida 2–4 soniya tasodifiy pauza
        pauza = random.uniform(2.0, 4.0)
        yuklash_xabari = (
            f"{sahifa_raqami}-sahifa yuklanmoqda (pauza: {pauza:.2f} soniya)..."
        )
        print(f"[Parser] {yuklash_xabari}")
        logger.info(yuklash_xabari)
        time.sleep(pauza)

        try:
            sahifa.goto(joriy_url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightTimeoutError:
            timeout_xabari = f"{joriy_url} sahifasini yuklashda vaqt tugadi (timeout)."
            print(f"[Parser] OGOHLANTIRISH: {timeout_xabari}")
            logger.warning(timeout_xabari)
            break

        yakka_belgi = sayt_konfigi.get("yakka_url_belgi", "") if sayt_konfigi else ""
        yakka_sahifami = bool(yakka_belgi and yakka_belgi in (joriy_url or ""))

        if sayt_konfigi and sayt_konfigi.get("kartochka") and not yakka_sahifami:
            try:
                if sayt_konfigi.get("valyuta") == "so'm":
                    _spa_yuklanishini_kutish(sahifa)
                qolgan = limit - len(mahsulotlar)
                yigildi, keyingi_url = _katalogdan_yigish(
                    sahifa, sayt_konfigi, sahifa_raqami, qolgan
                )
                mahsulotlar.extend(yigildi)
                joriy_url = keyingi_url
                sahifa_raqami += 1
            except PlaywrightTimeoutError:
                logger.warning(
                    "Katalog selektori topilmadi (%s), SPA yuklanishi va Universal Fallback sinab ko'rilmoqda...",
                    joriy_url,
                )
                _spa_yuklanishini_kutish(sahifa)
                mahsulotlar.extend(universal_fallback_ajratish(sahifa, sahifa.url))
                break
        elif sayt_konfigi:
            _spa_yuklanishini_kutish(sahifa)
            mahsulotlar.extend(_yakka_mahsulot_yigish(sahifa, sayt_konfigi))
            break
        else:
            # Noma'lum/SPA saytlar: JS to'liq yuklanishini kutib Universal Fallback ishga tushadi
            _spa_yuklanishini_kutish(sahifa)
            mahsulotlar.extend(universal_fallback_ajratish(sahifa, sahifa.url))
            break

    if len(mahsulotlar) == 0:
        ogohlantirish = (
            f"Birorta ham mahsulot topilmadi (0 ta): {manba_url}! "
            "Sayt strukturasi o'zgargan, internet aloqasi uzilgan yoki kirish cheklangan bo'lishi mumkin."
        )
        print(f"[Parser] OGOHLANTIRISH: {ogohlantirish}")
        logger.error(ogohlantirish)
    else:
        yakun_xabari = (
            f"Muvaffaqiyatli yakunlandi ({domen}): jami {len(mahsulotlar)} ta mahsulot yig'ildi."
        )
        print(f"[Parser] {yakun_xabari}")
        logger.info(yakun_xabari)

    return mahsulotlar


def kop_manbadan_yigish(
    manbalar: list[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Bir nechta URL manzilidan bitta umumiy Chromium sessiyasi orqali
    ma'lumot yig'adi (RAM va vaqtni tejaydi).
    """
    if not manbalar:
        return []

    barcha_mahsulotlar: list[dict[str, Any]] = []
    proksi_sozlamasi = proksi_sozlamasini_olish()

    try:
        with sync_playwright() as p:
            brauzer_parametrlari: dict[str, Any] = {
                "headless": True,
                "args": ["--disable-dev-shm-usage"],
            }
            if proksi_sozlamasi:
                brauzer_parametrlari["proxy"] = proksi_sozlamasi

            brauzer = p.chromium.launch(**brauzer_parametrlari)
            kontekst = brauzer.new_context(
                user_agent=HAQIQIY_USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="en-US",
            )
            sahifa = kontekst.new_page()

            for manba_url in manbalar:
                try:
                    yigilgan = _bitta_manbadan_yigish(sahifa, manba_url, limit)
                    barcha_mahsulotlar.extend(yigilgan)
                except Exception as manba_xatosi:
                    xabar = f"Manbani o'qishda xatolik ({manba_url}): {manba_xatosi}"
                    print(f"[Parser] XATOLIK: {xabar}")
                    logger.error(xabar)
                    continue

            kontekst.close()
            brauzer.close()

    except Exception as umumiy_xato:
        kritik_xabar = f"Brauzer bilan ishlashda muammo yuz berdi: {umumiy_xato}"
        print(f"[Parser] KRITIK XATOLIK: {kritik_xabar}")
        logger.error(kritik_xabar)

    return barcha_mahsulotlar


def mahsulotlarni_yigish(
    manba_url: str = MANBA_URL,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Bitta URL manzilidan mahsulotlarni yig'adi (eski chaqiruvlar bilan to'liq mos)."""
    return kop_manbadan_yigish([manba_url], limit=limit)
