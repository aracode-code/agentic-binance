"""Data contract for the deterministic multi-timeframe snapshot.

Everything here is computed by code, never by the LLM. Consumers (prompt
builder, CLI, GUI) read this contract; the LLM only returns MarketAnalysis.
"""
from typing import Literal

from pydantic import BaseModel, Field

Bias = Literal["bullish", "bearish", "mixed", "unknown"]


class TimeframeSnapshot(BaseModel):
    """Indicator state of one timeframe at the last closed bar."""

    timeframe: str = Field(..., description="Binance interval, e.g. '1h'")
    candles: int = Field(..., ge=0, description="Candles available")
    close: float = Field(..., description="Last close price")

    change_pct: float | None = Field(None, description="Change vs previous bar, %")

    ema: dict[str, float | None] = Field(
        default_factory=dict, description="EMA values keyed by period"
    )
    sma: dict[str, float | None] = Field(
        default_factory=dict, description="SMA values keyed by period"
    )
    ema_bias: Bias = Field(..., description="Price vs EMA50/EMA200 alignment")

    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None

    bb_percent_b: float | None = Field(None, description="0 = lower band, 1 = upper")
    bb_width: float | None = Field(None, description="Band width, % of middle")

    atr: float | None = None
    atr_pct: float | None = Field(None, description="ATR as % of price")

    volume_ratio: float | None = Field(None, description="Volume / SMA20 volume")

    structure: str = Field(..., description="HH_HL | LH_LL | MIXED | UNKNOWN")
    breakout: str = Field(
        ..., description="NONE | BREAKOUT_WEAK | BREAKOUT_CONFIRMED | RETEST"
    )

    support: list[float] = Field(default_factory=list)
    resistance: list[float] = Field(default_factory=list)


class MarketSnapshot(BaseModel):
    """Multi-timeframe snapshot for one symbol."""

    symbol: str
    generated_at: str = Field(..., description="ISO-8601 with offset")
    timeframes: list[TimeframeSnapshot] = Field(default_factory=list)
    bias_by_tf: dict[str, Bias] = Field(default_factory=dict)
    alignment_bullish: int = 0
    alignment_bearish: int = 0
    notes: list[str] = Field(default_factory=list)

    def by_timeframe(self, timeframe: str) -> TimeframeSnapshot | None:
        for item in self.timeframes:
            if item.timeframe == timeframe:
                return item
        return None
