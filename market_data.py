import yfinance as yf
from datetime import datetime
import threading

# Ticker map: category -> {display_name: symbol}
TICKERS = {
    "energy": {
        "WTI Crude Oil": ("CL=F", "$/bbl"),
        "Brent Crude Oil": ("BZ=F", "$/bbl"),
        "Natural Gas": ("NG=F", "$/MMBtu"),
        "RBOB Gasoline": ("RB=F", "$/gal"),
        "Heating Oil": ("HO=F", "$/gal"),
        "Uranium ETF (URA)": ("URA", "$"),
    },
    "metals": {
        "Gold": ("GC=F", "$/oz"),
        "Silver": ("SI=F", "$/oz"),
        "Copper": ("HG=F", "$/lb"),
        "Platinum": ("PL=F", "$/oz"),
        "Palladium": ("PA=F", "$/oz"),
    },
    "agriculture": {
        "Corn": ("ZC=F", "¢/bu"),
        "Wheat": ("ZW=F", "¢/bu"),
        "Soybeans": ("ZS=F", "¢/bu"),
        "Sugar #11": ("SB=F", "¢/lb"),
        "Coffee": ("KC=F", "¢/lb"),
        "Cotton": ("CT=F", "¢/lb"),
    },
    "indices": {
        "S&P 500": ("^GSPC", "pts"),
        "Dow Jones": ("^DJI", "pts"),
        "NASDAQ": ("^IXIC", "pts"),
        "Russell 2000": ("^RUT", "pts"),
        "VIX (Fear Index)": ("^VIX", ""),
    },
    "forex": {
        "US Dollar Index": ("DX-Y.NYB", ""),
        "EUR/USD": ("EURUSD=X", ""),
        "USD/JPY": ("JPY=X", ""),
        "GBP/USD": ("GBPUSD=X", ""),
        "USD/CAD": ("CAD=X", ""),
    },
}

_cache = {}
_cache_lock = threading.Lock()
_last_fetch_time = None


def _fetch_ticker(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        price = getattr(fast, "last_price", None)
        prev = getattr(fast, "previous_close", None)

        if price is None:
            hist = ticker.history(period="2d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])

        change = None
        change_pct = None
        if price is not None and prev is not None and prev != 0:
            change = price - prev
            change_pct = (change / prev) * 100

        return {
            "price": round(price, 4) if price is not None else None,
            "prev_close": round(prev, 4) if prev is not None else None,
            "change": round(change, 4) if change is not None else None,
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
        }
    except Exception as e:
        return {"price": None, "prev_close": None, "change": None, "change_pct": None, "error": str(e)}


def fetch_all_market_data(force: bool = False) -> dict:
    global _last_fetch_time

    with _cache_lock:
        now = datetime.now()
        # Refresh cache every 5 minutes unless forced
        if not force and _last_fetch_time and (now - _last_fetch_time).seconds < 300 and _cache:
            return dict(_cache)

        result = {}
        for category, items in TICKERS.items():
            result[category] = {}
            for name, (symbol, unit) in items.items():
                data = _fetch_ticker(symbol)
                result[category][name] = {
                    "symbol": symbol,
                    "unit": unit,
                    **data,
                }

        result["timestamp"] = now.isoformat()
        result["timestamp_display"] = now.strftime("%b %d, %Y %I:%M %p")

        _cache.clear()
        _cache.update(result)
        _last_fetch_time = now

    return dict(result)


def build_market_context(data: dict) -> str:
    """Format market data as a clean text block for the Claude system prompt."""
    lines = [f"LIVE MARKET DATA — {data.get('timestamp_display', 'Unknown time')}\n"]

    category_labels = {
        "energy": "ENERGY MARKETS",
        "metals": "PRECIOUS & BASE METALS",
        "agriculture": "AGRICULTURAL COMMODITIES",
        "indices": "EQUITY INDICES",
        "forex": "FOREX / USD",
    }

    for cat, label in category_labels.items():
        items = data.get(cat, {})
        if not items:
            continue
        lines.append(f"\n{label}")
        lines.append("-" * 40)
        for name, info in items.items():
            price = info.get("price")
            unit = info.get("unit", "")
            chg = info.get("change_pct")
            symbol = info.get("symbol", "")

            if price is not None:
                price_str = f"{price:,.4f}" if price < 100 else f"{price:,.2f}"
                if unit:
                    price_str += f" {unit}"
                if chg is not None:
                    arrow = "▲" if chg > 0 else "▼" if chg < 0 else "→"
                    chg_str = f"  {arrow} {chg:+.2f}%"
                else:
                    chg_str = ""
                lines.append(f"  {name} ({symbol}): {price_str}{chg_str}")
            else:
                lines.append(f"  {name} ({symbol}): N/A")

    return "\n".join(lines)
