"""Market Decision schema (Pydantic model).

Single responsibility: define the output structure of the Decision Engine.
This is the contract for trading decisions.
"""
from typing import Literal

from pydantic import BaseModel, Field


class MarketDecision(BaseModel):
    """Output schema of the Decision Engine."""

    action: Literal["LONG", "SHORT", "WAIT"] = Field(
        ..., description="Trading decision"
    )
    confidence: int = Field(
        ..., ge=0, le=100, description="Confidence level 0-100"
    )
    reason: str = Field(
        ..., description="Reasoning behind the decision"
    )