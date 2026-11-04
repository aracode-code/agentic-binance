"""Decision Engine — combines rule results into a MarketDecision.

Single responsibility: call all rules, aggregate scores, return decision.
- NO hardcoded rules (no "if bullish and strong → LONG")
- NO AI / DeepSeek
- Pure aggregation: sum scores, compare, decide

The engine doesn't know what "bullish" or "strong" means.
It only knows: sum long_scores, sum short_scores, compare.

Confidence is an internal score, not a probability of profit: it combines how
far the scores lean one way (edge) with how much total support the rules gave
(momentum and risk are direction-neutral, so they only scale conviction).
"""
from models.market_analysis import MarketAnalysis
from models.market_decision import MarketDecision
from rules import momentum_rule, trend_rule, volatility_rule
from rules.rule_result import RuleResult

# TrendRule is the only directional rule: 80 vs 10 means the largest possible
# edge is 70. Keep this in sync if the rule scores change.
MAX_DIRECTIONAL_EDGE = 70

# Below this edge the rules disagree too little to act on. Sideways trend
# produces an edge of 0, so it always resolves to WAIT.
MIN_DIRECTIONAL_EDGE = 20


def decide(analysis: MarketAnalysis) -> MarketDecision:
    """Convert market analysis into a trading decision.

    Calls all rules, aggregates their scores, picks the winner. The rules act
    as a veto over the AI bias: when they point the other way (or the AI asked
    to WAIT), the result is WAIT rather than a forced trade.

    Args:
        analysis: Validated MarketAnalysis from Market Agent.

    Returns:
        MarketDecision: action, confidence, reason.
    """
    # 1. Run all rules
    results: list[RuleResult] = [
        trend_rule.evaluate(analysis),
        momentum_rule.evaluate(analysis),
        volatility_rule.evaluate(analysis),
    ]

    # 2. Sum scores
    total_long = sum(r.long_score for r in results)
    total_short = sum(r.short_score for r in results)
    edge = total_long - total_short

    # 3. Decide from the edge, scaled by how much support the rules gave
    support = min(1.0, (total_long + total_short) / (len(results) * 100))
    if abs(edge) < MIN_DIRECTIONAL_EDGE:
        action = "WAIT"
        confidence = 0
    else:
        action = "LONG" if edge > 0 else "SHORT"
        confidence = round(min(1.0, abs(edge) / MAX_DIRECTIONAL_EDGE) * support * 100)

    # 4. Rule layer vetoes the AI bias instead of silently overriding it
    reasons = [f"{r.rule_name}: {r.reason}" for r in results]
    if action != "WAIT" and action != analysis.trade_bias:
        reasons.append(
            f"Konflik: bias AI {analysis.trade_bias} tidak sejalan dengan aturan "
            f"{action} — ditahan ke WAIT"
        )
        action = "WAIT"
        confidence = 0

    return MarketDecision(action=action, confidence=confidence, reason=" | ".join(reasons))
