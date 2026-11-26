"""
MarketPulse Core — Umumiy yordamchi modul (vaqt mintaqasi, DB yo'li va rotatsiyali loglash).

Xususiyatlari:
- Barcha modullar uchun yagona vaqt mintaqasi (.env dagi TIMEZONE).
- .env dagi DB_PATH orqali doimiy Volume (masalan: /data/marketpulse.db) qo'llab-quvvatlovi.
- logs/marketpulse.log uchun RotatingFileHandler (5 MB × 3 zaxira — disk to'lib qolmaydi).
"""

from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


STANDART_TIMEZONE = "Asia/Tashkent"
MOSKVA_TIMEZONE = "Europe/Moscow"
TIL_VAQT_MINTAQALARI: dict[str, str] = {
    "uz": STANDART_TIMEZONE,
    "ru": MOSKVA_TIMEZONE,
}
QULLAB_QUVVATLANADIGAN_VAQT_MINTAQALARI = (STANDART_TIMEZONE, MOSKVA_TIMEZONE)
STANDART_DB_YOLI = "marketpulse.db"
LOG_FAYL_YOLI = Path("logs") / "marketpulse.log"
LOG_MAKS_BAYT = 5 * 1024 * 1024  # 5 MB
LOG_ZAXIRA_SONI = 3


def vaqt_mintaqasini_olish(
    lang: str | None = None,
    tz_nomi: str | None = None,
) -> ZoneInfo:
    """
    Vaqt mintaqasini (ZoneInfo) qaytaradi:
    1. Agar `tz_nomi` aniq berilgan bo'lsa (masalan: 'Europe/Moscow' yoki 'Asia/Tashkent'), shu ishlatiladi.
    2. Aks holda `lang` berilgan bo'lsa: `ru` -> Europe/Moscow, `uz` -> Asia/Tashkent.
    3. Ikkalasi ham berilmasa, .env dagi TIMEZONE (standart: Asia/Tashkent) ishlatiladi.
    """
    load_dotenv()
    tanlangan = (tz_nomi or "").strip()
    if not tanlangan and lang is not None:
        til_kod = (lang or "").strip().lower()
        tanlangan = TIL_VAQT_MINTAQALARI.get(til_kod, STANDART_TIMEZONE)
    if not tanlangan:
        tanlangan = os.getenv("TIMEZONE", "").strip() or STANDART_TIMEZONE
    try:
        return ZoneInfo(tanlangan)
    except ZoneInfoNotFoundError:
        return ZoneInfo(STANDART_TIMEZONE)


def vaqt_mintaqasi_nomi(
    lang: str | None = None,
    tz_nomi: str | None = None,
) -> str:
    """Faol vaqt mintaqasining IANA nomini qaytaradi (masalan: Asia/Tashkent yoki Europe/Moscow)."""
    return str(vaqt_mintaqasini_olish(lang=lang, tz_nomi=tz_nomi))


def hozirgi_vaqt(
    lang: str | None = None,
    tz_nomi: str | None = None,
) -> datetime:
    """Faol vaqt mintaqasidagi joriy sana va vaqtni qaytaradi."""
    return datetime.now(vaqt_mintaqasini_olish(lang=lang, tz_nomi=tz_nomi))


def db_yolni_olish() -> str:
    """
    .env faylidagi DB_PATH qiymatini qaytaradi (standart: marketpulse.db).
    Docker / Railway Volume uchun masalan DB_PATH=/data/marketpulse.db qo'yiladi.
    """
    load_dotenv()
    return os.getenv("DB_PATH", "").strip() or STANDART_DB_YOLI


class _MintaqaliFormatter(logging.Formatter):
    """Log yozuvlari vaqtini tanlangan TIMEZONE bo'yicha formatlaydi."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        vaqt = datetime.fromtimestamp(record.created, tz=vaqt_mintaqasini_olish())
        if datefmt:
            return vaqt.strftime(datefmt)
        return vaqt.strftime("%Y-%m-%d %H:%M:%S %z")


def loggerni_olish(nom: str = "marketpulse") -> logging.Logger:
    """
    logs/marketpulse.log fayliga rotatsiya bilan (max 5 MB × 3) yozadigan
    umumiy logger obyektini sozlaydi va qaytaradi.
    """
    asosiy_logger = logging.getLogger("marketpulse")
    if not asosiy_logger.handlers:
        LOG_FAYL_YOLI.parent.mkdir(parents=True, exist_ok=True)
        asosiy_logger.setLevel(logging.INFO)

        formatlovchi = _MintaqaliFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        fayl_handler = RotatingFileHandler(
            LOG_FAYL_YOLI,
            maxBytes=LOG_MAKS_BAYT,
            backupCount=LOG_ZAXIRA_SONI,
            encoding="utf-8",
        )
        fayl_handler.setLevel(logging.INFO)
        fayl_handler.setFormatter(formatlovchi)
        asosiy_logger.addHandler(fayl_handler)
        asosiy_logger.propagate = False

    if nom == "marketpulse":
        return asosiy_logger
    return logging.getLogger(f"marketpulse.{nom}")
