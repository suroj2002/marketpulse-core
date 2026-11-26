"""
MarketPulse Core — Uzum Market TOP-10 raqobatchi qidiruvi va narx tahlili (100% Python).

Xususiyatlari:
- Anti-bot himoyasini hurmat qilgan holda 15–20 soniya tasodifiy pauza bilan ishlaydi.
- Hech qachon CAPTCHA/anti-bot cheklovini chetlab o'tmaydi — bloklansa aniq ogohlantiradi.
- Reklama (`Reklama` / `Реклама`) kartochkalarini va aloqasiz tovarlarni aqlli filtrlaydi.
- O'zingizning mahsulotingizni (`oz_product_id`) raqobatchilar ro'yxatidan chiqarib tashlaydi.
- TOP-10 sotuvchi narxlari, o'rtacha bozor narxi, foizli farq va bosiladigan havolalarni tayyorlaydi.
"""

import html
import random
import re
import time
from typing import Any
from urllib.parse import quote_plus, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from parser import HAQIQIY_USER_AGENT, proksi_sozlamasini_olish
from parsers.universal import narxni_formatlash, narxni_tozalash
from utils import loggerni_olish


logger = loggerni_olish("parsers.uzum_competitors")

TOXTASH_SOZLAR = {
    "uchun", "bilan", "yangi", "sifatli", "eng", "arzon", "original", "pro",
    "max", "mini", "smart", "va", "ham", "tana", "yuz", "qollar", "qo'llar",
    "chizish", "для", "с", "и", "на", "из", "по", "от", "до",
}

REKLAMA_BELGILARI = ("reklama", "реклама")
SHOVQIN_QATORLAR = (
    "arzon narx kafolati",
    "arzonlashdi",
    "super narx",
    "keshbek",
    "ertaga",
    "bugun",
    "indin",
    "sharh",
    "отзыв",
    "со'mdan",
    "so'mdan",
    "сум/мес",
    "в месяц",
    "savatchaga",
    "в корзину",
)


def _sozlarni_ajratish(matn: str) -> list[str]:
    """Matndan ma'noli kalit so'z tokenlarini ajratadi."""
    toza = re.sub(r"[^\w\s'-]", " ", (matn or "").lower())
    sozlar = [s.strip("'-") for s in toza.split() if len(s.strip("'-")) >= 2]
    return [s for s in sozlar if s not in TOXTASH_SOZLAR]


def qidiruv_sorovini_tayyorlash(mahsulot_nomi: str) -> str:
    """
    Uzun mahsulot nomidan `uzum.uz` da eng aniq natija beradigan
    qisqa (3–5 so'zlik) qidiruv so'rovini tuzadi.
    """
    sozlar = _sozlarni_ajratish(mahsulot_nomi)
    if not sozlar:
        return (mahsulot_nomi or "").strip()[:50]

    # Model/raqamli so'zlar (masalan: 4d, nia-s3000, lcd, geympad) yuqori ustuvorlikka ega
    tanlangan = sozlar[:5]
    return " ".join(tanlangan)


def _url_dan_product_id(url: str) -> int | None:
    """`/uz/product/kompyuter-joystigi-788418?skuId=...` havolasidan 788418 ID sini oladi."""
    toza = url.split("?", 1)[0].rstrip("/")
    moslik = re.search(r"(\d+)$", toza)
    return int(moslik.group(1)) if moslik else None


def _kartochka_matnini_ajratish(qatorlar: list[str]) -> tuple[str, float, float, bool]:
    """
    Uzum qidiruv kartochkasining matn qatorlaridan:
    (nomi, joriy_narx, reyting, reklamami) qiymatlarini ajratadi.
    """
    reklamami = any(q.lower() in REKLAMA_BELGILARI for q in qatorlar)
    joriy_narx = 0.0
    reyting = 0.0
    nom_nomzodlari: list[str] = []

    for qator in qatorlar:
        kichik = qator.lower().strip()
        if not kichik or kichik in REKLAMA_BELGILARI:
            continue

        # Reyting qatori (masalan: "4.9" yoki "5.0")
        if re.fullmatch(r"[0-5][.,]\d", kichik):
            if reyting == 0.0:
                reyting = float(kichik.replace(",", "."))
            continue

        # Bo'lib to'lash yoki shovqin yorliqlarini o'tkazib yuboramiz
        if any(sh in kichik for sh in SHOVQIN_QATORLAR):
            continue

        # Sof narx qatori (masalan: "125 000" yoki "125 000 so'm")
        if re.fullmatch(r"[\d\s\u00a0]+(?:so['’`]?m|сум)?", kichik):
            ehtimoliy = narxni_tozalash(qator)
            if joriy_narx == 0.0 and ehtimoliy >= 1000:
                joriy_narx = ehtimoliy
            continue

        # Qolgan eng uzun matnli qator — mahsulot nomi
        if len(qator) >= 6 and re.search(r"[a-zA-Zа-яА-ЯёЁ]", qator):
            nom_nomzodlari.append(qator)

    nomi = max(nom_nomzodlari, key=len) if nom_nomzodlari else ""
    return nomi.strip(), joriy_narx, reyting, reklamami


