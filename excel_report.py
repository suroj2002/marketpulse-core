"""
MarketPulse Core — Dizaynli ko'p valyutali va 2 tilli (uz / ru) Excel hisobot moduli.

openpyxl kutubxonasi yordamida tanlangan tilda kunlik hisobotni
(`hisobot_YYYY-MM-DD.xlsx` / `otchet_YYYY-MM-DD.xlsx`) rangli indikatorlar
va umumiy statistika bilan yaratadi.
"""

from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from database import barcha_mahsulotlarni_olish, faol_db_yoli
from locales import t, valyuta_yorligi
from utils import hozirgi_vaqt, loggerni_olish


logger = loggerni_olish("excel_report")


def excel_hisobot_yaratish(
    db_yoli: str | None = None,
    chiqish_fayli: str | None = None,
    lang: str = "uz",
    tz_nomi: str | None = None,
) -> str:
    """
    Bazadagi mahsulotlar asosida tanlangan tilda (`uz`/`ru`) dizaynli Excel hisobot yaratadi.

    Qaytaradi:
        Yaratilgan Excel fayl nomi/yo'li.
    """
    yol = faol_db_yoli(db_yoli)
    if chiqish_fayli is None:
        bugungi_sana = hozirgi_vaqt(lang=lang, tz_nomi=tz_nomi).strftime("%Y-%m-%d")
        prefiks = t("excel_filename_prefix", lang)
        chiqish_fayli = f"{prefiks}_{bugungi_sana}.xlsx"

    logger.info("Excel hisobot yaratish boshlandi: %s (lang=%s)", chiqish_fayli, lang)

    try:
        mahsulotlar: list[dict[str, Any]] = barcha_mahsulotlarni_olish(yol)

        wb = Workbook()
        ws = wb.active
        ws.title = t("excel_sheet_title", lang)

        # Uslublar
        sarlavha_fon = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        sarlavha_shrift = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

        yashil_fon = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        yashil_shrift = Font(name="Calibri", size=11, bold=True, color="006100")

        qizil_fon = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        qizil_shrift = Font(name="Calibri", size=11, bold=True, color="9C0006")

        stat_fon = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        oddiy_shrift = Font(name="Calibri", size=11, color="000000")
        qalin_shrift = Font(name="Calibri", size=11, bold=True, color="000000")
        havola_shrift = Font(name="Calibri", size=10, color="0563C1", underline="single")

        ingichka_chegara = Side(border_style="thin", color="BFBFBF")
        katak_chegarasi = Border(
            left=ingichka_chegara,
            right=ingichka_chegara,
            top=ingichka_chegara,
            bottom=ingichka_chegara,
        )

        markaz_tekislash = Alignment(horizontal="center", vertical="center")
        chap_tekislash = Alignment(horizontal="left", vertical="center")
        ong_tekislash = Alignment(horizontal="right", vertical="center")

        sarlavhalar = [
            t("excel_col_num", lang),
            t("excel_col_name", lang),
            t("excel_col_old_price", lang),
            t("excel_col_new_price", lang),
            t("excel_col_currency", lang),
            t("excel_col_diff", lang),
            t("excel_col_pct", lang),
            t("excel_col_status", lang),
            t("excel_col_rating", lang),
            t("excel_col_date", lang),
            t("excel_col_url", lang),
        ]
        ws.append(sarlavhalar)
        ws.row_dimensions[1].height = 28

        for ustun_indeksi in range(1, len(sarlavhalar) + 1):
            katak = ws.cell(row=1, column=ustun_indeksi)
            katak.fill = sarlavha_fon
            katak.font = sarlavha_shrift
            katak.alignment = markaz_tekislash
            katak.border = katak_chegarasi

        arzonlashgan_soni = 0
        qimmatlashgan_soni = 0
        ozgarmagan_yoki_yangi_soni = 0

        for tartib, m in enumerate(mahsulotlar, start=1):
            eski_narx = m["eski_narx"]
            yangi_narx = m["yangi_narx"]
            valyuta = valyuta_yorligi(m.get("valyuta", "") or "", lang) or "—"
            reyting_matni = f"{m['reyting']} / 5" if m["reyting"] else "—"

            holat_kodi = "unchanged"
            if eski_narx is None:
                farq = None
                foiz = None
                holat_kodi = "new"
                holat = t("excel_status_new", lang)
                ozgarmagan_yoki_yangi_soni += 1
            else:
                farq = round(yangi_narx - eski_narx, 2)
                foiz = (farq / eski_narx) if eski_narx > 0 else 0.0
                if farq < 0:
                    holat_kodi = "dropped"
                    holat = t("excel_status_dropped", lang)
                    arzonlashgan_soni += 1
                elif farq > 0:
                    holat_kodi = "increased"
                    holat = t("excel_status_increased", lang)
                    qimmatlashgan_soni += 1
                else:
                    holat_kodi = "unchanged"
                    holat = t("excel_status_unchanged", lang)
                    ozgarmagan_yoki_yangi_soni += 1

            qator_qiymatlari = [
                tartib,
                m["nomi"],
                eski_narx if eski_narx is not None else "—",
                yangi_narx,
                valyuta,
                farq if farq is not None else "—",
                foiz if foiz is not None else "—",
                holat,
                reyting_matni,
                m["oxirgi_sana"],
                m["url"],
            ]
            ws.append(qator_qiymatlari)
            qator_raqami = ws.max_row
            ws.row_dimensions[qator_raqami].height = 22

            for ustun in range(1, len(sarlavhalar) + 1):
                katak = ws.cell(row=qator_raqami, column=ustun)
                katak.font = oddiy_shrift
                katak.border = katak_chegarasi

                if ustun in (1, 5, 8, 9, 10):
                    katak.alignment = markaz_tekislash
                elif ustun in (3, 4, 6, 7):
                    katak.alignment = ong_tekislash
                else:
                    katak.alignment = chap_tekislash

            if eski_narx is not None:
                ws.cell(row=qator_raqami, column=3).number_format = "#,##0.00"
            ws.cell(row=qator_raqami, column=4).number_format = "#,##0.00"
            if farq is not None:
                ws.cell(row=qator_raqami, column=6).number_format = "+#,##0.00;-#,##0.00;0.00"
            if foiz is not None:
                ws.cell(row=qator_raqami, column=7).number_format = "+0.00%;-0.00%;0.00%"

            havola_katagi = ws.cell(row=qator_raqami, column=11)
            havola_katagi.hyperlink = m["url"]
            havola_katagi.font = havola_shrift

            if holat_kodi == "dropped":
                for ustun in (4, 6, 7, 8):
                    katak = ws.cell(row=qator_raqami, column=ustun)
                    katak.fill = yashil_fon
                    katak.font = yashil_shrift
            elif holat_kodi == "increased":
                for ustun in (4, 6, 7, 8):
                    katak = ws.cell(row=qator_raqami, column=ustun)
                    katak.fill = qizil_fon
                    katak.font = qizil_shrift

        # Jadval pastida umumiy statistika bo'limi
        stat_boshlanish = ws.max_row + 2
        ws.merge_cells(
            start_row=stat_boshlanish,
            start_column=1,
            end_row=stat_boshlanish,
            end_column=4,
        )
        stat_sarlavha = ws.cell(row=stat_boshlanish, column=1, value=t("excel_stats_header", lang))
        stat_sarlavha.fill = sarlavha_fon
        stat_sarlavha.font = sarlavha_shrift
        stat_sarlavha.alignment = markaz_tekislash
        ws.row_dimensions[stat_boshlanish].height = 24
        for u in range(1, 5):
            ws.cell(row=stat_boshlanish, column=u).border = katak_chegarasi

        statistika_qatorlari = [
            (t("excel_stats_total", lang), len(mahsulotlar), stat_fon, qalin_shrift),
            (t("excel_stats_dropped", lang), arzonlashgan_soni, yashil_fon, yashil_shrift),
            (t("excel_stats_increased", lang), qimmatlashgan_soni, qizil_fon, qizil_shrift),
            (t("excel_stats_unchanged", lang), ozgarmagan_yoki_yangi_soni, stat_fon, oddiy_shrift),
        ]

        for ofset, (nom, qiymat, fon, shrift) in enumerate(statistika_qatorlari, start=1):
            r = stat_boshlanish + ofset
            ws.row_dimensions[r].height = 22
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)

            nom_katak = ws.cell(row=r, column=1, value=nom)
            nom_katak.font = qalin_shrift
            nom_katak.alignment = chap_tekislash
            nom_katak.fill = stat_fon

            qiymat_katak = ws.cell(row=r, column=4, value=qiymat)
            qiymat_katak.font = shrift
            qiymat_katak.alignment = markaz_tekislash
            qiymat_katak.fill = fon

            for u in range(1, 5):
                ws.cell(row=r, column=u).border = katak_chegarasi

        ws.freeze_panes = "A2"

        for ustun_indeksi in range(1, len(sarlavhalar) + 1):
            ustun_harfi = get_column_letter(ustun_indeksi)
            maks_uzunlik = 0
            for qator in range(1, len(mahsulotlar) + 2):
                qiymat = ws.cell(row=qator, column=ustun_indeksi).value
                if qiymat is not None:
                    matn_uzunligi = len(str(qiymat))
                    if matn_uzunligi > maks_uzunlik:
                        maks_uzunlik = matn_uzunligi

            mos_kenglik = min(max(maks_uzunlik + 4, 10), 55)
            if ustun_indeksi == 1:
                mos_kenglik = 6
            ws.column_dimensions[ustun_harfi].width = mos_kenglik

        wb.save(chiqish_fayli)
        hajm_kb = Path(chiqish_fayli).stat().st_size / 1024
        print(f"[Excel] Hisobot muvaffaqiyatli saqlandi: {chiqish_fayli}")
        logger.info(
            "Excel hisobot muvaffaqiyatli saqlandi: %s (%.1f KB, %d ta qator, lang=%s)",
            chiqish_fayli,
            hajm_kb,
            len(mahsulotlar),
            lang,
        )
        return chiqish_fayli

    except Exception as xato:
        logger.error("Excel hisobot yaratishda xatolik (%s): %s", chiqish_fayli, xato)
        raise
