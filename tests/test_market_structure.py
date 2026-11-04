import unittest

from engines.market_structure import (
    breakout_state,
    classify_structure,
    detect_bos,
    detect_choch,
    support_resistance,
    swing_points,
)

# Zig-zag with rising highs and rising lows (HH_HL)
HH_HL_HIGHS = [10.0, 12.0, 11.0, 14.0, 12.0, 16.0]
HH_HL_LOWS = [9.0, 10.0, 9.5, 11.0, 10.5, 13.0]

# Mirror image: falling highs and falling lows (LH_LL)
LH_LL_HIGHS = [20.0, 18.0, 19.0, 16.0, 17.0, 14.0]
LH_LL_LOWS = [19.0, 17.0, 18.0, 15.0, 16.0, 13.0]


class SwingTest(unittest.TestCase):
    def test_confirmed_swings_only(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)

        self.assertEqual(
            [(s.kind, s.index, s.price) for s in swings],
            [("HIGH", 1, 12.0), ("LOW", 2, 9.5), ("HIGH", 3, 14.0), ("LOW", 4, 10.5)],
        )

    def test_equal_extremes_are_not_swings(self):
        highs = [5.0, 5.0, 5.0]
        lows = [4.0, 4.0, 4.0]
        self.assertEqual(swing_points(highs, lows, left=1, right=1), [])


class StructureTest(unittest.TestCase):
    def test_hh_hl(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)
        self.assertEqual(classify_structure(swings), "HH_HL")

    def test_lh_ll(self):
        swings = swing_points(LH_LL_HIGHS, LH_LL_LOWS, left=1, right=1)
        self.assertEqual(classify_structure(swings), "LH_LL")

    def test_unknown_without_enough_swings(self):
        self.assertEqual(classify_structure([]), "UNKNOWN")


class BosTest(unittest.TestCase):
    def test_bullish_bos_above_last_swing_high(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)
        event = detect_bos([15.0, 18.0], swings)

        self.assertIsNotNone(event)
        self.assertEqual((event.kind, event.direction, event.level), ("BOS", "BULLISH", 14.0))

    def test_bearish_bos_below_last_swing_low(self):
        swings = swing_points(LH_LL_HIGHS, LH_LL_LOWS, left=1, right=1)
        event = detect_bos([15.0, 14.9], swings)

        self.assertIsNotNone(event)
        self.assertEqual((event.kind, event.direction), ("BOS", "BEARISH"))

    def test_no_bos_inside_range(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)
        self.assertIsNone(detect_bos([12.0], swings))


class ChochTest(unittest.TestCase):
    def test_bearish_choch_inside_uptrend(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)
        event = detect_choch([10.0], swings, "HH_HL")

        self.assertIsNotNone(event)
        self.assertEqual((event.kind, event.direction), ("CHoCH", "BEARISH"))

    def test_no_choch_when_bos_agrees_with_structure(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)
        self.assertIsNone(detect_choch([18.0], swings, "HH_HL"))


class SupportResistanceTest(unittest.TestCase):
    def test_levels_are_split_by_current_price(self):
        swings = swing_points(HH_HL_HIGHS, HH_HL_LOWS, left=1, right=1)
        supports, resistances = support_resistance(swings, price=12.5, n=3)

        self.assertEqual(supports, [10.5, 9.5])
        self.assertEqual(resistances, [14.0])


class BreakoutTest(unittest.TestCase):
    FLAT = [10.0] * 20

    def test_none_inside_range(self):
        self.assertEqual(breakout_state([10.0] * 22, [1.0] * 22), "NONE")

    def test_confirmed_with_volume(self):
        closes = self.FLAT + [10.0, 11.0]
        volumes = [1.0] * 21 + [3.0]

        self.assertEqual(breakout_state(closes, volumes), "BREAKOUT_CONFIRMED")

    def test_weak_without_volume(self):
        closes = self.FLAT + [10.0, 11.0]
        volumes = [1.0] * 22

        self.assertEqual(breakout_state(closes, volumes), "BREAKOUT_WEAK")

    def test_retest_near_level(self):
        closes = self.FLAT + [11.0, 10.02]
        volumes = [1.0] * 22

        self.assertEqual(breakout_state(closes, volumes), "RETEST")

    def test_not_enough_history(self):
        self.assertEqual(breakout_state([10.0] * 5, [1.0] * 5), "NONE")


if __name__ == "__main__":
    unittest.main()