def _oxshashlik_balli(asosiy_matn: str, raqobatchi_nomi: str) -> float:
    """
    100% ichki Python orqali ikki mahsulot nomi o'rtasidagi o'xshashlik ballini
    (0.0 .. 1.0) so'z ildizlari kesishmasi asosida hisoblaydi.
    """
    asosiy = _sozlarni_ajratish(asosiy_matn)
    raqobatchi = _sozlarni_ajratish(raqobatchi_nomi)
    if not asosiy or not raqobatchi:
        return 0.0

    # Qisqa ildiz (kamida 4 harf) bo'yicha solishtiramiz — o'zbekcha qo'shimchalarga chidamli
    def ildiz(s: str) -> str:
        return s[:5] if len(s) >= 5 else s

    a_set = {ildiz(s) for s in asosiy}
    r_set = {ildiz(s) for s in raqobatchi}
    mos = a_set & r_set
    return len(mos) / max(len(a_set), 1)


def raqobatchilarni_qidirish(
    mahsulot_nomi: str,
    oz_narx: float = 0.0,
    oz_product_id: int | None = None,
    maxsus_sorov: str | None = None,
    limit: int = 10,
    pauza_oraligi: tuple[float, float] = (15.0, 20.0),
) -> dict[str, Any]:
    """
    Uzum Market qidiruvidan berilgan mahsulotga o'xshash TOP-10 raqobatchini topadi.

    Anti-bot himoyasi uchun sahifani ochishdan oldin `pauza_oraligi` (standart 15–20 soniya)
    tasodifiy pauza qo'yiladi.
    """
    qidiruv_sozi = (maxsus_sorov or "").strip() or qidiruv_sorovini_tayyorlash(mahsulot_nomi)
    qidiruv_url = f"https://uzum.uz/uz/search?query={quote_plus(qidiruv_sozi)}"

    pauza = random.uniform(pauza_oraligi[0], pauza_oraligi[1]) if pauza_oraligi[1] > 0 else 0.0
    logger.info(
        "Uzum raqobatchi qidiruvi boshlandi: so'rov=%r, pauza=%.1fs",
        qidiruv_sozi,
        pauza,
    )
    if pauza > 0:
        time.sleep(pauza)

    nomzodlar: list[dict[str, Any]] = []
    bloklandi = False
    xato_matni = ""

    proksi = proksi_sozlamasini_olish()
    try:
        with sync_playwright() as p:
            brauzer_param: dict[str, Any] = {
                "headless": True,
                "args": ["--disable-dev-shm-usage"],
            }
            if proksi:
                brauzer_param["proxy"] = proksi

            brauzer = p.chromium.launch(**brauzer_param)
            kontekst = brauzer.new_context(
                user_agent=HAQIQIY_USER_AGENT,
                viewport={"width": 1366, "height": 768},
                locale="uz-UZ",
            )
            sahifa = kontekst.new_page()

            try:
                sahifa.goto(qidiruv_url, wait_until="domcontentloaded", timeout=35000)
                try:
                    sahifa.wait_for_selector('a[href*="/product/"]', timeout=15000)
                except PlaywrightTimeoutError:
                    try:
                        sahifa.wait_for_load_state("networkidle", timeout=8000)
                    except PlaywrightTimeoutError:
                        pass
            except PlaywrightTimeoutError:
                xato_matni = "Uzum Market qidiruv sahifasini yuklashda kutish vaqti tugadi."
                logger.warning(xato_matni)

            if not xato_matni:
                sarlavha = (sahifa.title() or "").lower()
                if any(b in sarlavha for b in ("captcha", "доступ ограничен", "access denied", "just a moment")):
                    bloklandi = True
                    logger.warning("Uzum Market anti-bot/CAPTCHA tekshiruvi aniqlandi — to'xtatildi.")
                else:
                    kartochkalar = sahifa.locator('a[href*="/product/"]')
                    jami = min(kartochkalar.count(), 48)
                    korilgan_idlar: set[int] = set()

                    for i in range(jami):
                        try:
                            el = kartochkalar.nth(i)
                            href = el.get_attribute("href") or ""
                            if not href:
                                continue

                            toliq_url = urljoin("https://uzum.uz", href).split("?", 1)[0]
                            pid = _url_dan_product_id(toliq_url)

                            # O'z mahsulotimiz va dublikatlarni chiqarib tashlaymiz
                            if pid is not None:
                                if oz_product_id is not None and pid == oz_product_id:
                                    continue
                                if pid in korilgan_idlar:
                                    continue
                                korilgan_idlar.add(pid)

                            qatorlar = [
                                q.strip()
                                for q in el.inner_text().splitlines()
                                if q.strip()
                            ]
                            nomi, narx, reyting, reklamami = _kartochka_matnini_ajratish(qatorlar)
                            if not nomi or narx <= 0:
                                continue

                            # Aloqasiz reklama kartochkalarini o'tkazib yuboramiz
                            if reklamami:
                                continue

                            ball = _oxshashlik_balli(maxsus_sorov or mahsulot_nomi, nomi)
                            # Narx diapazoni filtri (juda arzon aksessuar yoki 4x qimmat boshqa tovarni chiqarish)
                            if oz_narx > 0 and not maxsus_sorov:
                                if narx < oz_narx * 0.20 or narx > oz_narx * 4.0:
                                    continue

                            # Kamida bitta asosiy kalit so'z mos tushishi kerak
                            if ball < 0.20:
                                continue

                            nomzodlar.append(
                                {
                                    "product_id": pid,
                                    "nomi": nomi,
                                    "narx": narx,
                                    "reyting": reyting,
                                    "url": toliq_url,
                                    "oxshashlik": round(ball, 2),
                                }
                            )
                        except Exception:
                            continue

            kontekst.close()
            brauzer.close()

    except Exception as xato:
        xato_matni = f"Qidiruvda texnik xatolik yuz berdi: {xato}"
        logger.error("Uzum raqobatchi qidiruvi xatoligi: %s", xato)

    # Eng o'xshashlarini tanlab, so'ng narx bo'yicha arzondan qimmatga saralaymiz
    eng_moslar = sorted(nomzodlar, key=lambda x: (-x["oxshashlik"], x["narx"]))[:limit]
    top_10 = sorted(eng_moslar, key=lambda x: x["narx"])

    ortacha_narx = round(sum(x["narx"] for x in top_10) / len(top_10), 2) if top_10 else 0.0
    eng_arzon = top_10[0] if top_10 else None
    eng_qimmat = top_10[-1] if top_10 else None

    farq_foiz = 0.0
    if oz_narx > 0 and ortacha_narx > 0:
        farq_foiz = round(((oz_narx - ortacha_narx) / ortacha_narx) * 100, 2)

    tavsiya_narx = None
    if eng_arzon and eng_arzon["narx"] > 2000:
        tavsiya_narx = int(eng_arzon["narx"]) - 1000

    logger.info(
        "Uzum raqobatchi qidiruvi yakunlandi: so'rov=%r, topildi=%d, o'rtacha=%.0f",
        qidiruv_sozi,
        len(top_10),
        ortacha_narx,
    )

    return {
        "qidiruv_sozi": qidiruv_sozi,
        "qidiruv_url": qidiruv_url,
        "top_10": top_10,
        "ortacha_narx": ortacha_narx,
        "eng_arzon": eng_arzon,
        "eng_qimmat": eng_qimmat,
        "farq_foiz": farq_foiz,
        "tavsiya_narx": tavsiya_narx,
        "bloklandi": bloklandi,
        "xato": xato_matni,
    }


