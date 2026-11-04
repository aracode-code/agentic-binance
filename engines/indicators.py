"""Deterministic technical indicators.

Pure functions over plain lists — no I/O, no pandas, no network. Every
function returns a list aligned with the input series and uses None during
the warm-up period, so callers can tell "not enough candles" apart from a
real value.

Conventions:
- EMA is seeded with the SMA of the first `period` values.
- RSI and ATR use Wilder smoothing (the original definition), not SMA.
- MACD is EMA(fast) - EMA(slow), signal is EMA(signal) of the MACD line.
"""
import math

Number = float


def _empty(values: list) -> list:
    return [None] * len(values)


def sma(values: list[float], period: int) -> list[float | None]:
    """Simple moving average."""
    out = _empty(values)
    if period <= 0 or len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average seeded with the first SMA."""
    out = _empty(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def _rsi_point(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def rsi(values: list[float], period: int = 14) -> list[float | None]:
    """Relative Strength Index with Wilder smoothing."""
    out = _empty(values)
    if period <= 0 or len(values) <= period:
        return out

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta

    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = _rsi_point(avg_gain, avg_loss)

    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_point(avg_gain, avg_loss)

    return out


def macd(
    values: list[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return (macd line, signal line, histogram)."""
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)

    macd_line = _empty(values)
    for i in range(len(values)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    signal_line = _empty(values)
    hist = _empty(values)

    start = next((i for i, v in enumerate(macd_line) if v is not None), None)
    if start is None:
        return macd_line, signal_line, hist

    series = macd_line[start:]
    for offset, value in enumerate(ema(series, signal)):
        if value is None:
            continue
        index = start + offset
        signal_line[index] = value
        hist[index] = series[offset] - value

    return macd_line, signal_line, hist


def bollinger(
    values: list[float],
    period: int = 20,
    mult: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Return (upper, middle, lower) Bollinger bands."""
    middle = sma(values, period)
    upper = _empty(values)
    lower = _empty(values)

    for i in range(period - 1, len(values)):
        mid = middle[i]
        if mid is None:
            continue
        window = values[i - period + 1 : i + 1]
        variance = sum((v - mid) ** 2 for v in window) / period
        deviation = math.sqrt(variance)
        upper[i] = mid + mult * deviation
        lower[i] = mid - mult * deviation

    return upper, middle, lower


def percent_b(values: list[float], period: int = 20, mult: float = 2.0) -> list[float | None]:
    """Position of price inside the bands: 0 = lower band, 1 = upper band."""
    upper, _, lower = bollinger(values, period, mult)
    out = _empty(values)
    for i in range(len(values)):
        if upper[i] is None or lower[i] is None:
            continue
        span = upper[i] - lower[i]
        if span <= 0:
            out[i] = 0.5
            continue
        out[i] = (values[i] - lower[i]) / span
    return out


def band_width(
    values: list[float],
    period: int = 20,
    mult: float = 2.0,
) -> list[float | None]:
    """Band width as a percentage of the middle band (volatility squeeze)."""
    upper, middle, lower = bollinger(values, period, mult)
    out = _empty(values)
    for i in range(len(values)):
        if upper[i] is None or lower[i] is None or not middle[i]:
            continue
        out[i] = (upper[i] - lower[i]) / middle[i] * 100
    return out


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[float | None]:
    """Average True Range with Wilder smoothing."""
    out = _empty(closes)
    if period <= 0 or len(closes) < period + 1:
        return out

    true_ranges = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    prev = sum(true_ranges[1 : period + 1]) / period
    out[period] = prev
    for i in range(period + 1, len(closes)):
        prev = (prev * (period - 1) + true_ranges[i]) / period
        out[i] = prev

    return out


def volume_ratio(volumes: list[float], period: int = 20) -> list[float | None]:
    """Current volume divided by its moving average (None when average is 0)."""
    average = sma(volumes, period)
    out = _empty(volumes)
    for i in range(len(volumes)):
        if average[i] in (None, 0):
            continue
        out[i] = volumes[i] / average[i]
    return out
