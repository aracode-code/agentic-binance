import unittest

from engines import risk_manager
from models.market_decision import MarketDecision
from models.market_snapshot import MarketSnapshot, TimeframeSnapshot
from tools.binance_tool import parse_symbol_filters


def make_snapshot(close: float = 100.0, atr: float | None = 2.0, timeframe: str = "1h"):
    item = TimeframeSnapshot(
        timeframe=timeframe,
        candles=250,
        close=close,
        ema_bias="bullish",
        structure="HH_HL",
        breakout="NONE",
        atr=atr,
        atr_pct=(atr / close * 100) if atr else None,
    )
    return MarketSnapshot(
        symbol="BTCUSDT",
        generated_at="2026-11-04T20:00:00+07:00",
        timeframes=[item],
        bias_by_tf={timeframe: "bullish"},
        alignment_bullish=1,
    )


def make_decision(action: str = "LONG", confidence: int = 80):
    return MarketDecision(action=action, confidence=confidence, reason="test")


def make_account(**overrides):
    account = {
        "total_wallet_balance": 10_000.0,
        "available_balance": 10_000.0,
        "unrealized_pnl": 0.0,
        "open_positions": 0,
        "open_symbols": [],
        "today_realized_pnl": 0.0,
    }
    account.update(overrides)
    return account


FILTERS = {
    "symbol": "BTCUSDT",
    "step_size": 0.001,
    "min_qty": 0.001,
    "max_qty": 0.0,
    "min_notional": 5.0,
    "price_tick": 0.01,
}


class RiskSizingTest(unittest.TestCase):
    def test_long_uses_risk_budget(self):
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(), FILTERS
        )

        self.assertTrue(plan.approved)
        self.assertEqual(plan.side, "LONG")
        # ATR 2 * 1.5 = 3% stop, risk 0.5% of 10k = 50 USDT
        self.assertAlmostEqual(plan.stop_loss, 97.0, places=2)
        self.assertAlmostEqual(plan.take_profit, 106.0, places=2)
        self.assertAlmostEqual(plan.quantity, 16.666, places=3)
        self.assertAlmostEqual(plan.notional, 1666.6, places=1)
        self.assertAlmostEqual(plan.risk_amount, 50.0, places=0)
        self.assertEqual(plan.leverage, 1)

    def test_short_mirrors_prices(self):
        plan = risk_manager.assess(
            make_decision("SHORT"), make_snapshot(), make_account(), FILTERS
        )

        self.assertTrue(plan.approved)
        self.assertEqual(plan.side, "SHORT")
        self.assertAlmostEqual(plan.stop_loss, 103.0, places=2)
        self.assertAlmostEqual(plan.take_profit, 94.0, places=2)

    def test_notional_cap_limits_size(self):
        # ATR 1 -> 1.5% stop; risk would allow 33.3 contracts but the
        # 20% equity notional cap allows only 20.
        plan = risk_manager.assess(
            make_decision(), make_snapshot(atr=1.0), make_account(), FILTERS
        )

        self.assertTrue(plan.approved)
        self.assertAlmostEqual(plan.quantity, 20.0, places=3)
        self.assertAlmostEqual(plan.notional, 2000.0, places=1)
        self.assertAlmostEqual(plan.risk_amount, 30.0, places=1)

    def test_stop_clamped_to_max_pct(self):
        plan = risk_manager.assess(
            make_decision(), make_snapshot(atr=10.0), make_account(), FILTERS
        )

        self.assertTrue(plan.approved)
        self.assertAlmostEqual(plan.stop_loss, 97.0, places=2)  # 3% max

    def test_stop_clamped_to_min_pct(self):
        plan = risk_manager.assess(
            make_decision(), make_snapshot(atr=0.05), make_account(), FILTERS
        )

        self.assertTrue(plan.approved)
        self.assertAlmostEqual(plan.stop_loss, 99.7, places=2)  # 0.3% min

    def test_quantity_rounds_down_to_step(self):
        filters = dict(FILTERS, step_size=0.1)
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(), filters
        )

        self.assertTrue(plan.approved)
        self.assertAlmostEqual(plan.quantity, 16.6, places=3)

    def test_max_quantity_cap(self):
        filters = dict(FILTERS, max_qty=10.0)
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(), filters
        )

        self.assertTrue(plan.approved)
        self.assertEqual(plan.quantity, 10.0)

    def test_falls_back_to_another_timeframe(self):
        snapshot = make_snapshot(timeframe="15m")
        plan = risk_manager.assess(
            make_decision(), snapshot, make_account(), FILTERS
        )

        self.assertTrue(plan.approved)
        self.assertEqual(plan.stop_timeframe, "15m")


