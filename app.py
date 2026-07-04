import os
import re
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from market_data import fetch_all_market_data, build_market_context
from market_brain import answer as brain_answer

app = Flask(__name__)

# ── News RSS feeds ─────────────────────────────────────────────────────────────
# All feeds below have confirmed working public RSS as of 2024
NEWS_FEEDS = {
    "Energy": [
        "https://oilprice.com/rss/main",
        "https://lngprime.com/feed/",
        "https://www.rigzone.com/news/rss/rigzone_latest.aspx",
        "https://www.hellenicshippingnews.com/feed/",
    ],
    "EIA": [
        "https://www.eia.gov/rss/news.xml",
        "https://www.eia.gov/rss/press_rss.xml",
    ],
    "Markets": [
        "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        "https://finance.yahoo.com/rss/headline?s=CL=F",
        "https://finance.yahoo.com/rss/headline?s=NG=F",
        "https://finance.yahoo.com/rss/headline?s=BZ=F",
    ],
    "Shipping": [
        "https://www.hellenicshippingnews.com/feed/",
        "https://www.tradewindsnews.com/rss",
        "https://splash247.com/feed/",
    ],
    "OilPrice": [
        "https://oilprice.com/rss/main",
        "https://oilprice.com/rss/category/1",
    ],
    "Argus": [
        "https://www.argusmedia.com/rss/feed/news",
    ],
    "Baltic": [],  # No public news RSS — uses curated index/data links
}

# Curated fallback headlines — clickable links to real articles
FALLBACK_HEADLINES = {
    "Energy": [
        {"title": "OilPrice: Latest crude oil and energy market news →", "link": "https://oilprice.com/latest-energy-news/world-news/", "pub": ""},
        {"title": "LNG Prime: LNG spot prices, cargo tracking and trade flows →", "link": "https://lngprime.com/", "pub": ""},
        {"title": "Rigzone: Upstream oil & gas industry news →", "link": "https://www.rigzone.com/news/", "pub": ""},
        {"title": "S&P Global: Commodity Insights — energy price assessments →", "link": "https://www.spglobal.com/commodityinsights/en/market-insights/latest-news/natural-gas", "pub": ""},
        {"title": "ICIS: LNG and natural gas market news →", "link": "https://www.icis.com/explore/resources/news/lng/", "pub": ""},
        {"title": "Natural Gas Intel: Daily gas market analysis →", "link": "https://www.naturalgasintel.com/", "pub": ""},
    ],
    "EIA": [
        {"title": "EIA: This Week in Petroleum — crude oil market analysis →", "link": "https://www.eia.gov/petroleum/weekly/", "pub": ""},
        {"title": "EIA: Weekly Natural Gas Storage Report →", "link": "https://www.eia.gov/naturalgas/storage/dashboard/", "pub": ""},
        {"title": "EIA: Short-Term Energy Outlook — price forecasts →", "link": "https://www.eia.gov/outlooks/steo/", "pub": ""},
        {"title": "EIA: LNG Monthly — export and import data →", "link": "https://www.eia.gov/naturalgas/lng/", "pub": ""},
        {"title": "EIA: Weekly Petroleum Status Report — inventory levels →", "link": "https://www.eia.gov/petroleum/supply/weekly/", "pub": ""},
        {"title": "EIA: Drilling Productivity Report →", "link": "https://www.eia.gov/petroleum/drilling/", "pub": ""},
    ],
    "Markets": [
        {"title": "CME Group: Crude oil futures prices and contract specs →", "link": "https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html", "pub": ""},
        {"title": "ICE: Brent crude futures and TTF gas market data →", "link": "https://www.theice.com/marketdata/reports/8", "pub": ""},
        {"title": "MarketWatch: Energy sector and commodity futures →", "link": "https://www.marketwatch.com/markets/futures", "pub": ""},
        {"title": "Yahoo Finance: WTI crude (CL=F) live price and chart →", "link": "https://finance.yahoo.com/quote/CL=F/", "pub": ""},
        {"title": "Yahoo Finance: Natural Gas (NG=F) live price and chart →", "link": "https://finance.yahoo.com/quote/NG=F/", "pub": ""},
        {"title": "Yahoo Finance: Brent Crude (BZ=F) live price and chart →", "link": "https://finance.yahoo.com/quote/BZ=F/", "pub": ""},
    ],
    "Shipping": [
        {"title": "Hellenic Shipping News: Tanker and LNG carrier market updates →", "link": "https://www.hellenicshippingnews.com/category/shipping-news/tankers/", "pub": ""},
        {"title": "Baltic Exchange: Daily freight indices — BDI, VLCC, Suezmax →", "link": "https://www.balticexchange.com/en/index.html", "pub": ""},
        {"title": "TradeWinds: Shipping and offshore industry news →", "link": "https://www.tradewindsnews.com/", "pub": ""},
        {"title": "Splash247: Global maritime and shipping news →", "link": "https://splash247.com/", "pub": ""},
        {"title": "Clarksons: Shipping market research and vessel data →", "link": "https://www.clarksons.com/", "pub": ""},
        {"title": "Worldscale Association: Flat rate calculator and WS points →", "link": "https://www.worldscale.co.uk/", "pub": ""},
    ],
    "OilPrice": [
        {"title": "OilPrice.com: Breaking energy news, oil and gas market analysis →", "link": "https://oilprice.com/latest-energy-news/world-news/", "pub": ""},
        {"title": "OilPrice: Live Brent and WTI crude oil price charts →", "link": "https://oilprice.com/oil-price-charts/", "pub": ""},
        {"title": "OilPrice: OPEC+ production policy and quota tracker →", "link": "https://oilprice.com/energy/crude-oil/", "pub": ""},
        {"title": "OilPrice: Natural gas, LNG and TTF/Henry Hub coverage →", "link": "https://oilprice.com/energy/natural-gas/", "pub": ""},
        {"title": "OilPrice: Geopolitical risk and its impact on energy markets →", "link": "https://oilprice.com/geopolitics/", "pub": ""},
        {"title": "OilPrice: Shipping, tankers and freight market news →", "link": "https://oilprice.com/energy/energy-general/", "pub": ""},
    ],
    "Argus": [
        {"title": "Argus Media: Crude oil price assessments and grade differentials →", "link": "https://www.argusmedia.com/en/oil/argus-crude", "pub": ""},
        {"title": "Argus: LNG and natural gas price benchmarks →", "link": "https://www.argusmedia.com/en/natural-gas-lng", "pub": ""},
        {"title": "Argus: Freight rates and tanker market assessments →", "link": "https://www.argusmedia.com/en/oil/argus-freight", "pub": ""},
        {"title": "Argus: Petrochemicals and refining margin analysis →", "link": "https://www.argusmedia.com/en/petrochemicals", "pub": ""},
        {"title": "Argus: Latest news and methodology updates →", "link": "https://www.argusmedia.com/en/news", "pub": ""},
        {"title": "Argus: Biofuels and energy transition coverage →", "link": "https://www.argusmedia.com/en/bioenergy", "pub": ""},
    ],
    "Baltic": [
        {"title": "Baltic Exchange: Baltic Dry Index (BDI) — live daily freight rates →", "link": "https://www.balticexchange.com/en/data-services/about-our-indices/dry-services.html", "pub": ""},
        {"title": "Baltic Exchange: Baltic Dirty Tanker Index (BDTI) — VLCC, Suezmax, Aframax routes →", "link": "https://www.balticexchange.com/en/data-services/about-our-indices/tanker-services.html", "pub": ""},
        {"title": "Baltic Exchange: Baltic LNG freight assessments →", "link": "https://www.balticexchange.com/en/data-services/about-our-indices.html", "pub": ""},
        {"title": "Baltic Exchange: Worldscale flat rates and WS point calculator →", "link": "https://www.worldscale.co.uk/", "pub": ""},
        {"title": "Baltic Exchange: Market reports and freight market commentary →", "link": "https://www.balticexchange.com/en/index.html", "pub": ""},
        {"title": "Hellenic Shipping News: Tanker and LNG carrier market updates →", "link": "https://www.hellenicshippingnews.com/category/shipping-news/tankers/", "pub": ""},
    ],
}

