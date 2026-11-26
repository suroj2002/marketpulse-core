"""
MarketPulse Core — Ikki tilli (O'zbekcha `uz` va Ruscha `ru`) til lug'ati moduli.

Botdagi barcha xabarlar, menyu tugmalari, aqlli kalkulyator, qoldiq va raqobatchi
signallari, Zero-Storage qoidasi, tahlil hamda Excel hisobot sarlavhalari shu yerda jamlangan.
"""

from typing import Any


QULLAB_QUVVATLANADIGAN_TILLAR = ("uz", "ru")

TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        # Umumiy va ruxsat
        "access_denied": "⛔ Ruxsat yo'q",
        "currency_uzs": "so'm",
        "unit_pcs": "ta",
        "status_connected": "Ulangan ✅",
        "status_not_configured": "Sozlanmagan (.env orqali)",
        "zero_storage_rule": (
            "📌 Muhim qoida: Xavfsizlik maqsadida barcha hisobot fayllari yuborilgandan so'ng "
            "serverdan darhol o'chiriladi va faqat ushbu Telegram chatda saqlanadi. "
            "Kerakli eski fayllarni faqat shu chat tarixidan topishingiz mumkin — "
            "bot ularni qayta jo'nata olmaydi."
        ),
        "zero_result_alert": "⚠️ DIQQAT: Sayt strukturasi o'zgargan bo'lishi mumkin, 0 ta mahsulot topildi!",
        "generic_error": (
            "❌ Monitoring jarayonida xatolik yuz berdi. "
            "Tafsilotlar <code>logs/marketpulse.log</code> fayliga yozildi."
        ),
        "excel_not_found": "❌ Excel hisobot fayli topilmadi.",
        "file_too_large": (
            "⚠️ OGOHLANTIRISH: '{filename}' hajmi {size_mb:.2f} MB — "
            "{limit_mb} MB chegarasidan katta bo'lgani uchun Telegram'ga yuborilmadi."
        ),
        "unknown_message_hint": (
            "ℹ️ Boshqaruv menyusini ochish uchun /start yuboring yoki quyidagi tugmalardan foydalaning:"
        ),
        # Til tanlash
        "choose_language_prompt": (
            "🌐 <b>Tilni tanlang / Выберите язык:</b>\n\n"
            "MarketPulse Core interfeysi, hisobotlar va Excel fayllar tanlangan tilda ishlaydi."
        ),
        "btn_lang_uz": "🇺🇿 O'zbekcha",
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_language": "🌐 Til / Язык",
        "language_saved": (
            "✅ Til muvaffaqiyatli o'zgartirildi: <b>🇺🇿 O'zbekcha</b>\n"
            "🕒 Vaqt mintaqasi: <b>Toshkent (UTC+5)</b>"
        ),
        "tz_tashkent": "Toshkent (UTC+5)",
        "tz_moscow": "Moskva (MSK, UTC+3)",
        "btn_tz_tashkent": "🇺🇿 Toshkent (UTC+5)",
        "btn_tz_moscow": "🇷🇺 Moskva (MSK, UTC+3)",
        "tz_saved_toast": "✅ Vaqt mintaqasi: {timezone}",
        "tz_saved_msg": (
            "✅ Vaqt mintaqasi yangilandi: <b>{timezone}</b>\n"
            "🕒 Hozirgi vaqt: <b>{now_time}</b>\n"
            "⏰ Kunlik avtomatik hisobot vaqti: <b>{schedule_time}</b>"
        ),
        # Asosiy menyu va tugmalar
        "main_menu_text": (
            "🚀 <b>MarketPulse Core — Boshqaruv Paneli</b>\n\n"
            "⏰ Avtomatik kunlik hisobot vaqti: <b>{schedule_time}</b> ({timezone})\n"
            "🕒 Hozirgi vaqt: <b>{now_time}</b>\n"
            "🟣 Uzum Seller API: <b>{uzum_status}</b>\n"
            "🟠 Ozon Seller API: <b>{ozon_status}</b>\n"
            "📦 Katalogdagi tovarlar: <b>{catalog_count} ta</b> | 🌐 Veb-manbalar: <b>{sources_count} ta</b>\n\n"
            "Kerakli amalni quyidagi tugmalar orqali tanlang:\n\n"
            "{zero_storage_rule}"
        ),
        "btn_my_catalog": "📦 Mening katalogim",
        "btn_recheck_now": "🔄 Hozir qayta tekshirish",
        "btn_set_time": "⏰ Vaqtni o'rnatish",
        "btn_add_source": "➕ Sayt/Mahsulot qo'shish",
        "btn_sources": "📋 Manbalar",
        "btn_cancel": "❌ Bekor qilish",
        "btn_back": "🔙 Ortga",
        "btn_main_menu": "🔙 Bosh menyu",
        "action_cancelled": "❌ Amal bekor qilindi.",
        "action_cancelled_toast": "Amal bekor qilindi.",
        # Qayta tekshirish
        "scan_in_progress_alert": "⏳ Tekshirilmoqda, iltimos kuting...",
        "scan_started_toast": "⏳ Tekshirilmoqda...",
        "scan_started_msg": (
            "⏳ Tekshirilmoqda... Mahsulotlar yig'ilib, tahlil va Excel hisobot tayyorlanmoqda."
        ),
        "excel_caption": (
            "📊 MarketPulse Core — {filename}\n"
            "🕒 Tayyorlangan vaqt: {timestamp} ({timezone})\n\n"
            "{zero_storage_rule}"
        ),
        # Vaqt o'rnatish (Schedule)
        "btn_custom_time": "✍️ Boshqa vaqt yozish",
        "choose_time_prompt": (
            "⏰ <b>Avtomatik hisobot vaqtini tanlang</b>\n"
            "📅 Belgilangan vaqt: <b>{current_time}</b> ({timezone})\n"
            "🕒 Hozirgi vaqt: <b>{now_time}</b>\n\n"
            "Quyidagi tayyor vaqtlardan birini bosing, vaqt mintaqasini tanlang yoki o'zingiz xohlagan vaqtni yozing:"
        ),
        "invalid_time_toast": "❌ Noto'g'ri vaqt formati.",
        "time_saved_toast": "✅ Vaqt {time} ga o'rnatildi!",
        "time_saved_msg": (
            "✅ Kunlik avtomatik hisobot vaqti <b>{time}</b> ({timezone}) "
            "qilib saqlandi va jadval yangilandi!"
        ),
        "ask_custom_time": (
            "✍️ Kunlik hisobot vaqtini <code>HH:MM</code> formatida yozing "
            "(masalan: <code>07:30</code> yoki <code>19:45</code>):"
        ),
        "invalid_custom_time": (
            "⚠️ Noto'g'ri format! Iltimos, vaqtni <code>HH:MM</code> ko'rinishida yozing "
            "(masalan: <code>09:30</code> yoki <code>20:15</code>):"
        ),
        # Manbalar (veb-saytlar)
        "sources_empty": (
            "📋 <b>Kuzatilayotgan veb-manbalar</b>\n\n"
            "Hozircha qo'shimcha veb-sayt qo'shilmagan.\n"
            "Yangi havola qo'shish uchun <b>➕ Sayt/Mahsulot qo'shish</b> tugmasini bosing."
        ),
        "sources_header": "📋 <b>Kuzatilayotgan veb-manbalar ro'yxati:</b>\n",
        "sources_item_mode": "   ⚙️ Rejim: {mode} ({domain})",
        "sources_footer": "\nKeraksiz havolani o'chirish uchun pastdagi mos tugmani bosing:",
        "btn_delete_source": "🗑 O'chirish #{index} ({domain})",
        "ask_source_url": (
            "🔗 Kuzatmoqchi bo'lgan yangi sayt yoki mahsulot havolasini (URL) yuboring.\n"
            "Masalan: <code>https://uzum.uz/uz/product/788418</code> yoki istalgan do'kon sahifasi.\n\n"
            "ℹ️ Agar sayt <code>sites_config.json</code> da bo'lmasa, <b>Universal Fallback</b> "
            "(JSON-LD / meta / DOM) avtomatik ishga tushadi."
        ),
        "invalid_url": (
            "⚠️ Noto'g'ri havola! Iltimos, <code>http://</code> yoki <code>https://</code> "
            "bilan boshlanadigan to'liq manzil yuboring (masalan: <code>https://uzum.uz/uz/product/788418</code>):"
        ),
        "parser_mode_config": "sites_config.json (maxsus selektor)",
        "parser_mode_fallback": "Universal Fallback (avtomatik)",
        "source_added": (
            "✅ <b>Yangi havola bazaga qo'shildi!</b>\n\n"
            "🌐 Manzil: <code>{url}</code>\n"
            "⚙️ Parser rejimi: {mode} (<code>{domain}</code>)\n"
            "📊 Jami kuzatilayotgan manbalar: <b>{count} ta</b>\n\n"
            "Darhol tekshirish uchun quyidagi <b>«🔄 Hozir qayta tekshirish»</b> tugmasini bosing."
        ),
        "source_exists": (
            "ℹ️ Ushbu havola bazada allaqachon mavjud:\n<code>{url}</code>\n\n"
            "📊 Jami kuzatilayotgan manbalar: <b>{count} ta</b>"
        ),
        "invalid_source_id": "❌ Noto'g'ri manba ID.",
        "source_deleted_toast": "🗑 Manba o'chirildi!",
        "source_deleted_msg": "🗑 Manba o'chirildi: <code>{url}</code>\n\n",
        "source_already_deleted": "ℹ️ Manba allaqachon o'chirilgan.",
        # Mening katalogim
        "btn_prev_page": "⬅️ Oldingi",
        "btn_next_page": "Keyingi ➡️",
        "btn_refresh_catalog": "🔄 Katalogni yangilash",
        "first_page_toast": "Siz birinchi sahifadasiz.",
        "last_page_toast": "Siz oxirgi sahifadasiz.",
        "catalog_empty": (
            "📦 <b>Mening katalogim bo'sh</b>\n\n"
            "Uzum Market do'koningizdan tovarlar va ombor qoldiqlarini yuklash uchun "
            "pastdagi <b>🔄 Katalogni yangilash</b> tugmasini bosing."
        ),
        "catalog_header": (
            "📦 <b>Mening katalogim</b> ({total} ta tovar)\n"
            "📄 Sahifa: <b>{page}/{total_pages}</b> | "
            "⚠️ Kam qoldiq (&lt;5): <b>{low_stock} ta</b>\n\n"
            "Batafsil ko'rish va aqlli kalkulyator uchun tovarni tanlang:"
        ),
        "catalog_refreshing_toast": "⏳ Katalog yangilanmoqda...",
        "catalog_refreshing_msg": "⏳ Uzum Market'dan tovarlar va ombor qoldiqlari yangilanmoqda...",
        "catalog_refresh_failed": (
            "⚠️ Uzum Seller API dan tovarlar yuklanmadi. <code>.env</code> dagi "
            "<code>UZUM_API_KEY</code> ni tekshiring."
        ),
        "catalog_refreshed": (
            "✅ <b>Katalog muvaffaqiyatli yangilandi!</b> ({count} ta tovar)\n"
            "📄 Sahifa: <b>1/{total_pages}</b>\n\n"
            "Tovarni tanlang:"
        ),
        "invalid_product_id": "❌ Noto'g'ri tovar ID.",
        "product_not_found": "❌ Tovar katalogda topilmadi.",
        "product_card_sku": "🏷️ SKU: <code>{sku}</code>",
        "product_card_price": "💰 Joriy narxi: <b>{price}</b>",
        "product_card_stock": "{icon} Ombordagi qoldig'i: <b>{stock} ta</b>",
        "product_card_commission": "📊 Komissiya foizi: <b>{commission:g}%</b>",
        "product_card_logistics": "🚚 Logistika to'lovi: <b>{logistics}</b>",
        "btn_smart_calculator": "🧮 Aqlli kalkulyator",
        "btn_competitors": "👀 Raqobatchilar",
        "btn_back_to_catalog": "🔙 Katalogga qaytish",
        "btn_back_to_product": "🔙 Tovarga qaytish",
        # Demo-rejim (Portfolio mijozlari uchun xavfsiz rejim)
        "demo_banner": (
            "🎭 <b>Siz Demo-rejimdasiz.</b> Bu yerda namunaviy tovarlar orqali barcha bo'limlarni — "
            "katalog, aqlli kalkulyator, Excel hisobot, jadval va raqobatchilar monitoringini "
            "sinab ko'rishingiz mumkin."
        ),
        "demo_main_menu_text": (
            "{demo_banner}\n\n"
            "🚀 <b>MarketPulse Core — Demo Panel</b>\n\n"
            "⏰ Demo kunlik hisobot vaqti: <b>{schedule_time}</b> ({timezone})\n"
            "🕒 Hozirgi vaqt: <b>{now_time}</b>\n"
            "📦 Namunaviy tovarlar: <b>{catalog_count} ta</b> | 🌐 Veb-manbalar: <b>{sources_count} ta</b>\n"
            "⚠️ Kam qoldiq (&lt;5): <b>{low_stock} ta</b> | 🔒 Rejim: <b>Zero-Leak (Demo)</b>\n\n"
            "Barcha imkoniyatlarni sinab ko'rish uchun quyidagi tugmalardan birini tanlang:"
        ),
        "btn_demo_stock_alerts": "📉 Qoldiqlar nazorati (Demo)",
        "demo_readonly_alert": (
            "🎭 Demo-rejimda real do'kon bazasi va API ga o'zgartirish kiritish cheklangan. "
            "Barcha bo'limlarni namunaviy ma'lumotlarda bemalol sinab ko'rishingiz mumkin."
        ),
        "demo_scan_started": (
            "🎭 Demo-rejim: namunaviy ma'lumotlar asosida tahlil va dizaynli Excel hisobot tayyorlanmoqda..."
        ),
        "demo_catalog_refreshed": (
            "✅ <b>Demo-katalog yangilandi!</b> ({count} ta namunaviy tovar)\n"
            "📄 Sahifa: <b>1/{total_pages}</b>\n\n"
            "Tovarni tanlang:"
        ),
        "demo_comp_refreshed": (
            "✅ <b>Demo-tekshiruv yakunlandi!</b>\n"
            "Quyida raqobatchilar narxi va sizdan arzonroq sotuv bo'lganda keladigan "
            "qizil signal namunasini ko'rishingiz mumkin:\n\n"
        ),
        "demo_tz_saved_msg": (
            "🎭 <b>Demo-rejim:</b> Vaqt mintaqasi yangilandi: <b>{timezone}</b>\n"
            "🕒 Hozirgi vaqt: <b>{now_time}</b>\n"
            "⏰ Demo hisobot vaqti: <b>{schedule_time}</b>"
        ),
        "demo_time_saved_msg": (
            "🎭 <b>Demo-rejim:</b> Kunlik hisobot vaqti <b>{time}</b> ({timezone}) qilib sinab ko'rildi!\n"
            "<i>Real versiyada bu vaqt avtomatik jadvalga (APScheduler) ulanadi.</i>"
        ),
        "demo_sources_readonly": (
            "🎭 Demo-rejimda namunaviy veb-manbalarni ko'rishingiz mumkin. "
            "Real havola qo'shish va o'chirish faqat Admin rejimida ishlaydi."
        ),
        # Aqlli kalkulyator
        "calc_title": "🧮 <b>Aqlli kalkulyator</b>",
        "calc_sell_price": "• Sotuv narxi: <b>{price}</b>",
        "calc_commission": "• Marketplace komissiyasi ({percent:g}%): <b>-{amount}</b>",
        "calc_logistics": "• Logistika to'lovi: <b>-{amount}</b>",
        "calc_net_payout": "✅ Marketplace ushlab qolganidan keyin qoladigan summa: <b>{amount}</b>",
        "btn_try_other_price": "✏️ Boshqa narxda sinash",
        "ask_calc_price": (
            "✏️ <b>Boshqa narxda sinash</b>\n"
            "📦 {name}\n\n"
            "Sinab ko'rmoqchi bo'lgan yangi sotuv narxini raqamda yozing (masalan: <code>145000</code>):"
        ),
        "invalid_calc_price": (
            "⚠️ Noto'g'ri narx! Iltimos, musbat raqam kiriting (masalan: <code>145000</code>):"
        ),
        # Qoldiqlar nazorati (Stock Alert)
        "stock_alert_title": "📉 <b>Qoldiqlar nazorati (Stock Alert)</b>\n",
        "stock_alert_line": "⚠️ Qoldiq kam qoldi: <b>{name}</b> — atigi <b>{qty}</b> ta qoldi!",
        # Raqobatchilar (qo'lda kiritilgan havolalar)
        "btn_add_competitor": "➕ Raqobatchi havolasini qo'shish",
        "btn_check_competitors": "🔄 Narxlarni hozir tekshirish",
        "btn_delete_competitor": "🗑 Raqobatchini o'chirish",
        "btn_back_to_competitors": "🔙 Raqobatchilarga qaytish",
        "comp_title": "👀 <b>Raqobatchilar kuzatuvi</b>",
        "comp_product_line": "📦 Tovar: <b>{name}</b>",
        "comp_our_price": "💰 Sizning narxingiz: <b>{price}</b>",
        "comp_empty": (
            "Hozircha bu tovarga raqobatchi havolasi qo'shilmagan.\n\n"
            "Kuzatishni boshlash uchun pastdagi <b>➕ Raqobatchi havolasini qo'shish</b> tugmasini bosing."
        ),
        "comp_diff_cheaper": "🔴 sizdan <b>-{diff}</b> arzon",
        "comp_diff_pricier": "🟢 sizdan <b>+{diff}</b> qimmat",
        "comp_diff_equal": "🟡 narx teng",
        "comp_price_unknown": "<i>Narx aniqlanmadi</i>",
        "comp_open_link": "Havolani ochish",
        "comp_link_word": "Havola",
        "comp_ask_url": (
            "➕ <b>Raqobatchi havolasini qo'shish</b>\n"
            "📦 Tovar: <b>{name}</b>\n\n"
            "Raqobatchining mahsulot havolasini (URL) yuboring "
            "(masalan: <code>https://uzum.uz/uz/product/...</code>):"
        ),
        "comp_exists": "ℹ️ Ushbu havola allaqachon kuzatuv ro'yxatida bor:\n<code>{url}</code>\n\n",
        "comp_checking_new": "⏳ Raqobatchi havolasi saqlandi! Hozir narxi tekshirilmoqda...",
        "comp_added_checked": "✅ <b>Raqobatchi muvaffaqiyatli qo'shildi va tekshirildi!</b>\n\n",
        "comp_need_at_least_one": "ℹ️ Avval kamida 1 ta raqobatchi havolasini qo'shing.",
        "comp_checking_toast": "⏳ Raqobatchi narxlari tekshirilmoqda...",
        "comp_checking_many": "⏳ {count} ta raqobatchi havolasi parser orqali tekshirilmoqda...",
        "comp_refreshed": "✅ <b>Raqobatchi narxlari yangilandi!</b>\n\n",
        "comp_none_to_delete": "ℹ️ O'chirish uchun raqobatchi yo'q.",
        "comp_choose_delete": "🗑 <b>Qaysi raqobatchini o'chirmoqchisiz?</b>\n📦 Tovar: <b>{name}</b>",
        "comp_invalid_data": "❌ Noto'g'ri ma'lumot.",
        "comp_already_deleted": "ℹ️ Raqobatchi allaqachon o'chirilgan.",
        "comp_deleted_toast": "🗑 Raqobatchi o'chirildi!",
        "comp_deleted_msg": "🗑 O'chirildi: <code>{url}</code>\n\n",
        "comp_price_changed_header": "🔔 <b>Raqobatchilar narxini o'zgartirdi:</b>\n\n",
        "comp_undercut_alert": (
            "🔴 <b>DIQQAT! Raqobatchi sizdan arzonroq sotyapti!</b>\n"
            "📦 Tovar: <b>{product_name}</b>\n"
            "🏪 Raqobatchi: {comp_name}\n"
            "Sizning narxingiz: <b>{our_price}</b> | "
            "Raqobatchi: <b>{comp_price}</b> | "
            "Farq: <b>-{diff}</b> | "
            "<a href=\"{url}\">Havola</a>"
        ),
        # Analytics hisobot matni
        "analytics_title": "📊 MarketPulse Core — Narxlar Monitoringi ({date}, {timezone})",
        "analytics_empty": "⚠️ Hozircha ma'lumotlar bazasida mahsulotlar mavjud emas.",
        "analytics_summary_header": "📌 UMUMIY KO'RSATKICHLAR:",
        "analytics_total": "• Jami kuzatilayotgan mahsulotlar: {count} ta",
        "analytics_dropped": "• 📉 Narxi tushganlar (arzonlashgan): {count} ta",
        "analytics_increased": "• 📈 Narxi oshganlar (qimmatlashgan): {count} ta",
        "analytics_unchanged": "• ➖ Narxi o'zgarmaganlar: {count} ta",
        "analytics_new": "• 🆕 Yangi qo'shilgan mahsulotlar: {count} ta",
        "analytics_avg_price": "• 💰 O'rtacha bozor narxi: {price}",
        "analytics_cheapest": "• 🏷️ Eng arzon mahsulot: {name} ({price})",
        "analytics_priciest": "• 💎 Eng qimmat mahsulot: {name} ({price})",
        "analytics_by_currency_header": "💱 VALYUTALAR KESIMIDA BOZOR NARXLARI:",
        "analytics_no_currency": "Valyutasiz",
        "analytics_currency_line": "• [{currency}] ({count} ta) — o'rtacha: {avg} | min: {min_p} | max: {max_p}",
        "analytics_top3_header": "🏆 ENG KATTA NARX O'ZGARISHI (TOP-3):",
        "analytics_no_changes": (
            "• Ushbu tekshiruvda narx o'zgarishi aniqlanmadi "
            "(ilk monitoring yoki barcha narxlar barqaror)."
        ),
        "analytics_dropped_header": "📉 NARXI TUSHGAN MAHSULOTLAR:",
        "analytics_increased_header": "📈 NARXI OSHGAN MAHSULOTLAR:",
        "analytics_stock_signals_header": "⚠️ OMBOR VA VOZVRAT SIGNALLARI:",
        "analytics_out_of_stock": "• 🔴 Omborda tugagan mahsulotlar: {count} ta",
        "analytics_high_return": (
            "• ↩️ Yuqori vozvrat: {name} ({pct:.1f}% | sotilgan: {sold}, qaytgan: {returned})"
        ),
        "analytics_footer": "📎 Batafsil ma'lumotlar kunlik Excel hisobotda keltirilgan.",
        # Excel hisobot
        "excel_filename_prefix": "hisobot",
        "excel_sheet_title": "Narxlar Monitoringi",
        "excel_col_num": "№",
        "excel_col_name": "Mahsulot nomi",
        "excel_col_old_price": "Eski narx",
        "excel_col_new_price": "Yangi narx",
        "excel_col_currency": "Valyuta",
        "excel_col_diff": "Farq",
        "excel_col_pct": "O'zgarish (%)",
        "excel_col_status": "Holati",
        "excel_col_rating": "Reyting",
        "excel_col_date": "Oxirgi sana",
        "excel_col_url": "Havola",
        "excel_status_new": "Yangi",
        "excel_status_dropped": "Arzonlashdi",
        "excel_status_increased": "Qimmatlashdi",
        "excel_status_unchanged": "O'zgarmadi",
        "excel_stats_header": "UMUMIY STATISTIKA",
        "excel_stats_total": "Jami mahsulotlar soni:",
        "excel_stats_dropped": "Arzonlashgan mahsulotlar soni:",
        "excel_stats_increased": "Qimmatlashgan mahsulotlar soni:",
        "excel_stats_unchanged": "O'zgarmagan / yangi mahsulotlar:",
    },
    "ru": {
        # Umumiy va ruxsat
        "access_denied": "⛔ Доступ запрещён",
        "currency_uzs": "сум",
        "unit_pcs": "шт.",
        "status_connected": "Подключён ✅",
        "status_not_configured": "Не настроен (через .env)",
        "zero_storage_rule": (
            "📌 Важное правило: В целях безопасности все файлы отчётов сразу удаляются с сервера "
            "после отправки и хранятся только в этом Telegram-чате. Нужные архивные файлы вы можете "
            "найти только в истории этого чата — бот не сможет отправить их повторно."
        ),
        "zero_result_alert": "⚠️ ВНИМАНИЕ: Возможно, изменилась структура сайта — найдено 0 товаров!",
        "generic_error": (
            "❌ Во время мониторинга произошла ошибка. "
            "Подробности записаны в файл <code>logs/marketpulse.log</code>."
        ),
        "excel_not_found": "❌ Файл Excel-отчёта не найден.",
        "file_too_large": (
            "⚠️ ПРЕДУПРЕЖДЕНИЕ: Размер файла '{filename}' составляет {size_mb:.2f} МБ — "
            "превышен лимит {limit_mb} МБ, отправка файла в Telegram отменена."
        ),
        "unknown_message_hint": (
            "ℹ️ Чтобы открыть панель управления, отправьте /start или воспользуйтесь кнопками ниже:"
        ),
        # Til tanlash
        "choose_language_prompt": (
            "🌐 <b>Tilni tanlang / Выберите язык:</b>\n\n"
            "Интерфейс MarketPulse Core, аналитика и Excel-отчёты будут формироваться на выбранном языке."
        ),
        "btn_lang_uz": "🇺🇿 O'zbekcha",
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_language": "🌐 Til / Язык",
        "language_saved": (
            "✅ Язык успешно изменён: <b>🇷🇺 Русский</b>\n"
            "🕒 Часовой пояс: <b>Москва (МСК, UTC+3)</b>"
        ),
        "tz_tashkent": "Ташкент (UTC+5)",
        "tz_moscow": "Москва (МСК, UTC+3)",
        "btn_tz_tashkent": "🇺🇿 Ташкент (UTC+5)",
        "btn_tz_moscow": "🇷🇺 Москва (МСК, UTC+3)",
        "tz_saved_toast": "✅ Часовой пояс: {timezone}",
        "tz_saved_msg": (
            "✅ Часовой пояс обновлён: <b>{timezone}</b>\n"
            "🕒 Текущее время: <b>{now_time}</b>\n"
            "⏰ Время ежедневного автоотчёта: <b>{schedule_time}</b>"
        ),
        # Asosiy menyu va tugmalar
        "main_menu_text": (
            "🚀 <b>MarketPulse Core — Панель управления</b>\n\n"
            "⏰ Ежедневный автоотчёт: <b>{schedule_time}</b> ({timezone})\n"
            "🕒 Текущее время: <b>{now_time}</b>\n"
            "🟣 Uzum Seller API: <b>{uzum_status}</b>\n"
            "🟠 Ozon Seller API: <b>{ozon_status}</b>\n"
            "📦 Товаров в каталоге: <b>{catalog_count} шт.</b> | 🌐 Веб-источников: <b>{sources_count} шт.</b>\n\n"
            "Выберите нужное действие с помощью кнопок ниже:\n\n"
            "{zero_storage_rule}"
        ),
        "btn_my_catalog": "📦 Мой каталог",
        "btn_recheck_now": "🔄 Проверить сейчас",
        "btn_set_time": "⏰ Настроить время",
        "btn_add_source": "➕ Добавить сайт/товар",
        "btn_sources": "📋 Источники",
        "btn_cancel": "❌ Отмена",
        "btn_back": "🔙 Назад",
        "btn_main_menu": "🔙 Главное меню",
        "action_cancelled": "❌ Действие отменено.",
        "action_cancelled_toast": "Действие отменено.",
        # Qayta tekshirish
        "scan_in_progress_alert": "⏳ Идёт проверка, пожалуйста, подождите...",
        "scan_started_toast": "⏳ Проверка запущена...",
        "scan_started_msg": (
            "⏳ Идёт проверка... Собираем данные, выполняем расчёт аналитики и формируем Excel-отчёт."
        ),
        "excel_caption": (
            "📊 MarketPulse Core — {filename}\n"
            "🕒 Сформировано: {timestamp} ({timezone})\n\n"
            "{zero_storage_rule}"
        ),
        # Vaqt o'rnatish (Schedule)
        "btn_custom_time": "✍️ Ввести другое время",
        "choose_time_prompt": (
            "⏰ <b>Выберите время ежедневного отчёта</b>\n"
            "📅 Установленное время: <b>{current_time}</b> ({timezone})\n"
            "🕒 Текущее время: <b>{now_time}</b>\n\n"
            "Выберите один из готовых вариантов, переключите часовой пояс (Москва / Ташкент) или укажите своё время:"
        ),
        "invalid_time_toast": "❌ Неверный формат времени.",
        "time_saved_toast": "✅ Время установлено на {time}!",
        "time_saved_msg": (
            "✅ Время ежедневного автоотчёта сохранено: <b>{time}</b> ({timezone}). "
            "Расписание обновлено!"
        ),
        "ask_custom_time": (
            "✍️ Введите время отправки ежедневного отчёта в формате <code>ЧЧ:ММ</code> "
            "(например: <code>07:30</code> или <code>19:45</code>):"
        ),
        "invalid_custom_time": (
            "⚠️ Неверный формат! Укажите время в виде <code>ЧЧ:ММ</code> "
            "(например: <code>09:30</code> или <code>20:15</code>):"
        ),
        # Manbalar (veb-saytlar)
        "sources_empty": (
            "📋 <b>Отслеживаемые веб-источники</b>\n\n"
            "Дополнительные сайты пока не добавлены.\n"
            "Чтобы добавить ссылку, нажмите <b>➕ Добавить сайт/товар</b>."
        ),
        "sources_header": "📋 <b>Список отслеживаемых веб-источников:</b>\n",
        "sources_item_mode": "   ⚙️ Режим: {mode} ({domain})",
        "sources_footer": "\nЧтобы удалить ненужную ссылку, нажмите соответствующую кнопку ниже:",
        "btn_delete_source": "🗑 Удалить #{index} ({domain})",
        "ask_source_url": (
            "🔗 Отправьте ссылку (URL) на сайт или карточку товара для отслеживания.\n"
            "Например: <code>https://uzum.uz/uz/product/788418</code> или страница любого интернет-магазина.\n\n"
            "ℹ️ Если домена нет в <code>sites_config.json</code>, автоматически включится "
            "<b>Universal Fallback</b> (JSON-LD / meta / DOM)."
        ),
        "invalid_url": (
            "⚠️ Некорректная ссылка! Отправьте полный URL, начинающийся с "
            "<code>http://</code> или <code>https://</code> (например: <code>https://uzum.uz/uz/product/788418</code>):"
        ),
        "parser_mode_config": "sites_config.json (настроенные селекторы)",
        "parser_mode_fallback": "Universal Fallback (автоопределение)",
        "source_added": (
            "✅ <b>Новая ссылка добавлена в базу!</b>\n\n"
            "🌐 Ссылка: <code>{url}</code>\n"
            "⚙️ Режим парсера: {mode} (<code>{domain}</code>)\n"
            "📊 Всего отслеживаемых источников: <b>{count} шт.</b>\n\n"
            "Для мгновенной проверки нажмите <b>«🔄 Проверить сейчас»</b>."
        ),
        "source_exists": (
            "ℹ️ Эта ссылка уже есть в базе:\n<code>{url}</code>\n\n"
            "📊 Всего отслеживаемых источников: <b>{count} шт.</b>"
        ),
        "invalid_source_id": "❌ Неверный ID источника.",
        "source_deleted_toast": "🗑 Источник удалён!",
        "source_deleted_msg": "🗑 Источник удалён: <code>{url}</code>\n\n",
        "source_already_deleted": "ℹ️ Источник уже был удалён.",
        # Mening katalogim
        "btn_prev_page": "⬅️ Назад",
        "btn_next_page": "Далее ➡️",
        "btn_refresh_catalog": "🔄 Обновить каталог",
        "first_page_toast": "Вы на первой странице.",
        "last_page_toast": "Вы на последней странице.",
        "catalog_empty": (
            "📦 <b>Мой каталог пуст</b>\n\n"
            "Чтобы загрузить товары и остатки из вашего магазина Uzum Market, "
            "нажмите кнопку <b>🔄 Обновить каталог</b> ниже."
        ),
        "catalog_header": (
            "📦 <b>Мой каталог</b> ({total} товаров)\n"
            "📄 Страница: <b>{page}/{total_pages}</b> | "
            "⚠️ Низкий остаток (&lt;5): <b>{low_stock} шт.</b>\n\n"
            "Выберите товар для просмотра карточки и умного калькулятора:"
        ),
        "catalog_refreshing_toast": "⏳ Обновление каталога...",
        "catalog_refreshing_msg": "⏳ Загружаем товары и остатки со склада Uzum Market...",
        "catalog_refresh_failed": (
            "⚠️ Не удалось загрузить товары из Uzum Seller API. Проверьте "
            "<code>UZUM_API_KEY</code> в файле <code>.env</code>."
        ),
        "catalog_refreshed": (
            "✅ <b>Каталог успешно обновлён!</b> ({count} товаров)\n"
            "📄 Страница: <b>1/{total_pages}</b>\n\n"
            "Выберите товар:"
        ),
        "invalid_product_id": "❌ Неверный ID товара.",
        "product_not_found": "❌ Товар не найден в каталоге.",
        "product_card_sku": "🏷️ SKU: <code>{sku}</code>",
        "product_card_price": "💰 Текущая цена: <b>{price}</b>",
        "product_card_stock": "{icon} Остаток на складе: <b>{stock} шт.</b>",
        "product_card_commission": "📊 Комиссия маркетплейса: <b>{commission:g}%</b>",
        "product_card_logistics": "🚚 Логистика: <b>{logistics}</b>",
        "btn_smart_calculator": "🧮 Умный калькулятор",
        "btn_competitors": "👀 Конкуренты",
        "btn_back_to_catalog": "🔙 Назад в каталог",
        "btn_back_to_product": "🔙 Назад к товару",
        # Demo-rejim (Portfolio mijozlari uchun xavfsiz rejim)
        "demo_banner": (
            "🎭 <b>Вы в Демо-режиме.</b> Здесь вы можете протестировать все разделы — "
            "каталог, умный калькулятор, Excel-отчёт, расписание и мониторинг конкурентов "
            "на демонстрационных товарах."
        ),
        "demo_main_menu_text": (
            "{demo_banner}\n\n"
            "🚀 <b>MarketPulse Core — Демо-панель</b>\n\n"
            "⏰ Демо-расписание отчёта: <b>{schedule_time}</b> ({timezone})\n"
            "🕒 Текущее время: <b>{now_time}</b>\n"
            "📦 Демо-товаров: <b>{catalog_count} шт.</b> | 🌐 Веб-источников: <b>{sources_count} шт.</b>\n"
            "⚠️ Низкий остаток (&lt;5): <b>{low_stock} шт.</b> | 🔒 Режим: <b>Zero-Leak (Демо)</b>\n\n"
            "Выберите любой раздел ниже, чтобы протестировать возможности бота:"
        ),
        "btn_demo_stock_alerts": "📉 Контроль остатков (Демо)",
        "demo_readonly_alert": (
            "🎭 В Демо-режиме изменение реальной базы и запуск API отключены. "
            "Все разделы можно свободно протестировать на демонстрационных данных."
        ),
        "demo_scan_started": (
            "🎭 Демо-режим: формируем аналитику и готовый Excel-отчёт на демонстрационных данных..."
        ),
        "demo_catalog_refreshed": (
            "✅ <b>Демо-каталог обновлён!</b> ({count} демонстрационных товаров)\n"
            "📄 Страница: <b>1/{total_pages}</b>\n\n"
            "Выберите товар:"
        ),
        "demo_comp_refreshed": (
            "✅ <b>Демо-проверка завершена!</b>\n"
            "Ниже показаны цены конкурентов и пример красного сигнала, когда конкурент "
            "продаёт дешевле вас:\n\n"
        ),
        "demo_tz_saved_msg": (
            "🎭 <b>Демо-режим:</b> Часовой пояс обновлён: <b>{timezone}</b>\n"
            "🕒 Текущее время: <b>{now_time}</b>\n"
            "⏰ Время демо-отчёта: <b>{schedule_time}</b>"
        ),
        "demo_time_saved_msg": (
            "🎭 <b>Демо-режим:</b> Время ежедневного отчёта <b>{time}</b> ({timezone}) успешно протестировано!\n"
            "<i>В боевом режиме оно автоматически подключается к расписанию (APScheduler).</i>"
        ),
        "demo_sources_readonly": (
            "🎭 В Демо-режиме можно просматривать примеры веб-источников. "
            "Добавление и удаление реальных ссылок доступно только в режиме администратора."
        ),
        # Aqlli kalkulyator
        "calc_title": "🧮 <b>Умный калькулятор</b>",
        "calc_sell_price": "• Цена продажи: <b>{price}</b>",
        "calc_commission": "• Комиссия маркетплейса ({percent:g}%): <b>-{amount}</b>",
        "calc_logistics": "• Стоимость логистики: <b>-{amount}</b>",
        "calc_net_payout": "✅ Сумма к выплате после удержаний маркетплейса: <b>{amount}</b>",
        "btn_try_other_price": "✏️ Проверить другую цену",
        "ask_calc_price": (
            "✏️ <b>Расчёт для другой цены</b>\n"
            "📦 {name}\n\n"
            "Введите новую цену продажи числом (например: <code>145000</code>):"
        ),
        "invalid_calc_price": (
            "⚠️ Некорректная цена! Введите положительное число (например: <code>145000</code>):"
        ),
        # Qoldiqlar nazorati (Stock Alert)
        "stock_alert_title": "📉 <b>Контроль остатков (Stock Alert)</b>\n",
        "stock_alert_line": "⚠️ Низкий остаток: <b>{name}</b> — осталось всего <b>{qty}</b> шт.!",
        # Raqobatchilar (qo'lda kiritilgan havolalar)
        "btn_add_competitor": "➕ Добавить ссылку конкурента",
        "btn_check_competitors": "🔄 Проверить цены сейчас",
        "btn_delete_competitor": "🗑 Удалить конкурента",
        "btn_back_to_competitors": "🔙 Назад к конкурентам",
        "comp_title": "👀 <b>Мониторинг конкурентов</b>",
        "comp_product_line": "📦 Товар: <b>{name}</b>",
        "comp_our_price": "💰 Ваша цена: <b>{price}</b>",
        "comp_empty": (
            "К этому товару пока не привязаны ссылки конкурентов.\n\n"
            "Чтобы начать мониторинг, нажмите <b>➕ Добавить ссылку конкурента</b> ниже."
        ),
        "comp_diff_cheaper": "🔴 дешевле вас на <b>-{diff}</b>",
        "comp_diff_pricier": "🟢 дороже вас на <b>+{diff}</b>",
        "comp_diff_equal": "🟡 цена совпадает",
        "comp_price_unknown": "<i>Цена не определена</i>",
        "comp_open_link": "Открыть ссылку",
        "comp_link_word": "Ссылка",
        "comp_ask_url": (
            "➕ <b>Добавление ссылки конкурента</b>\n"
            "📦 Товар: <b>{name}</b>\n\n"
            "Отправьте ссылку (URL) на карточку товара конкурента "
            "(например: <code>https://uzum.uz/uz/product/...</code>):"
        ),
        "comp_exists": "ℹ️ Эта ссылка уже находится в списке мониторинга:\n<code>{url}</code>\n\n",
        "comp_checking_new": "⏳ Ссылка сохранена! Проверяем текущую цену конкурента...",
        "comp_added_checked": "✅ <b>Конкурент добавлен и проверен!</b>\n\n",
        "comp_need_at_least_one": "ℹ️ Сначала добавьте хотя бы 1 ссылку конкурента.",
        "comp_checking_toast": "⏳ Проверяем цены конкурентов...",
        "comp_checking_many": "⏳ Проверяем {count} ссылок конкурентов через парсер...",
        "comp_refreshed": "✅ <b>Цены конкурентов обновлены!</b>\n\n",
        "comp_none_to_delete": "ℹ️ Нет конкурентов для удаления.",
        "comp_choose_delete": "🗑 <b>Какого конкурента удалить?</b>\n📦 Товар: <b>{name}</b>",
        "comp_invalid_data": "❌ Некорректные данные.",
        "comp_already_deleted": "ℹ️ Конкурент уже был удалён.",
        "comp_deleted_toast": "🗑 Конкурент удалён!",
        "comp_deleted_msg": "🗑 Удалено: <code>{url}</code>\n\n",
        "comp_price_changed_header": "🔔 <b>Конкуренты изменили цены:</b>\n\n",
        "comp_undercut_alert": (
            "🔴 <b>ВНИМАНИЕ! Конкурент продаёт дешевле вас!</b>\n"
            "📦 Товар: <b>{product_name}</b>\n"
            "🏪 Конкурент: {comp_name}\n"
            "Ваша цена: <b>{our_price}</b> | "
            "Конкурент: <b>{comp_price}</b> | "
            "Разница: <b>-{diff}</b> | "
            "<a href=\"{url}\">Ссылка</a>"
        ),
        # Analytics hisobot matni
        "analytics_title": "📊 MarketPulse Core — Мониторинг цен ({date}, {timezone})",
        "analytics_empty": "⚠️ В базе данных пока нет товаров.",
        "analytics_summary_header": "📌 ОСНОВНЫЕ ПОКАЗАТЕЛИ:",
        "analytics_total": "• Всего отслеживаемых товаров: {count} шт.",
        "analytics_dropped": "• 📉 Подешевели: {count} шт.",
        "analytics_increased": "• 📈 Подорожали: {count} шт.",
        "analytics_unchanged": "• ➖ Без изменений: {count} шт.",
        "analytics_new": "• 🆕 Новые товары: {count} шт.",
        "analytics_avg_price": "• 💰 Средняя рыночная цена: {price}",
        "analytics_cheapest": "• 🏷️ Самый дешёвый товар: {name} ({price})",
        "analytics_priciest": "• 💎 Самый дорогой товар: {name} ({price})",
        "analytics_by_currency_header": "💱 РЫНОЧНЫЕ ЦЕНЫ ПО ВАЛЮТАМ:",
        "analytics_no_currency": "Без валюты",
        "analytics_currency_line": "• [{currency}] ({count} шт.) — средняя: {avg} | мин: {min_p} | макс: {max_p}",
        "analytics_top3_header": "🏆 НАИБОЛЬШИЕ ИЗМЕНЕНИЯ ЦЕН (ТОП-3):",
        "analytics_no_changes": (
            "• В этой проверке изменений цен не выявлено "
            "(первый запуск или все цены стабильны)."
        ),
        "analytics_dropped_header": "📉 ТОВАРЫ СО СНИЖЕНИЕМ ЦЕНЫ:",
        "analytics_increased_header": "📈 ТОВАРЫ С ПОВЫШЕНИЕМ ЦЕНЫ:",
        "analytics_stock_signals_header": "⚠️ СИГНАЛЫ ПО ОСТАТКАМ И ВОЗВРАТАМ:",
        "analytics_out_of_stock": "• 🔴 Нет в наличии на складе: {count} шт.",
        "analytics_high_return": (
            "• ↩️ Высокий процент возвратов: {name} ({pct:.1f}% | продано: {sold}, возвращено: {returned})"
        ),
        "analytics_footer": "📎 Подробная таблица прикреплена в ежедневном Excel-отчёте.",
        # Excel hisobot
        "excel_filename_prefix": "otchet",
        "excel_sheet_title": "Мониторинг цен",
        "excel_col_num": "№",
        "excel_col_name": "Название товара",
        "excel_col_old_price": "Старая цена",
        "excel_col_new_price": "Новая цена",
        "excel_col_currency": "Валюта",
        "excel_col_diff": "Разница",
        "excel_col_pct": "Изменение (%)",
        "excel_col_status": "Статус",
        "excel_col_rating": "Рейтинг",
        "excel_col_date": "Последнее обновление",
        "excel_col_url": "Ссылка",
        "excel_status_new": "Новый",
        "excel_status_dropped": "Снизилась",
        "excel_status_increased": "Выросла",
        "excel_status_unchanged": "Без изменений",
        "excel_stats_header": "ОБЩАЯ СТАТИСТИКА",
        "excel_stats_total": "Всего товаров:",
        "excel_stats_dropped": "Подешевело:",
        "excel_stats_increased": "Подорожало:",
        "excel_stats_unchanged": "Без изменений / новые:",
    },
}


