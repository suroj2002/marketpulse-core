"""
MarketPulse Core — Ikki tilli (`uz` / `ru`) interaktiv Telegram bot va APScheduler moduli.

Barcha foydalanuvchi matnlari va tugmalari 100% `locales.py` (`TEXTS`, `t()`) orqali olinadi.
Xususiyatlari:
- Birinchi `/start` da til tanlash (`🇺🇿 O'zbekcha` / `🇷🇺 Русский`) va asosiy menyuda `🌐 Til / Язык`.
- `📦 Mening katalogim` (5 tadan sahifalash, `🔄 Katalogni yangilash`).
- `🧮 Aqlli kalkulyator` (faqat marketplace komissiyasi + logistika, soliqsiz, `✏️ Boshqa narxda sinash`).
- `👀 Raqobatchilar` (qo'lda URL qo'shish, hozir tekshirish, o'chirish, kunlik qizil signal).
- `📉 Qoldiqlar nazorati` (`qoldiq < 5` Stock Alert — katalog yangilanganda va kunlik jadvalda).
- Zero-Storage: Excel fayl Telegram'ga yuborilishi bilan `os.remove()` orqali darhol o'chiriladi.
"""

import asyncio
import html
import logging
import os
from pathlib import Path
import re
import socket
import sys
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramConflictError, TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from database import (
    barcha_manbalarni_olish,
    bazani_tayyorlash,
    faol_db_yoli,
    get_language,
    get_timezone,
    kam_qoldiq_tovarlar,
    katalog_sahifa_olish,
    katalog_tovar_olish,
    katalog_tovar_product_id_bilan_olish,
    katalogni_uzumdan_yangilash,
    manba_ochirish,
    manba_qoshish,
    manbalar_royxati,
    raqobatchi_narxini_yangilash,
    raqobatchi_ochirish,
    raqobatchi_qoshish,
    raqobatchilarni_olish,
    set_language,
    set_timezone,
    sozlama_olish,
    sozlama_saqlash,
    til_tanlanganmi,
    urlni_tozalash,
)
from demo_data import (
    demo_kam_qoldiq_tovarlar,
    demo_katalog_sahifa_olish,
    demo_katalog_tovar_olish,
    demo_raqobatchilarni_olish,
)
from locales import t, valyuta_yorligi, vaqt_mintaqasi_yorligi
from main import eski_excel_fayllarni_tozalash, hisobot_tayyorlash
from notifier import MAKS_FAYL_HAJMI_BAYT, MAKS_FAYL_HAJMI_MB, _matnni_bolish
from parser import kop_manbadan_yigish, mahsulotlarni_yigish
from parsers.ozon_api import ozon_sozlanganmi
from parsers.universal import domenni_olish, narxni_formatlash, narxni_tozalash, sayt_konfiguratsiyasini_topish
from parsers.uzum_api import uzum_sozlanganmi
from utils import (
    MOSKVA_TIMEZONE,
    STANDART_TIMEZONE,
    hozirgi_vaqt,
    loggerni_olish,
    vaqt_mintaqasi_nomi,
    vaqt_mintaqasini_olish,
)


logger = loggerni_olish("bot")

JADVAL_KALITI = "jadval_vaqti"
STANDART_VAQT = "09:00"
JADVAL_ISH_ID = "kunlik_monitoring"
TAYYOR_VAQTLAR = ("08:00", "09:00", "13:00", "18:00", "21:00")

router = Router()
jarayon_qulfi = asyncio.Lock()
rejalashtiruvchi: AsyncIOScheduler | None = None
ruxsat_etilgan_chat_id: str = ""
bot_obyekti: Bot | None = None
# Demo foydalanuvchilar tili faqat xotirada saqlanadi (SQLite bazasiga yozilmaydi — Zero-Leak)
_DEMO_FOYDALANUVCHI_TILLARI: dict[str, str] = {}
_MAKS_DEMO_SESSIYALAR = 5000


class VaqtKiritishHolati(StatesGroup):
    """Foydalanuvchi qo'lda HH:MM formatida vaqt kiritishini kutish holati."""

    vaqt_kutilmoqda = State()


class ManbaQoshishHolati(StatesGroup):
    """Foydalanuvchi kuzatish uchun yangi sayt/mahsulot havolasini yuborishini kutish holati."""

    url_kutilmoqda = State()


class KalkulyatorNarxHolati(StatesGroup):
    """Aqlli kalkulyatorda boshqa narxda sinab ko'rish holati."""

    narx_kutilmoqda = State()


class RaqobatchiQoshishHolati(StatesGroup):
    """Tovar kartochkasiga qo'lda raqobatchi havolasini (URL) qo'shish holati."""

    url_kutilmoqda = State()


def urlni_tekshirish(matn: str) -> str | None:
    """Kiritilgan matn haqiqiy http:// yoki https:// havola ekanini tekshiradi."""
    havola = (matn or "").strip()
    tahlil = urlparse(havola)
    if tahlil.scheme in ("http", "https") and tahlil.netloc and "." in tahlil.netloc:
        return havola
    return None


def vaqt_formatini_tekshirish(matn: str) -> str | None:
    """Foydalanuvchi kiritgan vaqtni HH:MM formatida tekshiradi va normallashtiradi."""
    moslik = re.fullmatch(r"\s*([01]?\d|2[0-3]):([0-5]\d)\s*", matn or "")
    if not moslik:
        return None
    soat = int(moslik.group(1))
    daqiqa = int(moslik.group(2))
    return f"{soat:02d}:{daqiqa:02d}"


def adminmi(chat_id: int | str) -> bool:
    """Faqat .env dagi TELEGRAM_CHAT_ID egasi (Admin) ekanini tekshiradi."""
    return bool(ruxsat_etilgan_chat_id) and str(chat_id) == ruxsat_etilgan_chat_id


def ruxsat_bormi(chat_id: int | str) -> bool:
    """Orqaga moslik (alias): Admin ekanini tekshiradi."""
    return adminmi(chat_id)


def _demo_tilni_saqlash(chat_id: int | str, lang: str) -> str:
    """Demo foydalanuvchi tilini bazaga tegmasdan faqat RAM da saqlaydi."""
    if len(_DEMO_FOYDALANUVCHI_TILLARI) >= _MAKS_DEMO_SESSIYALAR:
        _DEMO_FOYDALANUVCHI_TILLARI.clear()
    toza = "ru" if str(lang).strip().lower() == "ru" else "uz"
    _DEMO_FOYDALANUVCHI_TILLARI[str(chat_id)] = toza
    return toza


def _foydalanuvchi_tili(chat_id: int | str, db_yoli: str | None = None) -> str:
    """Admin uchun SQLite `settings.language`, Demo foydalanuvchi uchun RAM dan tilni qaytaradi."""
    if not adminmi(chat_id):
        return _DEMO_FOYDALANUVCHI_TILLARI.get(str(chat_id), "uz")
    return get_language(chat_id, db_yoli=faol_db_yoli(db_yoli))


def _foydalanuvchi_vaqt_mintaqasi(
    chat_id: int | str | None,
    lang: str | None = None,
    db_yoli: str | None = None,
) -> str:
    """Admin uchun SQLite dan, Demo foydalanuvchi uchun tilga mos standart vaqt mintaqasini qaytaradi."""
    if chat_id is not None and not adminmi(chat_id):
        til = lang or _foydalanuvchi_tili(chat_id)
        return vaqt_mintaqasi_nomi(lang=til)
    egasi = chat_id if chat_id is not None else ruxsat_etilgan_chat_id
    if not egasi:
        return vaqt_mintaqasi_nomi(lang=lang)
    return get_timezone(egasi, lang=lang, db_yoli=faol_db_yoli(db_yoli))


def demo_asosiy_tugmalar(lang: str = "uz") -> InlineKeyboardMarkup:
    """🎭 Demo-rejim uchun xavfsiz, faqat o'qish va kalkulyator tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_my_catalog", lang),
                    callback_data="mening_katalogim:1",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_demo_stock_alerts", lang),
                    callback_data="demo_qoldiqlar",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_language", lang),
                    callback_data="til_tanlash",
                )
            ],
        ]
    )


def _demo_bosh_menyu_matni(lang: str = "uz") -> str:
    """🎭 Demo-rejim bosh menyu matni (real bazaga mutlaqo murojaat qilmaydi)."""
    _, katalog_soni, _ = demo_katalog_sahifa_olish(sahifa=1, sahifa_hajmi=5, lang=lang)
    kam_soni = len(demo_kam_qoldiq_tovarlar(chegara=5, lang=lang))
    tz_nomi = vaqt_mintaqasi_nomi(lang=lang)
    tz_yorliq = html.escape(vaqt_mintaqasi_yorligi(tz_nomi, lang))
    hozir = html.escape(hozirgi_vaqt(lang=lang, tz_nomi=tz_nomi).strftime("%H:%M"))
    return t(
        "demo_main_menu_text",
        lang,
        demo_banner=t("demo_banner", lang),
        now_time=hozir,
        timezone=tz_yorliq,
        catalog_count=katalog_soni,
        low_stock=kam_soni,
    )


def _menyu_matni_va_tugmalar(
    chat_id: int | str,
    lang: str,
    db_yoli: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Admin uchun real bosh menyuni, begona foydalanuvchi uchun Demo-rejim menyusini qaytaradi."""
    if adminmi(chat_id):
        return _bosh_menyu_matni(lang, chat_id=chat_id, db_yoli=db_yoli), asosiy_tugmalar(lang)
    return _demo_bosh_menyu_matni(lang), demo_asosiy_tugmalar(lang)


