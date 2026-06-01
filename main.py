import feedparser
import requests
import time
import json
import os
import re
from datetime import datetime

# ===================== KONFIGURASI =====================
BOT_TOKEN = "8921896859:AAF7biUHKm_sD5rdpVvB9ybnxMYXCzvfozk"
CHAT_ID = "-1003890278221"
THREAD_ID = 11480
RSS_URL = "https://www.financialjuice.com/feed.ashx?xy=rss"
CHECK_INTERVAL = 60
SENT_FILE = "sent_ids.json"
TITLES_FILE = "sent_titles.json"
# =======================================================

# === FILTER 1: Data Ekonomi Major ===
DATA_EKONOMI_KEYWORDS = [
    # Format data ekonomi (Actual/Forecast/Previous)
    "actual", "forecast", "previous",

    # USD - Amerika
    "nfp", "non-farm", "nonfarm",
    "cpi", "pce", "gdp",
    "unemployment", "jobless",
    "retail sales", "ism", "pmi",
    "durable goods", "housing",
    "trade balance", "eia",
    "baker hughes", "rig count",
    "jolts", "adp",

    # EUR - Eropa
    "eurozone", "euro zone",
    "german", "germany",
    "france", "italy", "spain",
    "ifo", "zew", "sentix",

    # JPY - Jepang
    "japan", "japanese",
    "tankan", "tokyo cpi",

    # GBP - Inggris
    "uk ", "united kingdom", "britain",

    # CHF - Swiss
    "swiss", "switzerland",

    # AUD - Australia
    "australia", "australian",

    # NZD - Selandia Baru
    "new zealand",

    # CAD - Kanada
    "canada", "canadian",

    # CNH - China
    "china", "chinese",
]

# === FILTER 2: Bank Sentral & Suku Bunga ===
BANK_SENTRAL_KEYWORDS = [
    # Keputusan suku bunga
    "rate decision", "interest rate",
    "rate hike", "rate cut", "rate hold",
    "basis points", "bps",

    # Risalah
    "minutes",

    # Kebijakan moneter
    "monetary policy", "forward guidance",
    "quantitative", "balance sheet",

    # Nama pejabat Fed
    "powell", "daly", "waller", "kugler",
    "jefferson", "barkin", "bostic",

    # Nama pejabat BoE
    "bailey", "pill", "mann",

    # Nama pejabat ECB
    "lagarde", "lane", "schnabel",

    # Nama pejabat BoJ
    "ueda", "himino",

    # Nama pejabat lainnya
    "macklem", "bullock", "orr",
    "jordan", "schlegel",

    # Nama bank sentral
    "federal reserve", "fomc",
    "bank of england", "boe",
    "ecb", "boj", "rba", "rbnz",
    "snb", "pboc", "boc",
]

# === FILTER 3: Ekspektasi/Probabilitas Suku Bunga ===
EKSPEKTASI_KEYWORDS = [
    # Probabilitas
    "probability", "probabilitas",
    "odds", "pricing in",
    "market expects", "market pricing",
    "market bets", "market see",
    "swaps", "futures imply",
    "futures price", "traders price",

    # Ekspektasi cut/hold/hike
    "expected to cut", "expected to hold", "expected to hike",
    "likely to cut", "likely to hold", "likely to hike",
    "chances of cut", "chances of hike",
    "cut in", "hike in",
    "no cut", "no hike",
    "rate expectations", "rate outlook",
    "dovish", "hawkish",
]

