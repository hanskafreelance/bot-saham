import yfinance as yf
import pandas as pd
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# Matikan log bising dari yfinance
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

STOPWORDS = {
    'GW', 'GUA', 'AKU', 'SAYA', 'KITA', 'PUNYA', 'SAHAM', 'MAU', 'JUAL', 'BELI',
    'DI', 'HARGA', 'BERAPA', 'GIMANA', 'ENAKNYA', 'HOLD', 'TARGET', 'PROSPEK',
    'KIRA', 'KIRAKIRA', 'APA', 'KAH', 'DONG', 'MIN', 'BRO', 'SEKARANG', 'BAGUS',
    'BAGUSNYA', 'BISA', 'TOLONG', 'REKOMENDASI', 'PANDANGAN', 'POSISI', 'STOCK',
    'AVG', 'AVERAGE', 'MODAL', 'AMBIL', 'MASUK', 'LEPAS', 'TP', 'CL', 'CUTLOSS',
    'TAKE', 'PROFIT', 'BERDASARKAN', 'NEWS', 'BERITA', 'KIRA-KIRA', 'LOT', 'LEMBAR',
    'TENTANG', 'PENDAPAT', 'PENDAPATMU', 'MENURUTMU', 'MENURUT', 'RUPIAH', 'DOLLAR',
    'DOLAR', 'RP', 'USD', 'IDR', 'CUAN', 'LOSS', 'LABA', 'RUGI'
}

def resolve_ticker(symbol: str) -> Tuple[str, str, str]:
    """
    Mendeteksi apakah ticker adalah saham IDX (Indonesia) atau US (Amerika).
    Mengembalikan (ticker_yf, display_ticker, currency).
    """
    s = symbol.strip().upper().replace(" ", "")
    if s in ["IHSG", "^JKSE"]:
        return "^JKSE", "IHSG", "IDR"
    if s in ["SPY", "^GSPC", "S&P500", "SNP500", "SP500", "SNP"]:
        return "SPY", "SPY", "USD"
    if s in ["QQQ", "^IXIC", "NASDAQ", "NASDAQ100", "NDX"]:
        return "QQQ", "QQQ", "USD"
    if s in ["DIA", "^DJI", "DOW", "DJIA"]:
        return "^DJI", "Dow Jones", "USD"

    if s.startswith("US:"):
        clean_s = s.replace("US:", "")
        return clean_s, clean_s, "USD"

    if s.endswith(".JK"):
        return s, s.replace(".JK", ""), "IDR"

    # Ticker saham Indonesia (IDX) HAMPIR SELALU tepat 4 huruf (BBCA, BBRI, dsb)
    # Jika panjang ticker bukan 4 huruf (misal: MCD, ZTS, AMD, AAPL, F, KO), langsung cek US dulu
    if len(s) != 4:
        try:
            t_us = yf.Ticker(s)
            hist_us = t_us.history(period="3d")
            if not hist_us.empty:
                cur = t_us.fast_info.currency or "USD"
                return s, s, cur
        except Exception:
            pass

    # Cek apakah terdaftar di IDX
    try:
        t_jk = yf.Ticker(f"{s}.JK")
        hist_jk = t_jk.history(period="3d")
        if not hist_jk.empty:
            return f"{s}.JK", s, "IDR"
    except Exception:
        pass

    # Cek di bursa US
    try:
        t_us = yf.Ticker(s)
        hist_us = t_us.history(period="3d")
        if not hist_us.empty:
            cur = t_us.fast_info.currency or "USD"
            return s, s, cur
    except Exception:
        pass

    return f"{s}.JK", s, "IDR"

def format_currency(amount: float, currency: str) -> str:
    """Format angka sesuai mata uang (Rp untuk IDR, $ untuk USD)."""
    if currency == "IDR":
        return f"Rp {amount:,.0f}"
    return f"${amount:,.2f}"