def tilni_normallashtirish(lang: str | None) -> str:
    """Til kodini tekshirib `uz` yoki `ru` qaytaradi (standart: `uz`)."""
    kod = (lang or "uz").strip().lower()
    return kod if kod in QULLAB_QUVVATLANADIGAN_TILLAR else "uz"


def t(key: str, lang: str = "uz", **kwargs: Any) -> str:
    """
    Berilgan kalit (`key`) bo'yicha tanlangan tildagi (`uz` yoki `ru`) matnni qaytaradi.
    Agar qo'shimcha parametrlar (`kwargs`) berilsa, matnni formatlaydi.
    """
    til = tilni_normallashtirish(lang)
    matn = TEXTS[til].get(key, TEXTS["uz"].get(key, key))
    if kwargs:
        return matn.format(**kwargs)
    return matn


def valyuta_yorligi(valyuta: str, lang: str = "uz") -> str:
    """Valyutani tanlangan tilga mos ko'rinishda qaytaradi (masalan: so'm -> сум)."""
    toza = (valyuta or "").strip()
    if toza.lower() in ("so'm", "som", "сум", "uzs"):
        return t("currency_uzs", lang)
    return toza


def vaqt_mintaqasi_yorligi(tz_nomi: str, lang: str = "uz") -> str:
    """IANA vaqt mintaqasi nomini foydalanuvchi tilida chiroyli ko'rinishda qaytaradi."""
    toza = (tz_nomi or "").strip()
    if toza == "Europe/Moscow":
        return t("tz_moscow", lang)
    if toza == "Asia/Tashkent":
        return t("tz_tashkent", lang)
    return toza or t("tz_tashkent", lang)
