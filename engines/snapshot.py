"""Build the deterministic multi-timeframe snapshot.

Candles come from Binance (cached per interval); every number in the result
is computed by engines.indicators / engines.market_structure, so the LLM
receives facts instead of raw OHLCV to interpret.
"""
from datetime import datetime

from engines.indicators import (
    atr,
    band_width,
    ema,
    macd,
    percent_b,
    rsi,
    sma,
    volume_ratio,
)
from engines.market_structure import (
    breakout_state,
    classify_structure,
    support_resistance,
    swing_points,
)
from models.market_snapshot import MarketSnapshot, TimeframeSnapshot
from tools.binance_tool import get_klines
from tools.cache import get_or_fetch

TIMEFRAMES = ("1d", "4h", "1h", "15m")
CANDLE_LIMIT = 250
TTL_SECONDS = {"15m": 60, "1h": 120, "4h": 600, "1d": 1800}

EMA_PERIODS = (9, 21, 50, 200)
SMA_PERIODS = (7, 25, 99)

# An indicator is only meaningful once every period has enough candles.
REQUIRED_CANDLES = max(EMA_PERIODS + SMA_PERIODS) + 1


def load_klines(symbol: str, interval: str) -> list:
    """Fetch klines through the TTL cache."""
    ttl = TTL_SECONDS.get(interval, 60)
    key = f"klines:{symbol}:{interval}:{CANDLE_LIMIT}"
    return get_or_fetch(key, ttl, lambda: get_klines(symbol, interval, CANDLE_LIMIT))


def _last(values: list) -> float | None:
    return values[-1] if values else None


def _ema_bias(close: float, ema50: float | None, ema200: float | None) -> str:
    if ema50 is None:
        return "unknown"
    if ema200 is None:
        return "bullish" if close > ema50 else "bearish" if close < ema50 else "mixed"
    if close > ema50 and close > ema200:
        return "bullish"
    if close < ema50 and close < ema200:
        return "bearish"
    return "mixed"


def build_timeframe(symbol: str, interval: str, klines: list) -> TimeframeSnapshot:
    """Compute the snapshot of one timeframe from raw klines."""
    if len(klines) < 2:
        raise ValueError(f"{interval}: butuh minimal 2 candle, dapat {len(klines)}")

    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    close = closes[-1]
    previous = closes[-2]
    change_pct = ((close - previous) / previous * 100) if previous else None

    ema_values = {str(p): _last(ema(closes, p)) for p in EMA_PERIODS}
    sma_values = {str(p): _last(sma(closes, p)) for p in SMA_PERIODS}

    macd_line, macd_signal, macd_hist = macd(closes)

    atr_value = _last(atr(highs, lows, closes))

    swings = swing_points(highs, lows)
    structure = classify_structure(swings)
    supports, resistances = support_resistance(swings, close)

    return TimeframeSnapshot(
        timeframe=interval,
        candles=len(closes),
        close=close,
        change_pct=change_pct,
        ema=ema_values,
        sma=sma_values,
        ema_bias=_ema_bias(close, ema_values["50"], ema_values["200"]),
        rsi=_last(rsi(closes)),
        macd=_last(macd_line),
        macd_signal=_last(macd_signal),
        macd_hist=_last(macd_hist),
        bb_percent_b=_last(percent_b(closes)),
        bb_width=_last(band_width(closes)),
        atr=atr_value,
        atr_pct=(atr_value / close * 100) if atr_value is not None and close else None,
        volume_ratio=_last(volume_ratio(volumes)),
        structure=structure,
        breakout=breakout_state(closes, volumes),
        support=supports,
        resistance=resistances,
    )


