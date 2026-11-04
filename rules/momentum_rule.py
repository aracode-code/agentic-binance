"""MomentumRule — evaluates market momentum strength.

Single responsibility: look at analysis.momentum and score
how much it supports LONG vs SHORT.

Momentum is directionless — strong momentum could be up or down.
So this rule gives EQUAL scores to both sides:
- strong  → high equal scores (confirms a move, but not which way)
- weak    → low equal scores (no strong move)
- neutral → medium equal scores
"""
from models.market_analysis import MarketAnalysis
from rules.rule_result import RuleResult


def evaluate(analysis: MarketAnalysis) -> RuleResult:
    """Evaluate momentum strength.

    Args:
        analysis: Validated MarketAnalysis from Market Agent.

    Returns:
        RuleResult: long_score, short_score, reason.
    """
    if analysis.momentum == "strong":
        return RuleResult(
            rule_name="MomentumRule",
            long_score=60,
            short_score=60,
            reason="Strong momentum (direction-neutral)",
        )

    if analysis.momentum == "weak":
        return RuleResult(
            rule_name="MomentumRule",
            long_score=20,
            short_score=20,
            reason="Weak momentum",
        )

    return RuleResult(
        rule_name="MomentumRule",
        long_score=40,
        short_score=40,
        reason="Neutral momentum",
    )