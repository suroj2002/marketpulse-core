"""
MarketPulse Core — Asosiy ishga tushirish nuqtasi.

Barcha bosqichlarni ketma-ket bajaradi va logs/marketpulse.log ga yozib boradi:
1. Parser (bitta umumiy Chromium sessiyasi orqali barcha manbalardan ma'lumot yig'ish)
2. Database (SQLite bazaga saqlash — DB_PATH va narx tarixini yo'qotmaslik himoyasi bilan)
3. Analytics (100% Python orqali ko'p valyutali tahlil)
4. Excel Report (dizaynli .xlsx hisobot yaratish)
5. Notifier (Telegram yoki xavfsiz n8n Webhook orqali yuborish)
6. Zero-Storage va tozalash (yuborilgan Excel faylni os.remove() bilan o'chirish
   hamda 7 kundan eski qolib ketgan .xlsx fayllarni tozalash)
"""

from datetime import datetime, timedelta
import os
from pathlib import Path
import sys

from analytics import hisobot_matnini_yaratish
from database import (
    barcha_manbalarni_olish,
    faol_db_yoli,
    get_language,
    get_timezone,
    katalog_saqlash,
    mahsulotlarni_saqlash,
    manbalar_royxati,
    sinov_mahsulotlarini_tozalash,
)
from excel_report import excel_hisobot_yaratish
from locales import t
from notifier import ogohlantirish_yuborish, telegramga_yuborish
from parser import kop_manbadan_yigish
from parsers.ozon_api import ozon_mahsulotlarini_olish, ozon_sozlanganmi
from parsers.uzum_api import uzum_mahsulotlarini_olish, uzum_sozlanganmi
from utils import hozirgi_vaqt, loggerni_olish, vaqt_mintaqasi_nomi, vaqt_mintaqasini_olish


logger = loggerni_olish("main")

NOL_NATIJA_OGOHLANTIRISH = (
    "⚠️ DIQQAT: Sayt strukturasi o'zgargan bo'lishi mumkin, 0 ta mahsulot topildi!"
)


def eski_excel_fayllarni_tozalash(papka: str | Path = ".", kunlar: int = 7) -> int:
    """
    Ko'rsatilgan papkada `kunlar` (standart 7 kun) dan eski bo'lgan `.xlsx`
    fayllarni avtomatik o'chiradi.
    """
    papka_yoli = Path(papka)
    tz = vaqt_mintaqasini_olish()
    chegara_vaqt = hozirgi_vaqt() - timedelta(days=kunlar)
    ochirilganlar = 0

    for fayl in papka_yoli.glob("*.xlsx"):
        if not fayl.is_file():
            continue
        try:
            ozgarish_vaqti = datetime.fromtimestamp(fayl.stat().st_mtime, tz=tz)
            if ozgarish_vaqti < chegara_vaqt:
                fayl.unlink()
                ochirilganlar += 1
                logger.info(
                    "Eski Excel fayl o'chirildi (%d kundan eski): %s",
                    kunlar,
                    fayl.name,
                )
        except OSError as xato:
            logger.warning("Eski Excel faylni o'chirishda xatolik (%s): %s", fayl.name, xato)

    if ochirilganlar > 0:
        print(f"[Tozalash] {kunlar} kundan eski {ochirilganlar} ta .xlsx fayl o'chirildi.")
    else:
        print(f"[Tozalash] {kunlar} kundan eski .xlsx fayllar topilmadi.")
        logger.info("Tozalash tekshiruvi: %d kundan eski .xlsx fayllar topilmadi.", kunlar)

    return ochirilganlar


def faylni_xavfsiz_ochirish(fayl_yoli: str) -> bool:
    """Zero-Storage qoidasi: yuborilgan Excel faylni os.remove() bilan darhol o'chiradi."""
    if not fayl_yoli or not os.path.exists(fayl_yoli):
        return False
    try:
        os.remove(fayl_yoli)
        print(f"[Zero-Storage] Hisobot fayli serverdan darhol o'chirildi: {fayl_yoli}")
        logger.info("Zero-Storage: '%s' fayli os.remove() orqali darhol o'chirildi.", fayl_yoli)
        return True
    except OSError as xato:
        logger.warning("Faylni o'chirishda xatolik (%s): %s", fayl_yoli, xato)
        return False


