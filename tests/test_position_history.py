import unittest

from tools.position_history import aggregate_positions


def trade(side, qty, price, time, realized_pnl=None, commission="0", symbol="BTCUSDT"):
    row = {
        "symbol": symbol,
        "side": side,
        "qty": str(qty),
        "price": str(price),
        "commission": commission,
        "time": time,
    }
    if realized_pnl is not None:
        row["realizedPnl"] = str(realized_pnl)
    return row


class LongRoundTripTest(unittest.TestCase):
    def test_long_round_trip(self):
        trades = [
            trade("BUY", 1, 100, 1, commission="0.1"),
            trade("SELL", 1, 110, 2, realized_pnl=10, commission="0.11"),
        ]

        closed = aggregate_positions(trades)

        self.assertEqual(len(closed), 1)
        result = closed[0]
        self.assertEqual(result["side"], "LONG")
        self.assertAlmostEqual(result["entry_price"], 100)
        self.assertAlmostEqual(result["avg_close_price"], 110)
        self.assertAlmostEqual(result["realized_pnl"], 9.79)
        self.assertAlmostEqual(result["roi"], 9.79)
        self.assertEqual(result["open_time"], 1)
        self.assertEqual(result["close_time"], 2)


class ShortRoundTripTest(unittest.TestCase):
    def test_short_round_trip(self):
        trades = [
            trade("SELL", 1, 110, 1, commission="0.1"),
            trade("BUY", 1, 100, 2, realized_pnl=10, commission="0.11"),
        ]

        result = aggregate_positions(trades)[0]

        self.assertEqual(result["side"], "SHORT")
        self.assertAlmostEqual(result["entry_price"], 110)
        self.assertAlmostEqual(result["avg_close_price"], 100)
        self.assertAlmostEqual(result["realized_pnl"], 9.79)
        self.assertAlmostEqual(result["roi"], 8.9)

    def test_short_pnl_falls_back_to_price_difference(self):
        trades = [
            trade("SELL", 1, 110, 1),
            trade("BUY", 1, 100, 2),
        ]

        result = aggregate_positions(trades)[0]

        self.assertAlmostEqual(result["realized_pnl"], 10)


class PartialCloseTest(unittest.TestCase):
    def test_partial_close_does_not_emit_until_flat(self):
        trades = [
            trade("BUY", 2, 100, 1, commission="0.2"),
            trade("SELL", 1, 110, 2, realized_pnl=10, commission="0.1"),
        ]
        self.assertEqual(aggregate_positions(trades), [])

        trades.append(trade("SELL", 1, 120, 3, realized_pnl=20, commission="0.12"))
        closed = aggregate_positions(trades)

        self.assertEqual(len(closed), 1)
        result = closed[0]
        self.assertAlmostEqual(result["entry_price"], 100)
        self.assertAlmostEqual(result["avg_close_price"], 115)
        self.assertAlmostEqual(result["realized_pnl"], 30 - 0.42)
        self.assertAlmostEqual(result["closed_vol"], 2)


class PositionFlipTest(unittest.TestCase):
    def test_flip_closes_old_side_and_opens_new(self):
        trades = [
            trade("BUY", 1, 100, 1),
            trade("SELL", 2, 110, 2, realized_pnl=10),
        ]

        closed = aggregate_positions(trades)

        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0]["side"], "LONG")
        self.assertAlmostEqual(closed[0]["realized_pnl"], 10)
        self.assertAlmostEqual(closed[0]["closed_vol"], 1)


class EdgeCasesTest(unittest.TestCase):
    def test_open_position_is_not_reported_as_closed(self):
        trades = [trade("BUY", 1, 100, 1)]
        self.assertEqual(aggregate_positions(trades), [])

    def test_symbols_are_separated_and_sorted_newest_first(self):
        trades = [
            trade("BUY", 1, 100, 1, symbol="BTCUSDT"),
            trade("SELL", 1, 110, 2, realized_pnl=10, symbol="BTCUSDT"),
            trade("BUY", 1, 10, 3, symbol="ETHUSDT"),
            trade("SELL", 1, 12, 4, realized_pnl=2, symbol="ETHUSDT"),
        ]

        closed = aggregate_positions(trades)

        self.assertEqual([c["symbol"] for c in closed], ["ETHUSDT", "BTCUSDT"])


if __name__ == "__main__":
    unittest.main()
