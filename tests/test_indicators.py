import unittest

from engines.indicators import (
    atr,
    band_width,
    bollinger,
    ema,
    macd,
    percent_b,
    rsi,
    sma,
    volume_ratio,
)


class SmaTest(unittest.TestCase):
    def test_sma_values_and_warmup(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 3), [None, None, 2.0, 3.0, 4.0])

    def test_sma_returns_all_none_when_too_short(self):
        self.assertEqual(sma([1, 2], 3), [None, None])


class EmaTest(unittest.TestCase):
    def test_ema_is_seeded_with_sma(self):
        # seed = mean(1,2,3) = 2, k = 0.5
        self.assertEqual(ema([1, 2, 3, 4, 5], 3), [None, None, 2.0, 3.0, 4.0])

    def test_ema_output_length_matches_input(self):
        values = list(range(50))
        self.assertEqual(len(ema(values, 12)), 50)


class RsiTest(unittest.TestCase):
    def test_rising_series_is_maxed(self):
        values = [float(i) for i in range(20)]
        self.assertEqual(rsi(values, 14)[-1], 100.0)

    def test_falling_series_is_zero(self):
        values = [float(20 - i) for i in range(20)]
        self.assertEqual(rsi(values, 14)[-1], 0.0)

    def test_wilder_smoothing_by_hand(self):
        # period 2: changes +1, +1, -1
        values = [1.0, 2.0, 3.0, 2.0]
        result = rsi(values, 2)
        self.assertEqual(result[:2], [None, None])
        self.assertAlmostEqual(result[2], 100.0)
        # after one loss: avg_gain = (1*1 + 0)/2 = 0.5, avg_loss = (0*1 + 1)/2 = 0.5
        self.assertAlmostEqual(result[3], 50.0)

    def test_flat_series_is_neutral(self):
        values = [5.0] * 20
        self.assertEqual(rsi(values, 14)[-1], 50.0)

    def test_result_is_bounded(self):
        values = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84,
                  46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41,
                  46.22, 45.64, 46.21, 46.25, 45.71, 46.45, 45.78, 45.35, 44.03,
                  44.18, 44.22, 44.57, 43.42, 42.66, 43.13]
        for value in rsi(values, 14):
            if value is not None:
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 100.0)


class MacdTest(unittest.TestCase):
    def test_first_values_appear_after_slow_and_signal_warmup(self):
        values = [float(i % 10) + i * 0.1 for i in range(60)]
        macd_line, signal_line, hist = macd(values)

        self.assertIsNone(macd_line[24])
        self.assertIsNotNone(macd_line[25])
        self.assertIsNone(signal_line[32])
        self.assertIsNotNone(signal_line[33])
        self.assertAlmostEqual(hist[40], macd_line[40] - signal_line[40])


class BollingerTest(unittest.TestCase):
    def test_known_population_deviation(self):
        # mean 5, population sd 2
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        upper, middle, lower = bollinger(values, period=8, mult=2)

        self.assertAlmostEqual(middle[-1], 5.0)
        self.assertAlmostEqual(upper[-1], 9.0)
        self.assertAlmostEqual(lower[-1], 1.0)

    def test_flat_series_has_zero_width(self):
        values = [5.0] * 25
        self.assertAlmostEqual(percent_b(values)[-1], 0.5)
        self.assertAlmostEqual(band_width(values)[-1], 0.0)


class AtrTest(unittest.TestCase):
    def test_wilder_atr_by_hand(self):
        highs = [10.0, 11.0, 12.0]
        lows = [9.0, 10.0, 11.0]
        closes = [9.5, 10.5, 11.5]

        result = atr(highs, lows, closes, period=2)

        self.assertEqual(result[:2], [None, None])
        # TR = 1.0, 1.5, 1.5 -> seed = (1.5 + 1.5) / 2
        self.assertAlmostEqual(result[2], 1.5)


class VolumeRatioTest(unittest.TestCase):
    def test_ratio_against_moving_average(self):
        result = volume_ratio([1.0, 1.0, 1.0, 2.0], period=2)

        self.assertIsNone(result[0])
        self.assertAlmostEqual(result[1], 1.0)
        self.assertAlmostEqual(result[3], 2.0 / 1.5)


if __name__ == "__main__":
    unittest.main()
