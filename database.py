"""
MarketPulse Core — SQLite ma'lumotlar bazasi moduli.

Xususiyatlari:
- `.env` dagi `DB_PATH` (Docker/Railway Volume uchun `/data/marketpulse.db`) ni qo'llab-quvvatlaydi.
- Dublikatlarni oldini olish uchun URL'dan '?' dan keyingi qismni kesib tashlaydi.
- `eski_narx` faqat narx haqiqatan o'zgarganda yangilanadi (ketma-ket qayta
  tekshirilganda avvalgi arzonlashish/qimmatlashish yo'qolib ketmaydi).
- Har bir mahsulot uchun `valyuta` hamda Seller metrikalari (`shop_id`, `product_id`,
  `sku_id`, `qoldiq`, `sotilgan`, `qaytgan`, `vozvrat_foiz`, `komissiya_foiz`, `holat_matni`)
  avtomatik migratsiya bilan saqlanadi.
"""

from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import urlparse

from utils import (
    MOSKVA_TIMEZONE,
    QULLAB_QUVVATLANADIGAN_VAQT_MINTAQALARI,
    STANDART_TIMEZONE,
    TIL_VAQT_MINTAQALARI,
    db_yolni_olish,
    hozirgi_vaqt,
    loggerni_olish,
)


logger = loggerni_olish("database")
DB_NOMI = db_yolni_olish()
STANDART_SINOV_URL = "https://books.toscrape.com/"

QOSHIMCHA_USTUNLAR: tuple[tuple[str, str], ...] = (
    ("valyuta", "TEXT NOT NULL DEFAULT ''"),
    ("shop_id", "INTEGER"),
    ("product_id", "INTEGER"),
    ("sku_id", "INTEGER"),
    ("sku_title", "TEXT NOT NULL DEFAULT ''"),
    ("qoldiq", "INTEGER NOT NULL DEFAULT 0"),
    ("sotilgan", "INTEGER NOT NULL DEFAULT 0"),
    ("qaytgan", "INTEGER NOT NULL DEFAULT 0"),
    ("vozvrat_foiz", "REAL NOT NULL DEFAULT 0.0"),
    ("komissiya_foiz", "REAL NOT NULL DEFAULT 0.0"),
    ("holat_matni", "TEXT NOT NULL DEFAULT ''"),
)


def faol_db_yoli(db_yoli: str | None = None) -> str:
    """Faol SQLite baza yo'lini qaytaradi."""
    return db_yoli if db_yoli is not None else db_yolni_olish()


def urlni_tozalash(url: str) -> str:
    """Mahsulot havolasidan '?' belgisidan keyingi qismini kesib tashlaydi."""
    if not url:
        return ""
    return url.split("?", 1)[0].strip()


