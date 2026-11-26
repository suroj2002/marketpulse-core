"""
MarketPulse Core — Xabarnoma moduli (Telegram va xavfsiz n8n Webhook).

Xususiyatlari:
- Hech qanday token yoki kalit kod ichida saqlanmaydi (faqat .env dan olinadi).
- Internet uzilib qolsa yoki vaqtinchalik xato bo'lsa, 5 soniya kutib jami 3 marta
  qayta urinadi (retry) va barcha so'rovlarda timeout=60 soniya ishlatadi.
- 45 MB dan katta fayllarni yuborishdan oldin ogohlantirish beradi (Telegram limiti).
- .env da N8N_WEBHOOK_URL ko'rsatilgan bo'lsa, X-API-KEY sarlavhasi bilan Webhook'ga,
  aks holda to'g'ridan-to'g'ri Telegram Bot API ga yuboradi.
"""

import os
from pathlib import Path
import socket
import time

from dotenv import load_dotenv
import requests
import urllib3.util.connection as urllib3_cn

from utils import hozirgi_vaqt, loggerni_olish


logger = loggerni_olish("notifier")

MAKS_URINISHLAR = 3
QAYTA_URINISH_PAUZA = 5
SO_ROV_TIMEOUT = 60
MAKS_FAYL_HAJMI_MB = 45
MAKS_FAYL_HAJMI_BAYT = MAKS_FAYL_HAJMI_MB * 1024 * 1024


def _maxfiylikni_yashirish(matn: str, maxfiy_qiymatlar: list[str]) -> str:
    """Xato matnidan maxfiy token va API kalitlarni yashiradi."""
    natija = matn
    for qiymat in maxfiy_qiymatlar:
        if qiymat:
            natija = natija.replace(qiymat, "***")
    return natija


def _fayl_hajmini_tekshirish(fayl_yoli: Path) -> bool:
    """
    Fayl hajmi 45 MB dan oshmaganini tekshiradi.
    Agar 45 MB dan katta bo'lsa, ogohlantirish chiqarib False qaytaradi.
    """
    hajm_bayt = fayl_yoli.stat().st_size
    hajm_mb = hajm_bayt / (1024 * 1024)

    if hajm_bayt > MAKS_FAYL_HAJMI_BAYT:
        ogohlantirish = (
            f"⚠️ OGOHLANTIRISH: '{fayl_yoli.name}' fayl hajmi {hajm_mb:.2f} MB — "
            f"{MAKS_FAYL_HAJMI_MB} MB chegarasidan katta! Telegram chekloviga tushmaslik "
            "uchun fayl yuborilmadi."
        )
        print(f"[Notifier] {ogohlantirish}")
        logger.warning(ogohlantirish)
        return False

    return True


