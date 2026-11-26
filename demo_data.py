"""
MarketPulse Core — Portfolio mijozlari uchun xavfsiz Demo-rejim ma'lumotlari.

Zero-Leak qoidasi:
- Ushbu modul SQLite bazasiga, Uzum/Ozon Seller API ga va Playwright parserga
  mutlaqo ulanmaydi.
- Barcha ma'lumotlar faqat xotiradagi (in-memory) namunaviy tovarlar va
  namunaviy raqobatchilardan iborat (faqat o'qish va kalkulyator hisoblash uchun).
"""

import math
from typing import Any

from utils import hozirgi_vaqt


# 4 ta namunaviy e-commerce tovar (UZ va RU nomlari, komissiya, logistika, qoldiq va raqobatchilar bilan)
_DEMO_TOVARLAR: tuple[dict[str, Any], ...] = (
    {
        "id": 101,
        "product_id": 900101,
        "sku": "DEMO-EARBUDS-PRO2",
        "nomi_uz": "Simsiz quloqchin AirPods Pro 2 (ANC, MagSafe)",
        "nomi_ru": "Беспроводные наушники AirPods Pro 2 (ANC, MagSafe)",
        "narxi": 349000.0,
        "komissiya_foizi": 15.0,
        "logistika_tolovi": 12000.0,
        "qoldiq": 18,
    },
    {
        "id": 102,
        "product_id": 900102,
        "sku": "DEMO-PB-20000W",
        "nomi_uz": "Powerbank Xiaomi 20 000 mAh (22.5W tez zaryad)",
        "nomi_ru": "Повербанк Xiaomi 20 000 мАч (быстрая зарядка 22.5W)",
        "narxi": 285000.0,
        "komissiya_foizi": 12.0,
        "logistika_tolovi": 10000.0,
        "qoldiq": 3,
    },
    {
        "id": 103,
        "product_id": 900103,
        "sku": "DEMO-WATCH-AMOLED",
        "nomi_uz": "Smart-soat AMOLED Ultra Fit (GPS, suvga chidamli)",
        "nomi_ru": "Смарт-часы AMOLED Ultra Fit (GPS, влагозащита)",
        "narxi": 590000.0,
        "komissiya_foizi": 14.0,
        "logistika_tolovi": 15000.0,
        "qoldiq": 9,
    },
    {
        "id": 104,
        "product_id": 900104,
        "sku": "DEMO-VACUUM-S7",
        "nomi_uz": "Robot-changyutgich SmartClean S7 (Wi-Fi, nam tozalash)",
        "nomi_ru": "Робот-пылесос SmartClean S7 (Wi-Fi, влажная уборка)",
        "narxi": 1890000.0,
        "komissiya_foizi": 10.0,
        "logistika_tolovi": 25000.0,
        "qoldiq": 2,
    },
)

_DEMO_RAQOBATCHILAR: dict[int, tuple[dict[str, Any], ...]] = {
    900101: (
        {
            "id": 1001,
            "my_product_id": 900101,
            "url": "https://uzum.uz/uz/product/demo-airpods-store-a-9001011",
            "nomi_uz": "TechZone Market (namuna #1)",
            "nomi_ru": "TechZone Market (пример #1)",
            "eski_narx": 355000.0,
            "yangi_narx": 329000.0,
        },
        {
            "id": 1002,
            "my_product_id": 900101,
            "url": "https://uzum.uz/uz/product/demo-airpods-store-b-9001012",
            "nomi_uz": "GadgetPlus Store (namuna #2)",
            "nomi_ru": "GadgetPlus Store (пример #2)",
            "eski_narx": 370000.0,
            "yangi_narx": 375000.0,
        },
    ),
    900102: (
        {
            "id": 1003,
            "my_product_id": 900102,
            "url": "https://uzum.uz/uz/product/demo-powerbank-store-a-9001021",
            "nomi_uz": "SmartElectro UZ (namuna #1)",
            "nomi_ru": "SmartElectro UZ (пример #1)",
            "eski_narx": 280000.0,
            "yangi_narx": 269000.0,
        },
        {
            "id": 1004,
            "my_product_id": 900102,
            "url": "https://uzum.uz/uz/product/demo-powerbank-store-b-9001022",
            "nomi_uz": "MobilePro Shop (namuna #2)",
            "nomi_ru": "MobilePro Shop (пример #2)",
            "eski_narx": 299000.0,
            "yangi_narx": 299000.0,
        },
    ),
    900103: (
        {
            "id": 1005,
            "my_product_id": 900103,
            "url": "https://uzum.uz/uz/product/demo-watch-store-a-9001031",
            "nomi_uz": "TimeStyle Market (namuna #1)",
            "nomi_ru": "TimeStyle Market (пример #1)",
            "eski_narx": 610000.0,
            "yangi_narx": 625000.0,
        },
        {
            "id": 1006,
            "my_product_id": 900103,
            "url": "https://uzum.uz/uz/product/demo-watch-store-b-9001032",
            "nomi_uz": "WearableHub (namuna #2)",
            "nomi_ru": "WearableHub (пример #2)",
            "eski_narx": 595000.0,
            "yangi_narx": 590000.0,
        },
    ),
    900104: (
        {
            "id": 1007,
            "my_product_id": 900104,
            "url": "https://uzum.uz/uz/product/demo-vacuum-store-a-9001041",
            "nomi_uz": "HomeTech Plaza (namuna #1)",
            "nomi_ru": "HomeTech Plaza (пример #1)",
            "eski_narx": 1920000.0,
            "yangi_narx": 1799000.0,
        },
        {
            "id": 1008,
            "my_product_id": 900104,
            "url": "https://uzum.uz/uz/product/demo-vacuum-store-b-9001042",
            "nomi_uz": "CleanHouse Official (namuna #2)",
            "nomi_ru": "CleanHouse Official (пример #2)",
            "eski_narx": 1950000.0,
            "yangi_narx": 1980000.0,
        },
    ),
}