def til_tanlash_tugmalari(lang: str = "uz") -> InlineKeyboardMarkup:
    """🇺🇿 O'zbekcha va 🇷🇺 Русский til tanlash tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("btn_lang_uz", lang), callback_data="set_lang:uz"),
                InlineKeyboardButton(text=t("btn_lang_ru", lang), callback_data="set_lang:ru"),
            ]
        ]
    )


def asosiy_tugmalar(lang: str = "uz") -> InlineKeyboardMarkup:
    """Har bir hisobot va /start tagida chiqadigan asosiy interaktiv tugmalar."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_my_catalog", lang),
                    callback_data="mening_katalogim:1",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_recheck_now", lang),
                    callback_data="qayta_tekshirish",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_set_time", lang),
                    callback_data="vaqt_ornatish",
                ),
                InlineKeyboardButton(
                    text=t("btn_add_source", lang),
                    callback_data="manba_qoshish",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_sources", lang),
                    callback_data="manbalar_royxati",
                ),
                InlineKeyboardButton(
                    text=t("btn_language", lang),
                    callback_data="til_tanlash",
                ),
            ],
        ]
    )


def bekor_qilish_tugmasi(lang: str = "uz") -> InlineKeyboardMarkup:
    """FSM kiritish jarayonini 1 bosish bilan bekor qilish tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_cancel", lang),
                    callback_data="bekor_qilish",
                )
            ]
        ]
    )


def vaqt_tanlash_tugmalari(
    lang: str = "uz",
    faol_tz: str | None = None,
) -> InlineKeyboardMarkup:
    """Avtomatik hisobot vaqti va vaqt mintaqasini (Toshkent / Moskva) tanlash tugmalari."""
    joriy_tz = faol_tz or vaqt_mintaqasi_nomi(lang=lang)
    toshkent_matn = ("✅ " if joriy_tz == STANDART_TIMEZONE else "") + t("btn_tz_tashkent", lang)
    moskva_matn = ("✅ " if joriy_tz == MOSKVA_TIMEZONE else "") + t("btn_tz_moscow", lang)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="08:00", callback_data="vaqt:08:00"),
                InlineKeyboardButton(text="09:00", callback_data="vaqt:09:00"),
                InlineKeyboardButton(text="13:00", callback_data="vaqt:13:00"),
            ],
            [
                InlineKeyboardButton(text="18:00", callback_data="vaqt:18:00"),
                InlineKeyboardButton(text="21:00", callback_data="vaqt:21:00"),
            ],
            [
                InlineKeyboardButton(
                    text=toshkent_matn,
                    callback_data=f"set_tz:{STANDART_TIMEZONE}",
                ),
                InlineKeyboardButton(
                    text=moskva_matn,
                    callback_data=f"set_tz:{MOSKVA_TIMEZONE}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_custom_time", lang),
                    callback_data="boshqa_vaqt",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_back", lang),
                    callback_data="bosh_menyu",
                )
            ],
        ]
    )


def manbalar_tugmalari(manbalar: list[dict], lang: str = "uz") -> InlineKeyboardMarkup:
    """Har bir saqlangan manba uchun o'chirish tugmasi hamda qo'shish/ortga tugmalari."""
    qatorlar: list[list[InlineKeyboardButton]] = []
    for indeks, m in enumerate(manbalar, start=1):
        domen = domenni_olish(m["url"]) or m["url"][:25]
        qatorlar.append(
            [
                InlineKeyboardButton(
                    text=t("btn_delete_source", lang, index=indeks, domain=domen),
                    callback_data=f"manba_ochir:{m['id']}",
                )
            ]
        )

    qatorlar.append(
        [
            InlineKeyboardButton(
                text=t("btn_add_source", lang),
                callback_data="manba_qoshish",
            ),
            InlineKeyboardButton(
                text=t("btn_back", lang),
                callback_data="bosh_menyu",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def mening_katalogim_tugmalari(
    tovarlar: list[dict],
    joriy_sahifa: int,
    jami_sahifalar: int,
    lang: str = "uz",
    demo_rejim: bool = False,
) -> InlineKeyboardMarkup:
    """📦 Mening katalogim uchun sahifalangan (5 tadan) va (Admin uchun) yangilash tugmalari."""
    val = valyuta_yorligi("so'm", lang)
    qatorlar: list[list[InlineKeyboardButton]] = []
    bosh_raqam = (joriy_sahifa - 1) * 5 + 1
    for ofset, tovar in enumerate(tovarlar):
        tartib = bosh_raqam + ofset
        qoldiq = int(tovar.get("qoldiq") or 0)
        holat_belgi = "✅" if qoldiq >= 5 else "⚠️"
        qisqa_nom = str(tovar["nomi"])[:30] + ("…" if len(str(tovar["nomi"])) > 30 else "")
        narx_matn = narxni_formatlash(float(tovar["narxi"]), val)
        qatorlar.append(
            [
                InlineKeyboardButton(
                    text=f"{tartib}. {holat_belgi} {qisqa_nom} ({narx_matn})",
                    callback_data=f"kat_tovar:{tovar['id']}:{joriy_sahifa}",
                )
            ]
        )

    oldingi_cb = f"mening_katalogim:{joriy_sahifa - 1}" if joriy_sahifa > 1 else "sahifa_boshi"
    keyingi_cb = (
        f"mening_katalogim:{joriy_sahifa + 1}" if joriy_sahifa < jami_sahifalar else "sahifa_oxiri"
    )
    qatorlar.append(
        [
            InlineKeyboardButton(text=t("btn_prev_page", lang), callback_data=oldingi_cb),
            InlineKeyboardButton(text=f"{joriy_sahifa}/{jami_sahifalar}", callback_data="sahifa_holat"),
            InlineKeyboardButton(text=t("btn_next_page", lang), callback_data=keyingi_cb),
        ]
    )
    if not demo_rejim:
        qatorlar.append(
            [
                InlineKeyboardButton(
                    text=t("btn_refresh_catalog", lang),
                    callback_data="katalog_yangilash",
                )
            ]
        )
    qatorlar.append(
        [
            InlineKeyboardButton(text=t("btn_main_menu", lang), callback_data="bosh_menyu"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def katalog_tovar_tugmalari(
    katalog_id: int,
    sahifa: int,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """📦 Mening katalogim dan tanlangan tovar ostidagi 3 ta asosiy tugma."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_smart_calculator", lang),
                    callback_data=f"kalkulyator:{katalog_id}:{sahifa}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_competitors", lang),
                    callback_data=f"kat_raqobatchi:{katalog_id}:{sahifa}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_back_to_catalog", lang),
                    callback_data=f"mening_katalogim:{sahifa}",
                )
            ],
        ]
    )