class RiskGuardTest(unittest.TestCase):
    def assertRejected(self, plan, fragment):
        self.assertFalse(plan.approved)
        self.assertTrue(
            any(fragment in guard for guard in plan.guards),
            f"'{fragment}' tidak ada di {plan.guards}",
        )
        self.assertIsNone(plan.quantity)

    def test_wait_decision_is_rejected(self):
        plan = risk_manager.assess(
            make_decision("WAIT", 80), make_snapshot(), make_account(), FILTERS
        )
        self.assertRejected(plan, "WAIT")

    def test_low_conviction_is_rejected(self):
        plan = risk_manager.assess(
            make_decision("LONG", 59), make_snapshot(), make_account(), FILTERS
        )
        self.assertRejected(plan, "conviction 59")

    def test_open_position_limit(self):
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(open_positions=3), FILTERS
        )
        self.assertRejected(plan, "posisi terbuka 3")

    def test_symbol_already_open(self):
        plan = risk_manager.assess(
            make_decision(),
            make_snapshot(),
            make_account(open_symbols=["BTCUSDT"]),
            FILTERS,
        )
        self.assertRejected(plan, "sudah punya posisi")

    def test_daily_loss_limit(self):
        plan = risk_manager.assess(
            make_decision(),
            make_snapshot(),
            make_account(today_realized_pnl=-400.0),
            FILTERS,
        )
        self.assertRejected(plan, "batas 3%")

    def test_unreadable_daily_pnl_is_rejected(self):
        plan = risk_manager.assess(
            make_decision(),
            make_snapshot(),
            make_account(today_realized_pnl=None),
            FILTERS,
        )
        self.assertRejected(plan, "tidak bisa dibaca")

    def test_zero_equity_is_rejected(self):
        plan = risk_manager.assess(
            make_decision(),
            make_snapshot(),
            make_account(total_wallet_balance=0.0, available_balance=0.0),
            FILTERS,
        )
        self.assertRejected(plan, "equity tidak valid")

    def test_empty_available_balance_is_rejected(self):
        plan = risk_manager.assess(
            make_decision(),
            make_snapshot(),
            make_account(available_balance=0.0),
            FILTERS,
        )
        self.assertRejected(plan, "saldo tersedia kosong")

    def test_missing_atr_is_rejected(self):
        plan = risk_manager.assess(
            make_decision(), make_snapshot(atr=None), make_account(), FILTERS
        )
        self.assertRejected(plan, "ATR")

    def test_empty_snapshot_is_rejected(self):
        empty = MarketSnapshot(
            symbol="BTCUSDT",
            generated_at="2026-11-04T20:00:00+07:00",
            timeframes=[],
        )
        plan = risk_manager.assess(make_decision(), empty, make_account(), FILTERS)
        self.assertRejected(plan, "snapshot harga")

    def test_quantity_below_exchange_minimum(self):
        filters = dict(FILTERS, min_qty=100.0)
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(), filters
        )
        self.assertRejected(plan, "quantity")

    def test_notional_below_exchange_minimum(self):
        filters = dict(FILTERS, min_notional=5000.0)
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(), filters
        )
        self.assertRejected(plan, "notional")

    def test_api_failure_is_rejected_not_raised(self):
        original = risk_manager.get_account_state

        def boom():
            raise RuntimeError("API down")

        risk_manager.get_account_state = boom
        try:
            plan = risk_manager.assess_symbol(make_decision(), make_snapshot())
        finally:
            risk_manager.get_account_state = original

        self.assertRejected(plan, "data akun/filter tidak tersedia")


class SymbolFilterTest(unittest.TestCase):
    def test_parses_min_notional_filter(self):
        info = {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "filters": [
                        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                        {"filterType": "MIN_NOTIONAL", "notional": "5"},
                        {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
                    ],
                }
            ]
        }

        filters = parse_symbol_filters(info, "BTCUSDT")

        self.assertEqual(filters["step_size"], 0.001)
        self.assertEqual(filters["min_notional"], 5.0)
        self.assertEqual(filters["price_tick"], 0.1)

    def test_parses_renamed_notional_filter(self):
        info = {
            "symbols": [
                {
                    "symbol": "ETHUSDT",
                    "filters": [
                        {"filterType": "LOT_SIZE", "stepSize": "0.01", "minQty": "0.01"},
                        {"filterType": "NOTIONAL", "notional": "20"},
                    ],
                }
            ]
        }

        filters = parse_symbol_filters(info, "ETHUSDT")

        self.assertEqual(filters["min_notional"], 20.0)
        self.assertEqual(filters["price_tick"], 0.0)

    def test_unknown_symbol_raises(self):
        with self.assertRaises(ValueError):
            parse_symbol_filters({"symbols": []}, "NOPEUSDT")


class PlanFormattingTest(unittest.TestCase):
    def test_approved_plan_lines(self):
        plan = risk_manager.assess(
            make_decision(), make_snapshot(), make_account(), FILTERS
        )
        text = "\n".join(risk_manager.to_lines(plan))

        self.assertIn("APPROVED", text)
        self.assertIn("Stop Loss", text)
        self.assertIn("Take Profit", text)

    def test_rejected_plan_lines_show_guards(self):
        plan = risk_manager.assess(
            make_decision("WAIT", 0), make_snapshot(), make_account(), FILTERS
        )
        text = "\n".join(risk_manager.to_lines(plan))

        self.assertIn("REJECTED", text)
        self.assertIn("Guard", text)


if __name__ == "__main__":
    unittest.main()
