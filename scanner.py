"""Market Scanner — scan top coins by volume on 5M timeframe.

Single responsibility: get top 10 USDT pairs by volume,
fetch 5M klines, classify trend as bullish/bearish/pullback.

Uses simple EMA(20) — no DeepSeek, no complex indicators.
Fast and free.
"""
import sys

from tools.binance_tool import get_5m_change, get_klines, get_top_tickers


def ema(values: list[float], period: int) -> list[float]:
    """Calculate EMA (Exponential Moving Average)."""
    k = 2 / (period + 1)
    ema_values = [values[0]]
    for price in values[1:]:
        ema_values.append(price * k + ema_values[-1] * (1 - k))
    return ema_values


def classify_trend(symbol: str) -> tuple[str, float, float]:
    """Classify trend for a symbol on 5M timeframe."""
    klines = get_klines(symbol, interval="5m", limit=30)
    closes = [float(k[4]) for k in klines]

    ema_values = ema(closes, 20)
    current_price = closes[-1]
    current_ema = ema_values[-1]
    recent_high = max(closes[-10:])

    if current_price < recent_high * 0.98 and current_price > current_ema:
        return "PULLBACK", current_price, current_ema

    if current_price > current_ema and ema_values[-1] > ema_values[-5]:
        return "BULLISH", current_price, current_ema

    if current_price < current_ema and ema_values[-1] < ema_values[-5]:
        return "BEARISH", current_price, current_ema

    return "NEUTRAL", current_price, current_ema


def get_scan_data(top_n: int = 10) -> dict:
    """Get scan data as structured dict for GUI.

    Rows are sorted by 5-minute price change (highest gainers first).
    Also splits rows into those that ROSE (>= 0%) and those that FELL (< 0%)
    on the 5-minute timeframe.
    """
    # Fetch more tickers than displayed so we're likely to catch
    # coins that are actually falling on the 5M timeframe.
    fetch_n = max(top_n, 30)
    tickers = get_top_tickers(limit=fetch_n)
    if not tickers:
        return {}

    rows = []
    bullish = []
    bearish = []
    pullback = []

    for ticker in tickers:
        symbol = ticker["symbol"]
        try:
            change_data = get_5m_change(symbol)
            trend, price, ema_val = classify_trend(symbol)
            change_5m = change_data["change_pct"]
            rows.append({
                "symbol": symbol,
                "price": price,
                "change": change_5m,          # 5-minute change %
                "trend": trend,
                "volume": change_data["volume"],
            })
            if trend == "BULLISH":
                bullish.append(symbol)
            elif trend == "BEARISH":
                bearish.append(symbol)
            elif trend == "PULLBACK":
                pullback.append(symbol)
        except Exception:
            pass

    # Sort by 5-minute change, highest gainers first
    rows.sort(key=lambda r: r["change"], reverse=True)

    # Split into coins that rose vs fell on the 5M timeframe
    gainers = [r for r in rows if r["change"] >= 0]
    losers = [r for r in rows if r["change"] < 0]

    # 5-minute top movers
    top_gainers = gainers[:top_n]
    top_losers = losers[:top_n]

    return {
        "rows": rows,
        "bullish": bullish,
        "bearish": bearish,
        "pullback": pullback,
        "gainers": gainers,
        "losers": losers,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
    }


def scan(top_n: int = 10) -> None:
    """Scan top N pairs and print results."""
    print("Fetching top pairs by volume...\n")

    data = get_scan_data(top_n)
    if not data:
        print("No tickers found. Check your connection.")
        return

    print(f"{'Symbol':<12} {'Price':>10} {'5M Change%':>10} {'Trend':<10}")
    print("-" * 48)

    for row in data["rows"]:
        print(f"{row['symbol']:<12} {row['price']:>10.4f} {row['change']:>+9.2f}% {row['trend']:<10}")

    print("\n" + "=" * 55)
    print(f"BULLISH ({len(data['bullish'])}): {', '.join(data['bullish']) if data['bullish'] else 'none'}")
    print(f"BEARISH ({len(data['bearish'])}): {', '.join(data['bearish']) if data['bearish'] else 'none'}")
    print(f"PULLBACK ({len(data['pullback'])}): {', '.join(data['pullback']) if data['pullback'] else 'none'}")

    print("\n" + "=" * 55)
    print("TOP MOVERS (5M)")
    print("=" * 55)

    print(f"\n{'NAIK (5M)':}")
    print(f"{'Symbol':<12} {'Price':>10} {'5M Change%':>10}")
    print("-" * 38)
    for t in data["top_gainers"] or [{"symbol": "-", "price": 0, "change": 0}]:
        change = float(t["change"])
        price = float(t["price"])
        print(f"{t['symbol']:<12} {price:>10.4f} {change:>+9.2f}%")

    print(f"\n{'TURUN (5M)':}")
    print(f"{'Symbol':<12} {'Price':>10} {'5M Change%':>10}")
    print("-" * 38)
    for t in data["top_losers"] or [{"symbol": "-", "price": 0, "change": 0}]:
        change = float(t["change"])
        price = float(t["price"])
        print(f"{t['symbol']:<12} {price:>10.4f} {change:>+9.2f}%")

    print("=" * 55)


def main() -> None:
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    scan(top_n)


if __name__ == "__main__":
    main()