def kalkulyator_tugmalari(
    katalog_id: int,
    sahifa: int,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """🧮 Aqlli kalkulyator ostidagi tugmalar."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_try_other_price", lang),
                    callback_data=f"kalk_sinash:{katalog_id}:{sahifa}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_back_to_product", lang),
                    callback_data=f"kat_tovar:{katalog_id}:{sahifa}",
                ),
                InlineKeyboardButton(
                    text=t("btn_back_to_catalog", lang),
                    callback_data=f"mening_katalogim:{sahifa}",
                ),
            ],
        ]
    )


def raqobatchilar_menyu_tugmalari(
    katalog_id: int,
    sahifa: int,
    lang: str = "uz",
    demo_rejim: bool = False,
) -> InlineKeyboardMarkup:
    """👀 Raqobatchilar bo'limidagi boshqaruv tugmalari (Demo-rejimda faqat o'qish/qaytish)."""
    qatorlar: list[list[InlineKeyboardButton]] = []
    if not demo_rejim:
        qatorlar.extend(
            [
                [
                    InlineKeyboardButton(
                        text=t("btn_add_competitor", lang),
                        callback_data=f"raq_qoshish:{katalog_id}:{sahifa}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=t("btn_check_competitors", lang),
                        callback_data=f"raq_tekshir:{katalog_id}:{sahifa}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=t("btn_delete_competitor", lang),
                        callback_data=f"raq_ochir_menyu:{katalog_id}:{sahifa}",
                    )
                ],
            ]
        )
    qatorlar.append(
        [
            InlineKeyboardButton(
                text=t("btn_back_to_product", lang),
                callback_data=f"kat_tovar:{katalog_id}:{sahifa}",
            ),
            InlineKeyboardButton(
                text=t("btn_back_to_catalog", lang),
                callback_data=f"mening_katalogim:{sahifa}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def raqobatchi_ochirish_tugmalari(
    raqobatchilar: list[dict],
    katalog_id: int,
    sahifa: int,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """Har bir raqobatchini alohida o'chirish tugmalari."""
    val = valyuta_yorligi("so'm", lang)
    qatorlar: list[list[InlineKeyboardButton]] = []
    for indeks, r in enumerate(raqobatchilar, start=1):
        nom = str(r.get("raqobatchi_nomi") or domenni_olish(r["url"]) or "—")
        qisqa_nom = nom[:28] + ("…" if len(nom) > 28 else "")
        narx = float(r.get("yangi_narx") or 0.0)
        narx_matn = narxni_formatlash(narx, val) if narx > 0 else "—"
        qatorlar.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 #{indeks} {qisqa_nom} ({narx_matn})",
                    callback_data=f"raq_ochir:{r['id']}:{katalog_id}:{sahifa}",
                )
            ]
        )
    qatorlar.append(
        [
            InlineKeyboardButton(
                text=t("btn_back_to_competitors", lang),
                callback_data=f"kat_raqobatchi:{katalog_id}:{sahifa}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=qatorlar)


def kalkulyator_hisob_matni(
    tovar: dict,
    sinov_narxi: float | None = None,
    lang: str = "uz",
) -> str:
    """
    🧮 Aqlli kalkulyator (FAQAT marketplace to'lovlari — davlat soliqlarisiz).
    Tanlangan tilda (`uz`/`ru`) natija qaytaradi.
    """
    sotuv_narxi = float(sinov_narxi if sinov_narxi is not None else tovar["narxi"])
    kom_foiz = float(tovar.get("komissiya_foizi") or 0.0)
    logistika = float(tovar.get("logistika_tolovi") or 0.0)

    kom_summa = round(sotuv_narxi * kom_foiz / 100.0)
    logistika_summa = round(logistika)
    qoladigan_summa = sotuv_narxi - kom_summa - logistika_summa

    val = valyuta_yorligi("so'm", lang)
    qatorlar = [
        t("calc_title", lang),
        f"📦 <b>{html.escape(str(tovar['nomi']))}</b>",
        "━━━━━━━━━━━━━━━━━━",
        t("calc_sell_price", lang, price=narxni_formatlash(sotuv_narxi, val)),
        t(
            "calc_commission",
            lang,
            percent=kom_foiz,
            amount=narxni_formatlash(float(kom_summa), val),
        ),
    ]
    if logistika_summa > 0:
        qatorlar.append(
            t("calc_logistics", lang, amount=narxni_formatlash(float(logistika_summa), val))
        )
    qatorlar.append("━━━━━━━━━━━━━━━━━━")
    qatorlar.append(
        t("calc_net_payout", lang, amount=narxni_formatlash(qoladigan_summa, val))
    )
    return "\n".join(qatorlar)


def qoldiq_ogohlantirish_matni(kam_qoldiqlar: list[dict], lang: str = "uz") -> str:
    """📉 Qoldiqlar nazorati (qoldiq < 5) uchun alohida ogohlantirish matnini tuzadi."""
    if not kam_qoldiqlar:
        return ""
    qatorlar = [t("stock_alert_title", lang)]
    for item in kam_qoldiqlar:
        qatorlar.append(
            t(
                "stock_alert_line",
                lang,
                name=html.escape(str(item["nomi"])),
                qty=int(item["qoldiq"]),
            )
        )
    return "\n".join(qatorlar)


def raqobatchi_arzonroq_ogohlantirish_matni(
    bizning_tovar: dict,
    raqobatchi: dict,
    lang: str = "uz",
) -> str:
    """Raqobatchi narxi `catalog` narximizdan past bo'lganda qizil ogohlantirish tuzadi."""
    bizning_narx = float(bizning_tovar["narxi"])
    raq_narx = float(raqobatchi["yangi_narx"])
    farq = bizning_narx - raq_narx
    val = valyuta_yorligi("so'm", lang)
    return t(
        "comp_undercut_alert",
        lang,
        product_name=html.escape(str(bizning_tovar["nomi"])),
        comp_name=html.escape(
            str(raqobatchi.get("raqobatchi_nomi") or domenni_olish(raqobatchi["url"]))
        ),
        our_price=narxni_formatlash(bizning_narx, val),
        comp_price=narxni_formatlash(raq_narx, val),
        diff=narxni_formatlash(farq, val),
        url=html.escape(str(raqobatchi["url"])),
    )


def raqobatchilar_royxat_matni(
    tovar: dict,
    raqobatchilar: list[dict],
    lang: str = "uz",
) -> str:
    """Tovarga biriktirilgan barcha raqobatchilar ro'yxati va narx farqini formatlaydi."""
    val = valyuta_yorligi("so'm", lang)
    bizning_narx = float(tovar["narxi"])
    qatorlar = [
        t("comp_title", lang),
        t("comp_product_line", lang, name=html.escape(str(tovar["nomi"]))),
        t("comp_our_price", lang, price=narxni_formatlash(bizning_narx, val)),
        "━━━━━━━━━━━━━━━━━━",
    ]

    if not raqobatchilar:
        qatorlar.append(t("comp_empty", lang))
        return "\n".join(qatorlar)

    for indeks, r in enumerate(raqobatchilar, start=1):
        raq_nom = html.escape(str(r.get("raqobatchi_nomi") or domenni_olish(r["url"]) or "—"))
        raq_narx = float(r.get("yangi_narx") or 0.0)
        havola = html.escape(str(r["url"]))
        sana = html.escape(str(r.get("oxirgi_tekshiruv") or "—"))

        if raq_narx > 0:
            farq = raq_narx - bizning_narx
            if farq < 0:
                farq_matn = t("comp_diff_cheaper", lang, diff=narxni_formatlash(abs(farq), val))
            elif farq > 0:
                farq_matn = t("comp_diff_pricier", lang, diff=narxni_formatlash(farq, val))
            else:
                farq_matn = t("comp_diff_equal", lang)
            narx_qism = f"<b>{narxni_formatlash(raq_narx, val)}</b> ({farq_matn})"
        else:
            narx_qism = t("comp_price_unknown", lang)

        qatorlar.append(
            f"{indeks}. <b>{raq_nom}</b>\n"
            f"   💵 {narx_qism}\n"
            f"   🔗 <a href=\"{havola}\">{t('comp_open_link', lang)}</a> · 🕒 {sana}"
        )

    return "\n".join(qatorlar)


def _bosh_menyu_matni(
    lang: str = "uz",
    chat_id: int | str | None = None,
    db_yoli: str | None = None,
) -> str:
    """/start va bosh menyu uchun xavfsiz HTML matnni tayyorlaydi."""
    yol = faol_db_yoli(db_yoli)
    joriy_vaqt = html.escape(sozlama_olish(JADVAL_KALITI, STANDART_VAQT, db_yoli=yol) or STANDART_VAQT)
    tz_nomi = _foydalanuvchi_vaqt_mintaqasi(chat_id, lang=lang, db_yoli=yol)
    tz_yorliq = html.escape(vaqt_mintaqasi_yorligi(tz_nomi, lang))
    hozir = html.escape(hozirgi_vaqt(lang=lang, tz_nomi=tz_nomi).strftime("%H:%M"))
    manbalar_soni = len(manbalar_royxati(db_yoli=yol))
    _, katalog_soni, _ = katalog_sahifa_olish(sahifa=1, sahifa_hajmi=1, db_yoli=yol)
    ozon_holati = t("status_connected", lang) if ozon_sozlanganmi() else t("status_not_configured", lang)
    uzum_holati = t("status_connected", lang) if uzum_sozlanganmi() else t("status_not_configured", lang)

    return t(
        "main_menu_text",
        lang,
        schedule_time=joriy_vaqt,
        timezone=tz_yorliq,
        now_time=hozir,
        uzum_status=uzum_holati,
        ozon_status=ozon_holati,
        catalog_count=katalog_soni,
        sources_count=manbalar_soni,
        zero_storage_rule=html.escape(t("zero_storage_rule", lang)),
    )


def _manbalar_matni(manbalar: list[dict], lang: str = "uz") -> str:
    """📋 Manbalar ekrani uchun xavfsiz HTML ro'yxat matnini tayyorlaydi."""
    if not manbalar:
        return t("sources_empty", lang)

    qatorlar = [t("sources_header", lang)]
    for indeks, m in enumerate(manbalar, start=1):
        domen, konfig = sayt_konfiguratsiyasini_topish(m["url"])
        rejim = t("parser_mode_config", lang) if konfig else t("parser_mode_fallback", lang)
        xavfsiz_url = html.escape(m["url"])
        qatorlar.append(
            f"{indeks}. <code>{xavfsiz_url}</code>\n"
            + t("sources_item_mode", lang, mode=html.escape(rejim), domain=html.escape(domen))
        )
    qatorlar.append(t("sources_footer", lang))
    return "\n".join(qatorlar)


async def _qayta_urinish_bilan(korutin_yaratuvchi, maks_urinish: int = 3, pauza: int = 5):
    """Tarmoq uzilganda 5 soniya kutib jami 3 marta qayta urinadi."""
    for urinish in range(1, maks_urinish + 1):
        try:
            return await korutin_yaratuvchi()
        except (TelegramNetworkError, asyncio.TimeoutError, OSError) as xato:
            if urinish < maks_urinish:
                logger.warning(
                    "Telegram yuborishda tarmoq xatosi (%d/%d): %s. %d soniya kutilmoqda...",
                    urinish,
                    maks_urinish,
                    xato,
                    pauza,
                )
                await asyncio.sleep(pauza)
                continue
            raise


def jadvalni_yangilash(
    vaqt_matni: str,
    db_yoli: str | None = None,
    lang: str | None = None,
    tz_nomi: str | None = None,
) -> None:
    """Tanlangan vaqtni SQLite `settings` jadvaliga saqlaydi va APScheduler'ni yangilaydi."""
    sozlama_saqlash(JADVAL_KALITI, vaqt_matni, db_yoli=faol_db_yoli(db_yoli))
    soat_str, daqiqa_str = vaqt_matni.split(":")
    soat, daqiqa = int(soat_str), int(daqiqa_str)
    tz = vaqt_mintaqasini_olish(lang=lang, tz_nomi=tz_nomi)

    if rejalashtiruvchi is not None:
        rejalashtiruvchi.add_job(
            jadval_boyicha_hisobot,
            trigger=CronTrigger(hour=soat, minute=daqiqa, timezone=tz),
            id=JADVAL_ISH_ID,
            replace_existing=True,
        )
        logger.info("APScheduler kunlik vazifasi o'rnatildi: har kuni %s (%s)", vaqt_matni, tz)


async def qoldiq_ogohlantirish_yuborish(
    bot: Bot,
    chat_id: int | str,
    kam_qoldiqlar: list[dict],
    lang: str = "uz",
) -> bool:
    """Qoldig'i 5 dan kam tovarlar topilsa biznes egasiga alohida ogohlantirish yuboradi."""
    if not kam_qoldiqlar:
        return False

    matn = qoldiq_ogohlantirish_matni(kam_qoldiqlar, lang=lang)
    for bolak in _matnni_bolish(matn):
        await _qayta_urinish_bilan(
            lambda b=bolak: bot.send_message(chat_id=chat_id, text=b, parse_mode="HTML")
        )
    logger.warning("Qoldiqlar nazorati ogohlantirishi yuborildi: %d ta tovar (<5).", len(kam_qoldiqlar))
    return True


def raqobatchi_royxatini_tekshirish_sync(
    raqobatchilar: list[dict],
    db_yoli: str | None = None,
) -> list[dict]:
    """Berilgan raqobatchilar ro'yxatini bitta Chromium sessiyasida tekshirib yangilaydi."""
    if not raqobatchilar:
        return []

    url_royxat = [r["url"] for r in raqobatchilar]
    yigilganlar = kop_manbadan_yigish(manbalar=url_royxat, limit=1)

    natija_xarita: dict[str, dict] = {}
    for item in yigilganlar:
        kalit = urlni_tozalash(str(item.get("url", "")))
        if kalit and kalit not in natija_xarita:
            natija_xarita[kalit] = item

    yangilanganlar: list[dict] = []
    for r in raqobatchilar:
        toza = urlni_tozalash(r["url"])
        topilgan = natija_xarita.get(toza)
        if topilgan is None:
            r_domen = domenni_olish(toza)
            for item in yigilganlar:
                if domenni_olish(str(item.get("url", ""))) == r_domen and toza.split("/")[-1] in str(item.get("url", "")):
                    topilgan = item
                    break

        if topilgan:
            yangi_nom = str(topilgan.get("nomi") or r.get("raqobatchi_nomi") or "")
            yangi_narx = float(topilgan.get("narx") or 0.0)
            yozuv = raqobatchi_narxini_yangilash(
                comp_id=int(r["id"]),
                raqobatchi_nomi=yangi_nom,
                yangi_narx=yangi_narx,
                db_yoli=db_yoli,
            )
            if yozuv:
                yangilanganlar.append(yozuv)

    return yangilanganlar


async def kunlik_raqobatchilarni_tekshirish(
    bot: Bot,
    chat_id: int | str,
    my_product_id: int | None = None,
    db_yoli: str | None = None,
    lang: str | None = None,
) -> list[dict]:
    """
    `competitors` jadvalidagi barcha (yoki bitta tovarga tegishli) raqobatchilarni tekshiradi:
    1. Narx o'zgargan bo'lsa qisqa xabar yuboradi;
    2. Raqobatchi narxi `catalog` dagi narximizdan past bo'lsa, alohida qizil ogohlantirish yuboradi.
    """
    yol = faol_db_yoli(db_yoli)
    til = lang or _foydalanuvchi_tili(chat_id, db_yoli=yol)
    raqobatchilar = raqobatchilarni_olish(my_product_id=my_product_id, db_yoli=yol)
    if not raqobatchilar:
        return []

    logger.info(
        "Raqobatchi narxlarini tekshirish boshlandi (soni=%d, product_id=%s, lang=%s)...",
        len(raqobatchilar),
        my_product_id,
        til,
    )
    yangilanganlar = await asyncio.to_thread(raqobatchi_royxatini_tekshirish_sync, raqobatchilar, yol)

    val = valyuta_yorligi("so'm", til)
    ozgarish_xabarlari: list[str] = []
    arzon_ogohlantirishlar: list[str] = []

    for r in yangilanganlar:
        bizning_tovar = katalog_tovar_product_id_bilan_olish(int(r["my_product_id"]), db_yoli=yol)
        raq_nom = html.escape(str(r.get("raqobatchi_nomi") or domenni_olish(r["url"])))
        havola = html.escape(str(r["url"]))

        if r.get("ozgardimi") and float(r.get("avvalgi_narx") or 0.0) > 0:
            avvalgi = float(r["avvalgi_narx"])
            yangi = float(r["yangi_narx"])
            belgi = "📉" if yangi < avvalgi else "📈"
            ozgarish_xabarlari.append(
                f"{belgi} <b>{raq_nom}</b>: {narxni_formatlash(avvalgi, val)} → "
                f"<b>{narxni_formatlash(yangi, val)}</b> · "
                f"<a href=\"{havola}\">{t('comp_link_word', til)}</a>"
            )

        if bizning_tovar and float(r["yangi_narx"]) > 0 and float(bizning_tovar["narxi"]) > 0:
            if float(r["yangi_narx"]) < float(bizning_tovar["narxi"]):
                arzon_ogohlantirishlar.append(
                    raqobatchi_arzonroq_ogohlantirish_matni(bizning_tovar, r, lang=til)
                )

    if ozgarish_xabarlari:
        matn = t("comp_price_changed_header", til) + "\n".join(ozgarish_xabarlari)
        for bolak in _matnni_bolish(matn):
            await _qayta_urinish_bilan(
                lambda b=bolak: bot.send_message(
                    chat_id=chat_id,
                    text=b,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            )
        logger.info("Raqobatchi narx o'zgarishi xabari yuborildi (%d ta).", len(ozgarish_xabarlari))

    for qizil_xabar in arzon_ogohlantirishlar:
        await _qayta_urinish_bilan(
            lambda m=qizil_xabar: bot.send_message(
                chat_id=chat_id,
                text=m,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        )
    if arzon_ogohlantirishlar:
        logger.warning(
            "Qizil ogohlantirish yuborildi: %d ta raqobatchi bizdan arzonroq sotyapti!",
            len(arzon_ogohlantirishlar),
        )

    return yangilanganlar


async def monitoring_va_yuborish(
    bot: Bot,
    chat_id: int | str,
    manba: str = "qo'lda",
) -> None:
    """
    To'liq MarketPulse siklini tanlangan tilda ishga tushiradi, tahliliy matn + Excel faylni
    yuboradi va Zero-Storage qoidasi bo'yicha Excel faylni `os.remove()` bilan darhol o'chiradi.
    """
    if jarayon_qulfi.locked():
        logger.info("Monitoring allaqachon ishlamoqda, takroriy chaqiruv o'tkazib yuborildi.")
        return

    til = _foydalanuvchi_tili(chat_id)
    tz_nomi = _foydalanuvchi_vaqt_mintaqasi(chat_id, lang=til)
    async with jarayon_qulfi:
        logger.info("Bot orqali monitoring boshlandi (manba=%s, lang=%s, tz=%s)...", manba, til, tz_nomi)
        try:
            muvaffaqiyatli, matn, excel_fayl = await asyncio.to_thread(
                hisobot_tayyorlash,
                20,
                faol_db_yoli(),
                til,
                tz_nomi,
            )

            if not muvaffaqiyatli or not excel_fayl:
                await _qayta_urinish_bilan(
                    lambda: bot.send_message(
                        chat_id=chat_id,
                        text=matn,
                        reply_markup=asosiy_tugmalar(til),
                    )
                )
                logger.warning("0-natija ogohlantirishi Telegram'ga yuborildi.")
                return

            fayl_yoli = Path(excel_fayl)

            for bolak in _matnni_bolish(matn):
                await _qayta_urinish_bilan(
                    lambda b=bolak: bot.send_message(chat_id=chat_id, text=b)
                )

            if not fayl_yoli.exists():
                logger.error("Yaratilgan Excel fayl topilmadi: %s", excel_fayl)
                await bot.send_message(
                    chat_id=chat_id,
                    text=t("excel_not_found", til),
                    reply_markup=asosiy_tugmalar(til),
                )
                return

            hajm_bayt = fayl_yoli.stat().st_size
            if hajm_bayt > MAKS_FAYL_HAJMI_BAYT:
                hajm_mb = hajm_bayt / (1024 * 1024)
                ogohlantirish = t(
                    "file_too_large",
                    til,
                    filename=fayl_yoli.name,
                    size_mb=hajm_mb,
                    limit_mb=MAKS_FAYL_HAJMI_MB,
                )
                logger.warning(ogohlantirish)
                await _qayta_urinish_bilan(
                    lambda: bot.send_message(
                        chat_id=chat_id,
                        text=f"{ogohlantirish}\n\n{t('zero_storage_rule', til)}",
                        reply_markup=asosiy_tugmalar(til),
                    )
                )
                return

            sana_vaqt = hozirgi_vaqt(lang=til, tz_nomi=tz_nomi).strftime("%Y-%m-%d %H:%M")
            izoh = t(
                "excel_caption",
                til,
                filename=fayl_yoli.name,
                timestamp=sana_vaqt,
                timezone=vaqt_mintaqasi_yorligi(tz_nomi, til),
                zero_storage_rule=t("zero_storage_rule", til),
            )

            await _qayta_urinish_bilan(
                lambda: bot.send_document(
                    chat_id=chat_id,
                    document=FSInputFile(path=fayl_yoli, filename=fayl_yoli.name),
                    caption=izoh,
                    reply_markup=asosiy_tugmalar(til),
                )
            )
            logger.info("Excel hisobot bot orqali muvaffaqiyatli yuborildi: %s", fayl_yoli.name)

            try:
                if os.path.exists(excel_fayl):
                    os.remove(excel_fayl)
                    print(f"[Zero-Storage] Hisobot fayli serverdan darhol o'chirildi: {excel_fayl}")
                    logger.info(
                        "Zero-Storage: '%s' fayli os.remove() bilan serverdan darhol o'chirildi.",
                        excel_fayl,
                    )
            except OSError as ochirish_xatosi:
                logger.warning("Zero-Storage o'chirishda xatolik (%s): %s", excel_fayl, ochirish_xatosi)

            await asyncio.to_thread(eski_excel_fayllarni_tozalash, ".", 7)

        except Exception as xato:
            logger.exception("Bot monitoring jarayonida xatolik: %s", xato)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=t("generic_error", til),
                    parse_mode="HTML",
                    reply_markup=asosiy_tugmalar(til),
                )
            except Exception:
                pass


async def jadval_boyicha_hisobot() -> None:
    """APScheduler tomonidan har kuni belgilangan vaqtda ishga tushiriladigan vazifa."""
    if bot_obyekti is None or not ruxsat_etilgan_chat_id:
        return
    til = _foydalanuvchi_tili(ruxsat_etilgan_chat_id)
    logger.info("APScheduler kunlik avtomatik hisobotni ishga tushirdi (lang=%s).", til)
    await monitoring_va_yuborish(
        bot=bot_obyekti,
        chat_id=ruxsat_etilgan_chat_id,
        manba="avtomatik_jadval",
    )
    # 📉 Qoldiqlar nazorati (Stock Alert)
    kam_qoldiqlar = await asyncio.to_thread(kam_qoldiq_tovarlar, 5, faol_db_yoli())
    if kam_qoldiqlar:
        await qoldiq_ogohlantirish_yuborish(bot_obyekti, ruxsat_etilgan_chat_id, kam_qoldiqlar, lang=til)

    # 👀 Kunlik raqobatchilar tekshiruvi va qizil signal
    await kunlik_raqobatchilarni_tekshirish(bot_obyekti, ruxsat_etilgan_chat_id, lang=til)


# ==============================================================================
# HANDLERLAR
# ==============================================================================

@router.message(CommandStart())
async def start_buyrugi(message: Message, state: FSMContext) -> None:
    """
    /start buyrug'i:
    - Admin (.env dagi TELEGRAM_CHAT_ID) -> real do'kon boshqaruv paneli;
    - Boshqa istalgan foydalanuvchi -> xavfsiz 🎭 Demo-rejim (Zero-Leak).
    """
    await state.clear()
    chat_id = message.chat.id

    if adminmi(chat_id):
        if not til_tanlanganmi(chat_id):
            await message.answer(
                t("choose_language_prompt", "uz"),
                parse_mode="HTML",
                reply_markup=til_tanlash_tugmalari("uz"),
            )
            return

        til = _foydalanuvchi_tili(chat_id)
        await message.answer(
            _bosh_menyu_matni(til, chat_id=chat_id),
            parse_mode="HTML",
            reply_markup=asosiy_tugmalar(til),
        )
        return

    # Begona foydalanuvchi (portfolio mijozi) -> Demo-rejim
    logger.info("Demo-rejim /start ochildi: chat_id=%s", chat_id)
    if str(chat_id) not in _DEMO_FOYDALANUVCHI_TILLARI:
        await message.answer(
            f"{t('demo_banner', 'uz')}\n\n{t('choose_language_prompt', 'uz')}",
            parse_mode="HTML",
            reply_markup=til_tanlash_tugmalari("uz"),
        )
        return

    til = _foydalanuvchi_tili(chat_id)
    await message.answer(
        _demo_bosh_menyu_matni(til),
        parse_mode="HTML",
        reply_markup=demo_asosiy_tugmalar(til),
    )


@router.callback_query(F.data == "til_tanlash")
async def til_tanlash_menyusi(callback: CallbackQuery, state: FSMContext) -> None:
    """🌐 Til / Язык tugmasi: Admin ham, Demo foydalanuvchi ham tilni almashtira oladi."""
    if callback.message is None:
        return

    await state.clear()
    til = _foydalanuvchi_tili(callback.message.chat.id)
    await callback.answer()
    await callback.message.answer(
        t("choose_language_prompt", til),
        parse_mode="HTML",
        reply_markup=til_tanlash_tugmalari(til),
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def tilni_saqlash_tugmasi(callback: CallbackQuery, state: FSMContext) -> None:
    """🇺🇿 O'zbekcha / 🇷🇺 Русский tugmasi: Admin uchun DB+jadval, Demo uchun faqat RAM."""
    if callback.message is None:
        return

    await state.clear()
    chat_id = callback.message.chat.id
    tanlangan = (callback.data or "set_lang:uz").split("set_lang:", 1)[-1]

    if adminmi(chat_id):
        yangi_til = set_language(chat_id, tanlangan)
        yangi_tz = _foydalanuvchi_vaqt_mintaqasi(chat_id, lang=yangi_til)
        joriy_vaqt = sozlama_olish(JADVAL_KALITI, STANDART_VAQT) or STANDART_VAQT
        jadvalni_yangilash(joriy_vaqt, lang=yangi_til, tz_nomi=yangi_tz)
        menyu_matn, tugmalar = _bosh_menyu_matni(yangi_til, chat_id=chat_id), asosiy_tugmalar(yangi_til)
    else:
        yangi_til = _demo_tilni_saqlash(chat_id, tanlangan)
        menyu_matn, tugmalar = _demo_bosh_menyu_matni(yangi_til), demo_asosiy_tugmalar(yangi_til)

    await callback.answer()
    await callback.message.answer(
        f"{t('language_saved', yangi_til)}\n\n{menyu_matn}",
        parse_mode="HTML",
        reply_markup=tugmalar,
    )


@router.callback_query(F.data == "bekor_qilish")
async def amalni_bekor_qilish(callback: CallbackQuery, state: FSMContext) -> None:
    """Har qanday FSM kiritish holatini bekor qilib tegishli menyuga qaytaradi."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    await callback.answer(t("action_cancelled_toast", til))
    menyu_matn, tugmalar = _menyu_matni_va_tugmalar(chat_id, til)
    await callback.message.answer(
        f"{t('action_cancelled', til)}\n\n{menyu_matn}",
        parse_mode="HTML",
        reply_markup=tugmalar,
    )


@router.callback_query(F.data == "bosh_menyu")
async def bosh_menyuga_qaytish(callback: CallbackQuery, state: FSMContext) -> None:
    """Asosiy menyuga qaytish (Admin -> real panel, Demo -> demo panel)."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    await callback.answer()
    menyu_matn, tugmalar = _menyu_matni_va_tugmalar(chat_id, til)
    await callback.message.answer(
        menyu_matn,
        parse_mode="HTML",
        reply_markup=tugmalar,
    )


@router.callback_query(F.data == "demo_qoldiqlar")
async def demo_qoldiqlar_nazorati(callback: CallbackQuery, state: FSMContext) -> None:
    """📉 Demo-rejimda kam qoldiqli (<5) namunaviy tovarlar ogohlantirishini ko'rsatadi."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    await callback.answer()

    kam_qoldiqlar = demo_kam_qoldiq_tovarlar(chegara=5, lang=til)
    ogohlantirish = qoldiq_ogohlantirish_matni(kam_qoldiqlar, lang=til)
    tugmalar = asosiy_tugmalar(til) if adminmi(chat_id) else demo_asosiy_tugmalar(til)
    await callback.message.answer(
        f"{t('demo_banner', til)}\n\n{ogohlantirish}",
        parse_mode="HTML",
        reply_markup=tugmalar,
    )


@router.callback_query(F.data.startswith("mening_katalogim:"))
async def mening_katalogim_sahifasi(callback: CallbackQuery, state: FSMContext) -> None:
    """📦 Mening katalogim: Admin -> real DB, Demo -> demo_data.py (Zero-Leak)."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    is_demo = not adminmi(chat_id)
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    sahifa_str = (callback.data or "mening_katalogim:1").split("mening_katalogim:", 1)[-1]
    sahifa = int(sahifa_str) if sahifa_str.isdigit() else 1

    if is_demo:
        tovarlar, jami_soni, jami_sahifalar = demo_katalog_sahifa_olish(
            sahifa=sahifa, sahifa_hajmi=5, lang=til
        )
        kam_soni = len(demo_kam_qoldiq_tovarlar(chegara=5, lang=til))
    else:
        tovarlar, jami_soni, jami_sahifalar = katalog_sahifa_olish(sahifa=sahifa, sahifa_hajmi=5)
        kam_soni = len(kam_qoldiq_tovarlar(chegara=5))

    joriy_sahifa = max(1, min(sahifa, jami_sahifalar))
    await callback.answer()

    if jami_soni == 0:
        await callback.message.answer(
            t("catalog_empty", til),
            parse_mode="HTML",
            reply_markup=mening_katalogim_tugmalari([], 1, 1, lang=til, demo_rejim=is_demo),
        )
        return

    sarlavha = t(
        "catalog_header",
        til,
        total=jami_soni,
        page=joriy_sahifa,
        total_pages=jami_sahifalar,
        low_stock=kam_soni,
    )
    if is_demo:
        sarlavha = f"{t('demo_banner', til)}\n\n{sarlavha}"

    await callback.message.answer(
        sarlavha,
        parse_mode="HTML",
        reply_markup=mening_katalogim_tugmalari(
            tovarlar, joriy_sahifa, jami_sahifalar, lang=til, demo_rejim=is_demo
        ),
    )


@router.callback_query(F.data.in_({"sahifa_boshi", "sahifa_oxiri", "sahifa_holat"}))
async def sahifa_chegara_tugmasi(callback: CallbackQuery) -> None:
    """Sahifa chegarasidagi tugmalar uchun qisqa bildirishnoma."""
    til = _foydalanuvchi_tili(callback.message.chat.id) if callback.message else "uz"
    if callback.data == "sahifa_boshi":
        await callback.answer(t("first_page_toast", til))
    elif callback.data == "sahifa_oxiri":
        await callback.answer(t("last_page_toast", til))
    else:
        await callback.answer()


@router.callback_query(F.data == "katalog_yangilash")
async def katalogni_yangilash_tugmasi(callback: CallbackQuery, state: FSMContext) -> None:
    """🔄 Katalogni yangilash: FAQAT Admin uchun (Uzum API). Demo-rejimda bloklanadi."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    await callback.answer(t("catalog_refreshing_toast", til))
    holat = await callback.message.answer(t("catalog_refreshing_msg", til))

    try:
        soni, kam_qoldiqlar = await asyncio.to_thread(katalogni_uzumdan_yangilash, faol_db_yoli())
        tovarlar, _, jami_sahifalar = katalog_sahifa_olish(sahifa=1, sahifa_hajmi=5)

        if soni == 0:
            await callback.message.answer(
                t("catalog_refresh_failed", til),
                parse_mode="HTML",
                reply_markup=asosiy_tugmalar(til),
            )
            return

        await callback.message.answer(
            t("catalog_refreshed", til, count=soni, total_pages=jami_sahifalar),
            parse_mode="HTML",
            reply_markup=mening_katalogim_tugmalari(tovarlar, 1, jami_sahifalar, lang=til),
        )

        if kam_qoldiqlar and callback.bot is not None:
            await qoldiq_ogohlantirish_yuborish(
                callback.bot,
                callback.message.chat.id,
                kam_qoldiqlar,
                lang=til,
            )
    finally:
        try:
            await holat.delete()
        except Exception:
            pass


@router.callback_query(F.data.startswith("kat_tovar:"))
async def katalog_tovar_tafsiloti(callback: CallbackQuery, state: FSMContext) -> None:
    """Katalogdan tanlangan tovar tafsilotlari (Admin -> real DB, Demo -> demo_data.py)."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    is_demo = not adminmi(chat_id)
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = demo_katalog_tovar_olish(katalog_id, lang=til) if is_demo else katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    await callback.answer()
    sku_matn = html.escape(str(tovar.get("sku") or "—"))
    qoldiq = int(tovar.get("qoldiq") or 0)
    qoldiq_belgi = "✅" if qoldiq >= 5 else "⚠️"
    kom_foiz = float(tovar.get("komissiya_foizi") or 0.0)
    logistika = float(tovar.get("logistika_tolovi") or 0.0)
    val = valyuta_yorligi("so'm", til)

    qatorlar = [
        f"📦 <b>{html.escape(str(tovar['nomi']))}</b>",
        "━━━━━━━━━━━━━━━━━━",
        t("product_card_sku", til, sku=sku_matn),
        t("product_card_price", til, price=narxni_formatlash(float(tovar["narxi"]), val)),
        t("product_card_stock", til, icon=qoldiq_belgi, stock=qoldiq),
        t("product_card_commission", til, commission=kom_foiz),
    ]
    if logistika > 0:
        qatorlar.append(
            t("product_card_logistics", til, logistics=narxni_formatlash(logistika, val))
        )

    await callback.message.answer(
        "\n".join(qatorlar),
        parse_mode="HTML",
        reply_markup=katalog_tovar_tugmalari(katalog_id, sahifa, lang=til),
    )


@router.callback_query(F.data.startswith("kalkulyator:"))
async def aqlli_kalkulyator_ochish(callback: CallbackQuery, state: FSMContext) -> None:
    """🧮 Aqlli kalkulyator tugmasi: Admin ham, Demo foydalanuvchi ham bemalol sinay oladi."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    is_demo = not adminmi(chat_id)
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = demo_katalog_tovar_olish(katalog_id, lang=til) if is_demo else katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        kalkulyator_hisob_matni(tovar, lang=til),
        parse_mode="HTML",
        reply_markup=kalkulyator_tugmalari(katalog_id, sahifa, lang=til),
    )


@router.callback_query(F.data.startswith("kalk_sinash:"))
async def kalkulyator_narx_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    """✏️ Boshqa narxda sinash tugmasi (Admin va Demo uchun to'liq ishlaydi)."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    is_demo = not adminmi(chat_id)
    til = _foydalanuvchi_tili(chat_id)
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = demo_katalog_tovar_olish(katalog_id, lang=til) if is_demo else katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    await state.set_state(KalkulyatorNarxHolati.narx_kutilmoqda)
    await state.update_data(katalog_id=katalog_id, sahifa=sahifa)
    await callback.answer()
    await callback.message.answer(
        t("ask_calc_price", til, name=html.escape(str(tovar["nomi"]))),
        parse_mode="HTML",
        reply_markup=bekor_qilish_tugmasi(til),
    )


@router.message(KalkulyatorNarxHolati.narx_kutilmoqda)
async def kalkulyator_qayta_hisoblash(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi kiritgan sinov narxida qo'lga qoladigan summani darhol hisoblab beradi."""
    chat_id = message.chat.id
    is_demo = not adminmi(chat_id)
    til = _foydalanuvchi_tili(chat_id)
    sinov_narxi = narxni_tozalash(message.text or "")
    if sinov_narxi <= 0:
        await message.answer(
            t("invalid_calc_price", til),
            parse_mode="HTML",
            reply_markup=bekor_qilish_tugmasi(til),
        )
        return

    malumot = await state.get_data()
    katalog_id = int(malumot.get("katalog_id", 0))
    sahifa = int(malumot.get("sahifa", 1))
    tovar = demo_katalog_tovar_olish(katalog_id, lang=til) if is_demo else katalog_tovar_olish(katalog_id)
    await state.clear()

    if not tovar:
        tugmalar = demo_asosiy_tugmalar(til) if is_demo else asosiy_tugmalar(til)
        await message.answer(t("product_not_found", til), reply_markup=tugmalar)
        return

    await message.answer(
        kalkulyator_hisob_matni(tovar, sinov_narxi=sinov_narxi, lang=til),
        parse_mode="HTML",
        reply_markup=kalkulyator_tugmalari(katalog_id, sahifa, lang=til),
    )


@router.callback_query(F.data.startswith("kat_raqobatchi:"))
async def katalog_raqobatchilar_tugmasi(callback: CallbackQuery, state: FSMContext) -> None:
    """👀 Raqobatchilar tugmasi: Admin -> real DB, Demo -> demo_data.py (faqat o'qish)."""
    if callback.message is None:
        return

    chat_id = callback.message.chat.id
    is_demo = not adminmi(chat_id)
    til = _foydalanuvchi_tili(chat_id)
    await state.clear()
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = demo_katalog_tovar_olish(katalog_id, lang=til) if is_demo else katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    await callback.answer()
    if is_demo:
        raqobatchilar = demo_raqobatchilarni_olish(int(tovar["product_id"]), lang=til)
        matn = f"{t('demo_banner', til)}\n\n{raqobatchilar_royxat_matni(tovar, raqobatchilar, lang=til)}"
    else:
        raqobatchilar = raqobatchilarni_olish(my_product_id=int(tovar["product_id"]))
        matn = raqobatchilar_royxat_matni(tovar, raqobatchilar, lang=til)

    await callback.message.answer(
        matn,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=raqobatchilar_menyu_tugmalari(katalog_id, sahifa, lang=til, demo_rejim=is_demo),
    )


@router.callback_query(F.data.startswith("raq_qoshish:"))
async def raqobatchi_havola_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    """➕ Raqobatchi havolasini qo'shish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    await state.set_state(RaqobatchiQoshishHolati.url_kutilmoqda)
    await state.update_data(
        katalog_id=katalog_id,
        product_id=int(tovar["product_id"]),
        sahifa=sahifa,
    )
    await callback.answer()
    await callback.message.answer(
        t("comp_ask_url", til, name=html.escape(str(tovar["nomi"]))),
        parse_mode="HTML",
        reply_markup=bekor_qilish_tugmasi(til),
    )


@router.message(RaqobatchiQoshishHolati.url_kutilmoqda)
async def raqobatchi_havolasini_saqlash_va_tekshirish(message: Message, state: FSMContext) -> None:
    """Yuborilgan raqobatchi URL'ini saqlaydi va darhol narxini tekshirib ko'rsatadi (FAQAT Admin)."""
    if not adminmi(message.chat.id):
        await state.clear()
        til = _foydalanuvchi_tili(message.chat.id)
        await message.answer(t("demo_readonly_alert", til), reply_markup=demo_asosiy_tugmalar(til))
        return

    til = _foydalanuvchi_tili(message.chat.id)
    tekshirilgan_url = urlni_tekshirish(message.text or "")
    if not tekshirilgan_url:
        await message.answer(
            t("invalid_url", til),
            parse_mode="HTML",
            reply_markup=bekor_qilish_tugmasi(til),
        )
        return

    malumot = await state.get_data()
    katalog_id = int(malumot.get("katalog_id", 0))
    product_id = int(malumot.get("product_id", 0))
    sahifa = int(malumot.get("sahifa", 1))
    await state.clear()

    tovar = katalog_tovar_olish(katalog_id)
    if not tovar:
        await message.answer(t("product_not_found", til), reply_markup=asosiy_tugmalar(til))
        return

    qoshildi, yozuv = raqobatchi_qoshish(my_product_id=product_id, url=tekshirilgan_url)
    if not qoshildi:
        raqobatchilar = raqobatchilarni_olish(my_product_id=product_id)
        await message.answer(
            t("comp_exists", til, url=html.escape(yozuv["url"]))
            + raqobatchilar_royxat_matni(tovar, raqobatchilar, lang=til),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=raqobatchilar_menyu_tugmalari(katalog_id, sahifa, lang=til),
        )
        return

    holat = await message.answer(t("comp_checking_new", til))
    try:
        yigilgan = await asyncio.to_thread(mahsulotlarni_yigish, yozuv["url"], 1)
        yangilangan = None
        if yigilgan:
            yangilangan = raqobatchi_narxini_yangilash(
                comp_id=int(yozuv["id"]),
                raqobatchi_nomi=str(yigilgan[0].get("nomi") or ""),
                yangi_narx=float(yigilgan[0].get("narx") or 0.0),
            )

        raqobatchilar = raqobatchilarni_olish(my_product_id=product_id)
        await message.answer(
            t("comp_added_checked", til)
            + raqobatchilar_royxat_matni(tovar, raqobatchilar, lang=til),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=raqobatchilar_menyu_tugmalari(katalog_id, sahifa, lang=til),
        )

        if (
            yangilangan
            and float(yangilangan["yangi_narx"]) > 0
            and float(tovar["narxi"]) > 0
            and float(yangilangan["yangi_narx"]) < float(tovar["narxi"])
        ):
            await message.answer(
                raqobatchi_arzonroq_ogohlantirish_matni(tovar, yangilangan, lang=til),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    finally:
        try:
            await holat.delete()
        except Exception:
            pass


@router.callback_query(F.data.startswith("raq_tekshir:"))
async def raqobatchilar_narxini_hozir_tekshirish(callback: CallbackQuery, state: FSMContext) -> None:
    """🔄 Narxlarni hozir tekshirish (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    raqobatchilar = raqobatchilarni_olish(my_product_id=int(tovar["product_id"]))
    if not raqobatchilar:
        await callback.answer(t("comp_need_at_least_one", til), show_alert=True)
        return

    await callback.answer(t("comp_checking_toast", til))
    holat = await callback.message.answer(t("comp_checking_many", til, count=len(raqobatchilar)))
    try:
        if callback.bot is not None:
            await kunlik_raqobatchilarni_tekshirish(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                my_product_id=int(tovar["product_id"]),
                lang=til,
            )
        yangilangan_royxat = raqobatchilarni_olish(my_product_id=int(tovar["product_id"]))
        await callback.message.answer(
            t("comp_refreshed", til)
            + raqobatchilar_royxat_matni(tovar, yangilangan_royxat, lang=til),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=raqobatchilar_menyu_tugmalari(katalog_id, sahifa, lang=til),
        )
    finally:
        try:
            await holat.delete()
        except Exception:
            pass


@router.callback_query(F.data.startswith("raq_ochir_menyu:"))
async def raqobatchi_ochirish_menyusi(callback: CallbackQuery, state: FSMContext) -> None:
    """🗑 Raqobatchini o'chirish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 2 or not qismlar[1].isdigit():
        await callback.answer(t("invalid_product_id", til), show_alert=True)
        return

    katalog_id = int(qismlar[1])
    sahifa = int(qismlar[2]) if len(qismlar) >= 3 and qismlar[2].isdigit() else 1
    tovar = katalog_tovar_olish(katalog_id)
    if not tovar:
        await callback.answer(t("product_not_found", til), show_alert=True)
        return

    raqobatchilar = raqobatchilarni_olish(my_product_id=int(tovar["product_id"]))
    if not raqobatchilar:
        await callback.answer(t("comp_none_to_delete", til), show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        t("comp_choose_delete", til, name=html.escape(str(tovar["nomi"]))),
        parse_mode="HTML",
        reply_markup=raqobatchi_ochirish_tugmalari(raqobatchilar, katalog_id, sahifa, lang=til),
    )


@router.callback_query(F.data.startswith("raq_ochir:"))
async def raqobatchini_bazadan_ochirish(callback: CallbackQuery, state: FSMContext) -> None:
    """Tanlangan raqobatchini `competitors` jadvalidan o'chiradi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    qismlar = (callback.data or "").split(":")
    if len(qismlar) < 4 or not all(q.isdigit() for q in qismlar[1:4]):
        await callback.answer(t("comp_invalid_data", til), show_alert=True)
        return

    comp_id, katalog_id, sahifa = int(qismlar[1]), int(qismlar[2]), int(qismlar[3])
    ochirilgan = raqobatchi_ochirish(comp_id)
    tovar = katalog_tovar_olish(katalog_id)

    if not ochirilgan:
        await callback.answer(t("comp_already_deleted", til), show_alert=True)
        return

    await callback.answer(t("comp_deleted_toast", til))
    if tovar:
        qolganlar = raqobatchilarni_olish(my_product_id=int(tovar["product_id"]))
        await callback.message.answer(
            t("comp_deleted_msg", til, url=html.escape(str(ochirilgan["url"])))
            + raqobatchilar_royxat_matni(tovar, qolganlar, lang=til),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=raqobatchilar_menyu_tugmalari(katalog_id, sahifa, lang=til),
        )


@router.callback_query(F.data == "qayta_tekshirish")
async def hozir_qayta_tekshirish(callback: CallbackQuery, state: FSMContext) -> None:
    """🔄 Hozir qayta tekshirish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()

    if jarayon_qulfi.locked():
        await callback.answer(t("scan_in_progress_alert", til), show_alert=True)
        return

    await callback.answer(t("scan_started_toast", til))
    holat_xabari = await callback.message.answer(t("scan_started_msg", til))

    try:
        if callback.bot is not None:
            await monitoring_va_yuborish(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                manba="tugma",
            )
    finally:
        try:
            await holat_xabari.delete()
        except Exception:
            pass


@router.callback_query(F.data == "vaqt_ornatish")
async def vaqtni_ornatish_menyusi(callback: CallbackQuery, state: FSMContext) -> None:
    """⏰ Vaqtni o'rnatish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    tz_nomi = _foydalanuvchi_vaqt_mintaqasi(callback.message.chat.id, lang=til)
    await state.clear()
    await callback.answer()
    joriy_vaqt = html.escape(sozlama_olish(JADVAL_KALITI, STANDART_VAQT) or STANDART_VAQT)
    tz_yorliq = html.escape(vaqt_mintaqasi_yorligi(tz_nomi, til))
    hozir = html.escape(hozirgi_vaqt(lang=til, tz_nomi=tz_nomi).strftime("%H:%M"))
    await callback.message.answer(
        t(
            "choose_time_prompt",
            til,
            current_time=joriy_vaqt,
            timezone=tz_yorliq,
            now_time=hozir,
        ),
        parse_mode="HTML",
        reply_markup=vaqt_tanlash_tugmalari(til, faol_tz=tz_nomi),
    )


@router.callback_query(F.data.startswith("set_tz:"))
async def vaqt_mintaqasini_saqlash(callback: CallbackQuery, state: FSMContext) -> None:
    """🇺🇿 Toshkent / 🇷🇺 Moskva vaqt mintaqasi tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    tanlangan_tz = (callback.data or f"set_tz:{STANDART_TIMEZONE}").split("set_tz:", 1)[-1]
    yangi_tz = set_timezone(callback.message.chat.id, tanlangan_tz)
    joriy_vaqt = sozlama_olish(JADVAL_KALITI, STANDART_VAQT) or STANDART_VAQT
    jadvalni_yangilash(joriy_vaqt, lang=til, tz_nomi=yangi_tz)

    tz_yorliq = vaqt_mintaqasi_yorligi(yangi_tz, til)
    hozir = hozirgi_vaqt(lang=til, tz_nomi=yangi_tz).strftime("%H:%M")
    await callback.answer(t("tz_saved_toast", til, timezone=tz_yorliq))
    await callback.message.answer(
        t(
            "tz_saved_msg",
            til,
            timezone=html.escape(tz_yorliq),
            now_time=html.escape(hozir),
            schedule_time=html.escape(joriy_vaqt),
        ),
        parse_mode="HTML",
        reply_markup=vaqt_tanlash_tugmalari(til, faol_tz=yangi_tz),
    )


@router.callback_query(F.data.startswith("vaqt:"))
async def tayyor_vaqtni_saqlash(callback: CallbackQuery, state: FSMContext) -> None:
    """Tayyor tugmalardan (08:00..21:00) birini saqlaydi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    tz_nomi = _foydalanuvchi_vaqt_mintaqasi(callback.message.chat.id, lang=til)
    await state.clear()
    tanlangan = (callback.data or "").split("vaqt:", 1)[-1]
    toza_vaqt = vaqt_formatini_tekshirish(tanlangan)

    if not toza_vaqt:
        await callback.answer(t("invalid_time_toast", til), show_alert=True)
        return

    jadvalni_yangilash(toza_vaqt, lang=til, tz_nomi=tz_nomi)
    await callback.answer(t("time_saved_toast", til, time=toza_vaqt))
    await callback.message.answer(
        t(
            "time_saved_msg",
            til,
            time=html.escape(toza_vaqt),
            timezone=html.escape(vaqt_mintaqasi_yorligi(tz_nomi, til)),
        ),
        parse_mode="HTML",
        reply_markup=asosiy_tugmalar(til),
    )


@router.callback_query(F.data == "boshqa_vaqt")
async def boshqa_vaqt_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    """✍️ Boshqa vaqt yozish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.set_state(VaqtKiritishHolati.vaqt_kutilmoqda)
    await callback.answer()
    await callback.message.answer(
        t("ask_custom_time", til),
        parse_mode="HTML",
        reply_markup=bekor_qilish_tugmasi(til),
    )


@router.message(VaqtKiritishHolati.vaqt_kutilmoqda)
async def qolda_kiritilgan_vaqtni_saqlash(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi qo'lda yozgan vaqtni tekshirib, bazaga va jadvalga saqlaydi (FAQAT Admin)."""
    if not adminmi(message.chat.id):
        await state.clear()
        til = _foydalanuvchi_tili(message.chat.id)
        await message.answer(t("demo_readonly_alert", til), reply_markup=demo_asosiy_tugmalar(til))
        return

    til = _foydalanuvchi_tili(message.chat.id)
    tz_nomi = _foydalanuvchi_vaqt_mintaqasi(message.chat.id, lang=til)
    toza_vaqt = vaqt_formatini_tekshirish(message.text or "")
    if not toza_vaqt:
        await message.answer(
            t("invalid_custom_time", til),
            parse_mode="HTML",
            reply_markup=bekor_qilish_tugmasi(til),
        )
        return

    jadvalni_yangilash(toza_vaqt, lang=til, tz_nomi=tz_nomi)
    await state.clear()
    await message.answer(
        t(
            "time_saved_msg",
            til,
            time=html.escape(toza_vaqt),
            timezone=html.escape(vaqt_mintaqasi_yorligi(tz_nomi, til)),
        ),
        parse_mode="HTML",
        reply_markup=asosiy_tugmalar(til),
    )


@router.callback_query(F.data == "manba_qoshish")
async def manba_qoshish_sorash(callback: CallbackQuery, state: FSMContext) -> None:
    """➕ Sayt/Mahsulot qo'shish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.set_state(ManbaQoshishHolati.url_kutilmoqda)
    await callback.answer()
    await callback.message.answer(
        t("ask_source_url", til),
        parse_mode="HTML",
        reply_markup=bekor_qilish_tugmasi(til),
    )


@router.message(ManbaQoshishHolati.url_kutilmoqda)
async def manba_urlni_saqlash(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi yuborgan yangi sayt/mahsulot havolasini bazaga saqlaydi (FAQAT Admin)."""
    if not adminmi(message.chat.id):
        await state.clear()
        til = _foydalanuvchi_tili(message.chat.id)
        await message.answer(t("demo_readonly_alert", til), reply_markup=demo_asosiy_tugmalar(til))
        return

    til = _foydalanuvchi_tili(message.chat.id)
    tekshirilgan_url = urlni_tekshirish(message.text or "")
    if not tekshirilgan_url:
        await message.answer(
            t("invalid_url", til),
            parse_mode="HTML",
            reply_markup=bekor_qilish_tugmasi(til),
        )
        return

    yangi_qoshildi, toza_url = manba_qoshish(tekshirilgan_url)
    domen, konfig = sayt_konfiguratsiyasini_topish(toza_url)
    rejim = t("parser_mode_config", til) if konfig else t("parser_mode_fallback", til)
    jami_manbalar = len(barcha_manbalarni_olish())

    await state.clear()
    if yangi_qoshildi:
        await message.answer(
            t(
                "source_added",
                til,
                url=html.escape(toza_url),
                mode=html.escape(rejim),
                domain=html.escape(domen),
                count=jami_manbalar,
            ),
            parse_mode="HTML",
            reply_markup=asosiy_tugmalar(til),
        )
    else:
        await message.answer(
            t("source_exists", til, url=html.escape(toza_url), count=jami_manbalar),
            parse_mode="HTML",
            reply_markup=asosiy_tugmalar(til),
        )


@router.callback_query(F.data == "manbalar_royxati")
async def manbalarni_korsatish(callback: CallbackQuery, state: FSMContext) -> None:
    """📋 Manbalar tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    await callback.answer()
    manbalar = manbalar_royxati()
    await callback.message.answer(
        _manbalar_matni(manbalar, lang=til),
        parse_mode="HTML",
        reply_markup=manbalar_tugmalari(manbalar, lang=til),
    )


@router.callback_query(F.data.startswith("manba_ochir:"))
async def manbani_ochirish_tugmasi(callback: CallbackQuery, state: FSMContext) -> None:
    """🗑 O'chirish tugmasi (FAQAT Admin)."""
    if callback.message is None:
        return
    if not adminmi(callback.message.chat.id):
        til = _foydalanuvchi_tili(callback.message.chat.id)
        await callback.answer(t("demo_readonly_alert", til), show_alert=True)
        return

    til = _foydalanuvchi_tili(callback.message.chat.id)
    await state.clear()
    id_matn = (callback.data or "").split("manba_ochir:", 1)[-1]
    if not id_matn.isdigit():
        await callback.answer(t("invalid_source_id", til), show_alert=True)
        return

    ochirilgan_url = manba_ochirish(int(id_matn))
    manbalar = manbalar_royxati()
    if ochirilgan_url:
        await callback.answer(t("source_deleted_toast", til))
        await callback.message.answer(
            t("source_deleted_msg", til, url=html.escape(ochirilgan_url))
            + _manbalar_matni(manbalar, lang=til),
            parse_mode="HTML",
            reply_markup=manbalar_tugmalari(manbalar, lang=til),
        )
    else:
        await callback.answer(t("source_already_deleted", til), show_alert=True)


@router.message()
async def boshqa_xabarlar(message: Message) -> None:
    """Admin uchun real menyuni, begona foydalanuvchi uchun Demo-rejim menyusini ko'rsatadi."""
    chat_id = message.chat.id
    til = _foydalanuvchi_tili(chat_id)
    if adminmi(chat_id):
        await message.answer(
            t("unknown_message_hint", til),
            reply_markup=asosiy_tugmalar(til),
        )
        return

    await message.answer(
        f"{t('demo_banner', til)}\n\n{t('unknown_message_hint', til)}",
        parse_mode="HTML",
        reply_markup=demo_asosiy_tugmalar(til),
    )


async def botni_ishga_tushirish() -> None:
    """Telegram botni va APScheduler dinamik jadvalini ishga tushiradi."""
    global rejalashtiruvchi, ruxsat_etilgan_chat_id, bot_obyekti

    load_dotenv(override=True)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    ruxsat_etilgan_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    proksi_url = os.getenv("TELEGRAM_PROXY", "").strip()

    if not bot_token or not ruxsat_etilgan_chat_id:
        xabar = (
            "❌ XATOLIK: .env faylida TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_ID "
            "to'ldirilmagan. Bot ishga tushirilmadi."
        )
        print(xabar)
        logger.error("Bot ishga tushmadi: .env da TELEGRAM_BOT_TOKEN yoki TELEGRAM_CHAT_ID bo'sh.")
        sys.exit(1)

    yol = faol_db_yoli()
    bazani_tayyorlash(yol)
    saqlangan_vaqt = sozlama_olish(JADVAL_KALITI, STANDART_VAQT, db_yoli=yol)
    if not saqlangan_vaqt or not vaqt_formatini_tekshirish(saqlangan_vaqt):
        saqlangan_vaqt = STANDART_VAQT
        sozlama_saqlash(JADVAL_KALITI, saqlangan_vaqt, db_yoli=yol)

    if proksi_url:
        sessiya = AiohttpSession(proxy=proksi_url, timeout=45)
    else:
        sessiya = AiohttpSession(timeout=35)
        # IPv6 uzilishlarida Telegram polling qotib qolmasligi uchun majburiy IPv4
        sessiya._connector_init["family"] = socket.AF_INET
        sessiya._connector_init["keepalive_timeout"] = 15

    # aiogram xato va ogohlantirishlarini ham logs/marketpulse.log ga ulaymiz
    asosiy_log = loggerni_olish("marketpulse")
    for aiogram_nom in ("aiogram.dispatcher", "aiogram.event"):
        aiogram_log = logging.getLogger(aiogram_nom)
        aiogram_log.setLevel(logging.WARNING)
        for h in asosiy_log.handlers:
            if h not in aiogram_log.handlers:
                aiogram_log.addHandler(h)

    bot_obyekti = Bot(token=bot_token, session=sessiya)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    egasi_tili = get_language(ruxsat_etilgan_chat_id, db_yoli=yol)
    egasi_tz = get_timezone(ruxsat_etilgan_chat_id, lang=egasi_tili, db_yoli=yol)

    rejalashtiruvchi = AsyncIOScheduler(timezone=vaqt_mintaqasini_olish(lang=egasi_tili, tz_nomi=egasi_tz))
    jadvalni_yangilash(saqlangan_vaqt, db_yoli=yol, lang=egasi_tili, tz_nomi=egasi_tz)
    rejalashtiruvchi.start()

    try:
        bot_malumot = await bot_obyekti.get_me()
        await bot_obyekti.delete_webhook(drop_pending_updates=False)
        bot_username = f"@{bot_malumot.username}" if bot_malumot.username else str(bot_malumot.id)
    except Exception as ulanish_xato:
        logger.error("Telegram API ga ulanib bo'lmadi: %s", ulanish_xato)
        raise

    print("============================================================")
    print(f"🤖 MarketPulse Core Telegram Boti ishga tushdi! ({bot_username})")
    print(f"⏰ Kunlik jadval: har kuni {saqlangan_vaqt} ({egasi_tz} | til={egasi_tili})")
    print(f"💾 Ma'lumotlar bazasi: {yol}")
    print("🌐 Tarmoq: IPv4 majburiy (polling_timeout=15s)")
    print("🔒 Ruxsat: Admin (.env TELEGRAM_CHAT_ID) -> real do'kon | Boshqalar -> 🎭 Demo-rejim (Zero-Leak)")
    print("🛑 To'xtatish uchun Ctrl+C bosing")
    print("============================================================")
    logger.info(
        "=== MarketPulse Core boti ishga tushdi (%s, jadval=%s, TIMEZONE=%s, LANG=%s, DB=%s) ===",
        bot_username,
        saqlangan_vaqt,
        egasi_tz,
        egasi_tili,
        yol,
    )

    try:
        await dp.start_polling(
            bot_obyekti,
            polling_timeout=15,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except TelegramConflictError:
        xabar = (
            "❌ XATOLIK (Conflict): Ushbu TELEGRAM_BOT_TOKEN bilan boshqa joyda "
            "(masalan, boshqa terminal yoki serverda) yana bir bot nusxasi ishlamoqda! "
            "Avval eski nusxani to'xtating."
        )
        print(xabar)
        logger.error("TelegramConflictError: bir xil bot tokeni bilan 2-nusxa aniqlandi.")
        sys.exit(1)
    finally:
        if rejalashtiruvchi and rejalashtiruvchi.running:
            rejalashtiruvchi.shutdown(wait=False)
        await bot_obyekti.session.close()
        logger.info("=== MarketPulse Core boti to'xtatildi ===")


if __name__ == "__main__":
    try:
        asyncio.run(botni_ishga_tushirish())
    except KeyboardInterrupt:
        print("\n🛑 Bot foydalanuvchi tomonidan to'xtatildi.")