def _sorov_yuborish(
    url: str,
    data: dict[str, str],
    headers: dict[str, str] | None = None,
    fayl_yoli: Path | None = None,
    fayl_maydoni: str = "document",
    proksi: dict[str, str] | None = None,
    timeout: int = SO_ROV_TIMEOUT,
    maks_urinish: int = MAKS_URINISHLAR,
    pauza: int = QAYTA_URINISH_PAUZA,
    maxfiy_qiymatlar: list[str] | None = None,
) -> requests.Response:
    """
    HTTP POST so'rovini timeout=60 va 3 martalik qayta urinish (har urinishda 5 soniya pauza)
    himoyasi bilan yuboradi.
    """
    maxfiylar = maxfiy_qiymatlar or []

    for urinish in range(1, maks_urinish + 1):
        try:
            if fayl_yoli is not None:
                with fayl_yoli.open("rb") as fayl:
                    javob = requests.post(
                        url,
                        data=data,
                        headers=headers,
                        files={fayl_maydoni: (fayl_yoli.name, fayl)},
                        proxies=proksi,
                        timeout=timeout,
                    )
            else:
                javob = requests.post(
                    url,
                    data=data,
                    headers=headers,
                    proxies=proksi,
                    timeout=timeout,
                )

            # 429 (Too Many Requests) yoki 5xx server xatolarida qayta urinamiz
            if javob.status_code == 429 and urinish < maks_urinish:
                kutish = pauza
                try:
                    retry_after = int(javob.json().get("parameters", {}).get("retry_after", pauza))
                    kutish = max(pauza, retry_after + 1)
                except ValueError:
                    pass
                xabar = (
                    f"Server limiti (429), {kutish} soniya kutib qayta urinilmoqda "
                    f"({urinish}/{maks_urinish})..."
                )
                print(f"[Notifier] {xabar}")
                logger.warning(xabar)
                time.sleep(kutish)
                continue

            if 500 <= javob.status_code < 600 and urinish < maks_urinish:
                xabar = (
                    f"Server vaqtinchalik xatosi ({javob.status_code}), "
                    f"{pauza} soniya kutib qayta urinilmoqda ({urinish}/{maks_urinish})..."
                )
                print(f"[Notifier] {xabar}")
                logger.warning(xabar)
                time.sleep(pauza)
                continue

            javob.raise_for_status()
            return javob

        except (requests.ConnectionError, requests.Timeout) as tarmoq_xatosi:
            xavfsiz = _maxfiylikni_yashirish(str(tarmoq_xatosi), maxfiylar)
            if urinish < maks_urinish:
                xabar = (
                    f"Tarmoq/ulanish xatosi ({urinish}/{maks_urinish}): {xavfsiz}. "
                    f"{pauza} soniya kutib qayta urinilmoqda..."
                )
                print(f"[Notifier] {xabar}")
                logger.warning(xabar)
                time.sleep(pauza)
                continue
            raise

    raise requests.RequestException("Barcha qayta urinishlar muvaffaqiyatsiz tugadi.")


def _matnni_bolish(matn: str, maks_uzunlik: int = 4000) -> list[str]:
    """Uzun xabarlarni Telegram cheklovidan oshmaydigan bo'laklarga ajratadi."""
    if len(matn) <= maks_uzunlik:
        return [matn]

    bolaklar: list[str] = []
    joriy_bolak: list[str] = []
    joriy_uzunlik = 0

    for qator in matn.splitlines(keepends=True):
        if joriy_uzunlik + len(qator) > maks_uzunlik and joriy_bolak:
            bolaklar.append("".join(joriy_bolak))
            joriy_bolak = [qator]
            joriy_uzunlik = len(qator)
        else:
            joriy_bolak.append(qator)
            joriy_uzunlik += len(qator)

    if joriy_bolak:
        bolaklar.append("".join(joriy_bolak))

    return bolaklar


def _webhookga_yuborish(
    webhook_url: str,
    api_key: str,
    hisobot_matni: str,
    fayl_yoli: Path | None = None,
    turi: str = "hisobot",
) -> bool:
    """Xavfsiz n8n Webhook manziliga X-API-KEY sarlavhasi bilan yuboradi."""
    logger.info("n8n Webhook orqali yuborish boshlandi (turi=%s)...", turi)
    sarlavhalar: dict[str, str] = {}
    if api_key:
        sarlavhalar["X-API-KEY"] = api_key

    malumot = {
        "turi": turi,
        "hisobot_matni": hisobot_matni,
        "yuborilgan_vaqt": hozirgi_vaqt().strftime("%Y-%m-%d %H:%M:%S"),
    }

    yuboriladigan_fayl: Path | None = None
    if fayl_yoli is not None:
        if not fayl_yoli.exists():
            xabar = f"Excel fayl topilmadi: {fayl_yoli}"
            print(f"[Webhook] OGOHLANTIRISH: {xabar}")
            logger.warning(xabar)
            return False
        if _fayl_hajmini_tekshirish(fayl_yoli):
            yuboriladigan_fayl = fayl_yoli
            malumot["fayl_nomi"] = fayl_yoli.name
        else:
            malumot["hisobot_matni"] += (
                f"\n\n⚠️ Diqqat: '{fayl_yoli.name}' fayli {MAKS_FAYL_HAJMI_MB} MB dan "
                "katta bo'lgani sababli ilova qilinmadi."
            )

    try:
        _sorov_yuborish(
            url=webhook_url,
            data=malumot,
            headers=sarlavhalar,
            fayl_yoli=yuboriladigan_fayl,
            fayl_maydoni="file",
            timeout=SO_ROV_TIMEOUT,
            maks_urinish=MAKS_URINISHLAR,
            pauza=QAYTA_URINISH_PAUZA,
            maxfiy_qiymatlar=[api_key, webhook_url],
        )
        print("[Webhook] Ma'lumot va hisobot n8n Webhook'ga muvaffaqiyatli yuborildi.")
        logger.info("n8n Webhook orqali yuborish muvaffaqiyatli yakunlandi (turi=%s).", turi)
        return True
    except requests.RequestException as xato:
        xavfsiz = _maxfiylikni_yashirish(str(xato), [api_key, webhook_url])
        print(f"[Webhook] Xatolik yuz berdi (hisobot lokal saqlangan): {xavfsiz}")
        logger.error("n8n Webhook yuborishda xatolik: %s", xavfsiz)
        return False


