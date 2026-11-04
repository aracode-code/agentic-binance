import unittest

from engines.decision_engine import decide
from models.market_analysis import MarketAnalysis


def analysis(**overrides) -> MarketAnalysis:
    base = {
        "trend": "bullish",
        "momentum": "strong",
        "strength": "strong",
        "risk": "low",
        "trade_bias": "LONG",
        "action": "LOOK FOR LONG",
        "confidence": "HIGH",
        "reason": "test",
    }
    base.update(overrides)
    return MarketAnalysis(**base)


class DecisionTest(unittest.TestCase):
    def test_aligned_bullish_gives_long_with_full_conviction(self):
        decision = decide(analysis())

        self.assertEqual(decision.action, "LONG")
        self.assertEqual(decision.confidence, 100)

    def test_aligned_bearish_gives_short(self):
        decision = decide(analysis(
            trend="bearish",
            trade_bias="SHORT",
            action="LOOK FOR SHORT",
        ))

        self.assertEqual(decision.action, "SHORT")
        self.assertEqual(decision.confidence, 100)

    def test_sideways_never_trades(self):
        decision = decide(analysis(
            trend="sideways",
            momentum="neutral",
            risk="medium",
            trade_bias="WAIT",
            action="NO TRADE",
            confidence="LOW",
        ))

        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.confidence, 0)

    def test_weak_support_lowers_conviction(self):
        decision = decide(analysis(momentum="weak", risk="high"))

        self.assertEqual(decision.action, "LONG")
        self.assertEqual(decision.confidence, 57)

    def test_rules_veto_opposite_ai_bias(self):
        decision = decide(analysis(trade_bias="SHORT", action="LOOK FOR SHORT"))

        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.confidence, 0)
        self.assertIn("Konflik", decision.reason)

    def test_rules_veto_when_ai_wants_to_wait(self):
        decision = decide(analysis(
            trade_bias="WAIT",
            action="NO TRADE",
        ))

        self.assertEqual(decision.action, "WAIT")
        self.assertEqual(decision.confidence, 0)


if __name__ == "__main__":
    unittest.main()
