"""TrendRule — evaluates market trend direction.

Single responsibility: look at analysis.trend and score
how much it supports LONG vs SHORT.

- bullish  → high long_score, low short_score
- bearish  → low long_score, high short_score
- sideways → equal low scores (no direction)
"""
from models.market_analysis import MarketAnalysis
from rules.rule_result import RuleResult


def evaluate(analysis: MarketAnalysis) -> RuleResult:
    """Evaluate trend direction.

    Args:
        analysis: Validated MarketAnalysis from Market Agent.

    Returns:
        RuleResult: long_score, short_score, reason.
    """
    if analysis.trend == "bullish":
        return RuleResult(
            rule_name="TrendRule",
            long_score=80,
            short_score=10,
            reason="Bullish trend",
        )

    if analysis.trend == "bearish":
        return RuleResult(
            rule_name="TrendRule",
            long_score=10,
            short_score=80,
            reason="Bearish trend",
        )

    return RuleResult(
        rule_name="TrendRule",
        long_score=30,
        short_score=30,
        reason="Sideways trend - no clear direction",
    )