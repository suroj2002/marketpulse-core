"""
MarketPulse Core — 100% ichki Python tahlil moduli (ko'p valyutali va 2 tilli: uz / ru).

Tashqi AI API larsiz ma'lumotlar bazasidagi narx o'zgarishlarini hisoblaydi va
tanlangan tilda (`uz` yoki `ru`) tadbirkor uchun tushunarli hisobot matnini tayyorlaydi.
"""

from collections import defaultdict
from typing import Any

from database import barcha_mahsulotlarni_olish, faol_db_yoli
from locales import t, valyuta_yorligi, vaqt_mintaqasi_yorligi
from parsers.universal import narxni_formatlash
from utils import hozirgi_vaqt, loggerni_olish, vaqt_mintaqasi_nomi


logger = loggerni_olish("analytics")


def tahlil_qilish(db_yoli: str | None = None) -> dict[str, Any]:
    """
    Bazadagi barcha mahsulotlarni tahlil qilib, tuzilmaviy statistika qaytaradi.
    Har xil valyutadagi mahsulotlar bir-biriga aralashmasligi uchun o'rtacha/min/max
    ko'rsatkichlar valyutalar kesimida hisoblanadi.
    """
    yol = faol_db_yoli(db_yoli)
    logger.info("Ichki Python tahlili boshlandi (%s)...", yol)
    mahsulotlar = barcha_mahsulotlarni_olish(yol)

    arzonlashganlar: list[dict[str, Any]] = []
    qimmatlashganlar: list[dict[str, Any]] = []
    ozgarmaganlar: list[dict[str, Any]] = []
    yangi_mahsulotlar: list[dict[str, Any]] = []
    ozgarganlar: list[dict[str, Any]] = []

    for m in mahsulotlar:
        eski = m["eski_narx"]
        yangi = m["yangi_narx"]
        valyuta = m.get("valyuta", "") or ""

        if eski is None:
            yangi_mahsulotlar.append(
                {
                    **m,
                    "valyuta": valyuta,
                    "farq": 0.0,
                    "foiz": 0.0,
                    "holat": "yangi",
                }
            )
            continue

        farq = round(yangi - eski, 2)
        foiz = round((farq / eski) * 100, 2) if eski > 0 else 0.0

        yozuv = {
            **m,
            "valyuta": valyuta,
            "farq": farq,
            "foiz": foiz,
        }

        if farq < 0:
            yozuv["holat"] = "arzonlashdi"
            arzonlashganlar.append(yozuv)
            ozgarganlar.append(yozuv)
        elif farq > 0:
            yozuv["holat"] = "qimmatlashdi"
            qimmatlashganlar.append(yozuv)
            ozgarganlar.append(yozuv)
        else:
            yozuv["holat"] = "ozgarmadi"
            ozgarmaganlar.append(yozuv)

    top_3 = sorted(
        ozgarganlar,
        key=lambda x: (abs(x["foiz"]), abs(x["farq"])),
        reverse=True,
    )[:3]

    valyuta_guruhlari: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in mahsulotlar:
        if m["yangi_narx"] is not None and m["yangi_narx"] > 0:
            val_kalit = (m.get("valyuta", "") or "").strip()
            valyuta_guruhlari[val_kalit].append(m)

    valyuta_statistikasi: dict[str, dict[str, Any]] = {}
    for val, guruh in valyuta_guruhlari.items():
        narxlar = [x["yangi_narx"] for x in guruh]
        valyuta_statistikasi[val] = {
            "soni": len(guruh),
            "ortacha_narx": round(sum(narxlar) / len(narxlar), 2),
            "eng_arzon": min(guruh, key=lambda x: x["yangi_narx"]),
            "eng_qimmat": max(guruh, key=lambda x: x["yangi_narx"]),
        }

    birinchi_stat = next(iter(valyuta_statistikasi.values()), None)
    ortacha_narx = birinchi_stat["ortacha_narx"] if birinchi_stat else 0.0
    eng_arzon = birinchi_stat["eng_arzon"] if birinchi_stat else None
    eng_qimmat = birinchi_stat["eng_qimmat"] if birinchi_stat else None

    logger.info(
        "Tahlil yakunlandi: jami=%d, arzonlashgan=%d, qimmatlashgan=%d, o'zgarmagan=%d, yangi=%d",
        len(mahsulotlar),
        len(arzonlashganlar),
        len(qimmatlashganlar),
        len(ozgarmaganlar),
        len(yangi_mahsulotlar),
    )

    return {
        "jami": len(mahsulotlar),
        "arzonlashganlar": sorted(arzonlashganlar, key=lambda x: x["foiz"]),
        "qimmatlashganlar": sorted(qimmatlashganlar, key=lambda x: x["foiz"], reverse=True),
        "ozgarmaganlar": ozgarmaganlar,
        "yangi_mahsulotlar": yangi_mahsulotlar,
        "top_3": top_3,
        "valyuta_statistikasi": valyuta_statistikasi,
        "ortacha_narx": ortacha_narx,
        "eng_arzon": eng_arzon,
        "eng_qimmat": eng_qimmat,
    }


