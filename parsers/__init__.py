"""
MarketPulse Core — Universal Parser paketi.

sites_config.json konfiguratsiyasi va noma'lum saytlar uchun
Universal Fallback (JSON-LD, meta teglar, DOM narx qidiruvi) hamda
valyuta aniqlash/formatlash funksiyalarini taqdim etadi.
"""

from parsers.ozon_api import ozon_mahsulotlarini_olish, ozon_sozlanganmi
from parsers.universal import (
    domenni_olish,
    konfiguratsiyani_yuklash,
    narxni_formatlash,
    narxni_tozalash,
    reytingni_aniqlash,
    sayt_konfiguratsiyasini_topish,
    universal_fallback_ajratish,
    valyutani_aniqlash,
)
from parsers.uzum_api import uzum_mahsulotlarini_olish, uzum_narx_ozgartirish, uzum_sozlanganmi
from parsers.uzum_competitors import (
    qidiruv_sorovini_tayyorlash,
    raqobatchi_hisobotini_formatlash,
    raqobatchilarni_qidirish,
)

__all__ = [
    "domenni_olish",
    "konfiguratsiyani_yuklash",
    "narxni_formatlash",
    "narxni_tozalash",
    "ozon_mahsulotlarini_olish",
    "ozon_sozlanganmi",
    "qidiruv_sorovini_tayyorlash",
    "raqobatchi_hisobotini_formatlash",
    "raqobatchilarni_qidirish",
    "reytingni_aniqlash",
    "sayt_konfiguratsiyasini_topish",
    "universal_fallback_ajratish",
    "uzum_mahsulotlarini_olish",
    "uzum_narx_ozgartirish",
    "uzum_sozlanganmi",
    "valyutani_aniqlash",
]
