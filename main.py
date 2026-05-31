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
CHECK_INTERVAL = 60
SENT_FILE = "sent_ids.json"
# =======================================================

HIGH_IMPACT_KEYWORDS = [
    # === DATA EKONOMI ===
    "actual", "forecast", "previous",
    "nfp", "non-farm payroll", "nonfarm",
    "cpi", "pce", "gdp", "pdb",
    "unemployment", "jobless claims",
    "retail sales", "pmi", "ism",
    "trade balance", "housing", "durable goods",
    "eia", "crude oil inventories",
    "baker hughes", "rig count", "cftc",

    # === BANK SENTRAL & SUKU BUNGA ===
    "rate decision", "rate hike", "rate cut", "rate hold",
    "interest rate", "suku bunga",
    "monetary policy", "minutes", "forward guidance",
    "basis points", "bps", "quantitative",
    "fed", "fomc", "federal reserve",
    "powell", "daly", "waller", "kugler", "jefferson",
    "boe", "bank of england", "bailey",
    "ecb", "lagarde", "lane",
    "boj", "bank of japan", "ueda",
    "rba", "rbnz", "snb", "pboc",

    # === GEOPOLITIK ===
    "war", "attack", "missile", "nuclear",
    "blockade", "ceasefire", "hormuz",
    "iran", "israel", "ukraine", "russia",
    "hezbollah", "hamas", "sanctions",
    "trump", "white house", "pentagon", "nato",

    # === RINGKASAN PASAR ===
    "market wrap", "market summary",
    "asia wrap", "europe wrap", "us wrap",

    # === PASAR EKSTREM ===
    "all-time high", "all-time low",
    "record high", "record low",
    "crash", "collapse", "default",

    # === KOMODITAS & INDEKS ===
    "nymex", "brent", "wti",
    "s&p 500", "nasdaq", "dow",

    # === MOC/MOO IMBALANCE ===
    "moo imbalance", "moc imbalance",
]

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

def is_high_impact(title):
    title_lower = title.lower()
    for keyword in HIGH_IMPACT_KEYWORDS:
        if keyword in title_lower:
            return True
    return False

def normalize_title(title):
    """Normalisasi judul untuk deteksi duplikat"""
    import re
    title = title.lower().strip()
    title = re.sub(r'[^a-z0-9\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title

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

def format_message(entry, translated_title):
    pub_date = entry.get("published", "")
    link = entry.get("link", "")
    message = (
        f"🚨 <b>HIGH IMPACT ALERT</b>\n\n"
        f"🇮🇩 <b>{translated_title}</b>\n\n"
        f"🔗 <a href='{link}'>Baca selengkapnya</a>\n"
        f"🕐 {pub_date}"
    )
    return message

def main():
    print("🤖 Bot FinancialJuice HIGH IMPACT dimulai...")
    sent_ids = load_sent_ids()
    sent_titles = set()  # untuk cek duplikat berdasarkan judul

    # Pertama kali jalan, lewati semua berita lama
    if not sent_ids:
        print("📋 Loading berita lama...")
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:
            entry_id = entry.get("id", entry.get("link", ""))
            sent_ids.add(entry_id)
            title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
            sent_titles.add(normalize_title(title))
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

                original_title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
                normalized = normalize_title(original_title)

                # Cek duplikat berdasarkan judul
                if normalized in sent_titles:
                    print(f"🔄 Duplikat dilewati: {original_title[:60]}...")
                    sent_ids.add(entry_id)
                    continue

                if is_high_impact(original_title):
                    print(f"⚡ HIGH IMPACT: {original_title[:70]}...")
                    translated = translate_to_indonesian(original_title)
                    message = format_message(entry, translated)
                    send_to_telegram(message)
                    sent_titles.add(normalized)
                    new_count += 1
                    time.sleep(2)
                else:
                    print(f"⏭ Skip: {original_title[:60]}...")

                sent_ids.add(entry_id)

            save_sent_ids(sent_ids)
            if new_count == 0:
                print("💤 Tidak ada berita HIGH IMPACT baru.")

        except Exception as e:
            print(f"❌ Error: {e}")

        print(f"⏳ Tunggu {CHECK_INTERVAL} detik...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
