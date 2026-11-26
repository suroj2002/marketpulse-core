# MarketPulse Core — VPN'siz 24/7 server (Railway / VPS) uchun Docker obrazi
# Rasmiy Playwright Python obrazi barcha Linux kutubxonalari va Chromium v1.57.0 ni o'z ichiga oladi
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

# Python sozlamalari, standart vaqt mintaqasi va doimiy Volume baza yo'li
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tashkent \
    DB_PATH=/data/marketpulse.db

WORKDIR /app

# Obrazdagi tayyor Chromium bilan mos keluvchi playwright==1.57.0 ni o'rnatamiz
# (qo'shimcha ~200 MB brauzer qayta yuklanmaydi — build juda tez va yengil bo'ladi)
COPY requirements.txt .
RUN pip install --no-cache-dir playwright==1.57.0 \
    && pip install --no-cache-dir -r requirements.txt

# Loyiha kodlarini nusxalash (.dockerignore .env va vaqtinchalik fayllarni yashiradi)
COPY . .

# Doimiy ma'lumotlar bazasi (/data) va loglar (/app/logs) papkalarini yaratish
# Eslatma: Railway'da doimiy Volume servis sozlamalari orqali /data ga ulanadi
RUN mkdir -p /data /app/logs

# 24/7 interaktiv Telegram bot va APScheduler'ni ishga tushirish
CMD ["python", "bot.py"]