def bazani_tayyorlash(db_yoli: str | None = None) -> None:
    """SQLite ma'lumotlar bazasini, jadvallarni va kerakli ustun migratsiyalarini yaratadi."""
    yol = faol_db_yoli(db_yoli)
    ota_papka = Path(yol).parent
    if str(ota_papka) not in ("", "."):
        ota_papka.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mahsulotlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                nomi TEXT NOT NULL,
                eski_narx REAL,
                yangi_narx REAL NOT NULL,
                valyuta TEXT NOT NULL DEFAULT '',
                reyting INTEGER,
                oxirgi_sana TEXT NOT NULL,
                shop_id INTEGER,
                product_id INTEGER,
                sku_id INTEGER,
                sku_title TEXT NOT NULL DEFAULT '',
                qoldiq INTEGER NOT NULL DEFAULT 0,
                sotilgan INTEGER NOT NULL DEFAULT 0,
                qaytgan INTEGER NOT NULL DEFAULT 0,
                vozvrat_foiz REAL NOT NULL DEFAULT 0.0,
                komissiya_foiz REAL NOT NULL DEFAULT 0.0,
                holat_matni TEXT NOT NULL DEFAULT ''
            )
            """
        )

        # Mavjud eski bazalarga yetishmayotgan ustunlarni avtomatik qo'shamiz
        kursor.execute("PRAGMA table_info(mahsulotlar)")
        mavjud_ustunlar = {qator[1] for qator in kursor.fetchall()}
        for ustun_nomi, ustun_turi in QOSHIMCHA_USTUNLAR:
            if ustun_nomi not in mavjud_ustunlar:
                kursor.execute(f"ALTER TABLE mahsulotlar ADD COLUMN {ustun_nomi} {ustun_turi}")
                logger.info("Baza migratsiyasi: `mahsulotlar` ga `%s` ustuni qo'shildi.", ustun_nomi)
                if ustun_nomi == "valyuta":
                    kursor.execute(
                        "UPDATE mahsulotlar SET valyuta = '£' "
                        "WHERE url LIKE '%books.toscrape.com%' AND valyuta = ''"
                    )

        kursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                kalit TEXT PRIMARY KEY,
                qiymat TEXT NOT NULL,
                yangilangan_sana TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'uz'
            )
            """
        )
        # Mavjud eski `settings` jadvaliga `language` ustunini avtomatik migratsiya qilamiz
        kursor.execute("PRAGMA table_info(settings)")
        settings_ustunlar = {qator[1] for qator in kursor.fetchall()}
        if "language" not in settings_ustunlar:
            kursor.execute("ALTER TABLE settings ADD COLUMN language TEXT NOT NULL DEFAULT 'uz'")
            logger.info("Baza migratsiyasi: `settings` jadvaliga `language` ustuni qo'shildi.")
        kursor.execute(
            """
            CREATE TABLE IF NOT EXISTS manbalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                qoshilgan_sana TEXT NOT NULL
            )
            """
        )
        kursor.execute(
            """
            CREATE TABLE IF NOT EXISTS catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER UNIQUE NOT NULL,
                sku TEXT NOT NULL DEFAULT '',
                nomi TEXT NOT NULL,
                narxi REAL NOT NULL,
                komissiya_foizi REAL NOT NULL DEFAULT 0.0,
                logistika_tolovi REAL NOT NULL DEFAULT 0.0,
                qoldiq INTEGER NOT NULL DEFAULT 0,
                yangilangan_sana TEXT NOT NULL
            )
            """
        )
        kursor.execute(
            """
            CREATE TABLE IF NOT EXISTS competitors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                my_product_id INTEGER NOT NULL,
                url TEXT UNIQUE NOT NULL,
                raqobatchi_nomi TEXT NOT NULL DEFAULT '',
                eski_narx REAL,
                yangi_narx REAL NOT NULL DEFAULT 0.0,
                oxirgi_tekshiruv TEXT NOT NULL DEFAULT ''
            )
            """
        )
        ulanish.commit()