_news_cache = {}
_news_cache_time = {}
NEWS_TTL = 600

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def _fetch_rss(url: str) -> list[dict]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        pub   = (item.findtext("pubDate") or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "pub": pub})
        if len(items) >= 8:
            break
    if not items:
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            link_el  = entry.find("{http://www.w3.org/2005/Atom}link")
            pub_el   = entry.find("{http://www.w3.org/2005/Atom}published")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link  = link_el.get("href", "") if link_el is not None else ""
            pub   = (pub_el.text or "").strip() if pub_el is not None else ""
            if title and link:
                items.append({"title": title, "link": link, "pub": pub})
            if len(items) >= 8:
                break
    return items


def fetch_news(source: str) -> list[dict]:
    now = datetime.now().timestamp()
    if source in _news_cache and (now - _news_cache_time.get(source, 0)) < NEWS_TTL:
        return _news_cache[source]

    urls = NEWS_FEEDS.get(source, [])
    articles = []
    for url in urls:
        try:
            fetched = _fetch_rss(url)
            articles.extend(fetched)
            if articles:
                break  # stop at first working feed
        except Exception:
            continue

    # De-duplicate
    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    result = unique[:8]

    # Use curated fallback if all feeds fail
    if not result:
        result = FALLBACK_HEADLINES.get(source, [
            {"title": f"Visit the {source} website for latest energy news", "link": "#", "pub": ""}
        ])

    _news_cache[source] = result
    _news_cache_time[source] = now
    return result


# ── Market Read — transparent keyword-based headline tagging ───────────────────
# NOT a price forecast. This flags headlines containing bullish/bearish keyword
# patterns so the user can see WHY something was tagged, with full transparency
# about what triggered each tag. No black-box scoring, no fabricated probabilities.

