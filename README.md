# MarketPulse Core

**MarketPulse Core** — 100% Python asosidagi marketplace narxlar monitoringi, do'kon katalogi, aqlli kalkulyator, qoldiqlar nazorati, raqobatchilar kuzatuvi va Excel hisobot tizimi (Telegram bot + APScheduler).

Tashqi pullik AI API larsiz ishlaydi, 2 tilda (**O'zbekcha `uz`** / **Ruscha `ru`**) va 2 ta vaqt mintaqasida (**Toshkent UTC+5** / **Moskva МСК UTC+3**) xizmat ko'rsatadi.

---

## Asosiy imkoniyatlar

- **Rasmiy Seller API integratsiyalari**
  - **Uzum Market Seller OpenAPI** (`GET /v1/shops`, `GET /v1/product/shop/{shopId}`)
  - **Ozon Seller API** (`/v3/product/list`, `/v3/product/info/list`, `/v5/product/info/prices`)
  - **Universal Web Parser** (`Playwright` + `sites_config.json` + JSON-LD / meta / DOM fallback)
- **📦 Mening katalogim / Мой каталог** — sahifalangan (5 tadan) katalog, ombor qoldiqlari va 1 bosishda API orqali yangilash.
- **🧮 Aqlli kalkulyator / Умный калькулятор** — faqat marketplace komissiyasi (%) va logistika to'lovini hisoblab, qo'lga qoladigan summani ko'rsatadi; istalgan yangi narxda darhol qayta hisoblash (`✏️ Boshqa narxda sinash`).
- **👀 Raqobatchilar kuzatuvi / Мониторинг конкурентов** — har bir tovar kartochkasiga raqobatchi URL larini qo'shish, narx farqini ko'rish va raqobatchi sizdan arzonroq sotganda qizil ogohlantirish (`🔴`).
- **📉 Qoldiqlar nazorati (Stock Alert)** — omborda `qoldiq < 5` qolgan tovarlar bo'yicha avtomatik ogohlantirish.
- **📊 Dizaynli Excel hisobot** — `openpyxl` orqali ko'p valyutali, rangli indikatorli kunlik hisobot + **Zero-Storage** qoidasi (yuborilishi bilan `os.remove()` qilinadi).
- **🌐 2 til va 2 vaqt mintaqasi** — `🇺🇿 O'zbekcha` (`Asia/Tashkent`) va `🇷🇺 Русский` (`Europe/Moscow`, МСК) + `APScheduler` dinamik kunlik jadval.
- **🎭 Xavfsiz Demo-rejim (Zero-Leak)** — `.env` dagi `TELEGRAM_CHAT_ID` egasiga real do'kon paneli, boshqa istalgan foydalanuvchiga (portfolio mijozlariga) esa bazaga va API ga tegmaydigan namunaviy Demo-rejim ochiladi.

---

## Tezkor ishga tushirish (Lokal)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# .env fayliga TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID va UZUM_API_KEY kiriting
python bot.py
```

---

## Railway / Docker orqali 24/7 deploy

1. Loyihani **Dockerfile** orqali Railway'ga ulang (`mcr.microsoft.com/playwright/python:v1.57.0-noble` obrazi tayyor Chromium bilan tez build bo'ladi).
2. Railway servisiga `/data` nuqtasiga doimiy **Volume** ulang (`DB_PATH=/data/marketpulse.db`).
3. Railway **Variables** bo'limiga `.env.example` dagi kerakli o'zgaruvchilarni kiriting:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `UZUM_API_KEY` (ixtiyoriy: `UZUM_SHOP_ID`, `OZON_CLIENT_ID`, `OZON_API_KEY`)
   - `DB_PATH=/data/marketpulse.db`
   - `TIMEZONE=Asia/Tashkent`

---

## Xavfsizlik qoidalari

- Hech qanday token yoki API kalit kodga yozilmaydi — barcha maxfiy kalitlar faqat `.env` yoki server Environment Variables orqali olinadi.
- `.env`, `*.db`, `*.xlsx`, `logs/` va `.venv/` `.gitignore` va `.dockerignore` orqali to'liq himoyalangan.