def katalog_tovar_product_id_bilan_olish(
    product_id: int,
    db_yoli: str | None = None,
) -> dict[str, Any] | None:
    """`catalog` jadvalidan bitta tovarni `product_id` bo'yicha qaytaradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute(
            """
            SELECT id, product_id, sku, nomi, narxi, komissiya_foizi,
                   logistika_tolovi, qoldiq, yangilangan_sana
            FROM catalog
            WHERE product_id = ?
            """,
            (product_id,),
        )
        qator = kursor.fetchone()

    return dict(qator) if qator else None


def raqobatchi_qoshish(
    my_product_id: int,
    url: str,
    raqobatchi_nomi: str = "",
    yangi_narx: float = 0.0,
    db_yoli: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    """
    `competitors` jadvaliga tanlangan tovar uchun yangi raqobatchi havolasini qo'shadi.
    URL'dan '?' dan keyingi qism avtomatik kesib tashlanadi.

    Qaytaradi:
        (yangi_qoshildimi, raqobatchi_yozuvi)
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    toza_url = urlni_tozalash(url)
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute("SELECT * FROM competitors WHERE url = ?", (toza_url,))
        mavjud = kursor.fetchone()
        if mavjud is not None:
            return False, dict(mavjud)

        kursor.execute(
            """
            INSERT INTO competitors (
                my_product_id, url, raqobatchi_nomi, eski_narx, yangi_narx, oxirgi_tekshiruv
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(my_product_id), toza_url, raqobatchi_nomi.strip(), None, float(yangi_narx), sana_vaqt),
        )
        yangi_id = kursor.lastrowid
        ulanish.commit()

        kursor.execute("SELECT * FROM competitors WHERE id = ?", (yangi_id,))
        yozuv = dict(kursor.fetchone())

    logger.info(
        "Yangi raqobatchi qo'shildi (%s): my_product_id=%d, url=%s",
        yol,
        my_product_id,
        toza_url,
    )
    return True, yozuv


def raqobatchilarni_olish(
    my_product_id: int | None = None,
    db_yoli: str | None = None,
) -> list[dict[str, Any]]:
    """
    `competitors` jadvalidan raqobatchilar ro'yxatini qaytaradi.
    Agar `my_product_id` berilsa faqat shu tovarga biriktirilganlari, aks holda barchasi qaytadi.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        if my_product_id is not None:
            kursor.execute(
                """
                SELECT id, my_product_id, url, raqobatchi_nomi, eski_narx, yangi_narx, oxirgi_tekshiruv
                FROM competitors
                WHERE my_product_id = ?
                ORDER BY id ASC
                """,
                (int(my_product_id),),
            )
        else:
            kursor.execute(
                """
                SELECT id, my_product_id, url, raqobatchi_nomi, eski_narx, yangi_narx, oxirgi_tekshiruv
                FROM competitors
                ORDER BY my_product_id ASC, id ASC
                """
            )
        return [dict(q) for q in kursor.fetchall()]


def raqobatchi_narxini_yangilash(
    comp_id: int,
    raqobatchi_nomi: str,
    yangi_narx: float,
    db_yoli: str | None = None,
) -> dict[str, Any] | None:
    """
    Raqobatchi narxini va nomini yangilaydi.
    Narx haqiqatan o'zgargan bo'lsa, avvalgi narx `eski_narx` ga ko'chiriladi.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute("SELECT * FROM competitors WHERE id = ?", (int(comp_id),))
        mavjud = kursor.fetchone()
        if mavjud is None:
            return None

        avvalgi_eski = mavjud["eski_narx"]
        avvalgi_yangi = float(mavjud["yangi_narx"] or 0.0)
        yangi_qiymat = float(yangi_narx)
        nomi = (raqobatchi_nomi or "").strip() or str(mavjud["raqobatchi_nomi"] or "")

        ozgardimi = avvalgi_yangi > 0 and yangi_qiymat > 0 and round(avvalgi_yangi, 2) != round(yangi_qiymat, 2)
        saqlanadigan_eski = avvalgi_yangi if ozgardimi else avvalgi_eski

        kursor.execute(
            """
            UPDATE competitors
            SET raqobatchi_nomi = ?,
                eski_narx = ?,
                yangi_narx = ?,
                oxirgi_tekshiruv = ?
            WHERE id = ?
            """,
            (nomi, saqlanadigan_eski, yangi_qiymat, sana_vaqt, int(comp_id)),
        )
        ulanish.commit()

        kursor.execute("SELECT * FROM competitors WHERE id = ?", (int(comp_id),))
        yangilangan = dict(kursor.fetchone())

    yangilangan["ozgardimi"] = ozgardimi
    yangilangan["avvalgi_narx"] = avvalgi_yangi
    return yangilangan


def raqobatchi_ochirish(
    comp_id: int,
    db_yoli: str | None = None,
) -> dict[str, Any] | None:
    """Raqobatchini `competitors` jadvalidan ID bo'yicha o'chiradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute("SELECT * FROM competitors WHERE id = ?", (int(comp_id),))
        mavjud = kursor.fetchone()
        if mavjud is None:
            return None

        kursor.execute("DELETE FROM competitors WHERE id = ?", (int(comp_id),))
        ulanish.commit()

    logger.info("Raqobatchi o'chirildi (%s): id=%d, url=%s", yol, comp_id, mavjud["url"])
    return dict(mavjud)


def katalog_saqlash(
    tovarlar: list[dict[str, Any]],
    db_yoli: str | None = None,
) -> int:
    """
    Uzum Seller API dan olingan tovarlar va ularning ombordagi qoldig'ini
    `catalog` jadvaliga saqlaydi yoki yangilaydi.

    Qaytaradi:
        Saqlangan/yangilangan tovarlar soni.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")
    soni = 0

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        for tovar in tovarlar:
            pid = tovar.get("product_id")
            nomi = str(tovar.get("nomi", "")).strip()
            if pid is None or not nomi:
                continue

            sku = str(
                tovar.get("sku")
                or tovar.get("sku_title")
                or (str(tovar.get("sku_id")) if tovar.get("sku_id") is not None else "")
            ).strip()
            narxi = float(tovar.get("narx") if tovar.get("narx") is not None else (tovar.get("narxi") or 0.0))
            komissiya_foizi = float(
                tovar.get("komissiya_foizi")
                if tovar.get("komissiya_foizi") is not None
                else (tovar.get("komissiya_foiz") or 0.0)
            )
            logistika_tolovi = float(tovar.get("logistika_tolovi") or 0.0)
            qoldiq = int(tovar.get("qoldiq") or 0)

            kursor.execute(
                """
                INSERT INTO catalog (
                    product_id, sku, nomi, narxi, komissiya_foizi,
                    logistika_tolovi, qoldiq, yangilangan_sana
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    sku = excluded.sku,
                    nomi = excluded.nomi,
                    narxi = excluded.narxi,
                    komissiya_foizi = excluded.komissiya_foizi,
                    logistika_tolovi = excluded.logistika_tolovi,
                    qoldiq = excluded.qoldiq,
                    yangilangan_sana = excluded.yangilangan_sana
                """,
                (int(pid), sku, nomi, narxi, komissiya_foizi, logistika_tolovi, qoldiq, sana_vaqt),
            )
            soni += 1

        ulanish.commit()

    logger.info("`catalog` jadvali yangilandi (%s): %d ta tovar saqlandi.", yol, soni)
    return soni


def katalog_sahifa_olish(
    sahifa: int = 1,
    sahifa_hajmi: int = 5,
    db_yoli: str | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """
    `catalog` jadvalidan sahifalangan tovarlar ro'yxatini qaytaradi.

    Qaytaradi:
        (tovarlar, jami_soni, jami_sahifalar)
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute("SELECT COUNT(*) FROM catalog")
        jami_soni = int(kursor.fetchone()[0])

        jami_sahifalar = max(1, (jami_soni + sahifa_hajmi - 1) // sahifa_hajmi)
        joriy_sahifa = max(1, min(sahifa, jami_sahifalar))
        ofset = (joriy_sahifa - 1) * sahifa_hajmi

        kursor.execute(
            """
            SELECT id, product_id, sku, nomi, narxi, komissiya_foizi,
                   logistika_tolovi, qoldiq, yangilangan_sana
            FROM catalog
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            """,
            (sahifa_hajmi, ofset),
        )
        tovarlar = [dict(q) for q in kursor.fetchall()]

    return tovarlar, jami_soni, jami_sahifalar


def katalog_tovar_olish(
    katalog_id: int,
    db_yoli: str | None = None,
) -> dict[str, Any] | None:
    """`catalog` jadvalidan bitta tovarni ID bo'yicha qaytaradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute(
            """
            SELECT id, product_id, sku, nomi, narxi, komissiya_foizi,
                   logistika_tolovi, qoldiq, yangilangan_sana
            FROM catalog
            WHERE id = ?
            """,
            (katalog_id,),
        )
        qator = kursor.fetchone()

    return dict(qator) if qator else None


def kam_qoldiq_tovarlar(
    chegara: int = 5,
    db_yoli: str | None = None,
) -> list[dict[str, Any]]:
    """`catalog` jadvalidan ombordagi qoldig'i `chegara` (standart 5) dan kam tovarlarni qaytaradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute(
            """
            SELECT id, product_id, sku, nomi, narxi, komissiya_foizi,
                   logistika_tolovi, qoldiq, yangilangan_sana
            FROM catalog
            WHERE qoldiq < ?
            ORDER BY qoldiq ASC, id ASC
            """,
            (chegara,),
        )
        return [dict(q) for q in kursor.fetchall()]


def katalogni_uzumdan_yangilash(db_yoli: str | None = None) -> tuple[int, list[dict[str, Any]]]:
    """
    Uzum Market Seller API dan do'kondagi tovarlar va qoldiqlarni yuklab,
    `catalog` (va `mahsulotlar`) jadvaliga yozadi hamda qoldig'i 5 dan kam
    tovarlar ro'yxatini qaytaradi.
    """
    from parsers.uzum_api import uzum_mahsulotlarini_olish

    yol = faol_db_yoli(db_yoli)
    tovarlar = uzum_mahsulotlarini_olish(maks_soni=500)
    if not tovarlar:
        return 0, []

    soni = katalog_saqlash(tovarlar, db_yoli=yol)
    mahsulotlarni_saqlash(tovarlar, db_yoli=yol)
    kam_qoldiqlar = kam_qoldiq_tovarlar(chegara=5, db_yoli=yol)
    return soni, kam_qoldiqlar


def manba_qoshish(url: str, db_yoli: str | None = None) -> tuple[bool, str]:
    """Kuzatiladigan yangi sayt/mahsulot havolasini `manbalar` jadvaliga qo'shadi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    toza_url = urlni_tozalash(url)
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT COUNT(*) FROM manbalar")
        avvalgi_manbalar_soni = kursor.fetchone()[0]

        kursor.execute("SELECT id FROM manbalar WHERE url = ?", (toza_url,))
        if kursor.fetchone() is not None:
            return False, toza_url

        kursor.execute(
            "INSERT INTO manbalar (url, qoshilgan_sana) VALUES (?, ?)",
            (toza_url, sana_vaqt),
        )

        if avvalgi_manbalar_soni == 0 and "books.toscrape.com" not in toza_url.lower():
            kursor.execute("DELETE FROM mahsulotlar WHERE url LIKE '%books.toscrape.com%'")
            ochirilgan = kursor.rowcount
            if ochirilgan > 0:
                logger.info(
                    "Birinchi haqiqiy manba qo'shildi — %d ta eski sinov mahsuloti tozalandi.",
                    ochirilgan,
                )

        ulanish.commit()

    logger.info("Yangi kuzatuv manbasi qo'shildi (%s): %s", yol, toza_url)
    return True, toza_url


def manbalar_royxati(db_yoli: str | None = None) -> list[dict[str, Any]]:
    """`manbalar` jadvalidagi barcha manbalarni (id, url, qoshilgan_sana) qaytaradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute("SELECT id, url, qoshilgan_sana FROM manbalar ORDER BY id ASC")
        return [dict(q) for q in kursor.fetchall()]


def manba_ochirish(manba_id: int, db_yoli: str | None = None) -> str | None:
    """Manbani `manbalar` jadvalidan va unga bog'liq mahsulotlarni o'chiradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT url FROM manbalar WHERE id = ?", (manba_id,))
        qator = kursor.fetchone()
        if qator is None:
            return None

        url = str(qator[0])
        kursor.execute("DELETE FROM manbalar WHERE id = ?", (manba_id,))

        domen = (urlparse(url).netloc or "").lower().removeprefix("www.")
        kursor.execute("SELECT url FROM manbalar")
        qolgan_url = [str(r[0]) for r in kursor.fetchall()]
        boshqa_shu_domen = any(
            (urlparse(u).netloc or "").lower().removeprefix("www.") == domen
            for u in qolgan_url
        )
        if not boshqa_shu_domen and domen:
            kursor.execute("DELETE FROM mahsulotlar WHERE url LIKE ?", (f"%{domen}%",))
        else:
            kursor.execute("DELETE FROM mahsulotlar WHERE url = ?", (url,))

        ulanish.commit()

    logger.info("Kuzatuv manbasi o'chirildi (%s): id=%d, url=%s", yol, manba_id, url)
    return url


def barcha_manbalarni_olish(
    db_yoli: str | None = None,
    standart_url: str = STANDART_SINOV_URL,
) -> list[str]:
    """Kuzatilayotgan barcha manba havolalarini qaytaradi."""
    manbalar = [m["url"] for m in manbalar_royxati(db_yoli)]
    if not manbalar and standart_url:
        return [standart_url]
    return manbalar


def sozlama_saqlash(kalit: str, qiymat: str, db_yoli: str | None = None) -> None:
    """Sozlamani SQLite `settings` jadvaliga saqlaydi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute(
            """
            INSERT INTO settings (kalit, qiymat, yangilangan_sana)
            VALUES (?, ?, ?)
            ON CONFLICT(kalit) DO UPDATE SET
                qiymat = excluded.qiymat,
                yangilangan_sana = excluded.yangilangan_sana
            """,
            (kalit, qiymat, sana_vaqt),
        )
        ulanish.commit()

    logger.info("Sozlama saqlandi (%s): %s = %s", yol, kalit, qiymat)


def sozlama_olish(
    kalit: str,
    standart: str | None = None,
    db_yoli: str | None = None,
) -> str | None:
    """SQLite `settings` jadvalidan ko'rsatilgan sozlama qiymatini o'qiydi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT qiymat FROM settings WHERE kalit = ?", (kalit,))
        qator = kursor.fetchone()

    if qator is None:
        return standart
    return str(qator[0])


def set_language(
    user_id: int | str,
    lang: str,
    db_yoli: str | None = None,
) -> str:
    """
    Foydalanuvchining tanlagan tilini (`uz` yoki `ru`) `settings` jadvalidagi
    `language` ustuniga saqlaydi hamda unga mos standart vaqt mintaqasini
    (`uz` -> Asia/Tashkent, `ru` -> Europe/Moscow) avtomatik o'rnatadi.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    toza_til = "ru" if str(lang).strip().lower() == "ru" else "uz"
    mos_tz = TIL_VAQT_MINTAQALARI.get(toza_til, STANDART_TIMEZONE)
    kalit = f"user_lang:{user_id}"
    tz_kalit = f"user_tz:{user_id}"
    sana_vaqt = hozirgi_vaqt(tz_nomi=mos_tz).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute(
            """
            INSERT INTO settings (kalit, qiymat, yangilangan_sana, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kalit) DO UPDATE SET
                qiymat = excluded.qiymat,
                yangilangan_sana = excluded.yangilangan_sana,
                language = excluded.language
            """,
            (kalit, toza_til, sana_vaqt, toza_til),
        )
        kursor.execute(
            """
            INSERT INTO settings (kalit, qiymat, yangilangan_sana, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kalit) DO UPDATE SET
                qiymat = excluded.qiymat,
                yangilangan_sana = excluded.yangilangan_sana,
                language = excluded.language
            """,
            (tz_kalit, mos_tz, sana_vaqt, toza_til),
        )
        ulanish.commit()

    logger.info(
        "Foydalanuvchi tili saqlandi (%s): user_id=%s -> %s (TIMEZONE=%s)",
        yol,
        user_id,
        toza_til,
        mos_tz,
    )
    return toza_til


def get_language(
    user_id: int | str,
    db_yoli: str | None = None,
) -> str:
    """
    Foydalanuvchining saqlangan tilini `settings.language` ustunidan qaytaradi.
    Agar hali tanlanmagan bo'lsa standart `"uz"` qaytadi.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    kalit = f"user_lang:{user_id}"

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT language FROM settings WHERE kalit = ?", (kalit,))
        qator = kursor.fetchone()

    if qator is None or not qator[0]:
        return "uz"
    return "ru" if str(qator[0]).strip().lower() == "ru" else "uz"


def set_timezone(
    user_id: int | str,
    tz_nomi: str,
    db_yoli: str | None = None,
) -> str:
    """
    Foydalanuvchi uchun faol vaqt mintaqasini (`Asia/Tashkent` yoki `Europe/Moscow`)
    SQLite `settings` jadvaliga saqlaydi.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    toza_tz = (
        MOSKVA_TIMEZONE
        if str(tz_nomi).strip() == MOSKVA_TIMEZONE
        else STANDART_TIMEZONE
    )
    kalit = f"user_tz:{user_id}"
    joriy_til = get_language(user_id, db_yoli=yol)
    sana_vaqt = hozirgi_vaqt(tz_nomi=toza_tz).strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute(
            """
            INSERT INTO settings (kalit, qiymat, yangilangan_sana, language)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(kalit) DO UPDATE SET
                qiymat = excluded.qiymat,
                yangilangan_sana = excluded.yangilangan_sana,
                language = excluded.language
            """,
            (kalit, toza_tz, sana_vaqt, joriy_til),
        )
        ulanish.commit()

    logger.info("Foydalanuvchi vaqt mintaqasi saqlandi (%s): user_id=%s -> %s", yol, user_id, toza_tz)
    return toza_tz


def get_timezone(
    user_id: int | str,
    lang: str | None = None,
    db_yoli: str | None = None,
) -> str:
    """
    Foydalanuvchining saqlangan vaqt mintaqasini qaytaradi.
    Agar alohida saqlanmagan bo'lsa, tilga mos standart (`ru` -> Europe/Moscow,
    `uz` -> Asia/Tashkent) qaytadi.
    """
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    kalit = f"user_tz:{user_id}"

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT qiymat FROM settings WHERE kalit = ?", (kalit,))
        qator = kursor.fetchone()

    if qator is not None and qator[0] in QULLAB_QUVVATLANADIGAN_VAQT_MINTAQALARI:
        return str(qator[0])

    faol_til = lang if lang is not None else get_language(user_id, db_yoli=yol)
    return TIL_VAQT_MINTAQALARI.get(faol_til, STANDART_TIMEZONE)


def til_tanlanganmi(
    user_id: int | str,
    db_yoli: str | None = None,
) -> bool:
    """Foydalanuvchi avval til tanlagan-tanlamaganini tekshiradi (ilk /start uchun)."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    kalit = f"user_lang:{user_id}"

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT 1 FROM settings WHERE kalit = ?", (kalit,))
        return kursor.fetchone() is not None


def mahsulotlarni_saqlash(
    mahsulotlar: list[dict[str, Any]],
    db_yoli: str | None = None,
) -> tuple[int, int]:
    """
    Yig'ilgan mahsulotlarni bazaga saqlaydi yoki yangilaydi.
    `eski_narx` faqat narx haqiqatan o'zgarganda yangilanadi.
    """
    yol = faol_db_yoli(db_yoli)
    logger.info("Ma'lumotlar bazasini yangilash boshlandi (%s)...", yol)
    bazani_tayyorlash(yol)

    yangi_soni = 0
    yangilangan_soni = 0
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(yol) as ulanish:
            kursor = ulanish.cursor()

            for mahsulot in mahsulotlar:
                toza_url = urlni_tozalash(str(mahsulot.get("url", "")))
                nomi = str(mahsulot.get("nomi", "")).strip()
                narx = mahsulot.get("narx")
                valyuta = str(mahsulot.get("valyuta", "") or "").strip()
                reyting = mahsulot.get("reyting")

                shop_id = mahsulot.get("shop_id")
                product_id = mahsulot.get("product_id")
                sku_id = mahsulot.get("sku_id")
                sku_title = str(mahsulot.get("sku_title", "") or "").strip()
                qoldiq = int(mahsulot.get("qoldiq") or 0)
                sotilgan = int(mahsulot.get("sotilgan") or 0)
                qaytgan = int(mahsulot.get("qaytgan") or 0)
                vozvrat_foiz = float(mahsulot.get("vozvrat_foiz") or 0.0)
                komissiya_foiz = float(mahsulot.get("komissiya_foiz") or 0.0)
                holat_matni = str(mahsulot.get("holat_matni", "") or "").strip()

                if not toza_url or not nomi:
                    continue

                yangi_narx_qiymat = 0.0 if narx is None else float(narx)

                kursor.execute(
                    "SELECT id, eski_narx, yangi_narx, valyuta FROM mahsulotlar WHERE url = ?",
                    (toza_url,),
                )
                mavjud_yozuv = kursor.fetchone()

                if mavjud_yozuv is not None:
                    _, avvalgi_eski_narx, avvalgi_yangi_narx, avvalgi_valyuta = mavjud_yozuv
                    if round(float(avvalgi_yangi_narx), 2) != round(yangi_narx_qiymat, 2):
                        saqlanadigan_eski_narx = avvalgi_yangi_narx
                    else:
                        saqlanadigan_eski_narx = avvalgi_eski_narx

                    saqlanadigan_valyuta = valyuta or avvalgi_valyuta or ""
                    kursor.execute(
                        """
                        UPDATE mahsulotlar
                        SET nomi = ?,
                            eski_narx = ?,
                            yangi_narx = ?,
                            valyuta = ?,
                            reyting = ?,
                            oxirgi_sana = ?,
                            shop_id = COALESCE(?, shop_id),
                            product_id = COALESCE(?, product_id),
                            sku_id = COALESCE(?, sku_id),
                            sku_title = CASE WHEN ? != '' THEN ? ELSE sku_title END,
                            qoldiq = ?,
                            sotilgan = ?,
                            qaytgan = ?,
                            vozvrat_foiz = ?,
                            komissiya_foiz = ?,
                            holat_matni = CASE WHEN ? != '' THEN ? ELSE holat_matni END
                        WHERE url = ?
                        """,
                        (
                            nomi,
                            saqlanadigan_eski_narx,
                            yangi_narx_qiymat,
                            saqlanadigan_valyuta,
                            reyting,
                            sana_vaqt,
                            shop_id,
                            product_id,
                            sku_id,
                            sku_title,
                            sku_title,
                            qoldiq,
                            sotilgan,
                            qaytgan,
                            vozvrat_foiz,
                            komissiya_foiz,
                            holat_matni,
                            holat_matni,
                            toza_url,
                        ),
                    )
                    yangilangan_soni += 1
                else:
                    kursor.execute(
                        """
                        INSERT INTO mahsulotlar (
                            url, nomi, eski_narx, yangi_narx, valyuta, reyting, oxirgi_sana,
                            shop_id, product_id, sku_id, sku_title,
                            qoldiq, sotilgan, qaytgan, vozvrat_foiz, komissiya_foiz, holat_matni
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            toza_url,
                            nomi,
                            None,
                            yangi_narx_qiymat,
                            valyuta,
                            reyting,
                            sana_vaqt,
                            shop_id,
                            product_id,
                            sku_id,
                            sku_title,
                            qoldiq,
                            sotilgan,
                            qaytgan,
                            vozvrat_foiz,
                            komissiya_foiz,
                            holat_matni,
                        ),
                    )
                    yangi_soni += 1

            ulanish.commit()

        logger.info(
            "Baza muvaffaqiyatli yangilandi (%s): %d ta yangi qo'shildi, %d ta yangilandi.",
            yol,
            yangi_soni,
            yangilangan_soni,
        )
        return yangi_soni, yangilangan_soni

    except sqlite3.Error as xato:
        logger.error("SQLite bazasiga yozishda xatolik (%s): %s", yol, xato)
        raise


def sinov_mahsulotlarini_tozalash(db_yoli: str | None = None) -> int:
    """Eski `books.toscrape.com` sinov yozuvlarini bazadan tozalaydi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("DELETE FROM mahsulotlar WHERE url LIKE '%books.toscrape.com%'")
        ochirilgan = kursor.rowcount
        ulanish.commit()
    if ochirilgan > 0:
        logger.info("%d ta eski sinov mahsuloti (books.toscrape.com) tozalandi.", ochirilgan)
    return ochirilgan


def mahsulotni_id_bilan_olish(
    mahsulot_db_id: int,
    db_yoli: str | None = None,
) -> dict[str, Any] | None:
    """ID bo'yicha bitta mahsulotning to'liq ma'lumotlarini qaytaradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute(
            """
            SELECT id, url, nomi, eski_narx, yangi_narx, valyuta, reyting, oxirgi_sana,
                   shop_id, product_id, sku_id, sku_title,
                   qoldiq, sotilgan, qaytgan, vozvrat_foiz, komissiya_foiz, holat_matni
            FROM mahsulotlar
            WHERE id = ?
            """,
            (mahsulot_db_id,),
        )
        qator = kursor.fetchone()

    return dict(qator) if qator else None