BULLISH_PATTERNS = [
    (r"\bcuts?\b.*\bproduction\b|\bproduction\b.*\bcuts?\b", "Supply cut — tends to support prices"),
    (r"\boutage\b|\bdisrupt", "Supply disruption — tightens physical market"),
    (r"\bextend(s|ed)?\b.*\bcuts?\b", "Extended supply restriction"),
    (r"\bdraw\b.*\binventor|\binventor.*\bdraw|\bdrawdown\b", "Inventory draw — demand outpacing supply"),
    (r"\bsanctions?\b", "Sanctions — potential supply restriction"),
    (r"\bstrike\b|\bshutdown\b|\bhalt(s|ed)?\b", "Operational disruption"),
    (r"\bdemand\b.*\b(surge|rise|rising|jump|strong|robust)\b", "Strong demand signal"),
    (r"\bgeopolitical\b.*\btension|\bconflict\b|\bwar\b", "Geopolitical risk premium"),
    (r"\bopec\+?\b.*\b(cut|restrict|reduce)", "OPEC+ supply discipline"),
    (r"\bcold\b.*\bweather|\bwinter\b.*\bdemand|\bheatwave\b", "Weather-driven demand"),
]

BEARISH_PATTERNS = [
    (r"\brise\b.*\binventor|\binventor.*\brise|\bbuild(s|up)?\b.*\binventor", "Inventory build — signals oversupply"),
    (r"\boversupply\b|\bglut\b|\bsurplus\b", "Oversupply conditions"),
    (r"\bdemand\b.*\b(weak|fall|falling|drop|decline|destruction|miss)", "Weak demand signal"),
    (r"\bslowdown\b|\brecession\b", "Economic slowdown risk"),
    (r"\bincrease[sd]?\b.*\bproduction\b|\bproduction\b.*\bincrease", "Rising supply"),
    (r"\bopec\+?\b.*\b(increase|raise|boost|hike)", "OPEC+ supply increase"),
    (r"\bmiss(es|ed)?\b.*\bestimat", "Economic data miss"),
    (r"\bstockpile", "Stockpile growth"),
    (r"\bweak\b.*\bdata|\bdata\b.*\bweak", "Weak economic data"),
]


def tag_headline(title: str):
    """Check a headline against bullish/bearish keyword patterns.
    Returns (signal, reason) or (None, None) if no pattern matches."""
    title_lower = title.lower()
    for pattern, reason in BULLISH_PATTERNS:
        if re.search(pattern, title_lower):
            return "bullish", reason
    for pattern, reason in BEARISH_PATTERNS:
        if re.search(pattern, title_lower):
            return "bearish", reason
    return None, None


def build_market_read(sources=("Energy", "OilPrice", "Argus", "EIA")):
    """Scan current headlines across given sources and tag them.
    Fully transparent — every tag shows the headline and the matched reason."""
    tagged = []
    seen_titles = set()

    for source in sources:
        try:
            articles = fetch_news(source)
        except Exception:
            continue
        for art in articles:
            title = art.get("title", "")
            if not title or title in seen_titles:
                continue
            signal, reason = tag_headline(title)
            if signal:
                seen_titles.add(title)
                tagged.append({
                    "title": title,
                    "link": art.get("link", "#"),
                    "source": source,
                    "signal": signal,
                    "reason": reason,
                })

    bullish_count = sum(1 for t in tagged if t["signal"] == "bullish")
    bearish_count = sum(1 for t in tagged if t["signal"] == "bearish")

    if bullish_count == 0 and bearish_count == 0:
        bias = "No clear signal"
    elif bullish_count > bearish_count:
        bias = "Mixed — leaning bullish" if bearish_count > 0 else "Bullish-leaning"
    elif bearish_count > bullish_count:
        bias = "Mixed — leaning bearish" if bullish_count > 0 else "Bearish-leaning"
    else:
        bias = "Mixed / no clear directional bias"

    return {
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "bias": bias,
        "tagged": tagged[:12],  # cap to keep the panel readable
        "disclaimer": (
            "This reflects keyword patterns in today's headlines only — it is "
            "not a price forecast. Markets are driven by far more than news "
            "sentiment (positioning, technicals, macro flows, freight, FX). "
            "Use this as a quick read of the day's narrative, not a trading signal."
        ),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/arb")
def arb():
    return render_template("arb.html")


@app.route("/api/market-read")
def api_market_read():
    try:
        result = build_market_read()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/market-data")
def api_market_data():
    force = request.args.get("force", "false").lower() == "true"
    try:
        data = fetch_all_market_data(force=force)
        return jsonify({"status": "ok", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/news")
def api_news():
    source = request.args.get("source", "Energy")
    if source not in NEWS_FEEDS:
        return jsonify({"status": "error", "message": "Unknown source"}), 400
    try:
        articles = fetch_news(source)
        return jsonify({"status": "ok", "articles": articles})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(force=True)
    user_message = (body.get("message") or "").strip()
    history = body.get("history") or []

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    try:
        market_data = fetch_all_market_data()
    except Exception as e:
        return jsonify({"error": f"Market data unavailable: {e}"}), 503

    try:
        reply = brain_answer(user_message, market_data, history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "reply": reply,
        "timestamp": market_data.get("timestamp_display", ""),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting Market Intelligence on port {port}...")
    app.run(debug=False, port=port, host="0.0.0.0")
