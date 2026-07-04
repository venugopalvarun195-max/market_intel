"""
Local market intelligence engine — no API key required.
Understands natural language questions about energy, commodities,
indices, metals, forex, and generates structured, data-driven answers.
"""

import re
from datetime import datetime

# ── keyword → canonical name mappings ──────────────────────────────────────
ALIASES = {
    # Energy
    "wti": "WTI Crude Oil", "west texas": "WTI Crude Oil",
    "crude": "WTI Crude Oil", "oil": "WTI Crude Oil",
    "brent": "Brent Crude Oil", "brent crude": "Brent Crude Oil",
    "natural gas": "Natural Gas", "natgas": "Natural Gas", "gas": "Natural Gas",
    "gasoline": "RBOB Gasoline", "rbob": "RBOB Gasoline", "petrol": "RBOB Gasoline",
    "heating oil": "Heating Oil",
    "uranium": "Uranium ETF (URA)", "ura": "Uranium ETF (URA)",
    # Metals
    "gold": "Gold", "xau": "Gold",
    "silver": "Silver", "xag": "Silver",
    "copper": "Copper",
    "platinum": "Platinum",
    "palladium": "Palladium",
    # Agriculture
    "corn": "Corn", "maize": "Corn",
    "wheat": "Wheat",
    "soybean": "Soybeans", "soybeans": "Soybeans", "soy": "Soybeans",
    "sugar": "Sugar #11",
    "coffee": "Coffee",
    "cotton": "Cotton",
    # Indices
    "s&p": "S&P 500", "s&p 500": "S&P 500", "sp500": "S&P 500", "spx": "S&P 500",
    "dow": "Dow Jones", "djia": "Dow Jones", "dow jones": "Dow Jones",
    "nasdaq": "NASDAQ", "ndx": "NASDAQ", "tech": "NASDAQ",
    "russell": "Russell 2000", "small cap": "Russell 2000",
    "vix": "VIX (Fear Index)", "fear index": "VIX (Fear Index)", "volatility": "VIX (Fear Index)",
    # Forex
    "dollar index": "US Dollar Index", "dxy": "US Dollar Index", "usd": "US Dollar Index",
    "euro": "EUR/USD", "eurusd": "EUR/USD", "eur": "EUR/USD",
    "yen": "USD/JPY", "jpyjpy": "USD/JPY", "usdjpy": "USD/JPY",
    "pound": "GBP/USD", "gbp": "GBP/USD", "cable": "GBP/USD",
    "cad": "USD/CAD", "canadian dollar": "USD/CAD",
}

CATEGORY_KEYWORDS = {
    "energy": ["energy", "oil", "gas", "fuel", "crude", "petroleum", "rbob", "gasoline",
               "heating oil", "opec", "barrel", "uranium", "power"],
    "metals": ["metal", "gold", "silver", "copper", "platinum", "palladium", "precious",
               "base metal", "commodity metals"],
    "agriculture": ["agri", "agriculture", "grain", "crop", "corn", "wheat", "soy",
                    "sugar", "coffee", "cotton", "soft", "food"],
    "indices": ["index", "indices", "market", "stock", "equity", "s&p", "dow", "nasdaq",
                "russell", "vix", "wall street"],
    "forex": ["forex", "currency", "fx", "dollar", "euro", "yen", "pound", "exchange rate"],
}

CATEGORY_LABELS = {
    "energy": "Energy Markets",
    "metals": "Precious & Base Metals",
    "agriculture": "Agricultural Commodities",
    "indices": "Equity Indices",
    "forex": "Forex / Currencies",
}


# ── helper formatting ───────────────────────────────────────────────────────

def fmt_price(price, unit=""):
    if price is None:
        return "N/A"
    if price < 1:
        s = f"{price:.4f}"
    elif price < 100:
        s = f"{price:,.3f}"
    else:
        s = f"{price:,.2f}"
    return f"{s} {unit}".strip()