def hisobot_tayyorlash(
    limit: int = 20,
    db_yoli: str | None = None,
    lang: str = "uz",
    tz_nomi: str | None = None,
) -> tuple[bool, str, str | None]:
    """
    Parser / Ozon Seller API / Uzum Seller API -> Database -> Analytics -> Excel
    bosqichlarini bajarib, tanlangan tilda (`uz`/`ru`) tayyor natijani qaytaradi.
    """
    yol = faol_db_yoli(db_yoli)
    mahsulotlar = []

    # 1-bosqich: Rasmiy Seller API lar (Ozon va/yoki Uzum Market) + qo'shimcha veb-manbalar
    ozon_faol = ozon_sozlanganmi()
    uzum_faol = uzum_sozlanganmi()

    if ozon_faol or uzum_faol:
        if ozon_faol:
            print("1/5-bosqich: Ozon Seller API orqali mahsulotlarni yuklash...")
            mahsulotlar.extend(ozon_mahsulotlarini_olish(maks_soni=200))

        if uzum_faol:
            print("1/5-bosqich: Uzum Market Seller OpenAPI orqali mahsulotlarni yuklash...")
            uzum_tovarlar = uzum_mahsulotlarini_olish(maks_soni=500)
            if uzum_tovarlar:
                katalog_saqlash(uzum_tovarlar, db_yoli=yol)
            mahsulotlar.extend(uzum_tovarlar)

        # Foydalanuvchi alohida veb-manbalar ham qo'shgan bo'lsa, ularni ham qo'shamiz
        qoshimcha_manbalar = [m["url"] for m in manbalar_royxati(db_yoli=yol)]
        if mahsulotlar and not any("books.toscrape.com" in u for u in qoshimcha_manbalar):
            sinov_mahsulotlarini_tozalash(db_yoli=yol)
        if qoshimcha_manbalar:
            print(f"   + Qo'shimcha {len(qoshimcha_manbalar)} ta veb-manba tekshirilmoqda...")
            mahsulotlar.extend(kop_manbadan_yigish(manbalar=qoshimcha_manbalar, limit=limit))
    else:
        # Oddiy veb-parser rejimi (bitta Chromium sessiyasi orqali barcha manbalar)
        manbalar = barcha_manbalarni_olish(db_yoli=yol)
        print(f"1/5-bosqich: Mahsulotlarni yig'ish (Parser — {len(manbalar)} ta manba)...")
        mahsulotlar = kop_manbadan_yigish(manbalar=manbalar, limit=limit)

    if not mahsulotlar:
        logger.error("Parser/API 0 ta mahsulot qaytardi — bo'sh Excel yaratilmadi.")
        return False, t("zero_result_alert", lang), None

    # 2-bosqich: Database
    print("\n2/5-bosqich: Ma'lumotlar bazasini yangilash (SQLite)...")
    yangi_soni, yangilangan_soni = mahsulotlarni_saqlash(mahsulotlar, db_yoli=yol)
    print(
        f"[Baza] Saqlash yakunlandi ({yol}): "
        f"{yangi_soni} ta yangi qo'shildi, {yangilangan_soni} ta yangilandi."
    )

    # 3-bosqich: Analytics
    print("\n3/5-bosqich: Ichki Python tahlili (Analytics)...")
    hisobot_matni = hisobot_matnini_yaratish(db_yoli=yol, lang=lang, tz_nomi=tz_nomi)
    print("\n" + hisobot_matni + "\n")

    # 4-bosqich: Excel Report
    print("4/5-bosqich: Dizaynli Excel hisobot yaratish...")
    excel_fayl = excel_hisobot_yaratish(db_yoli=yol, lang=lang, tz_nomi=tz_nomi)

    return True, hisobot_matni, excel_fayl


def asosiy() -> int:
    """MarketPulse Core to'liq siklini ishga tushiradi."""
    yol = faol_db_yoli()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    til = get_language(chat_id, db_yoli=yol) if chat_id else "uz"
    tz_nomi = (
        get_timezone(chat_id, lang=til, db_yoli=yol)
        if chat_id
        else vaqt_mintaqasi_nomi(lang=til)
    )

    print("============================================================")
    print("🚀 MarketPulse Core — Narxlar Monitoringi Tizimi ishga tushdi")
    print(f"🕒 Vaqt mintaqasi: {tz_nomi} | {hozirgi_vaqt(lang=til, tz_nomi=tz_nomi).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💾 Ma'lumotlar bazasi: {yol} | 🌐 Til: {til}")
    print("============================================================\n")
    logger.info("=== MarketPulse Core sikli boshlandi (TIMEZONE=%s, DB=%s, LANG=%s) ===", tz_nomi, yol, til)

    try:
        muvaffaqiyatli, matn, excel_fayl = hisobot_tayyorlash(
            limit=20,
            db_yoli=yol,
            lang=til,
            tz_nomi=tz_nomi,
        )

        if not muvaffaqiyatli or excel_fayl is None:
            print(f"\n{matn}")
            print("❌ Bo'sh Excel yaratilmadi. Ogohlantirish yuborilmoqda...")
            ogohlantirish_yuborish(matn)
            logger.info("=== MarketPulse Core sikli 0-natija bilan yakunlandi ===")
            return 1

        # 5-bosqich: Notifier (Telegram yoki xavfsiz n8n Webhook)
        print("\n5/5-bosqich: Xabarnoma yuborish (Telegram / Webhook)...")
        yuborildi = telegramga_yuborish(matn, excel_fayl)

        # 6-bosqich: Zero-Storage (darhol o'chirish) + 7 kundan eski fayllarni tozalash
        if yuborildi:
            faylni_xavfsiz_ochirish(excel_fayl)
            eski_excel_fayllarni_tozalash(papka=".", kunlar=7)

        print("\n============================================================")
        print("✅ MarketPulse Core barcha bosqichlarni muvaffaqiyatli yakunladi!")
        print("============================================================")
        logger.info("=== MarketPulse Core sikli muvaffaqiyatli yakunlandi ===")
        return 0

    except Exception as kutilmagan_xato:
        print(f"\n❌ KRITIK XATOLIK: {kutilmagan_xato}")
        logger.exception("MarketPulse Core bajarilishida kutilmagan xatolik: %s", kutilmagan_xato)
        return 1


if __name__ == "__main__":
    sys.exit(asosiy())