def hisobot_matnini_yaratish(
    db_yoli: str | None = None,
    lang: str = "uz",
    tz_nomi: str | None = None,
) -> str:
    """
    Tadbirkor uchun tushunarli tahliliy hisobot matnini tanlangan tilda (`uz`/`ru`) yaratadi.
    """
    natija = tahlil_qilish(db_yoli)
    faol_tz = vaqt_mintaqasi_nomi(lang=lang, tz_nomi=tz_nomi)
    sana = hozirgi_vaqt(lang=lang, tz_nomi=faol_tz).strftime("%Y-%m-%d %H:%M")
    tz_korinish = vaqt_mintaqasi_yorligi(faol_tz, lang)

    if natija["jami"] == 0:
        return (
            f"{t('analytics_title', lang, date=sana, timezone=tz_korinish)}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{t('analytics_empty', lang)}"
        )

    arzon_soni = len(natija["arzonlashganlar"])
    qimmat_soni = len(natija["qimmatlashganlar"])
    ozgarmagan_soni = len(natija["ozgarmaganlar"])
    yangi_soni = len(natija["yangi_mahsulotlar"])

    qatorlar = [
        t("analytics_title", lang, date=sana, timezone=tz_korinish),
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        t("analytics_summary_header", lang),
        t("analytics_total", lang, count=natija["jami"]),
        t("analytics_dropped", lang, count=arzon_soni),
        t("analytics_increased", lang, count=qimmat_soni),
        t("analytics_unchanged", lang, count=ozgarmagan_soni),
        t("analytics_new", lang, count=yangi_soni),
    ]

    val_stat: dict[str, dict[str, Any]] = natija["valyuta_statistikasi"]
    if len(val_stat) == 1:
        val, st = next(iter(val_stat.items()))
        yorliq = valyuta_yorligi(val, lang)
        qatorlar.append(
            t("analytics_avg_price", lang, price=narxni_formatlash(st["ortacha_narx"], yorliq))
        )
        qatorlar.append(
            t(
                "analytics_cheapest",
                lang,
                name=st["eng_arzon"]["nomi"],
                price=narxni_formatlash(st["eng_arzon"]["yangi_narx"], yorliq),
            )
        )
        qatorlar.append(
            t(
                "analytics_priciest",
                lang,
                name=st["eng_qimmat"]["nomi"],
                price=narxni_formatlash(st["eng_qimmat"]["yangi_narx"], yorliq),
            )
        )
    elif len(val_stat) > 1:
        qatorlar.append("")
        qatorlar.append(t("analytics_by_currency_header", lang))
        for val, st in val_stat.items():
            yorliq = valyuta_yorligi(val, lang)
            val_nomi = yorliq if yorliq else t("analytics_no_currency", lang)
            qatorlar.append(
                t(
                    "analytics_currency_line",
                    lang,
                    currency=val_nomi,
                    count=st["soni"],
                    avg=narxni_formatlash(st["ortacha_narx"], yorliq),
                    min_p=narxni_formatlash(st["eng_arzon"]["yangi_narx"], yorliq),
                    max_p=narxni_formatlash(st["eng_qimmat"]["yangi_narx"], yorliq),
                )
            )

    qatorlar.append("")
    qatorlar.append(t("analytics_top3_header", lang))
    if natija["top_3"]:
        for indeks, item in enumerate(natija["top_3"], start=1):
            belgi = "📉" if item["farq"] < 0 else "📈"
            ishora = "+" if item["foiz"] > 0 else ""
            yorliq = valyuta_yorligi(item.get("valyuta", ""), lang)
            qatorlar.append(
                f"{indeks}. {belgi} {item['nomi']}\n"
                f"   {narxni_formatlash(item['eski_narx'], yorliq)} → "
                f"{narxni_formatlash(item['yangi_narx'], yorliq)} "
                f"({ishora}{item['foiz']:.2f}%)"
            )
    else:
        qatorlar.append(t("analytics_no_changes", lang))

    if natija["arzonlashganlar"]:
        qatorlar.append("")
        qatorlar.append(t("analytics_dropped_header", lang))
        for item in natija["arzonlashganlar"]:
            yorliq = valyuta_yorligi(item.get("valyuta", ""), lang)
            qatorlar.append(
                f"• {item['nomi']}: {narxni_formatlash(item['eski_narx'], yorliq)} → "
                f"{narxni_formatlash(item['yangi_narx'], yorliq)} ({item['foiz']:.2f}%)"
            )

    if natija["qimmatlashganlar"]:
        qatorlar.append("")
        qatorlar.append(t("analytics_increased_header", lang))
        for item in natija["qimmatlashganlar"]:
            yorliq = valyuta_yorligi(item.get("valyuta", ""), lang)
            qatorlar.append(
                f"• {item['nomi']}: {narxni_formatlash(item['eski_narx'], yorliq)} → "
                f"{narxni_formatlash(item['yangi_narx'], yorliq)} (+{item['foiz']:.2f}%)"
            )

    # Ombor qoldig'i va yuqori vozvrat signallari (Seller API ulangan bo'lsa)
    mahsulotlar = barcha_mahsulotlarni_olish(db_yoli)
    seller_mahsulotlari = [m for m in mahsulotlar if m.get("shop_id") is not None]
    if seller_mahsulotlari:
        tugaganlar = [m for m in seller_mahsulotlari if int(m.get("qoldiq") or 0) == 0]
        yuqori_vozvrat = [m for m in seller_mahsulotlari if float(m.get("vozvrat_foiz") or 0.0) >= 15.0]
        if tugaganlar or yuqori_vozvrat:
            qatorlar.append("")
            qatorlar.append(t("analytics_stock_signals_header", lang))
            if tugaganlar:
                qatorlar.append(t("analytics_out_of_stock", lang, count=len(tugaganlar)))
            for item in yuqori_vozvrat[:3]:
                qatorlar.append(
                    t(
                        "analytics_high_return",
                        lang,
                        name=item["nomi"],
                        pct=float(item["vozvrat_foiz"]),
                        sold=item["sotilgan"],
                        returned=item["qaytgan"],
                    )
                )

    qatorlar.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    qatorlar.append(t("analytics_footer", lang))

    return "\n".join(qatorlar)