def fmt_change(chg, chg_pct):
    if chg is None or chg_pct is None:
        return "change N/A"
    arrow = "▲" if chg_pct > 0 else "▼" if chg_pct < 0 else "→"
    sign = "+" if chg >= 0 else ""
    return f"{arrow} {sign}{chg_pct:.2f}%  ({sign}{chg:.3f})"


def sentiment(chg_pct):
    if chg_pct is None:
        return "flat"
    if chg_pct >= 2:
        return "sharply higher"
    if chg_pct >= 0.5:
        return "higher"
    if chg_pct >= 0:
        return "slightly higher"
    if chg_pct >= -0.5:
        return "slightly lower"
    if chg_pct >= -2:
        return "lower"
    return "sharply lower"


def vix_reading(price):
    if price is None:
        return ""
    if price < 15:
        return "indicating **low fear / complacency** in the market"
    if price < 20:
        return "indicating **calm market conditions**"
    if price < 30:
        return "indicating **elevated uncertainty**"
    if price < 40:
        return "indicating **high fear and volatility**"
    return "indicating **extreme fear / market stress**"


def find_item(name, data):
    """Return (category, info_dict) for a given display name."""
    for cat in ["energy", "metals", "agriculture", "indices", "forex"]:
        items = data.get(cat, {})
        if name in items:
            return cat, items[name]
    return None, None


def all_items(data):
    """Yield (category, name, info) for every instrument."""
    for cat in ["energy", "metals", "agriculture", "indices", "forex"]:
        for name, info in data.get(cat, {}).items():
            yield cat, name, info


def resolve_names(q_lower, data):
    """Return list of display names mentioned in the query."""
    found = set()
    for alias, canonical in ALIASES.items():
        if alias in q_lower:
            cat, info = find_item(canonical, data)
            if cat:
                found.add(canonical)
    return list(found)


def detect_categories(q_lower):
    matched = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            matched.append(cat)
    return matched


# ── single-instrument block ─────────────────────────────────────────────────

def describe_instrument(name, info):
    price = info.get("price")
    unit = info.get("unit", "")
    chg = info.get("change")
    chg_pct = info.get("change_pct")
    symbol = info.get("symbol", "")

    lines = [f"**{name}** `{symbol}`"]
    lines.append(f"- Price: **{fmt_price(price, unit)}**")
    lines.append(f"- Change: {fmt_change(chg, chg_pct)}")

    if chg_pct is not None:
        lines.append(f"- Session: trading {sentiment(chg_pct)} today")

    # Special context
    if name == "VIX (Fear Index)" and price:
        lines.append(f"- Reading: {vix_reading(price)}")
    if name in ("WTI Crude Oil", "Brent Crude Oil") and price:
        if price < 60:
            lines.append("- Context: prices below $60/bbl historically pressure shale producers")
        elif price > 90:
            lines.append("- Context: elevated prices may increase inflation pressure globally")
    if name == "Natural Gas" and price:
        if price < 2:
            lines.append("- Context: sub-$2/MMBtu signals weak demand or oversupply")
        elif price > 4:
            lines.append("- Context: above $4/MMBtu reflects tight supply or high demand")
    if name == "Gold" and price:
        if price > 2000:
            lines.append("- Context: above $2,000/oz indicates strong safe-haven demand")

    return "\n".join(lines)


# ── category summary block ──────────────────────────────────────────────────

def category_summary(cat, data):
    items = data.get(cat, {})
    if not items:
        return f"No data available for {CATEGORY_LABELS.get(cat, cat)}."

    label = CATEGORY_LABELS.get(cat, cat.title())
    lines = [f"### {label}\n"]

    for name, info in items.items():
        price = info.get("price")
        unit = info.get("unit", "")
        chg_pct = info.get("change_pct")
        sym = info.get("symbol", "")

        if price is None:
            lines.append(f"- **{name}** — N/A")
            continue

        arrow = "▲" if (chg_pct or 0) > 0 else "▼" if (chg_pct or 0) < 0 else "→"
        chg_str = f"{arrow} {chg_pct:+.2f}%" if chg_pct is not None else "—"
        lines.append(f"- **{name}** `{sym}`: {fmt_price(price, unit)}  {chg_str}")

    return "\n".join(lines)


