import os
import sys
import time
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Dummy HTTP Server agar lolos health-check Render Web Service (Free Tier)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Saham is running!")

    def log_message(self, format, *args):
        pass

def start_health_check_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Pastikan konsol Windows mendukung UTF-8 (emoji)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import stock_service
import alert_manager

# Load file .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_GROUP_ID = os.getenv("DEFAULT_GROUP_ID")

# Cooldown alert (dalam detik, default 1800 = 30 menit agar tidak spam)
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "1800"))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panduan lengkap perintah bot dan cara penggunaannya."""
    msg = (
        "🤖 *PANDUAN LENGKAP BOT SAHAM (IDX 🇮🇩 & US 🇺🇸)* 📈\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Bot ini mendukung saham **Indonesia (BEI)** dan **Bursa Amerika (US)**. Semua anggota grup bisa menggunakannya!\n\n"

        "💬 *1. Konsultasi Bebas (Free Ask AI)*\n"
        "• `/tanya <pertanyaan bebas>` : Tanya rekomendasi target jual modal Anda, pandangan saham, atau strategi berdasarkan berita.\n"
        "  _Contoh:_ `/tanya gw punya saham BBRI di 4500 mau jual di berapa enaknya?`\n"
        "  _Contoh US:_ `/tanya NVDA avg 120 sekarang enaknya take profit dimana?`\n\n"

        "🔍 *2. Cari Ticker Berdasarkan Nama Perusahaan*\n"
        "• `/cari <nama perusahaan>` : Cari kode ticker jika Anda lupa kodenya.\n"
        "  _Contoh:_ `/cari Indofood` atau `/cari Mandiri` atau `/cari Tesla`\n\n"

        "📌 *3. Cek Harga & Pasar*\n"
        "• `/cek <ticker atau nama>` : Cek harga realtime & NAMA RESMI perusahaan.\n"
        "  _Contoh:_ `/cek BBRI` atau `/cek NVDA` atau `/cek Indofood`\n"
        "• `/market` : Rangkuman IHSG & bursa global (Dow Jones, S&P 500, Nasdaq, Nikkei).\n\n"

        "📌 *4. Rangkuman Berita & Proyeksi Multi-Jangka Waktu*\n"
        "• `/news <ticker>` : Rangkuman berita jangka pendek, menengah, panjang, dan proyeksi.\n"
        "  _Contoh:_ `/news BBCA` atau `/news NVDA`\n\n"

        "📌 *5. Analisis Teknikal & Fundamental*\n"
        "• `/analisis <ticker>` : Indikator RSI 14, Tren MA20/50, Support & Resistance.\n"
        "• `/lapkeu <ticker>` : Laporan keuangan & valuasi (PER, PBV, ROE, Dividen, Market Cap).\n\n"

        "📌 *6. Alarm Target Harga (Realtime Alert)*\n"
        "• `/alert <ticker> < <harga>` : Pasang target beli (misal: `/alert BBCA < 9800`)\n"
        "• `/alert <ticker> > <harga>` : Pasang target profit (misal: `/alert NVDA > 190`)\n"
        "• `/listalert` : Melihat daftar alert aktif di grup.\n"
        "• `/hapus <ticker>` : Menghapus alert.\n\n"

        "📌 *7. Info IPO*\n"
        "• `/ipo` : Info calon emiten baru yang akan listing di BEI (e-IPO).\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Tips:* Bot selalu menampilkan NAMA RESMI perusahaan agar Anda yakin tidak salah saham!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cari_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mencari kode ticker berdasarkan nama perusahaan."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Masukkan nama perusahaan yang ingin dicari.\n"
            "Contoh: `/cari Indofood` atau `/cari Mandiri` atau `/cari Tesla`",
            parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Mencari ticker untuk *'{query}'*...", parse_mode="Markdown")

    results = stock_service.search_stocks_by_name(query, limit=5)
    if not results:
        await update.message.reply_text(f"❌ Tidak ditemukan saham dengan kata kunci *'{query}'*.", parse_mode="Markdown")
        return

    lines = [f"🔎 *Hasil Pencarian untuk '{query}':*\n━━━━━━━━━━━━━━━━━━━━━"]
    for idx, r in enumerate(results, 1):
        lines.append(
            f"{idx}. *{r['ticker']}* — {r['name']}\n"
            f"   🏷 _{r['market']}_ | Cek: `/cek {r['ticker']}`\n"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━━\n_Ketik `/cek <ticker>` atau `/tanya <ticker>` untuk meriset!_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cek_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Format: `/cek <ticker atau nama>`\nContoh: `/cek BBRI` atau `/cek Indofood`", parse_mode="Markdown")
        return

    input_text = " ".join(context.args).strip()
    await update.message.reply_text(f"⏳ Mengambil data *{input_text.upper()}*...", parse_mode="Markdown")

    quote = stock_service.get_stock_quote(input_text)
    # Jika gagal dengan input langsung, coba cari apakah ini nama perusahaan
    if not quote:
        search_res = stock_service.search_stocks_by_name(input_text, limit=1)
        if search_res:
            quote = stock_service.get_stock_quote(search_res[0]["ticker"])

    if not quote:
        await update.message.reply_text(
            f"❌ Saham *'{input_text}'* tidak ditemukan.\n"
            f"Coba gunakan `/cari {input_text}` untuk mencari kode tickernya.",
            parse_mode="Markdown"
        )
        return

    icon = "🟢" if quote["change"] >= 0 else "🔴"
    cur = quote["currency"]
    price_str = stock_service.format_currency(quote["price"], cur)
    change_str = stock_service.format_currency(quote["change"], cur)
    high_str = stock_service.format_currency(quote["high"], cur)
    low_str = stock_service.format_currency(quote["low"], cur)
    vol_unit = "lembar" if cur == "IDR" else "shares"

    msg = (
        f"🏢 *{quote['name']}*\n"
        f"🏷 Ticker: *{quote['display_ticker']}* ({quote['market']})\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Harga Terakhir*: {price_str}\n"
        f"📈 *Perubahan*: {icon} {change_str} ({quote['pct_change']:+.2f}%)\n"
        f"🔼 *High (Tertinggi)*: {high_str}\n"
        f"🔽 *Low (Terendah)*: {low_str}\n"
        f"📦 *Volume*: {quote['volume']:,} {vol_unit}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 _{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} WIB_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def tanya_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fitur Konsultasi Bebas (Free Ask) berbasis AI."""
    if not context.args:
        await update.message.reply_text(
            "💬 *Format Konsultasi Bebas (Free Ask)*\n\n"
            "Tuliskan pertanyaan Anda, misalnya:\n"
            "• `/tanya gw punya BBRI di 4500 mau jual di berapa enaknya?`\n"
            "• `/tanya NVDA avg 120 sekarang enaknya gimana?`\n"
            "• `/tanya pandangan prospek saham ASII berdasarkan berita terkini`",
            parse_mode="Markdown"
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text("🤔 *Sedang menganalisis posisi modal, teknikal, dan berita terkini...*", parse_mode="Markdown")

    plan = stock_service.consult_stock_plan(query)
    if not plan:
        await update.message.reply_text(
            "❌ Bot belum berhasil mengenali saham yang Anda tanyakan.\n"
            "Pastikan menyebutkan kode ticker (misal: `BBRI`, `BBCA`, `NVDA`) atau nama perusahaan.",
            parse_mode="Markdown"
        )
        return

    cur = plan["currency"]
    tp1_str = stock_service.format_currency(plan["tp1"], cur)
    tp2_str = stock_service.format_currency(plan["tp2"], cur)
    sl_str = stock_service.format_currency(plan["stop_loss"], cur)
    curr_str = stock_service.format_currency(plan["curr_price"], cur)

    msg = (
        f"💡 *KONSULTASI & STRATEGI: {plan['ticker']}*\n"
        f"🏢 *{plan['company_name']}*\n"
        f"🏷 {plan['market']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{plan['user_pnl_str']}"
        f"🎯 *Rekomendasi Area Target Jual (Take Profit):*\n"
        f"• *Target 1 (Konservatif / TP1)*: *{tp1_str}*\n"
        f"  ↳ _Area resistance terdekat. Bagus untuk amankan cuan 30-50% posisi._\n"
        f"• *Target 2 (Optimis / TP2)*: *{tp2_str}*\n"
        f"  ↳ _Level ekstensi jika momentum penguatan berlanjut._\n\n"
        f"🛡 *Level Pengaman (Trailing Stop / Support)*: *{sl_str}*\n"
        f"  ↳ _Jika harga berbalik turun ke level ini, pertimbangkan keluar agar modal/keuntungan terlindungi._\n\n"
        f"📰 *Dasar Pertimbangan Berita & Sentimen:*\n"
        f"• Status Sentimen: *{plan['sentiment']}*\n"
        f"• Berita Terkini: {plan['news_headline']}\n\n"
        f"🧭 *Indikator Teknikal:*\n"
        f"• Tren: {plan['trend']}\n"
        f"• RSI (14): {plan['rsi']:.1f} ({plan['rsi_desc']})\n"
        f"• Valuasi PER: {plan['pe']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _Disclaimer: Rencana di atas disusun secara kuantitatif berdasarkan level support-resistance & sentimen terkini, bukan ajakan mutlak._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def analisis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Format: `/analisis <ticker>`\nContoh: `/analisis BBCA` atau `/analisis NVDA`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"🔍 Menganalisis teknikal *{symbol}*...", parse_mode="Markdown")

    analysis = stock_service.analyze_stock(symbol)
    quote = stock_service.get_stock_quote(symbol)
    if not analysis:
        await update.message.reply_text(f"❌ Gagal menganalisis *{symbol}*. Pastikan ticker valid.", parse_mode="Markdown")
        return

    cur = analysis["currency"]
    curr_str = stock_service.format_currency(analysis["current_price"], cur)
    sma20_str = stock_service.format_currency(analysis["sma20"], cur)
    sma50_str = stock_service.format_currency(analysis["sma50"], cur) if analysis["sma50"] else "N/A"
    sup_str = stock_service.format_currency(analysis["support"], cur)
    res_str = stock_service.format_currency(analysis["resistance"], cur)
    comp_name = quote["name"] if quote else analysis["display_ticker"]

    msg = (
        f"🧭 *Analisis Teknikal: {analysis['display_ticker']}*\n"
        f"🏢 *{comp_name}*\n"
        f"🏷 Pasar: {analysis['market']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Harga Saat Ini*: {curr_str}\n"
        f"📊 *Tren*: {analysis['trend']}\n\n"
        f"• *SMA 20 (Tren Pendek)*: {sma20_str}\n"
        f"• *SMA 50 (Tren Menengah)*: {sma50_str}\n\n"
        f"• *RSI 14*: {analysis['rsi']:.1f}\n"
        f"  ↳ Status: {analysis['rsi_desc']}\n\n"
        f"🛡 *Support Terdekat*: {sup_str}\n"
        f"🎯 *Resistance Terdekat*: {res_str}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ _Indikasi matematis, bukan ajakan transaksi keuangan._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def lapkeu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Format: `/lapkeu <ticker>`\nContoh: `/lapkeu BBCA` atau `/lapkeu AAPL`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"📑 Mengambil data fundamental *{symbol}*...", parse_mode="Markdown")

    fund = stock_service.get_stock_fundamentals(symbol)
    if not fund:
        await update.message.reply_text(f"❌ Data fundamental untuk *{symbol}* tidak tersedia.", parse_mode="Markdown")
        return

    msg = (
        f"🏢 *{fund['name']}*\n"
        f"🏷 Ticker: *{fund['display_ticker']}* ({fund['market']})\n"
        f"Sektor: {fund['sector']} | Industri: {fund['industry']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏛 *Market Cap*: {fund['market_cap']}\n\n"
        f"💎 *Valuasi Saham:*\n"
        f"• *PER (Trailing)*: {fund['pe']}\n"
        f"• *Forward PER*: {fund['forward_pe']}\n"
        f"• *PBV*: {fund['pbv']}\n\n"
        f"💰 *Profitabilitas & Dividen:*\n"
        f"• *ROE*: {fund['roe']} _(Return on Equity)_\n"
        f"• *Profit Margin*: {fund['profit_margin']}\n"
        f"• *EPS*: {fund['eps']} _(Laba per Saham)_\n"
        f"• *Dividend Yield*: {fund['dividend_yield']} per tahun\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 _{datetime.datetime.now().strftime('%d/%m/%Y')} | Sumber: Yahoo Finance_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Merangkum berita terkini saham ke dalam multi-timeframe dan proyeksi."""
    if not context.args:
        await update.message.reply_text("⚠️ Format: `/news <ticker>`\nContoh: `/news BBCA` atau `/news NVDA`", parse_mode="Markdown")
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"📰 Menghimpun & merangkum analisis berita *{symbol}*...", parse_mode="Markdown")

    summary = stock_service.generate_news_summary(symbol)
    if not summary:
        await update.message.reply_text(f"📭 Tidak ditemukan berita terkini untuk *{symbol}*.", parse_mode="Markdown")
        return

    msg = (
        f"📰 *RANGKUMAN & PROYEKSI BERITA*\n"
        f"🏢 *{summary['company_name']}* ({summary['ticker']})\n"
        f"🏷 {summary['market']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ *1. Jangka Pendek (Katalis Harian/Mingguan)*\n"
        f"{summary['short_term']}\n\n"
        f"📈 *2. Jangka Menengah (1 - 6 Bulan)*\n"
        f"{summary['medium_term']}\n\n"
        f"🏛 *3. Jangka Panjang (1 - 3+ Tahun)*\n"
        f"{summary['long_term']}\n\n"
        f"🎯 *4. Proyeksi & Kesimpulan Sentimen*\n"
        f"{summary['projection']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📎 *Berita Terkini yang Dianalisis:*\n"
    )

    art_lines = []
    for idx, a in enumerate(summary["articles"], 1):
        art_lines.append(f"{idx}. [{a['title']}]({a['link']})")

    full_msg = msg + "\n".join(art_lines)
    await update.message.reply_text(full_msg, parse_mode="Markdown", disable_web_page_preview=True)

async def ipo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Mencari jadwal & info IPO terbaru di BEI...", parse_mode="Markdown")
    ipos = stock_service.get_ipo_news(limit=5)
    if not ipos:
        await update.message.reply_text("📭 Belum ada berita IPO terbaru yang ditemukan.", parse_mode="Markdown")
        return

    lines = ["🔔 *Info & Berita Calon Emiten IPO (e-IPO BEI)*\n━━━━━━━━━━━━━━━━━━━"]
    for idx, item in enumerate(ipos, 1):
        lines.append(
            f"{idx}. [{item['title']}]({item['link']})\n"
            f"   🕒 _{item['pub_date']}_\n"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━\n_Klik judul untuk membaca jadwal penawaran & prospektus._")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)

async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    user_tag = f"@{user.username}" if user and user.username else (user.first_name if user else "Member")
    args = context.args

    if not args or len(args) < 2:
        await update.message.reply_text(
            "⚠️ Format salah!\n\n"
            "*Contoh pengisian:*\n"
            "• `/alert BBCA < 9800` (Indo: alert saat turun <= 9800)\n"
            "• `/alert NVDA < 180` (US: alert saat turun <= $180)\n"
            "• `/alert AAPL > 250` (US: alert saat naik >= $250)",
            parse_mode="Markdown"
        )
        return

    symbol = args[0].upper()
    quote = stock_service.get_stock_quote(symbol)
    if not quote:
        await update.message.reply_text(f"❌ Ticker *{symbol}* tidak valid atau gagal diambil.", parse_mode="Markdown")
        return

    ticker_yf = quote["ticker"]
    display = quote["display_ticker"]
    cur = quote["currency"]
    current_price = quote["price"]

    if len(args) >= 3 and args[1] in ["<", "<=", ">", ">="]:
        condition = "<=" if "<" in args[1] else ">="
        try:
            target_price = float(args[2].replace(",", "").replace("$", ""))
        except ValueError:
            await update.message.reply_text("❌ Target harga harus berupa angka.", parse_mode="Markdown")
            return
    else:
        try:
            target_price = float(args[1].replace(",", "").replace("$", ""))
            condition = "<=" if target_price < current_price else ">="
        except ValueError:
            await update.message.reply_text("❌ Format target harga tidak dikenali.", parse_mode="Markdown")
            return

    alert_manager.add_alert(chat_id, ticker_yf, display, condition, target_price, user_tag)
    cond_text = "TURUN menyentuh atau <=" if condition == "<=" else "NAIK menyentuh atau >="
    target_str = stock_service.format_currency(target_price, cur)
    curr_str = stock_service.format_currency(current_price, cur)

    msg = (
        f"✅ *Alert Berhasil Disimpan!*\n\n"
        f"Saham: *{display}* — {quote['name']}\n"
        f"Pasar: {quote['market']}\n"
        f"Harga Saat Ini: *{curr_str}*\n"
        f"Kondisi: Alert jika *{cond_text} {target_str}*\n"
        f"👤 *Dipasang oleh*: {user_tag}\n\n"
        f"Bot akan otomatis memberi notifikasi ke grup ini saat target tercapai!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def listalert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    alerts = alert_manager.list_alerts(chat_id)

    if not alerts:
        await update.message.reply_text("📭 Belum ada alert saham yang aktif di chat/grup ini.", parse_mode="Markdown")
        return

    lines = ["📋 *Daftar Alert Saham Aktif:*\n━━━━━━━━━━━━━━━━━━━"]
    for idx, a in enumerate(alerts, 1):
        cond = "≤" if a["condition"] == "<=" else "≥"
        by_user = f" (oleh {a['user_name']})" if a.get("user_name") else ""
        cur = "IDR" if a["ticker"].endswith(".JK") else "USD"
        price_str = stock_service.format_currency(a["target_price"], cur)
        lines.append(f"{idx}. *{a['display_ticker']}* {cond} {price_str}{by_user}")

    lines.append("━━━━━━━━━━━━━━━━━━━\n_Ketik `/hapus <ticker>` untuk membatalkan._")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def hapus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text("Contoh: `/hapus BBCA` atau `/hapus NVDA`", parse_mode="Markdown")
        return

    ticker = context.args[0].upper()
    deleted = alert_manager.remove_alert(chat_id, ticker)
    if deleted > 0:
        await update.message.reply_text(f"🗑 Alert untuk saham *{ticker}* berhasil dihapus.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"Saham *{ticker}* tidak ditemukan di daftar alert grup ini.", parse_mode="Markdown")

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil data indeks bursa...", parse_mode="Markdown")
    overview = stock_service.get_market_overview()
    msg = (
        f"🌐 *Ringkasan Bursa Dunia & IHSG*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{overview}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 _{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} WIB_"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ================= BACKGROUND WORKER =================
async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE):
    """Mengecek harga saham di database setiap 60 detik."""
    all_alerts = alert_manager.get_all_alerts()
    if not all_alerts:
        return

    unique_tickers = list(set([a["ticker"] for a in all_alerts]))
    price_cache = {}

    for ticker in unique_tickers:
        quote = stock_service.get_stock_quote(ticker)
        if quote:
            price_cache[ticker] = {
                "price": quote["price"],
                "currency": quote["currency"],
                "market": quote["market"],
                "name": quote["name"]
            }

    now = time.time()
    for alert in all_alerts:
        ticker = alert["ticker"]
        if ticker not in price_cache:
            continue

        item = price_cache[ticker]
        curr_price = item["price"]
        cur = item["currency"]
        target = alert["target_price"]
        condition = alert["condition"]
        last_triggered = alert.get("last_triggered_at", 0)

        triggered = False
        if condition == "<=" and curr_price <= target:
            triggered = True
            action_desc = "TARGET BELI / SUPPORT"
        elif condition == ">=" and curr_price >= target:
            triggered = True
            action_desc = "TARGET TAKE PROFIT / RESISTANCE"

        if triggered and (now - last_triggered > ALERT_COOLDOWN_SECONDS):
            by_info = f"\n👤 Dipasang oleh: *{alert['user_name']}*" if alert.get("user_name") else ""
            curr_str = stock_service.format_currency(curr_price, cur)
            target_str = stock_service.format_currency(target, cur)

            msg = (
                f"🚨 *ALERT HARGA TERCAPAI!* 🚨\n\n"
                f"Saham: *{alert['display_ticker']}* — {item['name']}\n"
                f"Pasar: {item['market']}\n"
                f"Kategori: *{action_desc}*\n"
                f"Harga Terkini: *{curr_str}*\n"
                f"Target Anda: *{target_str}*{by_info}\n\n"
                f"🕒 _{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')} WIB_"
            )
            try:
                await context.bot.send_message(chat_id=alert["chat_id"], text=msg, parse_mode="Markdown")
                alert_manager.update_triggered_time(alert["id"])
            except Exception as e:
                print(f"Gagal kirim alert ke {alert['chat_id']}: {e}")

async def daily_morning_brief(context: ContextTypes.DEFAULT_TYPE):
    """Pesan otomatis pagi sebelum bursa buka (08:30 WIB)."""
    target_chat = DEFAULT_GROUP_ID
    if not target_chat:
        return

    overview = stock_service.get_market_overview()
    msg = (
        f"☀️ *MORNING BRIEFING PASAR SAHAM* ☕\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Selamat pagi rekan investor! Berikut pantauan indeks global sebelum pembukaan bursa:\n\n"
        f"{overview}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Gunakan `/cek <ticker>`, `/tanya <pertanyaan>`, atau `/news <ticker>` untuk meriset saham Anda hari ini. Selamat bertransaksi!"
    )
    await context.bot.send_message(chat_id=target_chat, text=msg, parse_mode="Markdown")

def main():
    if not BOT_TOKEN or "MASUKKAN" in BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN belum diisi di file .env!")
        return

    # Jalankan server HTTP mini di latar belakang untuk Render Free Web Service
    threading.Thread(target=start_health_check_server, daemon=True).start()

    alert_manager.init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Daftarkan command handlers
    app.add_handler(CommandHandler(["start", "help", "info", "cmd", "menu"], help_command))
    app.add_handler(CommandHandler(["tanya", "ask"], tanya_command))
    app.add_handler(CommandHandler(["cari", "search"], cari_command))
    app.add_handler(CommandHandler("cek", cek_command))
    app.add_handler(CommandHandler("analisis", analisis_command))
    app.add_handler(CommandHandler(["lapkeu", "fundamental"], lapkeu_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("ipo", ipo_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("listalert", listalert_command))
    app.add_handler(CommandHandler("hapus", hapus_command))
    app.add_handler(CommandHandler("market", market_command))

    # Background Job: Cek harga setiap 60 detik
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(check_alerts_job, interval=60, first=10)
        morning_time = datetime.time(hour=1, minute=30, tzinfo=datetime.timezone.utc)
        job_queue.run_daily(daily_morning_brief, time=morning_time, days=(0, 1, 2, 3, 4))

    print("🚀 Bot Saham Telegram (IDX & US + AI Free Ask) Berhasil Dijalankan!")
    print("Tekan Ctrl+C untuk menghentikan bot.")
    app.run_polling()

if __name__ == "__main__":
    main()
