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
RSS_URL = "https://rss.app/feeds/r9owT9XW529b35oJ.xml"  # ← Reuters
CHECK_INTERVAL = 60
DATA_FILE = "bot_data_reuters.json"  # ← file terpisah dari FinancialJuice
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
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

SYSTEM_PROMPT = """Kamu adalah analis pasar keuangan senior untuk terminal PETILASAN, platform berita FX profesional untuk trader Indonesia.

Tugasmu: Ringkas artikel berita keuangan dalam SATU paragraf padat dalam Bahasa Indonesia, menggunakan gaya Trading Economics.

Struktur wajib dalam satu paragraf:
[Aset + level/pergerakan] → [faktor pendorong utama] → [detail mekanisme/negosiasi] → [angka/data kunci] → [risiko/hambatan] → [proyeksi analis]

Aturan diksi:
- Gunakan "karena" (bukan "didorong")
- Gunakan "setelah" (bukan "di mana")
- Jangan gunakan kata "tersirat"
- Sertakan kutipan analis jika ada di artikel
- Sertakan konteks makro yang relevan
- Gunakan kausalitas berlapis, bukan daftar poin
- JANGAN gunakan bullet points atau header
- Hanya satu paragraf, padat dan informatif"""

def scrape_article(url):
    """Scrape artikel menggunakan Firecrawl."""
    if not FIRECRAWL_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"url": url, "formats": ["markdown"]}
    try:
        response = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("data", {}).get("markdown", "").strip()
        return text[:12000] if len(text) > 12000 else text
    except Exception as e:
        print(f"❌ Gagal scrape artikel: {e}")
        return None

def summarize_with_deepseek(article_text, title):
    """Ringkas artikel dengan DeepSeek."""
    if not DEEPSEEK_API_KEY:
        return None
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Ringkas artikel berita keuangan berikut:\n\n{article_text}"}
        ],
        "temperature": 0.3,
        "max_tokens": 1024
    }
    try:
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"❌ Gagal summarize DeepSeek: {e}")
        return None

