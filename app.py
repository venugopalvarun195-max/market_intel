import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from market_data import fetch_all_market_data, build_market_context
from market_brain import answer as brain_answer

app = Flask(__name__)

# ── News RSS feeds ─────────────────────────────────────────────────────────────
NEWS_FEEDS = {
    "Reuters": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.reuters.com/reuters/companyNews",
    ],
    "Bloomberg": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.bloomberg.com/energy/news.rss",
    ],
    "Argus Media": [
        "https://www.argusmedia.com/rss/feed/news",
    ],
}

_news_cache = {}
_news_cache_time = {}
NEWS_TTL = 600  # seconds


def _fetch_rss(url: str) -> list[dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=8) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    items = []
    # Try RSS 2.0 <item> first
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            items.append({"title": title, "link": link, "pub": pub})
        if len(items) >= 8:
            break
    # Fall back to Atom <entry>
    if not items:
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title_el = entry.find("{http://www.w3.org/2005/Atom}title")
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            pub_el = entry.find("{http://www.w3.org/2005/Atom}published")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = link_el.get("href", "") if link_el is not None else ""
            pub = (pub_el.text or "").strip() if pub_el is not None else ""
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
            articles.extend(_fetch_rss(url))
        except Exception:
            pass
        if len(articles) >= 8:
            break

    # De-duplicate by title
    seen = set()
    unique = []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)

    result = unique[:8]
    _news_cache[source] = result
    _news_cache_time[source] = now
    return result


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


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
    source = request.args.get("source", "Reuters")
    if source not in NEWS_FEEDS:
        return jsonify({"status": "error", "message": "Unknown source"}), 400
    try:
        articles = fetch_news(source)
        if articles:
            return jsonify({"status": "ok", "articles": articles})
        # Return placeholder if feed is unavailable
        return jsonify({
            "status": "ok",
            "articles": [
                {
                    "title": f"{source} feed temporarily unavailable",
                    "link": "#",
                    "pub": ""
                }
            ]
        })
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