def mahsulot_narxini_yangilash_lokal(
    mahsulot_db_id: int,
    yangi_narx: float,
    db_yoli: str | None = None,
) -> bool:
    """API orqali narx yangilangandan so'ng lokal bazada ham darhol yangilaydi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)
    sana_vaqt = hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S")

    with sqlite3.connect(yol) as ulanish:
        kursor = ulanish.cursor()
        kursor.execute("SELECT yangi_narx FROM mahsulotlar WHERE id = ?", (mahsulot_db_id,))
        qator = kursor.fetchone()
        if qator is None:
            return False

        avvalgi_narx = float(qator[0])
        kursor.execute(
            """
            UPDATE mahsulotlar
            SET eski_narx = ?, yangi_narx = ?, oxirgi_sana = ?
            WHERE id = ?
            """,
            (avvalgi_narx, float(yangi_narx), sana_vaqt, mahsulot_db_id),
        )
        ulanish.commit()
    return True


def barcha_mahsulotlarni_olish(db_yoli: str | None = None) -> list[dict[str, Any]]:
    """Bazadagi barcha mahsulotlarni lug'atlar ro'yxati ko'rinishida qaytaradi."""
    yol = faol_db_yoli(db_yoli)
    bazani_tayyorlash(yol)

    with sqlite3.connect(yol) as ulanish:
        ulanish.row_factory = sqlite3.Row
        kursor = ulanish.cursor()
        kursor.execute(
            """
            SELECT id, url, nomi, eski_narx, yangi_narx, valyuta, reyting, oxirgi_sana,
                   shop_id, product_id, sku_id, sku_title,
                   qoldiq, sotilgan, qaytgan, vozvrat_foiz, komissiya_foiz, holat_matni
            FROM mahsulotlar
            ORDER BY id ASC
            """
        )
        qatorlar = kursor.fetchall()

    return [dict(qator) for qator in qatorlar]
