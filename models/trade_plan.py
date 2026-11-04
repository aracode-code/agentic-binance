"""Output contract of the Risk Manager.

A plan is a proposal, not an order: nothing here is sent to Binance. When
`approved` is false every price/size field is None and `guards` explains why.
"""
from typing import Literal

from pydantic import BaseModel, Field


class TradePlan(BaseModel):
    """Risk-managed position size for one decision."""

    symbol: str
    approved: bool

    side: Literal["LONG", "SHORT"] | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None

    quantity: float | None = Field(None, description="Contracts after step rounding")
    notional: float | None = Field(None, description="USDT value of the position")
    leverage: int | None = None

    risk_amount: float | None = Field(None, description="Loss if stop is hit, USDT")
    risk_pct: float | None = Field(None, description="risk_amount as % of equity")
    equity: float | None = None
    stop_timeframe: str | None = None

    guards: list[str] = Field(
        default_factory=list, description="Failed checks (empty when approved)"
    )
    reason: str
