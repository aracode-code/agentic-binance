import math
import unittest

from engines.snapshot import (
    build_timeframe,
    to_prompt_table,
    to_summary_lines,
)
from models.market_snapshot import MarketSnapshot, TimeframeSnapshot


def make_klines(closes, volumes=None):
    bars = []
    for i, close in enumerate(closes):
        open_ = closes[i - 1] if i else close
        high = max(open_, close) * 1.001
        low = min(open_, close) * 0.999
        volume = volumes[i] if volumes else 100.0
        bars.append([
            i * 60_000, str(open_), str(high), str(low), str(close),
            str(volume), 0, "0", 0, "0", "0", "0",
        ])
    return bars


def zigzag(count=250, start=100.0):
    return [start + i * 0.2 + math.sin(i / 4) * 5 for i in range(count)]


class BuildTimeframeTest(unittest.TestCase):
    def test_full_history_populates_every_indicator(self):
        snapshot = build_timeframe("BTCUSDT", "1h", make_klines(zigzag()))

        self.assertEqual(snapshot.timeframe, "1h")
        self.assertEqual(snapshot.candles, 250)
        self.assertIsNotNone(snapshot.ema["9"])
        self.assertIsNotNone(snapshot.ema["200"])
        self.assertIsNotNone(snapshot.rsi)
        self.assertIsNotNone(snapshot.macd_hist)
        self.assertIsNotNone(snapshot.bb_percent_b)
        self.assertIsNotNone(snapshot.atr_pct)
        self.assertGreater(snapshot.atr_pct, 0)
        self.assertIn(snapshot.structure, {"HH_HL", "LH_LL", "MIXED", "UNKNOWN"})
        self.assertIn(
            snapshot.breakout,
            {"NONE", "BREAKOUT_WEAK", "BREAKOUT_CONFIRMED", "RETEST"},
        )

    def test_short_history_leaves_long_ema_empty(self):
        snapshot = build_timeframe("BTCUSDT", "1h", make_klines(zigzag(60)))

        self.assertIsNone(snapshot.ema["200"])
        self.assertIsNotNone(snapshot.ema["50"])
        self.assertIn(snapshot.ema_bias, {"bullish", "bearish", "mixed"})

    def test_too_few_candles_raises(self):
        with self.assertRaises(ValueError):
            build_timeframe("BTCUSDT", "1h", make_klines([100.0]))


def sample_snapshot() -> MarketSnapshot:
    timeframe = build_timeframe("BTCUSDT", "1h", make_klines(zigzag()))
    return MarketSnapshot(
        symbol="BTCUSDT",
        generated_at="2026-11-04T10:00:00+07:00",
        timeframes=[timeframe],
        bias_by_tf={"1h": timeframe.ema_bias},
        alignment_bullish=1 if timeframe.ema_bias == "bullish" else 0,
        alignment_bearish=1 if timeframe.ema_bias == "bearish" else 0,
        notes=[],
    )


class PromptTableTest(unittest.TestCase):
    def test_table_has_header_row_and_alignment(self):
        text = to_prompt_table(sample_snapshot())

        self.assertIn("| TF | Close | EMA 9/21/50/200 |", text)
        self.assertIn("| 1h |", text)
        self.assertIn("Alignment:", text)

    def test_table_has_no_placeholder_left(self):
        text = to_prompt_table(sample_snapshot())
        self.assertNotIn("{{", text)

    def test_unknown_values_render_as_not_available(self):
        empty = TimeframeSnapshot(
            timeframe="15m",
            candles=5,
            close=100.0,
            ema_bias="unknown",
            structure="UNKNOWN",
            breakout="NONE",
        )
        snapshot = MarketSnapshot(
            symbol="BTCUSDT",
            generated_at="2026-11-04T10:00:00+07:00",
            timeframes=[empty],
            bias_by_tf={"15m": "unknown"},
            notes=["15m: hanya 5 candle"],
        )

        text = to_prompt_table(snapshot)

        self.assertIn("n/a", text)
        self.assertIn("Catatan: 15m", text)


class SummaryLinesTest(unittest.TestCase):
    def test_summary_mentions_rsi_and_alignment(self):
        lines = to_summary_lines(sample_snapshot())
        joined = "\n".join(lines)

        self.assertIn("RSI", joined)
        self.assertIn("Alignment:", joined)


if __name__ == "__main__":
    unittest.main()
