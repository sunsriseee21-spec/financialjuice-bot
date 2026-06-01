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

    if any(k in title_lower for k in ["currency strength", "fx strength", "strongest", "weakest", "market wrap", "wrap", "imbalance", "option expiries"]):
        return "📊"
    if any(k in title_lower for k in ["war", "attack", "missile", "nuclear", "blockade", "ceasefire", "strike", "military", "troops"]):
        return "🌍"
    if any(k in title_lower for k in ["fed", "fomc", "powell", "daly", "waller", "us ", "u.s.", "united states", "america", "white house", "trump", "pentagon"]):
        return "🇺🇸"
    if any(k in title_lower for k in ["ecb", "lagarde", "lane", "schnabel", "villeroy", "eurozone", "euro zone", "germany", "german", "france", "italy", "spain", "ifo", "zew"]):
        return "🇪🇺"
    if any(k in title_lower for k in ["boe", "bank of england", "bailey", "pill", "uk ", "united kingdom", "britain", "british"]):
        return "🇬🇧"
    if any(k in title_lower for k in ["boj", "bank of japan", "ueda", "himino", "japan", "japanese", "tankan", "takaichi"]):
        return "🇯🇵"
    if any(k in title_lower for k in ["snb", "swiss", "switzerland", "jordan", "schlegel"]):
        return "🇨🇭"
    if any(k in title_lower for k in ["rba", "australia", "australian", "bullock"]):
        return "🇦🇺"
    if any(k in title_lower for k in ["rbnz", "new zealand", "orr"]):
        return "🇳🇿"
    if any(k in title_lower for k in ["boc", "bank of canada", "macklem", "canada", "canadian"]):
        return "🇨🇦"
    if any(k in title_lower for k in ["pboc", "china", "chinese", "yuan", "renminbi"]):
        return "🇨🇳"
    return "📰"

# ========== KEYWORD UNTUK HIGH IMPACT (SETELAH PERBAIKAN) ==========
# Hanya BANK SENTRAL (keputusan suku bunga), EKSPEKTASI, SESI, dan MARKET RISK
# DATA EKONOMI biasa (CPI, NFP, GDP, dll) DIHAPUS

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

# KEYWORD TAMBAHAN: "Need to know market risk"
RISK_KEYWORDS = [
    "market risk", "risk sentiment", "risk appetite", "risk warning",
    "need to know", "market warning", "risk off", "risk on",
    "volatility warning", "market exposure", "risk alert"
]

def is_high_impact(title, description):
    """Menentukan apakah berita high impact.
    - Data ekonomi biasa TIDAK termasuk.
    - Hanya: Keputusan suku bunga (bank sentral), ekspektasi pasar, sesi pasar, dan risiko pasar.
    """
    title_lower = title.lower()

    # Bank sentral (termasuk rate decision)
    for kw in BANK_SENTRAL_KEYWORDS:
        if kw in title_lower:
            return True, "bank"

    # Ekspektasi pasar
    for kw in EKSPEKTASI_KEYWORDS:
        if kw in title_lower:
            return True, "ekspektasi"

    # Sesi pasar
    for kw in SESI_KEYWORDS:
        if kw in title_lower:
            return True, "sesi"

    # Market risk (Need to know market risk)
    for kw in RISK_KEYWORDS:
        if kw in title_lower:
            return True, "risk"

    return False, None

def extract_tradingview_chart(description):
    """Ekstrak link TradingView dari deskripsi. Return URL lengkap atau None."""
    if not description:
        return None

    # Cari URL TradingView langsung
    match = re.search(r'https?://(?:www\.)?tradingview\.com/chart/([A-Za-z0-9]+)', description)
    if match:
        return f"https://www.tradingview.com/chart/{match.group(1)}/"

    # Cari pola chart = "KODE8KARAKTER" atau chart: KODE
    match = re.search(r'chart["\s:]+["\s]*([A-Za-z0-9]{8,12})', description)
    if match:
        return f"https://www.tradingview.com/chart/{match.group(1)}/"

    # Jika ada kata tradingview tapi tidak ditemukan pola, coba cari dalam tag href
    match = re.search(r'href=["\']([^"\']*tradingview\.com/chart/[^"\']+)["\']', description, re.IGNORECASE)
    if match:
        return match.group(1)

    return None