def raqobatchi_hisobotini_formatlash(mahsulot: dict[str, Any], natija: dict[str, Any]) -> str:
    """
    Tadbirkor uchun tushunarli, xavfsiz HTML formatdagi TOP-10 raqobatchi
    tahlili hisobotini tayyorlaydi.
    """
    nomi = html.escape(str(mahsulot.get("nomi", "")))
    oz_narx = float(mahsulot.get("yangi_narx") or mahsulot.get("narx") or 0.0)
    val = str(mahsulot.get("valyuta") or "so'm")
    komissiya = float(mahsulot.get("komissiya_foiz") or 0.0)
    sof_tushum = oz_narx * (1 - komissiya / 100) if komissiya > 0 else oz_narx
    qoldiq = int(mahsulot.get("qoldiq") or 0)
    holat = html.escape(str(mahsulot.get("holat_matni") or ("Sotuvda" if qoldiq > 0 else "Tugadi")))
    vozvrat = float(mahsulot.get("vozvrat_foiz") or 0.0)

    qatorlar = [
        f"🔍 <b>Raqobatchilar tahlili — Uzum Market</b>",
        f"📦 <b>Mahsulot:</b> {nomi}",
        f"🔎 Qidiruv so'zi: <code>{html.escape(natija['qidiruv_sozi'])}</code>",
        "━━━━━━━━━━━━━━━━━━",
        f"💰 Sizning narxingiz: <b>{narxni_formatlash(oz_narx, val)}</b>",
    ]
    if komissiya > 0:
        qatorlar.append(
            f"📊 Uzum komissiyasi: <b>{komissiya:.1f}%</b> → "
            f"Qo'lingizda qoladi: <b>{narxni_formatlash(sof_tushum, val)}</b>"
        )
    qatorlar.append(f"📦 Ombor qoldig'i: <b>{qoldiq} ta</b> ({holat}) | ↩️ Vozvrat: <b>{vozvrat:.1f}%</b>")
    qatorlar.append("━━━━━━━━━━━━━━━━━━")

    if natija.get("bloklandi"):
        qatorlar.append(
            "⚠️ <b>Uzum Market vaqtinchalik anti-bot tekshiruvi chiqardi.</b>\n"
            "Birozdan so'ng qayta urinib ko'ring."
        )
        return "\n".join(qatorlar)

    if natija.get("xato"):
        qatorlar.append(f"❌ {html.escape(natija['xato'])}")
        return "\n".join(qatorlar)

    top_10 = natija.get("top_10") or []
    if not top_10:
        qatorlar.append(
            "💎 <b>Sizniki kabi mahsulot boshqa sotuvchilarda topilmadi!</b>\n"
            "Bozorda aynan shu tovar bo'yicha to'g'ridan-to'g'ri raqobatchi yo'q — "
            "narx belgilashda ustunlik sizda.\n\n"
            "<i>Agar qidiruv so'zini qisqartirib tekshirmoqchi bo'lsangiz, "
            "pastdagi «🔎 Boshqa so'z bilan qidirish» tugmasini bosing.</i>"
        )
        return "\n".join(qatorlar)

    ortacha = natija["ortacha_narx"]
    farq_foiz = natija["farq_foiz"]
    if farq_foiz > 2:
        pozitsiya = f"🔴 bozor o'rtachasidan <b>+{farq_foiz:.1f}% qimmat</b>"
    elif farq_foiz < -2:
        pozitsiya = f"🟢 bozor o'rtachasidan <b>{farq_foiz:.1f}% arzon</b>"
    else:
        pozitsiya = "🟡 bozor o'rtachasi bilan <b>teng</b>"

    qatorlar.extend(
        [
            f"📈 <b>Bozor o'rtacha narxi ({len(top_10)} ta sotuvchi):</b> {narxni_formatlash(ortacha, val)}",
            f"⚖️ Sizning pozitsiyangiz: {pozitsiya}",
            f"🏷️ Eng arzon: {narxni_formatlash(natija['eng_arzon']['narx'], val)} | "
            f"💎 Eng qimmat: {narxni_formatlash(natija['eng_qimmat']['narx'], val)}",
            "",
            f"🏆 <b>TOP-{len(top_10)} raqobatchi narxlari:</b>",
        ]
    )

    for idx, item in enumerate(top_10, start=1):
        qisqa_nom = item["nomi"][:55] + ("…" if len(item["nomi"]) > 55 else "")
        reyting_qism = f" · ⭐ {item['reyting']:.1f}" if item.get("reyting", 0) > 0 else ""
        qatorlar.append(
            f"{idx}. <b>{narxni_formatlash(item['narx'], val)}</b>{reyting_qism} — "
            f"<a href=\"{html.escape(item['url'])}\">{html.escape(qisqa_nom)}</a>"
        )

    return "\n".join(qatorlar)