# ── movers ──────────────────────────────────────────────────────────────────

def movers_block(data, top_n=5, direction="both", categories=None):
    scored = []
    for cat, name, info in all_items(data):
        if categories and cat not in categories:
            continue
        chg_pct = info.get("change_pct")
        if chg_pct is None:
            continue
        if direction == "up" and chg_pct <= 0:
            continue
        if direction == "down" and chg_pct >= 0:
            continue
        scored.append((cat, name, info, chg_pct))

    if not scored:
        return "No movers data available right now."

    if direction == "down":
        scored.sort(key=lambda x: x[3])
    else:
        scored.sort(key=lambda x: abs(x[3]), reverse=True)

    lines = []
    for i, (cat, name, info, chg_pct) in enumerate(scored[:top_n], 1):
        price = info.get("price")
        unit = info.get("unit", "")
        arrow = "▲" if chg_pct > 0 else "▼"
        lines.append(f"{i}. **{name}** ({CATEGORY_LABELS[cat]}) — {fmt_price(price, unit)}  {arrow} {chg_pct:+.2f}%")

    return "\n".join(lines)


# ── comparison block ────────────────────────────────────────────────────────

def compare_block(names, data):
    lines = ["**Comparison**\n"]
    lines.append(f"{'Instrument':<28} {'Price':<16} {'Change':>10}")
    lines.append("-" * 56)
    for name in names:
        cat, info = find_item(name, data)
        if not info:
            continue
        price_str = fmt_price(info.get("price"), info.get("unit", ""))
        chg_pct = info.get("change_pct")
        chg_str = f"{chg_pct:+.2f}%" if chg_pct is not None else "N/A"
        lines.append(f"{name:<28} {price_str:<16} {chg_str:>10}")
    return "\n".join(lines)


# ── full market snapshot ────────────────────────────────────────────────────

def full_snapshot(data):
    lines = [f"**Full Market Snapshot** — {data.get('timestamp_display', '')}\n"]
    for cat in ["energy", "metals", "agriculture", "indices", "forex"]:
        lines.append(category_summary(cat, data))
        lines.append("")
    return "\n".join(lines)


# ── intent detection ────────────────────────────────────────────────────────

def detect_intent(q):
    q = q.lower()
    tokens = set(re.findall(r'\b\w[\w&/]*\b', q))

    intents = {
        "snapshot": any(w in q for w in ["all", "everything", "snapshot", "overview", "full", "summary of all", "show all", "list all"]),
        "movers_up": any(w in q for w in ["biggest gain", "top gain", "movers up", "highest", "up today", "rallying", "rising"]),
        "movers_down": any(w in q for w in ["biggest loss", "top loss", "movers down", "lowest", "down today", "falling", "dropping", "declining"]),
        "movers_all": any(w in q for w in ["biggest mover", "most active", "volatile", "biggest change", "moved the most", "biggest move"]),
        "compare": any(w in q for w in ["compare", "vs", "versus", "difference between", "which is higher", "which is better"]),
        "category": any(w in q for w in ["energy", "metal", "agri", "grain", "index", "indices", "forex", "currency", "commodit"]),
        "help": any(w in q for w in ["help", "what can you", "what do you", "how do you", "what can i ask"]),
    }
    return intents, q


# ── main brain function ─────────────────────────────────────────────────────

