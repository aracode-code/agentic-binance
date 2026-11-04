"""Entry point for Agentic Binance.

Usage:
    python app.py BTCUSDT
    python app.py ETHUSDT

If no symbol given, defaults to BTCUSDT.
"""
import sys

from agents.market_agent import analyze
from engines.decision_engine import decide
from engines.snapshot import build_snapshot, to_summary_lines


def main() -> None:
    symbol = sys.argv[1].strip().upper() if len(sys.argv) > 1 else "BTCUSDT"
    if not symbol:
        symbol = "BTCUSDT"

    print("Fetching Binance data...")
    print("Analyzing market...")

    try:
        analysis = analyze(symbol)
        decision = decide(analysis)
        snapshot = build_snapshot(symbol)
    except Exception as exc:
        print(f"\n[ERROR] {type(exc).__name__}: {exc}")
        print(f"Periksa symbol '{symbol}' dan koneksi internet Anda.")
        return

    print()
    print("=" * 50)
    print(symbol)
    print("=" * 50)
    print()
    print(f"{'Market Bias':<16}: {analysis.trend.capitalize()}")
    print(f"{'Momentum':<16}: {analysis.momentum.capitalize()}")
    print(f"{'Risk':<16}: {analysis.risk.capitalize()}")
    print()
    print("INDICATORS (dihitung sistem)")
    for line in to_summary_lines(snapshot):
        print(f"  {line}")
    print()
    print(f"{'AI Bias':<16}: {analysis.trade_bias}")
    print(f"{'AI Action':<16}: {analysis.action}")
    print(f"{'AI Confidence':<16}: {analysis.confidence}")
    print()
    print(f"{'Decision':<16}: {decision.action}")
    print(f"{'Conviction':<16}: {decision.confidence} (skor internal, bukan probabilitas)")
    print()
    print(f"{'Reason':<16}: {analysis.reason}")
    print(f"{'Rule Detail':<16}: {decision.reason}")
    print("=" * 50)


if __name__ == "__main__":
    main()