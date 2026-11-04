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
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from config.settings import USE_TESTNET
from tools.cache import get_or_fetch

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


def _signed_get(path: str, params: dict | None = None):
    """GET a signed Futures endpoint.

    The query string is built once and signed, then sent verbatim, so the
    signature cannot drift from the parameters Binance receives.
    """
    from config.settings import BINANCE_API_KEY, BINANCE_API_SECRET

    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET belum diisi di .env")

    query = dict(params or {})
    query["timestamp"] = int(time.time() * 1000)
    query["recvWindow"] = 5000
    payload = urlencode(query)
    signature = hmac.new(
        BINANCE_API_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    url = f"{BASE_URL}{path}?{payload}&signature={signature}"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def get_account_state() -> dict:
    """Read-only account snapshot used by the risk manager.

    Returns:
        {
            "total_wallet_balance": float,  # equity used for sizing
            "available_balance": float,
            "unrealized_pnl": float,
            "open_positions": int,
            "open_symbols": list[str],
            "today_realized_pnl": float | None,  # None when unreadable
        }
    """
    account = _signed_get("/fapi/v2/account")

    positions = [
        p for p in account.get("positions", [])
        if float(p.get("positionAmt", 0) or 0) != 0
    ]

    return {
        "total_wallet_balance": float(account.get("totalWalletBalance", 0) or 0),
        "available_balance": float(account.get("availableBalance", 0) or 0),
        "unrealized_pnl": float(account.get("totalUnrealizedProfit", 0) or 0),
        "open_positions": len(positions),
        "open_symbols": sorted({p.get("symbol", "") for p in positions}),
        "today_realized_pnl": _today_realized_pnl(),
    }


def _today_realized_pnl() -> float | None:
    """Sum of realized PnL since 00:00 UTC; None when the key cannot read it."""
    start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    try:
        rows = _signed_get(
            "/fapi/v1/income",
            {
                "incomeType": "REALIZED_PNL",
                "startTime": int(start.timestamp() * 1000),
                "limit": 1000,
            },
        )
    except requests.HTTPError:
        return None

    return sum(float(row.get("income", 0) or 0) for row in rows)


EXCHANGE_INFO_TTL = 3600


def _fetch_exchange_info() -> dict:
    response = requests.get(f"{BASE_URL}/fapi/v1/exchangeInfo", timeout=15)
    response.raise_for_status()
    return response.json()


def get_symbol_filters(symbol: str) -> dict:
    """Trading filters for a symbol, cached for an hour."""
    info = get_or_fetch("exchange_info", EXCHANGE_INFO_TTL, _fetch_exchange_info)
    return parse_symbol_filters(info, symbol)


def parse_symbol_filters(info: dict, symbol: str) -> dict:
    """Extract step size, minimums, and tick size from an exchangeInfo payload."""
    for item in info.get("symbols", []):
        if item.get("symbol") != symbol:
            continue

        filters = {f.get("filterType"): f for f in item.get("filters", [])}
        lot = filters.get("LOT_SIZE", {})
        # Binance renamed MIN_NOTIONAL to NOTIONAL; accept both shapes.
        notional = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
        price = filters.get("PRICE_FILTER", {})

        return {
            "symbol": symbol,
            "step_size": float(lot.get("stepSize", 0) or 0),
            "min_qty": float(lot.get("minQty", 0) or 0),
            "max_qty": float(lot.get("maxQty", 0) or 0),
            "min_notional": float(
                notional.get("notional") or notional.get("minNotional") or 0
            ),
            "price_tick": float(price.get("tickSize", 0) or 0),
        }

    raise ValueError(f"{symbol} tidak ditemukan di exchangeInfo")