def build_snapshot(symbol: str) -> MarketSnapshot:
    """Build the snapshot for every tracked timeframe.

    A timeframe that fails to load is recorded in `notes`; the caller still
    gets every timeframe that succeeded.
    """
    timeframes: list[TimeframeSnapshot] = []
    notes: list[str] = []

    for interval in TIMEFRAMES:
        try:
            snapshot = build_timeframe(symbol, interval, load_klines(symbol, interval))
        except Exception as exc:
            notes.append(f"{interval}: data tidak tersedia ({type(exc).__name__}: {exc})")
            continue

        if snapshot.candles < REQUIRED_CANDLES:
            notes.append(
                f"{interval}: hanya {snapshot.candles} candle, "
                "sebagian indikator belum punya nilai"
            )
        timeframes.append(snapshot)

    bias_by_tf = {item.timeframe: item.ema_bias for item in timeframes}

    return MarketSnapshot(
        symbol=symbol,
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        timeframes=timeframes,
        bias_by_tf=bias_by_tf,
        alignment_bullish=sum(1 for b in bias_by_tf.values() if b == "bullish"),
        alignment_bearish=sum(1 for b in bias_by_tf.values() if b == "bearish"),
        notes=notes,
    )


def _number(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def _signed(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:+.{digits}f}"


def _ema_cell(snapshot: TimeframeSnapshot) -> str:
    """Per-period sign: + above price, - below price, = equal, ? unknown."""
    tokens = []
    for period in EMA_PERIODS:
        value = snapshot.ema.get(str(period))
        if value is None:
            tokens.append("?")
        elif snapshot.close > value:
            tokens.append("+")
        elif snapshot.close < value:
            tokens.append("-")
        else:
            tokens.append("=")
    return " ".join(tokens)


def to_prompt_table(snapshot: MarketSnapshot) -> str:
    """Render the snapshot as a compact markdown block for the LLM prompt."""
    lines = [
        "| TF | Close | EMA 9/21/50/200 | RSI14 | MACD hist | BB %B | ATR% | Vol x | Struktur | Breakout |",
        "|----|-------|-----------------|-------|-----------|-------|------|-------|----------|----------|",
    ]

    for item in snapshot.timeframes:
        lines.append(
            "| {tf} | {close} | {ema} | {rsi} | {hist} | {b} | {atr} | {vol} | {structure} | {breakout} |".format(
                tf=item.timeframe,
                close=f"{item.close:,.4f}" if item.close < 1000 else f"{item.close:,.1f}",
                ema=_ema_cell(item),
                rsi=_number(item.rsi, 1),
                hist=_signed(item.macd_hist),
                b=_number(item.bb_percent_b),
                atr=_number(item.atr_pct),
                vol=_number(item.volume_ratio),
                structure=item.structure,
                breakout=item.breakout,
            )
        )

    for wanted in ("1h", "1d"):
        item = snapshot.by_timeframe(wanted)
        if item is None:
            continue
        supports = ", ".join(f"{v:,.4f}" for v in item.support) or "n/a"
        resistances = ", ".join(f"{v:,.4f}" for v in item.resistance) or "n/a"
        lines.append(f"Support {wanted}: {supports}")
        lines.append(f"Resistance {wanted}: {resistances}")

    bias_text = ", ".join(f"{tf}={bias}" for tf, bias in snapshot.bias_by_tf.items())
    lines.append(
        f"Alignment: {snapshot.alignment_bullish}/{len(snapshot.bias_by_tf)} bullish, "
        f"{snapshot.alignment_bearish}/{len(snapshot.bias_by_tf)} bearish ({bias_text})"
    )

    for note in snapshot.notes:
        lines.append(f"Catatan: {note}")

    return "\n".join(lines)


def to_summary_lines(snapshot: MarketSnapshot) -> list[str]:
    """Short human-readable summary for the CLI and GUI."""
    lines = []

    for item in snapshot.timeframes:
        lines.append(
            f"{item.timeframe:<4} RSI {_number(item.rsi, 1):>5} | "
            f"MACD {_signed(item.macd_hist):>9} | BB %B {_number(item.bb_percent_b):>4} | "
            f"ATR {_number(item.atr_pct)}% | Vol {_number(item.volume_ratio)}x | "
            f"{item.structure} | {item.breakout}"
        )

    lines.append(
        f"Alignment: {snapshot.alignment_bullish}/{len(snapshot.bias_by_tf)} bullish, "
        f"{snapshot.alignment_bearish}/{len(snapshot.bias_by_tf)} bearish"
    )

    for note in snapshot.notes:
        lines.append(f"Note: {note}")

    return lines
