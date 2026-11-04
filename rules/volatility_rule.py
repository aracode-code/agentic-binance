"""VolatilityRule — evaluates market risk level.

Single responsibility: look at analysis.risk and score
how much it supports LONG vs SHORT.

Risk is directionless — it measures danger, not direction.
- high   → low equal scores (risky, reduce confidence)
- medium → medium equal scores
- low    → high equal scores (safer to act)
"""
from models.market_analysis import MarketAnalysis
from rules.rule_result import RuleResult


def evaluate(analysis: MarketAnalysis) -> RuleResult:
    """Evaluate market risk level.

    Args:
        analysis: Validated MarketAnalysis from Market Agent.

    Returns:
        RuleResult: long_score, short_score, reason.
    """
    if analysis.risk == "high":
        return RuleResult(
            rule_name="RiskRule",
            long_score=20,
            short_score=20,
            reason="High risk",
        )

    if analysis.risk == "medium":
        return RuleResult(
            rule_name="RiskRule",
            long_score=40,
            short_score=40,
            reason="Medium risk",
        )

    return RuleResult(
        rule_name="RiskRule",
        long_score=50,
        short_score=50,
        reason="Low risk (stable)",
    )