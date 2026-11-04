"""Binance Futures data fetching tool.

Single responsibility: fetch raw market data from Binance Futures API.
- No analysis
- No DeepSeek calls
- No indicator calculation

Each function is independently testable and returns raw API response.
"""
import hashlib
import hmac
import time

import requests

from config.settings import USE_TESTNET

# Base URL depends on testnet/mainnet mode
BASE_URL = (
    "https://testnet.binancefuture.com" if USE_TESTNET else "https://fapi.binance.com"
)

# Exclude top market-cap coins — focus on mid/small caps
EXCLUDED_SYMBOLS = {
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    "LINKUSDT", "UNIUSDT", "LTCUSDT", "BCHUSDT", "ATOMUSDT",
}


def get_ticker(symbol: str) -> dict:
    """Get 24hr ticker price change statistics for a symbol."""
    url = f"{BASE_URL}/fapi/v1/ticker/24hr"
    response = requests.get(url, params={"symbol": symbol}, timeout=10)
    response.raise_for_status()
    return response.json()


def get_klines(symbol: str, interval: str = "1h", limit: int = 100) -> list:
    """Get kline (candlestick) data for a symbol."""
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_5m_change(symbol: str) -> dict:
    """Get price change percentage on the 5-minute timeframe.

    Calculates change between the last two 5m candles:
    ((close_now - close_prev) / close_prev) * 100

    Returns:
        {
            "symbol": symbol,
            "change_pct": float,   # +/- percentage
            "price": float,        # current price (last close)
            "open": float,         # open of current candle
            "high": float,
            "low": float,
            "volume": float,
        }
    """
    klines = get_klines(symbol, interval="5m", limit=2)
    if len(klines) < 2:
        return {"symbol": symbol, "change_pct": 0.0, "price": 0.0, "open": 0.0, "high": 0.0, "low": 0.0, "volume": 0.0}

    prev_close = float(klines[-2][4])   # close of previous 5m candle
    current_close = float(klines[-1][4])  # close of current 5m candle

    if prev_close == 0:
        change_pct = 0.0
    else:
        change_pct = ((current_close - prev_close) / prev_close) * 100

    return {
        "symbol": symbol,
        "change_pct": round(change_pct, 4),
        "price": current_close,
        "open": float(klines[-1][1]),
        "high": float(klines[-1][2]),
        "low": float(klines[-1][3]),
        "volume": float(klines[-1][5]),
    }


def get_funding_rate(symbol: str, limit: int = 30) -> list:
    """Get funding rate history for a symbol."""
    url = f"{BASE_URL}/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": limit}
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def get_premium_index(symbol: str) -> dict:
    """Get mark price, index price, and funding rate for a symbol."""
    url = f"{BASE_URL}/fapi/v1/premiumIndex"
    response = requests.get(url, params={"symbol": symbol}, timeout=10)
    response.raise_for_status()
    return response.json()


def get_top_tickers(limit: int = 10) -> list[dict]:
    """Get top trading pairs sorted by 24h volume.

    Excludes large-cap coins (BTC, ETH, SOL, etc.) to focus
    on mid/small caps with higher volatility.
    """
    url = f"{BASE_URL}/fapi/v1/ticker/24hr"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    all_tickers = response.json()

    usdt_pairs = [
        t for t in all_tickers
        if t["symbol"].endswith("USDT")
        and not any(x in t["symbol"] for x in ["BUSD", "USDC", "TUSD"])
        and t["symbol"] not in EXCLUDED_SYMBOLS
    ]

    usdt_pairs.sort(key=lambda t: float(t["quoteVolume"]), reverse=True)
    return usdt_pairs[:limit]


def get_open_interest(symbol: str) -> dict:
    """Get current open interest for a symbol."""
    url = f"{BASE_URL}/fapi/v1/openInterest"
    response = requests.get(url, params={"symbol": symbol}, timeout=10)
    response.raise_for_status()
    return response.json()


def get_positions() -> list:
    """Get current open positions (authenticated).

    Requires:
        BINANCE_API_KEY and BINANCE_API_SECRET in .env
        with Futures permission enabled.
    """
    from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET

    api_key = BINANCE_API_KEY
    api_secret = BINANCE_API_SECRET
    if not api_key or not api_secret:
        return []

    timestamp = int(time.time() * 1000)
    query = f"timestamp={timestamp}"
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    url = f"{BASE_URL}/fapi/v2/positionRisk"
    headers = {"X-MBX-APIKEY": api_key}
    params = {"timestamp": timestamp, "signature": signature}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return [p for p in data if float(p.get("positionAmt", 0)) != 0]


def get_trade_history(symbol: str, limit: int = 20) -> list:
    """Get trade history for a symbol (authenticated).

    Requires:
        BINANCE_API_KEY and BINANCE_API_SECRET in .env
    """
    from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET

    api_key = BINANCE_API_KEY
    api_secret = BINANCE_API_SECRET
    if not api_key or not api_secret:
        return []

    timestamp = int(time.time() * 1000)
    query = f"limit={limit}&symbol={symbol}&timestamp={timestamp}"
    signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

    url = f"{BASE_URL}/fapi/v1/userTrades"
    headers = {"X-MBX-APIKEY": api_key}
    params = {"limit": limit, "symbol": symbol, "timestamp": timestamp, "signature": signature}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    return response.json()