def telegramga_yuborish(hisobot_matni: str, excel_fayl_yoli: str) -> bool:
    """
    Hisobot matni va Excel faylni yuboradi:
    - Agar .env da N8N_WEBHOOK_URL mavjud bo'lsa -> Webhook'ga (X-API-KEY bilan);
    - Aks holda -> Telegram Bot API orqali yuboradi.
    """
    load_dotenv()

    webhook_url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    n8n_api_key = os.getenv("N8N_API_KEY", "").strip()

    # 1-variant: Xavfsiz n8n Webhook zaxirasi faol bo'lsa
    if webhook_url:
        return _webhookga_yuborish(
            webhook_url=webhook_url,
            api_key=n8n_api_key,
            hisobot_matni=hisobot_matni,
            fayl_yoli=Path(excel_fayl_yoli),
            turi="hisobot",
        )

    # 2-variant: Oddiy Telegram Bot API
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    proksi_url = os.getenv("TELEGRAM_PROXY", "").strip()

    if not bot_token or not chat_id:
        print("Telegram sozlanmagan, hisobot lokal saqlandi")
        logger.info("Telegram va Webhook sozlanmagan — hisobot lokal saqlandi.")
        return False

    logger.info("Telegram orqali hisobot yuborish boshlandi...")
    proksi = {"http": proksi_url, "https": proksi_url} if proksi_url else None
    asosiy_api = f"https://api.telegram.org/bot{bot_token}"
    eski_oila = urllib3_cn.allowed_gai_family
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

    try:
        fayl_yoli = Path(excel_fayl_yoli)
        fayl_yuborish_mumkin = False
        matn_yuborish = hisobot_matni

        if not fayl_yoli.exists():
            xabar = f"Excel fayl topilmadi: {excel_fayl_yoli}"
            print(f"[Telegram] OGOHLANTIRISH: {xabar}")
            logger.warning(xabar)
            return False

        if _fayl_hajmini_tekshirish(fayl_yoli):
            fayl_yuborish_mumkin = True
        else:
            matn_yuborish += (
                f"\n\n⚠️ OGOHLANTIRISH: '{fayl_yoli.name}' fayl hajmi "
                f"{MAKS_FAYL_HAJMI_MB} MB dan katta bo'lgani uchun Telegram'ga yuborilmadi."
            )

        # 1. Tahliliy matnni yuborish
        for bolak in _matnni_bolish(matn_yuborish):
            _sorov_yuborish(
                url=f"{asosiy_api}/sendMessage",
                data={"chat_id": chat_id, "text": bolak},
                proksi=proksi,
                timeout=SO_ROV_TIMEOUT,
                maks_urinish=MAKS_URINISHLAR,
                pauza=QAYTA_URINISH_PAUZA,
                maxfiy_qiymatlar=[bot_token],
            )

        # 2. Excel hisobot faylini (agar 45 MB dan oshmagan bo'lsa) hujjat sifatida yuborish
        if fayl_yuborish_mumkin:
            _sorov_yuborish(
                url=f"{asosiy_api}/sendDocument",
                data={
                    "chat_id": chat_id,
                    "caption": f"📊 MarketPulse Core — {fayl_yoli.name}",
                },
                fayl_yoli=fayl_yoli,
                fayl_maydoni="document",
                proksi=proksi,
                timeout=SO_ROV_TIMEOUT,
                maks_urinish=MAKS_URINISHLAR,
                pauza=QAYTA_URINISH_PAUZA,
                maxfiy_qiymatlar=[bot_token],
            )
            print("[Telegram] Tahliliy matn va Excel hisobot muvaffaqiyatli yuborildi.")
            logger.info("Telegram'ga tahliliy matn va '%s' muvaffaqiyatli yuborildi.", fayl_yoli.name)
        else:
            print("[Telegram] Tahliliy matn yuborildi (Excel fayl 45 MB dan katta edi).")
            logger.warning("Telegram'ga faqat matn yuborildi (fayl 45 MB limitidan oshgan).")

        return True

    except requests.RequestException as xato:
        xavfsiz_xato = _maxfiylikni_yashirish(str(xato), [bot_token])
        print(f"[Telegram] Xatolik yuz berdi (hisobot lokal saqlangan): {xavfsiz_xato}")
        logger.error("Telegram'ga yuborishda xatolik: %s", xavfsiz_xato)
        return False
    finally:
        urllib3_cn.allowed_gai_family = eski_oila


