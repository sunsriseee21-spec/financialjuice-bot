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
    "Mon": "Sen", "Tue": "Sel", "Wed": "Rab",
    "Thu": "Kam", "Fri": "Jum", "Sat": "Sab", "Sun": "Min"
}

BULAN_INDO = {
    "Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr",
    "May": "Mei", "Jun": "Jun", "Jul": "Jul", "Aug": "Agu",
    "Sep": "Sep", "Oct": "Okt", "Nov": "Nov", "Dec": "Des"
}

def format_tanggal_indo(pub_date):
    try:
        for en, id in HARI_INDO.items():
            pub_date = pub_date.replace(en, id)
        for en, id in BULAN_INDO.items():
            pub_date = pub_date.replace(en, id)
        return pub_date
    except:
        return pub_date

def get_flag_emoji(title):
    t = title.lower()

    # Grafik & Sesi (cek dulu)
    if any(k in t for k in ["currency strength", "fx strength", "strongest", "weakest",
                              "market wrap", "market summary", "asia wrap", "europe wrap",
                              "us wrap", "london wrap", "daily wrap", "weekly wrap",
                              "moo imbalance", "moc imbalance", "option expiries",
                              "need to know", "market risk"]):
        return "📊"

    # NZD
    if any(k in t for k in ["new zealand", "rbnz", "orr", "nzd"]):
        return "🇳🇿"

    # AUD
    if any(k in t for k in ["australia", "australian", "rba", "bullock", "aud"]):
        return "🇦🇺"

    # CAD
    if any(k in t for k in ["canada", "canadian", "boc", "bank of canada", "macklem", "cad"]):
        return "🇨🇦"

    # CHF
    if any(k in t for k in ["swiss", "switzerland", "snb", "jordan", "schlegel", "chf"]):
        return "🇨🇭"

    # JPY
    if any(k in t for k in ["japan", "japanese", "boj", "bank of japan", "ueda",
                              "himino", "tankan", "takaichi", "jpy"]):
        return "🇯🇵"

    # CNH
    if any(k in t for k in ["china", "chinese", "pboc", "yuan", "renminbi", "cnh", "cny"]):
        return "🇨🇳"

    # GBP
    if any(k in t for k in ["boe", "bank of england", "bailey", "pill", "mann",
                              "uk ", "united kingdom", "britain", "british", "gbp"]):
        return "🇬🇧"

    # EUR
    if any(k in t for k in ["ecb", "lagarde", "lane", "schnabel", "villeroy",
                              "eurozone", "euro zone", "germany", "german",
                              "france", "italy", "spain", "ifo", "zew", "eur"]):
        return "🇪🇺"

    # USD
    if any(k in t for k in ["fed", "fomc", "federal reserve", "powell", "daly",
                              "waller", "kugler", "jefferson", "barkin", "bostic",
                              "us ", "u.s.", "united states", "america",
                              "white house", "trump", "pentagon", "usd"]):
        return "🇺🇸"

    # Geopolitik
    if any(k in t for k in ["war", "attack", "missile", "nuclear", "blockade",
                              "ceasefire", "strike", "military", "troops",
                              "iran", "israel", "ukraine", "russia"]):
        return "🌍"

    return "📰"

# === FILTER 1: Bank Sentral & Suku Bunga ===
BANK_SENTRAL_KEYWORDS = [
    # Keputusan suku bunga
    "rate decision", "interest rate",
    "rate hike", "rate cut", "rate hold",
    "basis points", "bps",

    # Risalah & Vote
    "minutes", "vote", "voting",
    "monetary policy", "forward guidance",
    "quantitative", "balance sheet",

    # Ekspektasi/Probabilitas
    "probability", "odds", "pricing in",
    "market expects", "market pricing",
    "market bets", "swaps",
    "futures imply", "futures price",
    "expected to cut", "expected to hold", "expected to hike",
    "likely to cut", "likely to hold", "likely to hike",
    "rate expectations", "rate outlook",
    "dovish", "hawkish",

    # Nama pejabat Fed
    "powell", "daly", "waller", "kugler",
    "jefferson", "barkin", "bostic",

    # Nama pejabat BoE
    "bailey", "pill", "mann",

    # Nama pejabat ECB
    "lagarde", "lane", "schnabel", "villeroy",

    # Nama pejabat BoJ
    "ueda", "himino", "takaichi",

    # Nama pejabat lain
    "macklem", "bullock", "orr",
    "jordan", "schlegel",

    # Nama bank sentral
    "federal reserve", "fomc",
    "bank of england", "boe",
    "ecb", "boj", "rba", "rbnz",
    "snb", "pboc", "boc",
]