def answer(user_message: str, data: dict, history: list = None) -> str:
    q = user_message.strip()
    intents, q_lower = detect_intent(q)
    ts = data.get("timestamp_display", "")

    # ── HELP ──
    if intents["help"]:
        return (
            "I'm **MarketBot**, your live market intelligence assistant. Here's what you can ask me:\n\n"
            "**Single instruments**\n"
            "- *What's the crude oil price?*\n"
            "- *How is natural gas trading today?*\n"
            "- *Gold price right now*\n\n"
            "**Categories**\n"
            "- *Show me all energy prices*\n"
            "- *Agricultural commodities summary*\n"
            "- *All metals today*\n\n"
            "**Movers & Rankings**\n"
            "- *Biggest movers today*\n"
            "- *What's rising in energy?*\n"
            "- *Top gaining commodities*\n\n"
            "**Comparisons**\n"
            "- *Compare WTI vs Brent*\n"
            "- *Gold vs Silver today*\n\n"
            "**Full Snapshot**\n"
            "- *Show me everything*\n"
            f"\nData last updated: {ts}"
        )

    # ── FULL SNAPSHOT ──
    if intents["snapshot"] and not resolve_names(q_lower, data):
        return full_snapshot(data)

    # ── NAMED INSTRUMENTS ──
    names = resolve_names(q_lower, data)

    if intents["compare"] and len(names) >= 2:
        return compare_block(names, data) + f"\n\n*Data as of {ts}*"

    if len(names) == 1:
        cat, info = find_item(names[0], data)
        return describe_instrument(names[0], info) + f"\n\n*Data as of {ts}*"

    if len(names) > 1:
        parts = []
        for name in names:
            cat, info = find_item(name, data)
            if info:
                parts.append(describe_instrument(name, info))
        if parts:
            return "\n\n---\n\n".join(parts) + f"\n\n*Data as of {ts}*"

    # ── MOVERS ──
    cats = detect_categories(q_lower) or None

    if intents["movers_up"]:
        header = "**Top Gainers Today" + (f" — {CATEGORY_LABELS.get(cats[0], cats[0].title())}" if cats and len(cats) == 1 else "") + "**\n"
        return header + movers_block(data, top_n=5, direction="up", categories=cats) + f"\n\n*Data as of {ts}*"

    if intents["movers_down"]:
        header = "**Biggest Decliners Today" + (f" — {CATEGORY_LABELS.get(cats[0], cats[0].title())}" if cats and len(cats) == 1 else "") + "**\n"
        return header + movers_block(data, top_n=5, direction="down", categories=cats) + f"\n\n*Data as of {ts}*"

    if intents["movers_all"]:
        header = "**Biggest Movers Today" + (f" — {CATEGORY_LABELS.get(cats[0], cats[0].title())}" if cats and len(cats) == 1 else "") + "**\n"
        return header + movers_block(data, top_n=8, direction="both", categories=cats) + f"\n\n*Data as of {ts}*"

    # ── CATEGORY SUMMARY ──
    if cats:
        if len(cats) == 1:
            return category_summary(cats[0], data) + f"\n\n*Data as of {ts}*"
        parts = [category_summary(c, data) for c in cats]
        return "\n\n".join(parts) + f"\n\n*Data as of {ts}*"

    # ── FALLBACK: search all names for partial match ──
    q_words = set(re.findall(r'\b\w+\b', q_lower))
    for cat, name, info in all_items(data):
        name_words = set(re.findall(r'\b\w+\b', name.lower()))
        if q_words & name_words:
            return describe_instrument(name, info) + f"\n\n*Data as of {ts}*"

    # ── GENERIC UNKNOWN ──
    return (
        f"I have live data for **energy**, **metals**, **agriculture**, **indices**, and **forex** markets.\n\n"
        f"Try asking:\n"
        f"- *What's crude oil at?*\n"
        f"- *Show energy prices*\n"
        f"- *Biggest movers today*\n"
        f"- *Gold vs Silver*\n\n"
        f"*Data last updated: {ts}*"
    )