def load_data():
    """Load link yang sudah pernah dikirim."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("links", []))
    return set()

def save_data(sent_links):
    with open(DATA_FILE, "w") as f:
        json.dump({"links": list(sent_links)}, f)

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

def format_message(entry, translated_title, chart_url):
    pub_date = format_tanggal_indo(entry.get("published", ""))
    link = entry.get("link", "")
    flag = get_flag_emoji(translated_title + " " + entry.get("title", ""))

    message = (
        f"📡 <b>FinancialJuice</b>\n\n"
        f"{flag} <b>{translated_title}</b>\n\n"
        f"🔗 <a href='{link}'>Baca selengkapnya</a>\n"
        f"🕐 {pub_date}"
    )
    if chart_url:
        message += f"\n📊 <a href='{chart_url}'>Lihat Chart TradingView</a>"
    return message

def main():
    print("🤖 Bot FinancialJuice HIGH IMPACT (Rate Decision + Market Risk) dimulai...")
    sent_links = load_data()

    # Jika pertama kali, jangan skip semua berita lama? Biarkan kosong agar langsung membaca baru.
    # Tapi agar tidak mengirim berita lama saat pertama jalan, kita bisa isi dengan 50 link terbaru?
    # Alternatif: biarkan kosong, nanti akan terkirim semua berita yang masuk kategori saat startup.
    # Agar tidak flood, lebih baik kita preload beberapa link terbaru dari feed pertama.
    if not sent_links:
        print("📋 Preloading beberapa link terbaru untuk menghindari spam...")
        feed = feedparser.parse(RSS_URL)
        count = 0
        for entry in feed.entries:
            link = entry.get("link", "")
            if link:
                sent_links.add(link)
                count += 1
                if count >= 50:  # ambil 50 link terbaru sebagai sudah terkirim
                    break
        save_data(sent_links)
        print(f"✅ Preloaded {len(sent_links)} link. Menunggu berita BARU...")

    while True:
        try:
            print(f"🔍 Cek RSS... ({datetime.now().strftime('%H:%M:%S')})")
            feed = feedparser.parse(RSS_URL)

            new_count = 0
            for entry in feed.entries:
                entry_link = entry.get("link", "")
                if not entry_link:
                    continue
                if entry_link in sent_links:
                    continue  # sudah pernah dikirim

                original_title = entry.get("title", "").replace("FinancialJuice: ", "").strip()
                description = entry.get("description", "") or entry.get("summary", "")

                hit, category = is_high_impact(original_title, description)

                if hit:
                    chart_url = extract_tradingview_chart(description)
                    print(f"⚡ [{category.upper()}] {original_title[:70]}...")
                    translated = translate_to_indonesian(original_title)
                    message = format_message(entry, translated, chart_url)
                    send_to_telegram(message)
                    sent_links.add(entry_link)
                    save_data(sent_links)
                    new_count += 1
                    time.sleep(2)  # jeda antar kirim
                else:
                    # Tidak high impact, tetap tandai sebagai sudah dilihat agar tidak diproses ulang
                    sent_links.add(entry_link)
                    # Optional: print skip jika ingin debug
                    # print(f"⏭ Skip: {original_title[:60]}...")

            save_data(sent_links)
            if new_count == 0:
                print("💤 Tidak ada berita HIGH IMPACT baru (Rate Decision / Market Risk).")

        except Exception as e:
            print(f"❌ Error: {e}")

        print(f"⏳ Tunggu {CHECK_INTERVAL} detik...\n")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
