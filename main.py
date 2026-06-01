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
DATA_FILE = "bot_data.json"
# =======================================================

HARI_INDO = {
    "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
    "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
}

BULAN_INDO = {
    "Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr",
    "May": "Mei", "Jun": "Jun", "Jul": "Jul", "Aug": "Agu",
    "Sep": "Sep", "Oct": "Okt", "Nov": "Nov", "Dec": "Des"
}

def format_tanggal_indo(pub_date):
    """Ubah format tanggal ke Bahasa Indonesia"""
    try:
        # Format asli: Mon, 01 Jun 2026 10:36:11 GMT
        for en, id in HARI_INDO.items():
            pub_date = pub_date.replace(en, id)
        for en, id in BULAN_INDO.items():
            pub_date = pub_date.replace(en, id)
        return pub_date
    except:
        return pub_date

def get_flag_emoji(title):
    """Tentukan bendera/emoji berdasarkan isi berita"""
    title_lower = title.lower()

    # Grafik/Chart
    if any(k in title_lower for k in ["currency strength", "fx strength", "strongest", "weakest", "market wrap", "wrap", "imbalance", "option expiries"]):
        return "📊"

    # Geopolitik
    if any(k in title_lower for k in ["war", "attack", "missile", "nuclear", "blockade", "ceasefire", "strike", "military", "troops"]):
        return "🌍"

    # Amerika (USD)
    if any(k in title_lower for k in ["fed", "fomc", "powell", "daly", "waller", "us ", "u.s.", "united states", "america", "nfp", "non-farm", "cpi", "pce", "gdp", "unemployment", "jolts", "adp", "ism", "eia", "baker hughes", "white house", "trump", "pentagon"]):
        return "🇺🇸"

    # Eropa (EUR)
    if any(k in title_lower for k in ["ecb", "lagarde", "lane", "schnabel", "villeroy", "eurozone", "euro zone", "germany", "german", "france", "italy", "spain", "ifo", "zew"]):
        return "🇪🇺"

    # Inggris (GBP)
    if any(k in title_lower for k in ["boe", "bank of england", "bailey", "pill", "uk ", "united kingdom", "britain", "british"]):
        return "🇬🇧"

    # Jepang (JPY)
    if any(k in title_lower for k in ["boj", "bank of japan", "ueda", "himino", "japan", "japanese", "tankan", "takaichi"]):
        return "🇯🇵"

    # Swiss (CHF)
    if any(k in title_lower for k in ["snb", "swiss", "switzerland", "jordan", "schlegel"]):
        return "🇨🇭"

    # Australia (AUD)
    if any(k in title_lower for k in ["rba", "australia", "australian", "bullock"]):
        return "🇦🇺"

    # Selandia Baru (NZD)
    if any(k in title_lower for k in ["rbnz", "new zealand", "orr"]):
        return "🇳🇿"

    # Kanada (CAD)
    if any(k in title_lower for k in ["boc", "bank of canada", "macklem", "canada", "canadian"]):
        return "🇨🇦"

    # China (CNH)
    if any(k in title_lower for k in ["pboc", "china", "chinese", "yuan", "renminbi"]):
        return "🇨🇳"

    # Default
    return "📰"

DATA_EKONOMI_KEYWORDS = [
    "actual", "forecast", "previous",
    "nfp", "non-farm", "nonfarm",
    "cpi", "pce", "gdp",
    "unemployment", "jobless",
    "retail sales", "ism", "pmi",
    "durable goods", "housing",
    "trade balance", "eia",
    "baker hughes", "rig count",
    "jolts", "adp",
    "eurozone", "euro zone",
    "german", "germany",
    "france", "italy", "spain",
    "ifo", "zew", "sentix",
    "japan", "japanese", "tankan",
    "uk ", "united kingdom", "britain",
    "swiss", "switzerland",
    "australia", "australian",
    "new zealand",
    "canada", "canadian",
    "china", "chinese",
]