# === FILTER 4: Ringkasan Per Sesi ===
SESI_KEYWORDS = [
    "market wrap", "market summary", "market review",
    "asia wrap", "asian wrap", "asia session",
    "europe wrap", "european wrap", "europe open",
    "us wrap", "us open", "us session",
    "london wrap", "london open",
    "daily wrap", "weekly wrap",
    "fx option expiries", "option expiries",
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

def load_sent_titles():
    if os.path.exists(TITLES_FILE):
        with open(TITLES_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent_titles(sent_titles):
    with open(TITLES_FILE, "w") as f:
        json.dump(list(sent_titles), f)

def normalize_title(title):
    title = title.lower().strip()
    title = re.sub(r'[^a-z0-9\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title

def extract_tradingview_chart(description):
    if not description:
        return None
    if "tradingview" not in description.lower():
        return None
    match = re.search(r'chart["\s:]+["\s]*([A-Za-z0-9]{8})', description)
    if match:
        return match.group(1)
    return "found"

def is_high_impact(title, description):
    title_lower = title.lower()

    # Cek chart TradingView di description
    if extract_tradingview_chart(description):
        return True, "chart"

    # Cek data ekonomi major
    for kw in DATA_EKONOMI_KEYWORDS:
        if kw in title_lower:
            return True, "data"

    # Cek bank sentral & suku bunga
    for kw in BANK_SENTRAL_KEYWORDS:
        if kw in title_lower:
            return True, "bank"

    # Cek ekspektasi/probabilitas suku bunga
    for kw in EKSPEKTASI_KEYWORDS:
        if kw in title_lower:
            return True, "ekspektasi"

    # Cek ringkasan sesi
    for kw in SESI_KEYWORDS:
        if kw in title_lower:
            return True, "sesi"

    return False, None

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

def get_category_emoji(category):
    return {
        "chart": "📊",
        "data": "📈",
        "bank": "🏦",
        "ekspektasi": "🎯",
        "sesi": "🌍",
    }.get(category, "🚨")

def format_message(entry, translated_title, category, chart_id=None):
    pub_date = entry.get("published", "")
    link = entry.get("link", "")
    emoji = get_category_emoji(category)

    message = (
        f"🚨 <b>HIGH IMPACT ALERT</b> {emoji}\n\n"
        f"🇮🇩 <b>{translated_title}</b>\n\n"
        f"🔗 <a href='{link}'>Baca selengkapnya</a>\n"
        f"🕐 {pub_date}"
    )

    if chart_id and chart_id != "found":
        chart_url = f"https://www.tradingview.com/chart/{chart_id}/"
        message += f"\n📊 <a href='{chart_url}'>Lihat Chart TradingView</a>"
    elif chart_id == "found":
        message += f"\n📊 <a href='{link}'>Lihat Chart di FinancialJuice</a>"

    return message

def main():
    print("🤖 Bot FinancialJuice HIGH IMPACT dimulai...")
    sent_ids = load_sent_ids()
    sent_titles = load_sent_titles()

    if not sent_ids:
        print("📋 Loading berita lama...")
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:
            entry_id = entry.get("id", entry.get("link", ""))
            sent_ids.add(entry_id)
            title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
            sent_titles.add(normalize_title(title))
        save_sent_ids(sent_ids)
        save_sent_titles(sent_titles)
        print(f"✅ {len(sent_ids)} berita lama dilewati. Menunggu berita BARU...")

    while True:
        try:
            print(f"🔍 Cek RSS... ({datetime.now().strftime('%H:%M:%S')})")
            feed = feedparser.parse(RSS_URL)

            new_count = 0
            for entry in feed.entries:
                entry_id = entry.get("id", entry.get("link", ""))

                # Lapis 1: cek ID
                if entry_id in sent_ids:
                    continue

                original_title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
                description = entry.get("description", "") or entry.get("summary", "")
                normalized = normalize_title(original_title)

                # Lapis 2: cek judul (permanen, tidak hilang saat restart)
                if normalized in sent_titles:
                    print(f"🔄 Duplikat: {original_title[:60]}...")
                    sent_ids.add(entry_id)
                    save_sent_ids(sent_ids)
                    continue

                hit, category = is_high_impact(original_title, description)

                if hit:
                    chart_id = extract_tradingview_chart(description)
                    print(f"⚡ [{category.upper()}] {original_title[:70]}...")
                    translated = translate_to_indonesian(original_title)
                    message = format_message(entry, translated, category, chart_id)
                    send_to_telegram(message)
                    sent_titles.add(normalized)
                    save_sent_titles(sent_titles)
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