def ogohlantirish_yuborish(ogohlantirish_matni: str) -> bool:
    """
    Parser 0 ta mahsulot topganda yoki kritik hodisa yuz berganda,
    bo'sh Excel yubormasdan faqat ogohlantirish xabarini yuboradi.
    """
    load_dotenv()

    webhook_url = os.getenv("N8N_WEBHOOK_URL", "").strip()
    n8n_api_key = os.getenv("N8N_API_KEY", "").strip()

    if webhook_url:
        return _webhookga_yuborish(
            webhook_url=webhook_url,
            api_key=n8n_api_key,
            hisobot_matni=ogohlantirish_matni,
            fayl_yoli=None,
            turi="ogohlantirish",
        )

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    proksi_url = os.getenv("TELEGRAM_PROXY", "").strip()

    if not bot_token or not chat_id:
        print("Telegram sozlanmagan, ogohlantirish faqat lokal logga yozildi")
        logger.warning("Telegram sozlanmagan — ogohlantirish yuborilmadi: %s", ogohlantirish_matni)
        return False

    logger.warning("Telegram'ga ogohlantirish xabari yuborilmoqda...")
    proksi = {"http": proksi_url, "https": proksi_url} if proksi_url else None
    asosiy_api = f"https://api.telegram.org/bot{bot_token}"
    eski_oila = urllib3_cn.allowed_gai_family
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET

    try:
        for bolak in _matnni_bolish(ogohlantirish_matni):
            _sorov_yuborish(
                url=f"{asosiy_api}/sendMessage",
                data={"chat_id": chat_id, "text": bolak},
                proksi=proksi,
                timeout=SO_ROV_TIMEOUT,
                maks_urinish=MAKS_URINISHLAR,
                pauza=QAYTA_URINISH_PAUZA,
                maxfiy_qiymatlar=[bot_token],
            )
        print("[Telegram] Ogohlantirish xabari muvaffaqiyatli yuborildi.")
        logger.info("Telegram'ga ogohlantirish xabari muvaffaqiyatli yuborildi.")
        return True
    except requests.RequestException as xato:
        xavfsiz_xato = _maxfiylikni_yashirish(str(xato), [bot_token])
        print(f"[Telegram] Ogohlantirish yuborishda xatolik: {xavfsiz_xato}")
        logger.error("Telegram'ga ogohlantirish yuborishda xatolik: %s", xavfsiz_xato)
        return False
    finally:
        urllib3_cn.allowed_gai_family = eski_oila