BANK_SENTRAL_KEYWORDS = [
    "rate decision", "interest rate",
    "rate hike", "rate cut", "rate hold",
    "basis points", "bps",
    "minutes",
    "monetary policy", "forward guidance",
    "quantitative", "balance sheet",
    "powell", "daly", "waller", "kugler",
    "jefferson", "barkin", "bostic",
    "bailey", "pill", "mann",
    "lagarde", "lane", "schnabel", "villeroy",
    "ueda", "himino", "takaichi",
    "macklem", "bullock", "orr",
    "jordan", "schlegel",
    "federal reserve", "fomc",
    "bank of england", "boe",
    "ecb", "boj", "rba", "rbnz",
    "snb", "pboc", "boc",
]

EKSPEKTASI_KEYWORDS = [
    "probability", "probabilitas",
    "odds", "pricing in",
    "market expects", "market pricing",
    "market bets", "swaps",
    "futures imply", "futures price",
    "expected to cut", "expected to hold", "expected to hike",
    "likely to cut", "likely to hold", "likely to hike",
    "rate expectations", "rate outlook",
    "dovish", "hawkish",
]

SESI_KEYWORDS = [
    "market wrap",
    "market summary", "market review",
    "market open", "market close",
    "asia wrap", "asian wrap",
    "europe wrap", "european wrap",
    "us wrap", "us open", "us session",
    "london wrap", "london open",
    "daily wrap", "weekly wrap",
    "fx option expiries", "option expiries",
    "moo imbalance", "moc imbalance",
    "currency strength", "fx strength",
    "strongest", "weakest",
]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("ids", [])), set(data.get("titles", []))
    return set(), set()

def save_data(sent_ids, sent_titles):
    with open(DATA_FILE, "w") as f:
        json.dump({
            "ids": list(sent_ids),
            "titles": list(sent_titles)
        }, f)

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

    if extract_tradingview_chart(description):
        return True, "chart"

    for kw in DATA_EKONOMI_KEYWORDS:
        if kw in title_lower:
            return True, "data"

    for kw in BANK_SENTRAL_KEYWORDS:
        if kw in title_lower:
            return True, "bank"

    for kw in EKSPEKTASI_KEYWORDS:
        if kw in title_lower:
            return True, "ekspektasi"

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

def format_message(entry, translated_title, chart_id=None):
    pub_date = format_tanggal_indo(entry.get("published", ""))
    link = entry.get("link", "")
    flag = get_flag_emoji(translated_title + " " + entry.get("title", ""))

    message = (
        f"📡 <b>FinancialJuice</b>\n\n"
        f"{flag} <b>{translated_title}</b>\n\n"
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
    sent_ids, sent_titles = load_data()

    if not sent_ids:
        print("📋 Loading berita lama...")
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:
            entry_id = entry.get("id", entry.get("link", ""))
            sent_ids.add(entry_id)
            title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
            sent_titles.add(normalize_title(title))
        save_data(sent_ids, sent_titles)
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
                description = entry.get("description", "") or entry.get("summary", "")
                normalized = normalize_title(original_title)

                if normalized in sent_titles:
                    print(f"🔄 Duplikat: {original_title[:60]}...")
                    sent_ids.add(entry_id)
                    save_data(sent_ids, sent_titles)
                    continue

                hit, category = is_high_impact(original_title, description)

                if hit:
                    chart_id = extract_tradingview_chart(description)
                    print(f"⚡ [{category.upper()}] {original_title[:70]}...")
                    translated = translate_to_indonesian(original_title)
                    message = format_message(entry, translated, chart_id)
                    send_to_telegram(message)
                    sent_titles.add(normalized)
                    sent_ids.add(entry_id)
                    save_data(sent_ids, sent_titles)
                    new_count += 1
                    time.sleep(2)
                else:
                    print(f"⏭ Skip: {original_title[:60]}...")
                    sent_ids.add(entry_id)

            save_data(sent_ids, sent_titles)
            if new_count == 0:
                print("💤 Tidak ada berita HIGH IMPACT baru.")

        except Exception as e:
            print(f"❌ Error: {e}")

        print(f"⏳ Tunggu {CHECK_INTERVAL} detik...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