def _til_kaliti(lang: str) -> str:
    """Til kodini normallashtiradi (`uz` yoki `ru`)."""
    return "ru" if str(lang).strip().lower() == "ru" else "uz"


def _tovarni_formatlash(xom: dict[str, Any], lang: str = "uz") -> dict[str, Any]:
    """Namunaviy tovarni `catalog` jadvali formatida (copy) qaytaradi."""
    til = _til_kaliti(lang)
    sana = hozirgi_vaqt(lang=til).strftime("%Y-%m-%d %H:%M")
    return {
        "id": int(xom["id"]),
        "product_id": int(xom["product_id"]),
        "sku": str(xom["sku"]),
        "nomi": str(xom[f"nomi_{til}"]),
        "narxi": float(xom["narxi"]),
        "komissiya_foizi": float(xom["komissiya_foizi"]),
        "logistika_tolovi": float(xom["logistika_tolovi"]),
        "qoldiq": int(xom["qoldiq"]),
        "yangilangan_sana": sana,
    }


def demo_katalog_sahifa_olish(
    sahifa: int = 1,
    sahifa_hajmi: int = 5,
    lang: str = "uz",
) -> tuple[list[dict[str, Any]], int, int]:
    """Demo katalogdan sahifalangan (standart 5 tadan) namunaviy tovarlarni qaytaradi."""
    jami_soni = len(_DEMO_TOVARLAR)
    jami_sahifalar = max(1, math.ceil(jami_soni / max(1, sahifa_hajmi)))
    joriy_sahifa = max(1, min(sahifa, jami_sahifalar))
    boshlanish = (joriy_sahifa - 1) * sahifa_hajmi
    tugash = boshlanish + sahifa_hajmi
    tovarlar = [_tovarni_formatlash(t, lang=lang) for t in _DEMO_TOVARLAR[boshlanish:tugash]]
    return tovarlar, jami_soni, jami_sahifalar


def demo_katalog_tovar_olish(
    katalog_id: int,
    lang: str = "uz",
) -> dict[str, Any] | None:
    """Demo katalogdan `id` bo'yicha bitta namunaviy tovarni qaytaradi."""
    for item in _DEMO_TOVARLAR:
        if int(item["id"]) == int(katalog_id):
            return _tovarni_formatlash(item, lang=lang)
    return None


def demo_kam_qoldiq_tovarlar(
    chegara: int = 5,
    lang: str = "uz",
) -> list[dict[str, Any]]:
    """Demo katalogda qoldig'i `chegara` dan kam bo'lgan namunaviy tovarlarni qaytaradi."""
    return [
        _tovarni_formatlash(item, lang=lang)
        for item in _DEMO_TOVARLAR
        if int(item["qoldiq"]) < int(chegara)
    ]


def demo_raqobatchilarni_olish(
    my_product_id: int,
    lang: str = "uz",
) -> list[dict[str, Any]]:
    """Tanlangan demo tovarga biriktirilgan 2 ta namunaviy raqobatchini qaytaradi."""
    til = _til_kaliti(lang)
    sana = hozirgi_vaqt(lang=til).strftime("%Y-%m-%d %H:%M")
    xom_royxat = _DEMO_RAQOBATCHILAR.get(int(my_product_id), ())
    natija: list[dict[str, Any]] = []
    for r in xom_royxat:
        natija.append(
            {
                "id": int(r["id"]),
                "my_product_id": int(r["my_product_id"]),
                "url": str(r["url"]),
                "raqobatchi_nomi": str(r[f"nomi_{til}"]),
                "eski_narx": float(r["eski_narx"]),
                "yangi_narx": float(r["yangi_narx"]),
                "oxirgi_tekshiruv": sana,
            }
        )
    return natija
