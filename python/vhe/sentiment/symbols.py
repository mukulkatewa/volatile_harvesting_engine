from __future__ import annotations

import re

# NSE tickers → search aliases for social/news matching.
SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "RELIANCE": ("RELIANCE", "Reliance Industries", "RIL", "Reliance stock"),
    "HDFCBANK": ("HDFCBANK", "HDFC Bank", "HDFC bank stock"),
    "ICICIBANK": ("ICICIBANK", "ICICI Bank"),
    "INFY": ("INFY", "Infosys", "Infosys stock"),
    "TCS": ("TCS", "Tata Consultancy", "TCS stock"),
    "SBIN": ("SBIN", "State Bank", "SBI stock"),
    "BHARTIARTL": ("BHARTIARTL", "Airtel", "Bharti Airtel"),
    "ITC": ("ITC", "ITC stock", "ITC Ltd"),
    "LT": ("LT", "Larsen Toubro", "L&T stock"),
    "KOTAKBANK": ("KOTAKBANK", "Kotak Bank"),
    "BEL": ("BEL", "Bharat Electronics"),
    "WIPRO": ("WIPRO", "Wipro", "Wipro stock"),
    "HCLTECH": ("HCLTECH", "HCL Tech", "HCL Technologies"),
    "AXISBANK": ("AXISBANK", "Axis Bank", "Axis bank stock"),
    "MARUTI": ("MARUTI", "Maruti Suzuki", "Maruti stock"),
    "SUNPHARMA": ("SUNPHARMA", "Sun Pharma", "Sun Pharmaceutical"),
    "TATAMOTORS": ("TATAMOTORS", "Tata Motors"),
}


def search_queries(symbol: str) -> list[str]:
    aliases = SYMBOL_ALIASES.get(symbol, (symbol,))
    primary = aliases[0]
    return [
        f"{primary} NSE India stock",
        f"{primary} stock India",
        f"subreddit:IndiaInvestments {primary}",
        f"subreddit:IndianStreetBets {primary}",
    ]


def match_symbol(text: str, symbol: str) -> bool:
    lowered = text.lower()
    for alias in SYMBOL_ALIASES.get(symbol, (symbol,)):
        alias_lower = alias.lower()
        if len(alias_lower) <= 4:
            if re.search(rf"\b{re.escape(alias_lower)}\b", lowered):
                return True
        elif alias_lower in lowered:
            return True
    return False
