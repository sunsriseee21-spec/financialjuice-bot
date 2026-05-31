import feedparser
import requests
import time
import json
import os
from datetime import datetime

# ===================== KONFIGURASI =====================
BOT_TOKEN = "8921896859:AAF7biUHKm_sD5rdpVvB9ybnxMYXCzvfozk"
CHAT_ID = "-1003890278221"
THREAD_ID = 11480
RSS_URL = "https://www.financialjuice.com/feed.ashx?xy=rss"
CHECK_INTERVAL = 60  # cek tiap 60 detik
SENT_FILE = "sent_ids.json"
# =======================================================

def load_sent_ids():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent_ids(sent_ids):
    with open(SENT_FILE, "w") as f:
        json.dump(list(sent_ids), f)

def translate_to_indonesian(text):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "id",
            "dt": "t",
            "q": text
        }
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        translated = ""
        for item in result[0]:
            if item[0]:
                translated += item[0]
        return translated
    except Exception as e:
        print(f"Translate error: {e}")
        return text

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": THREAD_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Terkirim!")
        else:
            print(f"❌ Gagal: {response.text}")
    except Exception as e:
        print(f"❌ Error telegram: {e}")

def format_message(entry, translated_title, original_title):
    pub_date = entry.get("published", "")
    link = entry.get("link", "")
    message = (
        f"📰 <b>FinancialJuice News</b>\n\n"
        f"🇮🇩 <b>{translated_title}</b>\n\n"
        f"🇬🇧 <i>{original_title}</i>\n\n"
        f"🔗 <a href='{link}'>Baca selengkapnya</a>\n"
        f"🕐 {pub_date}"
    )
    return message

def main():
    print("🤖 Bot FinancialJuice TEST MODE (semua berita) dimulai...")
    
    # Kosongkan sent_ids agar semua berita baru masuk
    sent_ids = set()

    # Isi dulu sent_ids dengan berita yang sudah ada
    # agar tidak spam berita lama
    print("📋 Loading berita lama...")
    feed = feedparser.parse(RSS_URL)
    for entry in feed.entries:
        entry_id = entry.get("id", entry.get("link", ""))
        sent_ids.add(entry_id)
    save_sent_ids(sent_ids)
    print(f"✅ {len(sent_ids)} berita lama dilewati. Menunggu berita BARU...")

    while True:
        try:
            print(f"🔍 Cek RSS... ({datetime.now().strftime('%H:%M:%S')})")
            feed = feedparser.parse(RSS_URL)

            new_count = 0
            for entry in feed.entries:
                entry_id = entry.get("id", entry.get("link", ""))

                if entry_id in sent_ids:
                    continue

                # Berita baru! Langsung kirim tanpa filter
                original_title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
                print(f"📨 Berita baru: {original_title[:70]}...")
                
                translated = translate_to_indonesian(original_title)
                message = format_message(entry, translated, original_title)
                send_to_telegram(message)
                sent_ids.add(entry_id)
                new_count += 1
                time.sleep(2)

            save_sent_ids(sent_ids)
            if new_count == 0:
                print("💤 Tidak ada berita baru.")

        except Exception as e:
            print(f"❌ Error: {e}")

        print(f"⏳ Tunggu {CHECK_INTERVAL} detik...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