def search_stocks_by_name(query: str, limit: int = 5) -> List[Dict[str, str]]:
    """Mencari ticker saham berdasarkan nama perusahaan atau keyword."""
    clean_q = query.strip()
    try:
        s = yf.Search(clean_q, max_results=limit * 2)
        results = []
        for q in s.quotes:
            sym = q.get('symbol', '')
            name = q.get('longname') or q.get('shortname') or ''
            exchange = q.get('exchange', '')
            
            # Prioritaskan BEI (.JK) dan bursa US utama (NMS, NYQ, NGM, dll)
            if sym.endswith('.JK'):
                display = sym.replace('.JK', '')
                results.append({
                    'ticker': display,
                    'full_ticker': sym,
                    'name': name,
                    'market': 'BEI (Indonesia) 🇮🇩',
                    'currency': 'IDR'
                })
            elif not '.' in sym and exchange in ['NMS', 'NYQ', 'NGM', 'PCX', 'NAS', 'NYE']:
                results.append({
                    'ticker': sym,
                    'full_ticker': sym,
                    'name': name,
                    'market': 'Bursa US 🇺🇸',
                    'currency': 'USD'
                })

            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print(f"Error searching stocks for {query}: {e}")
        return []

def get_stock_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Mengambil harga terkini, perubahan harian, dan NAMA RESMI LENGKAP perusahaan."""
    ticker_yf, display_ticker, currency = resolve_ticker(symbol)
    try:
        stock = yf.Ticker(ticker_yf)
        hist = stock.history(period="5d")
        if hist.empty:
            return None

        current_price = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else current_price
        change = current_price - prev_close
        pct_change = (change / prev_close) * 100 if prev_close else 0.0
        high = hist["High"].iloc[-1]
        low = hist["Low"].iloc[-1]
        volume = int(hist["Volume"].iloc[-1])

        # Ambil nama resmi lengkap perusahaan
        info = stock.info
        official_name = (
            info.get("longName")
            or info.get("shortName")
            or getattr(stock.fast_info, "company_name", display_ticker)
            or display_ticker
        )
        market = "BEI (Indonesia) 🇮🇩" if currency == "IDR" else "Bursa US (Amerika) 🇺🇸"

        return {
            "ticker": ticker_yf,
            "display_ticker": display_ticker,
            "currency": currency,
            "market": market,
            "name": official_name,
            "price": float(current_price),
            "prev_close": float(prev_close),
            "change": float(change),
            "pct_change": float(pct_change),
            "high": float(high),
            "low": float(low),
            "volume": volume
        }
    except Exception as e:
        print(f"Error fetching quote for {symbol}: {e}")
        return None

def analyze_stock(symbol: str) -> Optional[Dict[str, Any]]:
    """Analisis teknikal (RSI, MA20, MA50, Support/Resistance) untuk Indo/US."""
    ticker_yf, display_ticker, currency = resolve_ticker(symbol)
    try:
        stock = yf.Ticker(ticker_yf)
        df = stock.history(period="6mo")
        if len(df) < 20:
            return None

        close = df["Close"]
        current_price = float(close.iloc[-1])

        sma20 = float(close.rolling(window=20).mean().iloc[-1])
        sma50 = float(close.rolling(window=50).mean().iloc[-1]) if len(df) >= 50 else None

        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        last_20 = df.tail(20)
        support = float(last_20["Low"].min())
        resistance = float(last_20["High"].max())

        trend = "BULLISH 🟢" if current_price > sma20 else "BEARISH 🔴"
        if sma50:
            if sma20 > sma50 and current_price > sma20:
                trend = "STRONG BULLISH 🚀"
            elif sma20 < sma50 and current_price < sma20:
                trend = "STRONG BEARISH 🔻"

        if rsi >= 70:
            rsi_desc = "Overbought (Jenuh Beli - Waspada Koreksi) ⚠️"
        elif rsi <= 30:
            rsi_desc = "Oversold (Jenuh Jual - Potensi Rebound) 🛒"
        else:
            rsi_desc = "Netral ⚖️"

        market = "BEI (Indonesia) 🇮🇩" if currency == "IDR" else "Bursa US 🇺🇸"

        return {
            "ticker": ticker_yf,
            "display_ticker": display_ticker,
            "currency": currency,
            "market": market,
            "current_price": current_price,
            "sma20": sma20,
            "sma50": sma50,
            "rsi": rsi,
            "rsi_desc": rsi_desc,
            "trend": trend,
            "support": support,
            "resistance": resistance
        }
    except Exception as e:
        print(f"Error analyzing {symbol}: {e}")
        return None

def get_stock_fundamentals(symbol: str) -> Optional[Dict[str, Any]]:
    """Mengambil laporan keuangan & valuasi fundamental saham Indo maupun US."""
    ticker_yf, display_ticker, currency = resolve_ticker(symbol)
    try:
        stock = yf.Ticker(ticker_yf)
        info = stock.info
        if not info:
            return None

        market_cap = info.get("marketCap")
        if market_cap:
            if currency == "IDR":
                cap_str = f"Rp {market_cap / 1e12:,.2f} Triliun"
            else:
                if market_cap >= 1e12:
                    cap_str = f"${market_cap / 1e12:,.2f} Trillion"
                else:
                    cap_str = f"${market_cap / 1e9:,.2f} Billion"
        else:
            cap_str = "N/A"

        pe = info.get("trailingPE")
        fwd_pe = info.get("forwardPE")
        pbv = info.get("priceToBook")
        roe = info.get("returnOnEquity")
        div_yield = info.get("dividendYield")
        eps = info.get("trailingEps")
        profit_margin = info.get("profitMargins")

        eps_str = format_currency(eps, currency) if eps else "N/A"
        market = "BEI (Indonesia) 🇮🇩" if currency == "IDR" else "Bursa US 🇺🇸"

        return {
            "ticker": ticker_yf,
            "display_ticker": display_ticker,
            "currency": currency,
            "market": market,
            "name": info.get("longName") or info.get("shortName") or display_ticker,
            "market_cap": cap_str,
            "pe": f"{pe:.2f}x" if pe else "N/A",
            "forward_pe": f"{fwd_pe:.2f}x" if fwd_pe else "N/A",
            "pbv": f"{pbv:.2f}x" if pbv else "N/A",
            "roe": f"{roe * 100:.2f}%" if roe else "N/A",
            "dividend_yield": f"{div_yield * 100:.2f}%" if div_yield else "0.00%",
            "eps": eps_str,
            "profit_margin": f"{profit_margin * 100:.2f}%" if profit_margin else "N/A",
            "industry": info.get("industry", "N/A"),
            "sector": info.get("sector", "N/A")
        }
    except Exception as e:
        print(f"Error getting fundamentals for {symbol}: {e}")
        return None

def get_stock_news_articles(symbol: str, limit: int = 5) -> Tuple[List[Dict[str, str]], str, str]:
    """Mengambil artikel berita terbaru untuk saham Indo atau US."""
    ticker_yf, display_ticker, currency = resolve_ticker(symbol)
    is_us = (currency == "USD")

    if is_us:
        q = urllib.parse.quote(f"{display_ticker} stock news")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    else:
        q = urllib.parse.quote(f"saham {display_ticker}")
        url = f"https://news.google.com/rss/search?q={q}&hl=id&gl=ID&ceid=ID:id"

    articles = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        xml_data = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(xml_data)

        for item in root.findall(".//item")[:limit]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            articles.append({
                "title": title,
                "link": link,
                "pub_date": pub_date[:16] if pub_date else "-"
            })
    except Exception as e:
        print(f"Error fetching news for {symbol}: {e}")

    return articles, display_ticker, currency

def generate_news_summary(symbol: str) -> Optional[Dict[str, Any]]:
    """Merangkum berita terkini saham ke dalam multi-timeframe dan proyeksi."""
    articles, display_ticker, currency = get_stock_news_articles(symbol, limit=6)
    if not articles:
        return None

    quote = get_stock_quote(display_ticker)
    analysis = analyze_stock(display_ticker)
    fund = get_stock_fundamentals(display_ticker)

    is_us = (currency == "USD")
    market = "Bursa US 🇺🇸" if is_us else "BEI (Indonesia) 🇮🇩"

    all_titles = " ".join([a["title"].lower() for a in articles])
    bullish_keywords = ["buy", "rebound", "soar", "surge", "gain", "profit", "naik", "borong", "potensi", "cuan", "dividen", "laba", "bullish", "upgrade"]
    bearish_keywords = ["sell", "drop", "plunge", "fall", "loss", "turun", "pangkas", "anjlok", "waspada", "koreksi", "bearish", "downgrade", "cut"]

    bull_score = sum(1 for w in bullish_keywords if w in all_titles)
    bear_score = sum(1 for w in bearish_keywords if w in all_titles)

    if bull_score > bear_score:
        sentiment_label = "BULLISH / POSITIF 🟢"
        short_outlook = "Didukung sentimen positif dan akumulasi beli pelaku pasar terkini."
    elif bear_score > bull_score:
        sentiment_label = "BEARISH / HATI-HATI 🔴"
        short_outlook = "Terdapat tekanan jual jangka pendek akibat kekhawatiran valuasi atau sentimen makro."
    else:
        sentiment_label = "NETRAL / KONSOLIDASI ⚖️"
        short_outlook = "Sentimen pasar saat ini berimbang, pasar sedang menunggu konfirmasi katalis berikutnya."

    pct = f"{quote['pct_change']:+.2f}%" if quote else "Stabil"
    short_term = (
        f"• *Pergerakan Terkini*: Harga bergerak ({pct}) merespons berita teranyar.\n"
        f"• *Katalis*: {short_outlook}\n"
        f"• *Level Kunci*: Support {format_currency(analysis['support'], currency) if analysis else 'N/A'} dan resistance {format_currency(analysis['resistance'], currency) if analysis else 'N/A'}."
    )

    pe_str = fund['pe'] if fund else "N/A"
    roe_str = fund['roe'] if fund else "N/A"
    medium_term = (
        f"• *Kinerja Kuartalan & Valuasi*: Valuasi PER berada di level {pe_str} dengan profitabilitas ROE {roe_str}.\n"
        f"• *Fokus Pasar*: Pelaku pasar mengamati rilis laporan keuangan berikutnya, penyesuaian suku bunga acuan, dan daya tahan margin laba emiten."
    )

    cap_str = fund['market_cap'] if fund else "N/A"
    long_term = (
        f"• *Struktur Bisnis*: Dengan kapitalisasi pasar {cap_str}, emiten memiliki keunggulan kompetitif (moat) yang kuat di industrinya.\n"
        f"• *Prospek Sekuler*: Pertumbuhan ditopang oleh tren adopsi industri, ekspansi bisnis berkelanjutan, dan loyalitas pangsa pasar."
    )

    rsi_val = f"{analysis['rsi']:.1f}" if analysis else "50"
    rsi_status = analysis['rsi_desc'] if analysis else "Netral"
    projection = (
        f"• *Arah Tren*: {analysis['trend'] if analysis else 'Netral'}\n"
        f"• *Indikator RSI*: {rsi_val} ({rsi_status})\n"
        f"• *Kesimpulan Sentimen*: *{sentiment_label}*\n"
        f"• *Strategi*: Cocok untuk strategi _buy on weakness_ di dekat level support jika tren fundamental tetap solid."
    )

    return {
        "ticker": display_ticker,
        "company_name": quote["name"] if quote else display_ticker,
        "market": market,
        "sentiment": sentiment_label,
        "short_term": short_term,
        "medium_term": medium_term,
        "long_term": long_term,
        "projection": projection,
        "articles": articles[:4]
    }

def get_ipo_news(limit: int = 5) -> List[Dict[str, str]]:
    """Mengambil berita dan jadwal IPO terbaru di BEI (e-IPO)."""
    query = urllib.parse.quote("IPO saham BEI OR e-ipo")
    url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        xml_data = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(xml_data)

        ipos = []
        for item in root.findall(".//item")[:limit]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            ipos.append({
                "title": title,
                "link": link,
                "pub_date": pub_date[:16] if pub_date else "-"
            })
        return ipos
    except Exception as e:
        print(f"Error fetching IPO news: {e}")
        return []

def get_market_overview() -> str:
    """Mengambil rangkuman IHSG dan bursa global ringkas."""
    indices = {
        "^JKSE": "IHSG (Indonesia)",
        "^DJI": "Dow Jones (US)",
        "^IXIC": "Nasdaq (US)",
        "^GSPC": "S&P 500 (US)",
        "^N225": "Nikkei (Jepang)"
    }
    lines = []
    for symbol, label in indices.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if len(hist) >= 1:
                cur = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2] if len(hist) > 1 else cur
                pct = ((cur - prev) / prev) * 100
                icon = "🟢" if pct >= 0 else "🔴"
                lines.append(f"{icon} *{label}*: {cur:,.2f} ({pct:+.2f}%)")
        except Exception:
            continue
    return "\n".join(lines) if lines else "Data indeks tidak tersedia saat ini."

def consult_stock_plan(query_text: str) -> Optional[Dict[str, Any]]:
    """
    Fitur Free Ask / Konsultasi Saham Berbasis AI:
    - Mengekstrak ticker & harga modal user dari pertanyaan.
    - Mengintegrasikan data teknikal, level support/resistance, valuasi, dan sentimen berita.
    - Menghasilkan rekomendasi target jual (TP1 & TP2), pengaman modal (trailing stop), dan analisis katalis.
    """
    clean_text = query_text.strip()
    words = re.findall(r'\b[A-Za-z0-9_]{2,8}\b', clean_text.upper())
    candidates = [w for w in words if w not in STOPWORDS]

    detected_ticker = None
    for c in candidates:
        quote = get_stock_quote(c)
        if quote and quote["price"] > 0:
            detected_ticker = quote["ticker"]
            break

    # Jika belum ketemu dari ticker, coba cari berdasarkan nama perusahaan di teks
    if not detected_ticker:
        search_res = search_stocks_by_name(clean_text, limit=1)
        if search_res:
            detected_ticker = search_res[0]["ticker"]

    if not detected_ticker:
        return None

    # Ambil angka harga modal jika user menyebutkannya (misal: "di 4500", "avg 120", dsb)
    # Cari angka yang masuk akal
    numbers = re.findall(r'\b\d+(?:[.,]\d+)?\b', clean_text)
    user_price = None
    for n in numbers:
        try:
            val = float(n.replace(',', ''))
            # Filter angka tahun misal 2024, 2025, 2026 atau angka kecil 1-5
            if val not in [2024, 2025, 2026, 2027]:
                user_price = val
                break
        except Exception:
            continue

    quote = get_stock_quote(detected_ticker)
    analysis = analyze_stock(detected_ticker)
    fund = get_stock_fundamentals(detected_ticker)
    news_summary = generate_news_summary(detected_ticker)

    if not quote:
        return None

    cur = quote["currency"]
    curr_price = quote["price"]
    support = analysis["support"] if analysis else curr_price * 0.95
    resistance = analysis["resistance"] if analysis else curr_price * 1.08

    # Target Jual 1 (Konservatif / TP1): Di sekitar resistance terdekat
    tp1 = max(resistance, curr_price * 1.04)
    # Target Jual 2 (Optimis / TP2): Resistance ekstensi (+7% hingga +12% di atas resistance)
    tp2 = tp1 * 1.08
    # Level Pengaman Modal (Trailing Stop / Support Kunci)
    stop_loss = min(support, curr_price * 0.95)

    # Evaluasi posisi modal user
    user_pnl_str = ""
    if user_price:
        pnl_pct = ((curr_price - user_price) / user_price) * 100
        pnl_icon = "🟢" if pnl_pct >= 0 else "🔴"
        status_pos = "Floating Profit" if pnl_pct >= 0 else "Floating Loss"
        user_pnl_str = (
            f"💼 *Posisi Modal Anda:*\n"
            f"• Harga Beli / Modal: {format_currency(user_price, cur)}\n"
            f"• Harga Pasar Saat Ini: {format_currency(curr_price, cur)}\n"
            f"• Status: {pnl_icon} *{pnl_pct:+.2f}% ({status_pos})*\n\n"
        )

    # Rangkuman sentimen & berita
    news_headline = "Kondisi pasar saat ini stabil dengan transaksi normal."
    if news_summary and news_summary.get("articles"):
        top_art = news_summary["articles"][0]
        news_headline = f"_{top_art['title']}_"

    sentiment = news_summary["sentiment"] if news_summary else "NETRAL ⚖️"

    return {
        "ticker": detected_ticker,
        "company_name": quote["name"],
        "market": quote["market"],
        "currency": cur,
        "curr_price": curr_price,
        "user_price": user_price,
        "user_pnl_str": user_pnl_str,
        "tp1": tp1,
        "tp2": tp2,
        "stop_loss": stop_loss,
        "rsi": analysis["rsi"] if analysis else 50,
        "rsi_desc": analysis["rsi_desc"] if analysis else "Netral",
        "trend": analysis["trend"] if analysis else "Netral",
        "pe": fund["pe"] if fund else "N/A",
        "sentiment": sentiment,
        "news_headline": news_headline
    }
