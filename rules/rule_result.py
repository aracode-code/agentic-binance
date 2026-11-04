"""RuleResult schema — output of a single rule.

Each rule returns a RuleResult with long_score and short_score
(0-100). This score-based design lets directionless rules
(momentum, volatility) contribute equally to both sides
without biasing the final decision.
"""
from pydantic import BaseModel, Field


class RuleResult(BaseModel):
    """Output of a single evaluation rule."""

    rule_name: str = Field(..., description="Name of the rule")
    long_score: int = Field(
        ..., ge=0, le=100, description="Score supporting LONG (0-100)"
    )
    short_score: int = Field(
        ..., ge=0, le=100, description="Score supporting SHORT (0-100)"
    )
    reason: str = Field(..., description="Why this rule gave these scores")