# === FILTER 2: Ringkasan Sesi & Grafik ===
SESI_KEYWORDS = [
    "market wrap", "market summary", "market review",
    "market open", "market close",
    "asia wrap", "asian wrap", "asia session",
    "europe wrap", "european wrap", "europe open",
    "us wrap", "us open", "us session",
    "london wrap", "london open",
    "daily wrap", "weekly wrap",
    "fx option expiries", "option expiries",
    "moo imbalance", "moc imbalance",
    "currency strength", "fx strength",
    "strongest", "weakest", "currency performance",
    "need to know", "market risk",
]

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Pakai link sebagai kunci duplikat
            return set(data.get("ids", [])), set(data.get("links", []))
    return set(), set()

def save_data(sent_ids, sent_links):
    with open(DATA_FILE, "w") as f:
        json.dump({
            "ids": list(sent_ids),
            "links": list(sent_links)
        }, f)

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

    # Cek chart TradingView
    if extract_tradingview_chart(description):
        return True, "chart"

    # Cek bank sentral & suku bunga
    for kw in BANK_SENTRAL_KEYWORDS:
        if kw in title_lower:
            return True, "bank"

    # Cek ringkasan sesi & grafik
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
    original_title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
    flag = get_flag_emoji(original_title)

    message = (
        f"📡 <b>FinancialJuice</b>\n\n"
        f"{flag} <b>{translated_title}</b>\n\n"
        f"🔗 <a href='{link}'>Baca selengkapnya</a>\n"
        f"🕐 {pub_date}"
    )

    if chart_id and chart_id != "found":
        chart_url = f"https://www.tradingview.com/chart/{chart_id}/"
        message += f"\n📊 Chart: <a href='{chart_url}'>TradingView</a>"
    elif chart_id == "found":
        message += f"\n📊 Chart: <a href='{link}'>FinancialJuice</a>"

    return message

def main():
    print("🤖 Bot FinancialJuice dimulai...")
    sent_ids, sent_links = load_data()

    if not sent_ids:
        print("📋 Loading berita lama...")
        feed = feedparser.parse(RSS_URL)
        for entry in feed.entries:
            entry_id = entry.get("id", entry.get("link", ""))
            entry_link = entry.get("link", "")
            sent_ids.add(entry_id)
            sent_links.add(entry_link)
        save_data(sent_ids, sent_links)
        print(f"✅ {len(sent_ids)} berita lama dilewati. Menunggu berita BARU...")

    while True:
        try:
            print(f"🔍 Cek RSS... ({datetime.now().strftime('%H:%M:%S')})")
            feed = feedparser.parse(RSS_URL)

            new_count = 0
            for entry in feed.entries:
                entry_id = entry.get("id", entry.get("link", ""))
                entry_link = entry.get("link", "")

                # Lapis 1: cek ID
                if entry_id in sent_ids:
                    continue

                # Lapis 2: cek Link URL (anti duplikat utama)
                if entry_link in sent_links:
                    print(f"🔄 Duplikat (link): {entry_link[-50:]}...")
                    sent_ids.add(entry_id)
                    save_data(sent_ids, sent_links)
                    continue

                original_title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
                description = entry.get("description", "") or entry.get("summary", "")

                hit, category = is_high_impact(original_title, description)

                if hit:
                    chart_id = extract_tradingview_chart(description)
                    print(f"⚡ [{category.upper()}] {original_title[:70]}...")
                    translated = translate_to_indonesian(original_title)
                    message = format_message(entry, translated, chart_id)
                    send_to_telegram(message)
                    sent_ids.add(entry_id)
                    sent_links.add(entry_link)
                    save_data(sent_ids, sent_links)
                    new_count += 1
                    time.sleep(2)
                else:
                    print(f"⏭ Skip: {original_title[:60]}...")
                    sent_ids.add(entry_id)
                    sent_links.add(entry_link)

            save_data(sent_ids, sent_links)
            if new_count == 0:
                print("💤 Tidak ada berita baru.")

        except Exception as e:
            print(f"❌ Error: {e}")

        print(f"⏳ Tunggu {CHECK_INTERVAL} detik...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