def send_summary_to_telegram(title, summary, link):
    """Kirim ringkasan ke ALERT topic."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    message = (
        f"📊 <b>{title}</b>\n\n"
        f"{summary}\n\n"
        f"🔗 <a href='{link}'>Baca artikel lengkap</a>"
    )
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
            print(f"✅ Ringkasan terkirim!")
        else:
            print(f"❌ Gagal kirim ringkasan: {response.text}")
    except Exception as e:
        print(f"❌ Error kirim ringkasan: {e}")

def get_flag_emoji(title):
    t = title.lower()

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

    # CNH / CNY
    if any(k in t for k in ["china", "chinese", "pboc", "yuan", "renminbi", "cnh", "cny"]):
        return "🇨🇳"

    # INR
    if any(k in t for k in ["india", "indian", "rbi", "reserve bank of india", "inr", "rupee"]):
        return "🇮🇳"

    # IDR
    if any(k in t for k in ["indonesia", "indonesian", "bi ", "bank indonesia", "idr", "rupiah"]):
        return "🇮🇩"

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

    # Komoditas
    if any(k in t for k in ["gold", "silver", "oil", "crude", "brent", "wti",
                              "opec", "copper", "commodity", "commodities",
                              "natural gas", "lng"]):
        return "🟡" if any(k in t for k in ["gold", "silver"]) else "🛢️"

    # Geopolitik
    if any(k in t for k in ["war", "attack", "missile", "nuclear", "blockade",
                              "ceasefire", "strike", "military", "troops",
                              "iran", "israel", "ukraine", "russia", "taiwan",
                              "sanctions", "embargo"]):
        return "🌍"

    # Saham / Pasar
    if any(k in t for k in ["stock", "equity", "s&p", "nasdaq", "dow jones",
                              "wall street", "market", "shares", "index"]):
        return "📈"

    return "📰"


# =====================================================================
# FILTER KEYWORD — hanya berita yang relevan dengan trading yang lolos
# =====================================================================

# === 1. Bank Sentral & Kebijakan Moneter ===
BANK_SENTRAL_KEYWORDS = [
    # Keputusan & arah kebijakan
    "rate decision", "interest rate", "rate hike", "rate cut", "rate hold",
    "basis points", "bps", "monetary policy", "forward guidance",
    "quantitative easing", "quantitative tightening", "balance sheet",
    "minutes", "vote", "voting",

    # Ekspektasi pasar
    "probability", "odds", "pricing in", "market expects", "market pricing",
    "market bets", "swaps", "futures imply", "futures price",
    "expected to cut", "expected to hold", "expected to hike",
    "likely to cut", "likely to hold", "likely to hike",
    "rate expectations", "rate outlook", "dovish", "hawkish",
    "neutral stance", "policy pivot",

    # Nama pejabat Fed
    "powell", "daly", "waller", "kugler", "jefferson", "barkin", "bostic",
    "collins", "goolsbee", "musalem", "kashkari",

    # Nama pejabat BoE
    "bailey", "pill", "mann", "ramsden", "haskel",

    # Nama pejabat ECB
    "lagarde", "lane", "schnabel", "villeroy", "nagel", "de guindos",

    # Nama pejabat BoJ
    "ueda", "himino", "takaichi", "adachi", "nakagawa",

    # Nama pejabat lain
    "macklem", "bullock", "orr", "jordan", "schlegel",
    "shaktikanta", "das", "malhotra",  # RBI India

    # Nama bank sentral
    "federal reserve", "fomc", "bank of england", "boe",
    "ecb", "boj", "rba", "rbnz", "snb", "pboc", "boc",
    "bank of japan", "reserve bank", "central bank",
    "reserve bank of india", "rbi",
]

# === 2. Forex & Mata Uang ===
FOREX_KEYWORDS = [
    "usd", "eur", "gbp", "jpy", "aud", "nzd", "cad", "chf",
    "cnh", "cny", "inr", "idr", "rupiah", "rupee",
    "eurusd", "gbpusd", "usdjpy", "audusd", "usdcad", "usdchf",
    "nzdusd", "usdcnh", "usdidr", "usdinr",
    "dollar", "euro", "sterling", "yen", "yuan",
    "currency", "currencies", "forex", "fx",
    "exchange rate", "fx rate",
    "dollar index", "dxy",
    "currency war", "currency intervention",
    "safe haven", "risk off", "risk on",
]

# === 3. Komoditas ===
COMMODITY_KEYWORDS = [
    # Emas
    "gold", "xau", "bullion",

    # Perak
    "xag", "silver",

    # Minyak
    "oil", "crude", "brent", "wti", "opec", "opec+",
    "oil price", "oil production", "oil supply", "oil demand",
]

# === 4. Yield & Obligasi ===
YIELD_KEYWORDS = [
    "yield", "treasury", "bond", "bonds",
    "10-year", "2-year", "30-year",
    "yield curve", "inverted yield",
    "t-bill", "t-note", "gilt",
    "debt", "deficit", "credit rating",
    "sovereign debt", "bond market",
    "spread", "credit spread",
]

# === 5. Saham & Indeks ===
SAHAM_KEYWORDS = [
    "stock", "stocks", "equity", "equities",
    "s&p", "s&p 500", "sp500", "nasdaq", "dow jones",
    "wall street", "nyse", "nikkei", "hang seng",
    "dax", "ftse", "cac", "asx",
    "ipo", "earnings", "revenue", "profit",
    "bull market", "bear market", "correction",
    "rally", "selloff", "sell-off",
]

ALL_KEYWORDS = (
    BANK_SENTRAL_KEYWORDS +
    FOREX_KEYWORDS +
    COMMODITY_KEYWORDS +
    YIELD_KEYWORDS +
    SAHAM_KEYWORDS
)

def is_market_relevant(title):
    """Return True jika judul berita relevan dengan trading."""
    t = title.lower()
    for kw in ALL_KEYWORDS:
        if kw in t:
            return True
    return False

def get_category(title):
    """Tentukan label kategori berdasarkan isi judul."""
    t = title.lower()

    # Bank Sentral (prioritas tinggi)
    if any(k in t for k in BANK_SENTRAL_KEYWORDS):
        return "🏦 Bank Sentral"

    # Komoditas
    if any(k in t for k in ["gold", "xau", "bullion"]):
        return "🟡 Komoditas · Emas"
    if any(k in t for k in ["silver", "xag"]):
        return "⚪ Komoditas · Perak"
    if any(k in t for k in ["oil", "crude", "brent", "wti", "opec"]):
        return "🛢️ Komoditas · Minyak"

    # Yield & Obligasi
    if any(k in t for k in YIELD_KEYWORDS):
        return "📊 Yield & Obligasi"

    # Forex
    if any(k in t for k in FOREX_KEYWORDS):
        return "💱 Forex"

    # Saham
    if any(k in t for k in SAHAM_KEYWORDS):
        return "📈 Saham & Indeks"

    # Geopolitik — dihapus

    return "📰 Pasar Global"


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("ids", [])), set(data.get("links", []))
    return set(), set()

def save_data(sent_ids, sent_links):
    with open(DATA_FILE, "w") as f:
        json.dump({
            "ids": list(sent_ids),
            "links": list(sent_links)
        }, f)

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

def pub_date_to_wib(pub_date_str):
    """Konversi pubDate RSS ke jam WIB (UTC+7)."""
    try:
        from email.utils import parsedate_to_datetime
        dt_utc = parsedate_to_datetime(pub_date_str)
        from datetime import timezone, timedelta
        wib = timezone(timedelta(hours=7))
        dt_wib = dt_utc.astimezone(wib)
        return dt_wib.strftime("%H:%M WIB")
    except:
        return ""

def format_message(entry, translated_title):
    pub_date_raw = entry.get("published", "")
    jam_wib = pub_date_to_wib(pub_date_raw)
    link = entry.get("link", "")
    original_title = entry.get("title", "").strip()
    flag = get_flag_emoji(original_title)
    kategori = get_category(original_title)

    message = (
        f"{flag} <b>Reuters</b>\n"
        f"{kategori}\n\n"
        f"💠 <b>{translated_title}</b>\n\n"
        f"🕐 {jam_wib}\n"
        f"🔗 <a href='{link}'>Baca selengkapnya</a>"
    )
    return message

def main():
    print("🤖 Bot Reuters dimulai...")
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
            print(f"🔍 Cek RSS Reuters... ({datetime.now().strftime('%H:%M:%S')})")
            feed = feedparser.parse(RSS_URL)

            new_count = 0
            for entry in feed.entries:
                entry_id = entry.get("id", entry.get("link", ""))
                entry_link = entry.get("link", "")

                # Lapis 1: cek ID
                if entry_id in sent_ids:
                    continue

                # Lapis 2: cek Link (anti duplikat)
                if entry_link in sent_links:
                    print(f"🔄 Duplikat (link): {entry_link[-50:]}...")
                    sent_ids.add(entry_id)
                    save_data(sent_ids, sent_links)
                    continue

                original_title = entry.get("title", "").strip()

                # Filter relevansi pasar
                if is_market_relevant(original_title):
                    print(f"⚡ LOLOS: {original_title[:70]}...")
                    translated = translate_to_indonesian(original_title)
                    message = format_message(entry, translated)
                    send_to_telegram(message)
                    sent_ids.add(entry_id)
                    sent_links.add(entry_link)
                    save_data(sent_ids, sent_links)
                    new_count += 1
                    time.sleep(2)

                    # === RINGKASAN OTOMATIS ===
                    print(f"📖 Scraping artikel untuk ringkasan...")
                    article_text = scrape_article(entry_link)
                    if article_text:
                        print(f"🧠 Meringkas dengan DeepSeek...")
                        summary = summarize_with_deepseek(article_text, translated)
                        if summary:
                            send_summary_to_telegram(translated, summary, entry_link)
                            time.sleep(2)
                        else:
                            print(f"⚠️ Ringkasan gagal, skip.")
                    else:
                        print(f"⚠️ Scrape gagal, skip ringkasan.")
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
