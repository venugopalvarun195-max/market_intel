"""
Local market intelligence engine — no API key required.
Understands natural language questions about energy, commodities,
indices, metals, forex, AND Trafigura/Shell company intelligence.
"""

import re
from datetime import datetime

# ── keyword → canonical name mappings ──────────────────────────────────────
ALIASES = {
    "wti": "WTI Crude Oil", "west texas": "WTI Crude Oil",
    "crude": "WTI Crude Oil", "oil": "WTI Crude Oil",
    "brent": "Brent Crude Oil", "brent crude": "Brent Crude Oil",
    "natural gas": "Natural Gas", "natgas": "Natural Gas", "gas": "Natural Gas",
    "gasoline": "RBOB Gasoline", "rbob": "RBOB Gasoline", "petrol": "RBOB Gasoline",
    "heating oil": "Heating Oil",
    "uranium": "Uranium ETF (URA)", "ura": "Uranium ETF (URA)",
    "gold": "Gold", "xau": "Gold",
    "silver": "Silver", "xag": "Silver",
    "copper": "Copper",
    "platinum": "Platinum",
    "palladium": "Palladium",
    "corn": "Corn", "maize": "Corn",
    "wheat": "Wheat",
    "soybean": "Soybeans", "soybeans": "Soybeans", "soy": "Soybeans",
    "sugar": "Sugar #11",
    "coffee": "Coffee",
    "cotton": "Cotton",
    "s&p": "S&P 500", "s&p 500": "S&P 500", "sp500": "S&P 500", "spx": "S&P 500",
    "dow": "Dow Jones", "djia": "Dow Jones", "dow jones": "Dow Jones",
    "nasdaq": "NASDAQ", "ndx": "NASDAQ", "tech": "NASDAQ",
    "russell": "Russell 2000", "small cap": "Russell 2000",
    "vix": "VIX (Fear Index)", "fear index": "VIX (Fear Index)", "volatility": "VIX (Fear Index)",
    "dollar index": "US Dollar Index", "dxy": "US Dollar Index", "usd": "US Dollar Index",
    "euro": "EUR/USD", "eurusd": "EUR/USD", "eur": "EUR/USD",
    "yen": "USD/JPY", "usdjpy": "USD/JPY",
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

# ── Trafigura & Shell knowledge base ───────────────────────────────────────

COMPANY_KB = {
    "trafigura": {
        "overview": """**Trafigura** — one of the world's largest independent commodity trading companies.

**Founded:** 1993 (by Claude Dauphin and others who left Marc Rich & Co)
**HQ:** Singapore (registered), Geneva (key hub), Houston, London
**Ownership:** Private — owned by ~1,000 employees and management (no public listing)
**Revenue:** ~$244 billion (FY2023) — one of the largest privately held companies globally
**Employees:** ~14,000 across 48 countries
**Key products traded:** Crude oil, refined products, LNG, metals & minerals, power""",

        "trading": """**What Trafigura actually trades:**

**Oil & Petroleum Products**
- Trades ~7.2 million barrels/day of crude and refined products
- Major player in West African, North Sea, US Gulf Coast, and Asian crude markets
- Significant presence in physical gasoline, diesel, fuel oil, and naphtha

**LNG & Natural Gas**
- Growing LNG portfolio — long-term SPAs plus active spot/short-term trading
- Operates across Atlantic and Pacific basins
- Key focus on emerging market LNG demand (India, SE Asia, Africa)

**Metals & Minerals**
- Copper, zinc, aluminium, lead — physical trading and concentrates
- Operates Nyrstar (zinc smelting) and Puma Energy (fuel distribution)

**Power**
- Expanding into electricity trading in Europe and the Americas""",

        "strategy": """**Trafigura's strategic direction:**

- **Asset-light model** — avoids large upstream production assets, focuses on logistics and trading
- **Infrastructure ownership** — terminals, pipelines, ports (adds optionality)
- **Emerging markets** — strong presence in Africa, Latin America, Southeast Asia
- **Energy transition** — investing in LNG as transition fuel, copper (EV demand), biofuels
- **Private ownership** — allows long-term thinking without quarterly earnings pressure
- **Balance sheet strength** — uses commodity-backed financing (repos, prepays)

**Recent moves:**
- Expanded LNG desk significantly post-2022 European energy crisis
- Growing power trading book
- Investing in copper mining assets for energy transition exposure""",

        "culture": """**Trafigura culture & what they look for:**

- **Traders are generalists first** — you're expected to understand the full supply chain
- **P&L accountability from day one** — every trade has a clear owner
- **Global mobility** — expect rotations between Geneva, Singapore, Houston, London
- **Entrepreneurial** — flat structure, decisions made fast, close to the market
- **Quantitative rigour** — they want people who can build and defend a cost stack

**Graduate Trader Programme:**
- Highly competitive (~1% acceptance rate)
- Rotations across desks (crude, products, metals, LNG)
- Early responsibility — you'll be placing real trades within months
- Strong preference for candidates who can articulate market structure, not just prices""",

        "interview": """**Trafigura interview prep — what they actually test:**

**Round 1 — Competency + Market Knowledge**
- Walk me through a crude or LNG trade from purchase to sale
- What is Brent–WTI spread telling you right now?
- Why would a cargo go East of Suez vs West?
- What is contango and how would you trade it?

**Round 2 — Trading Case / Numerical**
- Build a full cost stack for a VLCC cargo (WTI → Asia)
- Calculate demurrage on a given laytime scenario
- Which grade would you buy if the arb shows X margin?
- Freight rate just moved 5 WS points — how does your P&L change?

**Round 3 — Senior Trader / MD**
- What's your view on the Atlantic–Pacific LNG arb right now?
- How does OPEC+ production discipline affect your trading strategy?
- Tell me about a market event that changed your view on something

**Key things they're NOT looking for:**
- Memorised textbook definitions
- Generic "I'm passionate about commodities" answers
- Inability to put a number on anything""",

        "news": [
            {"title": "Trafigura Annual Report 2023 — full financial results and strategy", "link": "https://www.trafigura.com/reports-and-publications/annual-report/", "pub": "2023"},
            {"title": "Trafigura expands LNG trading desk amid European energy transition", "link": "https://www.trafigura.com/news-and-insights/", "pub": "2024"},
            {"title": "Trafigura: Commodity Trader Outlook — oil, metals and energy transition", "link": "https://www.trafigura.com/reports-and-publications/", "pub": "2024"},
            {"title": "Trafigura Graduate Trader Programme — applications and requirements", "link": "https://www.trafigura.com/careers/", "pub": "2024"},
            {"title": "Trafigura's role in West African crude markets — trade flow analysis", "link": "https://www.trafigura.com/news-and-insights/", "pub": "2024"},
            {"title": "Trafigura invests in copper assets for energy transition exposure", "link": "https://www.trafigura.com/news-and-insights/", "pub": "2024"},
            {"title": "Trafigura Puma Energy — fuel distribution and downstream strategy", "link": "https://www.pumaenergy.com/", "pub": "2024"},
            {"title": "Trafigura: Understanding commodity-backed financing and prepay structures", "link": "https://www.trafigura.com/reports-and-publications/", "pub": "2024"},
        ]
    },

    "shell": {
        "overview": """**Shell plc** — one of the world's largest integrated energy companies.

**Founded:** 1907 (merger of Royal Dutch Petroleum and Shell Transport)
**HQ:** London, UK (listed on LSE and NYSE)
**Revenue:** ~$316 billion (2023)
**Employees:** ~103,000 globally
**Structure:** Publicly listed (SHEL.L / SHEL)
**Key segments:** Integrated Gas, Upstream, Marketing, Chemicals & Products, Renewables & Energy Solutions""",

        "trading": """**Shell's trading & supply operations:**

**Shell Trading & Supply — one of the world's largest commodity traders**
- Trades ~12-13 million boe/day across oil, gas, LNG, power, and chemicals
- Physically integrated — trading supports the upstream, refining, and retail businesses
- Active in spot, forward, and derivatives markets across all major benchmarks

**LNG — Shell is the world's largest LNG trader**
- Operates ~70 LNG vessels (owned and chartered)
- Long-term SPAs with Qatar, Australia, US, Nigeria, Malaysia (MLNG)
- Runs the largest LNG portfolio globally — balances volumes across Atlantic and Pacific
- Shell is a founding member of the LNG spot market

**Crude Oil**
- Buys equity crude from upstream assets (Nigeria, Gulf of Mexico, Oman, etc.)
- Trades third-party crude to optimise refinery feedstock
- Major player in Dated Brent price formation (participates in MOC window)

**Power & Renewables**
- Growing power trading book — particularly in Europe and North America
- Integrated with renewable generation assets""",

        "strategy": """**Shell's strategic direction:**

- **Integrated Gas** — LNG remains Shell's highest-margin business; protecting and growing this
- **Deepwater & LNG** — focusing upstream capex on highest-return assets
- **Simplification** — divesting refining, chemicals, and upstream assets with poor returns
- **Energy Transition** — investing in biofuels, hydrogen, EV charging (Shell Recharge), carbon credits
- **Trading as competitive advantage** — uses trading to extract value from integrated portfolio
- **Shareholder returns** — aggressive buybacks and dividends post-2022 windfall

**Recent moves:**
- Sold Singapore chemicals complex (2023)
- Acquired renewable natural gas and biogas assets
- Expanded LNG Canada project (largest Canadian LNG project)
- Growing presence in carbon markets and nature-based solutions""",

        "culture": """**Shell Trading & Supply culture:**

- **Analytical rigour** — Shell traders are known for deep fundamental analysis
- **Process-driven** — more structured than independent traders like Trafigura/Vitol
- **Risk management culture** — strong controls, VaR limits, clear escalation paths
- **Global rotation** — London, Singapore, Houston, Rotterdam are key hubs
- **Long-term career development** — Shell invests heavily in graduate training

**Shell Trader Development Programme (TDP):**
- 18-month rotational programme across trading desks
- Exposure to crude, products, LNG, freight, risk
- Strong technical training — you'll learn VaR, Greeks, cargo economics
- More structured than independent trader programmes
- Path to becoming a fully licensed trader with P&L responsibility""",

        "interview": """**Shell Trader Development Programme interview prep:**

**Online Assessment**
- Numerical reasoning, situational judgement, commodity market knowledge quiz

**Video Interview — Market Knowledge**
- Explain the difference between Brent and WTI
- What drives the JKM–TTF spread?
- Walk me through an LNG cargo from liquefaction to regas
- What is Worldscale and how is freight calculated?

**Assessment Centre**
- Group exercise: trade a cargo under time pressure with changing market data
- Case study: given market data, build a P&L and recommend a position
- Competency interview: commercial acumen, resilience, analytical thinking

**Final Interview — Senior Trader**
- What's your view on European gas supply security going into winter?
- How would you hedge a 6-month LNG exposure?
- Walk me through the Brent crude price formation process

**Shell vs Trafigura — key difference:**
Shell values structured thinking and risk framework knowledge.
Trafigura values raw commercial instinct and speed of execution.""",

        "news": [
            {"title": "Shell Annual Report 2023 — Integrated Gas and LNG performance", "link": "https://reports.shell.com/annual-report/2023/", "pub": "2023"},
            {"title": "Shell LNG Outlook 2024 — global demand and supply projections", "link": "https://www.shell.com/energy-and-innovation/natural-gas/lng/lng-outlook-2024.html", "pub": "2024"},
            {"title": "Shell Trader Development Programme — applications open", "link": "https://www.shell.com/careers/students-and-graduates/trading-and-supply.html", "pub": "2024"},
            {"title": "Shell LNG Canada — first cargo milestone and project update", "link": "https://www.shell.com/media/news-and-media-releases.html", "pub": "2024"},
            {"title": "Shell's role in Dated Brent price formation — MOC window participation", "link": "https://www.shell.com/energy-and-innovation/natural-gas.html", "pub": "2024"},
            {"title": "Shell power trading expansion — European renewables integration", "link": "https://www.shell.com/what-we-do/trading-and-supply.html", "pub": "2024"},
            {"title": "Shell vs independent traders — integrated model explained", "link": "https://www.shell.com/what-we-do/trading-and-supply.html", "pub": "2024"},
            {"title": "Shell energy transition strategy — biofuels, hydrogen, carbon credits", "link": "https://www.shell.com/sustainability.html", "pub": "2024"},
        ]
    }
}

# ── Company intent detection ────────────────────────────────────────────────

COMPANY_TRIGGERS = {
    "trafigura": ["trafigura", "traf", "graduate trader programme", "trafigura interview", "trafigura culture"],
    "shell": ["shell", "shell tdp", "trader development programme", "shell trading", "shell lng", "shell interview"],
}

TOPIC_TRIGGERS = {
    "overview":  ["what is", "who is", "tell me about", "overview", "about", "background", "founded", "hq", "history"],
    "trading":   ["what do they trade", "trading", "trade", "commodities", "lng", "crude", "portfolio", "desk"],
    "strategy":  ["strategy", "strategic", "direction", "focus", "future", "plan", "investing", "energy transition"],
    "culture":   ["culture", "work", "working", "life", "team", "structure", "flat", "graduate", "programme", "tdp", "career"],
    "interview": ["interview", "prep", "question", "how to", "round", "assessment", "case study", "what do they ask", "test"],
    "news":      ["news", "latest", "recent", "update", "announcement", "report", "insight"],
}


def detect_company(q_lower):
    for company, triggers in COMPANY_TRIGGERS.items():
        if any(t in q_lower for t in triggers):
            return company
    return None


def detect_company_topic(q_lower):
    for topic, triggers in TOPIC_TRIGGERS.items():
        if any(t in q_lower for t in triggers):
            return topic
    return "overview"


def company_answer(company, topic, q_lower):
    kb = COMPANY_KB[company]
    name = company.capitalize()

    if topic == "news":
        articles = kb.get("news", [])
        lines = [f"**{name} — Latest Insights & Resources**\n"]
        for a in articles:
            lines.append(f"• [{a['title']}]({a['link']})")
        lines.append(f"\nVisit **{'trafigura.com' if company == 'trafigura' else 'shell.com'}** for the latest news.")
        return "\n".join(lines)

    text = kb.get(topic, kb.get("overview", ""))

    # Append a relevant follow-up prompt
    follow_ups = {
        "overview":  f"\n\n*Ask me: '{name} trading portfolio', '{name} strategy', '{name} interview prep'*",
        "trading":   f"\n\n*Ask me: '{name} strategy', '{name} interview questions'*",
        "strategy":  f"\n\n*Ask me: '{name} culture', '{name} interview prep'*",
        "culture":   f"\n\n*Ask me: '{name} interview questions', '{name} graduate programme'*",
        "interview": f"\n\n*Tip: Open the ARB CALC tab to practice building a cost stack — they will ask you to do this.*",
    }
    return text + follow_ups.get(topic, "")


def compare_companies(q_lower):
    return """**Trafigura vs Shell — Key Differences**

| | **Trafigura** | **Shell** |
|---|---|---|
| **Type** | Independent trader (private) | Integrated major (public) |
| **Focus** | Pure trading & logistics | Trading + upstream + downstream |
| **LNG role** | Growing spot/short-term trader | World's largest LNG portfolio |
| **Culture** | Entrepreneurial, fast, flat | Structured, process-driven |
| **Graduate prog** | Trader Programme (highly competitive) | Trader Development Programme (TDP) |
| **Risk appetite** | Higher — proprietary risk | Managed within integrated portfolio |
| **Upside** | Large profit share if successful | Structured salary + bonus |
| **Rotation** | Geneva, Singapore, Houston, London | London, Singapore, Houston, Rotterdam |

**Which is right for you?**
- Choose **Trafigura** if you want raw trading exposure, P&L accountability fast, and entrepreneurial culture
- Choose **Shell** if you want structured training, integrated market exposure, and a defined career path

*Both are elite — getting into either puts you among the top commodity traders in the world.*"""


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
    if chg_pct is None: return "flat"
    if chg_pct >= 2: return "sharply higher"
    if chg_pct >= 0.5: return "higher"
    if chg_pct >= 0: return "slightly higher"
    if chg_pct >= -0.5: return "slightly lower"
    if chg_pct >= -2: return "lower"
    return "sharply lower"


def vix_reading(price):
    if price is None: return ""
    if price < 15: return "indicating **low fear / complacency** in the market"
    if price < 20: return "indicating **calm market conditions**"
    if price < 30: return "indicating **elevated uncertainty**"
    if price < 40: return "indicating **high fear and volatility**"
    return "indicating **extreme fear / market stress**"


def find_item(name, data):
    for cat in ["energy", "metals", "agriculture", "indices", "forex"]:
        items = data.get(cat, {})
        if name in items:
            return cat, items[name]
    return None, None


def all_items(data):
    for cat in ["energy", "metals", "agriculture", "indices", "forex"]:
        for name, info in data.get(cat, {}).items():
            yield cat, name, info


def resolve_names(q_lower, data):
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


def movers_block(data, top_n=5, direction="both", categories=None):
    scored = []
    for cat, name, info in all_items(data):
        if categories and cat not in categories:
            continue
        chg_pct = info.get("change_pct")
        if chg_pct is None: continue
        if direction == "up" and chg_pct <= 0: continue
        if direction == "down" and chg_pct >= 0: continue
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


def compare_block(names, data):
    lines = ["**Comparison**\n"]
    lines.append(f"{'Instrument':<28} {'Price':<16} {'Change':>10}")
    lines.append("-" * 56)
    for name in names:
        cat, info = find_item(name, data)
        if not info: continue
        price_str = fmt_price(info.get("price"), info.get("unit", ""))
        chg_pct = info.get("change_pct")
        chg_str = f"{chg_pct:+.2f}%" if chg_pct is not None else "N/A"
        lines.append(f"{name:<28} {price_str:<16} {chg_str:>10}")
    return "\n".join(lines)


def full_snapshot(data):
    lines = [f"**Full Market Snapshot** — {data.get('timestamp_display', '')}\n"]
    for cat in ["energy", "metals", "agriculture", "indices", "forex"]:
        lines.append(category_summary(cat, data))
        lines.append("")
    return "\n".join(lines)


def detect_intent(q):
    q = q.lower()
    intents = {
        "snapshot":    any(w in q for w in ["all", "everything", "snapshot", "overview", "full", "show all", "list all"]),
        "movers_up":   any(w in q for w in ["biggest gain", "top gain", "movers up", "highest", "up today", "rallying", "rising"]),
        "movers_down": any(w in q for w in ["biggest loss", "top loss", "movers down", "lowest", "down today", "falling", "dropping"]),
        "movers_all":  any(w in q for w in ["biggest mover", "most active", "volatile", "biggest change", "moved the most"]),
        "compare":     any(w in q for w in ["compare", "vs", "versus", "difference between", "which is higher"]),
        "category":    any(w in q for w in ["energy", "metal", "agri", "grain", "index", "indices", "forex", "currency"]),
        "help":        any(w in q for w in ["help", "what can you", "what do you", "how do you", "what can i ask"]),
    }
    return intents, q


# ── main brain function ─────────────────────────────────────────────────────

def answer(user_message: str, data: dict, history: list = None) -> str:
    q = user_message.strip()
    intents, q_lower = detect_intent(q)
    ts = data.get("timestamp_display", "")

    # ── COMPANY INTELLIGENCE (Trafigura / Shell) ──
    company = detect_company(q_lower)

    if company:
        # Compare both companies
        if ("vs" in q_lower or "versus" in q_lower or "difference" in q_lower or "compare" in q_lower) \
                and "trafigura" in q_lower and ("shell" in q_lower):
            return compare_companies(q_lower)

        topic = detect_company_topic(q_lower)
        return company_answer(company, topic, q_lower)

    # ── HELP ──
    if intents["help"]:
        return (
            "I'm **MarketBot**, your live market intelligence and trading career assistant.\n\n"
            "**Market Data**\n"
            "- *What's the crude oil price?*\n"
            "- *Show energy prices / all metals*\n"
            "- *Biggest movers today*\n"
            "- *Compare WTI vs Brent*\n\n"
            "**Company Intelligence**\n"
            "- *Tell me about Trafigura*\n"
            "- *Shell trading strategy*\n"
            "- *Trafigura interview questions*\n"
            "- *Shell TDP prep*\n"
            "- *Trafigura vs Shell — which is better?*\n\n"
            "**Arb Calculator**\n"
            "- Switch to the ARB CALC tab to model LNG and crude arbitrage trades\n\n"
            f"*Data last updated: {ts}*"
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

    # ── FALLBACK: partial name match ──
    q_words = set(re.findall(r'\b\w+\b', q_lower))
    for cat, name, info in all_items(data):
        name_words = set(re.findall(r'\b\w+\b', name.lower()))
        if q_words & name_words:
            return describe_instrument(name, info) + f"\n\n*Data as of {ts}*"

    # ── GENERIC FALLBACK ──
    return (
        "I have live market data and company intelligence. Try asking:\n\n"
        "**Markets:** *crude oil price*, *energy snapshot*, *biggest movers*\n"
        "**Trafigura:** *tell me about Trafigura*, *Trafigura interview questions*\n"
        "**Shell:** *Shell TDP prep*, *Shell LNG strategy*\n"
        "**Compare:** *Trafigura vs Shell*\n\n"
        f"*Data last updated: {ts}*"
    )
