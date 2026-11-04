"""Market Analysis schema (Pydantic model).

Single responsibility: define the official output structure
of the Market Agent. This is the contract that all consumers
must follow.

If DeepSeek returns JSON that doesn't match this schema,
a clear ValidationError is raised automatically.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class MarketAnalysis(BaseModel):
    """Official output schema of the Market Agent."""

    trend: Literal["bullish", "bearish", "sideways"] = Field(
        ..., description="Market trend direction"
    )
    momentum: Literal["strong", "weak", "neutral"] = Field(
        ..., description="Momentum strength"
    )
    strength: Literal["strong", "medium", "weak"] = Field(
        ..., description="Overall signal strength"
    )
    risk: Literal["low", "medium", "high"] = Field(
        ..., description="Market risk level"
    )
    trade_bias: Literal["LONG", "SHORT", "WAIT"] = Field(
        ..., description="Trade direction bias"
    )
    action: Literal[
        "LOOK FOR LONG",
        "WAIT FOR PULLBACK",
        "LOOK FOR SHORT",
        "WAIT FOR BREAKDOWN",
        "NO TRADE",
    ] = Field(..., description="Action recommendation")
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        ..., description="Confidence level"
    )
    reason: str = Field(..., description="Brief reason, max 2 sentences")

    @field_validator(
        "trend", "momentum", "strength", "risk", mode="before"
    )
    @classmethod
    def normalize_case(cls, v: str) -> str:
        """Lowercase values before validation (DeepSeek may capitalize)."""
        return v.lower() if isinstance(v, str) else v

    @field_validator("trade_bias", "action", "confidence", mode="before")
    @classmethod
    def normalize_upper(cls, v: str) -> str:
        """Uppercase values before validation."""
        return v.upper() if isinstance(v, str) else v