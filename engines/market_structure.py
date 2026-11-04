"""Market structure detection: swings, BOS/CHoCH, S/R, breakout state.

Heuristics over closed candles only. Each rule is written down in the
docstring so the output can be audited and tested, instead of being an
implicit LLM judgement.
"""
from dataclasses import dataclass

from engines.indicators import volume_ratio


@dataclass(frozen=True)
class Swing:
    kind: str    # "HIGH" | "LOW"
    index: int
    price: float


@dataclass(frozen=True)
class Event:
    kind: str        # "BOS" | "CHoCH"
    direction: str   # "BULLISH" | "BEARISH"
    level: float


def swing_points(
    highs: list[float],
    lows: list[float],
    left: int = 2,
    right: int = 2,
) -> list[Swing]:
    """Fractal swings: a bar must be the strict extreme of its window.

    A swing is only confirmed once `right` bars have closed after it, so the
    most recent bars never count (no repainting).
    """
    swings: list[Swing] = []
    for i in range(left, len(highs) - right):
        high_window = highs[i - left : i + right + 1]
        if highs[i] == max(high_window) and high_window.count(highs[i]) == 1:
            swings.append(Swing("HIGH", i, highs[i]))

        low_window = lows[i - left : i + right + 1]
        if lows[i] == min(low_window) and low_window.count(lows[i]) == 1:
            swings.append(Swing("LOW", i, lows[i]))

    return swings


def classify_structure(swings: list[Swing]) -> str:
    """Compare the last two swing highs and lows: HH_HL, LH_LL, MIXED, UNKNOWN."""
    highs = [s.price for s in swings if s.kind == "HIGH"]
    lows = [s.price for s in swings if s.kind == "LOW"]

    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"

    higher_high = highs[-1] > highs[-2]
    higher_low = lows[-1] > lows[-2]

    if higher_high and higher_low:
        return "HH_HL"
    if not higher_high and not higher_low:
        return "LH_LL"
    return "MIXED"


def detect_bos(closes: list[float], swings: list[Swing]) -> Event | None:
    """Break of structure: last close beyond the last confirmed swing.

    Bullish when the close is above the latest swing high, bearish when it is
    below the latest swing low.
    """
    if not closes or not swings:
        return None

    last_close = closes[-1]
    highs = [s for s in swings if s.kind == "HIGH"]
    lows = [s for s in swings if s.kind == "LOW"]

    if highs and last_close > highs[-1].price:
        return Event("BOS", "BULLISH", highs[-1].price)
    if lows and last_close < lows[-1].price:
        return Event("BOS", "BEARISH", lows[-1].price)
    return None


def detect_choch(
    closes: list[float],
    swings: list[Swing],
    structure: str,
) -> Event | None:
    """Change of character: a BOS pointing against the prevailing structure."""
    bos = detect_bos(closes, swings)
    if bos is None:
        return None

    if structure == "HH_HL" and bos.direction == "BEARISH":
        return Event("CHoCH", "BEARISH", bos.level)
    if structure == "LH_LL" and bos.direction == "BULLISH":
        return Event("CHoCH", "BULLISH", bos.level)
    return None


def _cluster(levels: list[float], tolerance: float = 0.002) -> list[float]:
    """Drop levels that sit within `tolerance` of an already kept level."""
    kept: list[float] = []
    for level in levels:
        if all(abs(level - other) / other > tolerance for other in kept):
            kept.append(level)
    return kept


def support_resistance(
    swings: list[Swing],
    price: float,
    n: int = 3,
) -> tuple[list[float], list[float]]:
    """Nearest swing lows below price and swing highs above it."""
    supports = sorted(
        (s.price for s in swings if s.kind == "LOW" and s.price < price),
        reverse=True,
    )
    resistances = sorted(
        s.price for s in swings if s.kind == "HIGH" and s.price > price
    )
    return _cluster(supports)[:n], _cluster(resistances)[:n]


def breakout_state(
    closes: list[float],
    volumes: list[float],
    lookback: int = 20,
    volume_threshold: float = 1.5,
) -> str:
    """Classify the last bar against the prior range high.

    Reference high is the highest close of the `lookback` bars ending two bars
    before the last one, so the breakout bar itself cannot raise the level.

    NONE                : still inside the range
    BREAKOUT_WEAK       : first close above the range, volume below threshold
    BREAKOUT_CONFIRMED  : first close above the range, volume at/above threshold
    RETEST              : already above the range, price returned near the level
    """
    if len(closes) < lookback + 2:
        return "NONE"

    prior_high = max(closes[-(lookback + 2) : -2])
    last_close = closes[-1]
    prev_close = closes[-2]

    if last_close <= prior_high:
        return "NONE"

    if prev_close <= prior_high:
        ratios = volume_ratio(volumes, 20)
        ratio = ratios[-1] if ratios else None
        return "BREAKOUT_CONFIRMED" if (ratio or 0) >= volume_threshold else "BREAKOUT_WEAK"

    if last_close <= prior_high * 1.003:
        return "RETEST"
    return "NONE"
