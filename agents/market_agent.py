"""Market Agent — orchestrator for market analysis.

Single responsibility: coordinate tools to produce a market analysis.
1. Call Binance Tool → fetch ticker, open interest, funding rate
2. Build the deterministic multi-timeframe indicator snapshot
3. Read prompt template from prompts/market_prompt.md
4. Fill placeholders with real data
5. Call DeepSeek Tool → get reasoning
6. Parse + validate → return MarketAnalysis object

Indicators are computed by engines.indicators, never by the model.
Does NOT calculate Edge Score, Trade Plan, Entry/SL/TP.
Those are responsibilities of other agents.
"""
from datetime import datetime, timezone
from pathlib import Path

from engines.snapshot import build_snapshot, load_klines, to_prompt_table
from models.market_analysis import MarketAnalysis
from tools.binance_tool import (
    get_open_interest,
    get_premium_index,
    get_ticker,
)
from tools.deepseek_tool import ask

PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "market_prompt.md"


def _format_funding(premium: dict) -> str:
    """Format the current funding rate as a signed percentage.

    The prompt requires funding to be mentioned when it is extreme, so the
    value must always be present in the prompt instead of left to the model.
    """
    raw = premium.get("lastFundingRate")
    if raw in (None, ""):
        return "tidak tersedia"
    try:
        return f"{float(raw) * 100:+.4f}%"
    except (TypeError, ValueError):
        return "tidak tersedia"


def _format_klines(klines: list, count: int = 3) -> str:
    """Format the last closed candles as a small markdown table.

    Only a handful of bars are sent: the numbers that matter are already in
    the indicator snapshot, so this is price-action context only.
    """
    recent = klines[-count:]
    header = "| Time (UTC) | Open | High | Low | Close | Volume |\n"
    header += "|------------|------|------|-----|-------|--------|\n"
    rows = []
    for k in recent:
        # k = [openTime, open, high, low, close, volume, closeTime, ...]
        opened = datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc)
        rows.append(
            f"| {opened:%Y-%m-%d %H:%M} | {k[1]} | {k[2]} | {k[3]} | {k[4]} | {k[5]} |"
        )
    return header + "\n".join(rows)


def _fill_prompt(template: str, data: dict) -> str:
    """Replace {{PLACEHOLDER}} tokens in the prompt template with real data.

    Args:
        template: Raw prompt text with {{...}} placeholders.
        data: Dict mapping placeholder names to values.

    Returns:
        str: Filled prompt ready to send to DeepSeek.
    """
    filled = template
    for key, value in data.items():
        filled = filled.replace(f"{{{{{key}}}}}", str(value))
    return filled


def _clean_response(text: str) -> str:
    """Strip markdown code blocks from DeepSeek response.

    Args:
        text: Raw response text from DeepSeek.

    Returns:
        str: Cleaned text ready for JSON parsing.
    """
    cleaned = text.strip()
    # Strip markdown code blocks if present
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]  # Remove opening ```
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]  # Remove "json" language tag
        elif cleaned.startswith("python"):
            cleaned = cleaned[6:]  # Remove "python" language tag
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]  # Remove closing ```
        cleaned = cleaned.strip()
    return cleaned


def analyze(symbol: str) -> MarketAnalysis:
    """Run market analysis for a symbol.

    Orchestrates: Binance Tool → prompt → DeepSeek Tool → MarketAnalysis.

    Args:
        symbol: Trading pair, e.g. "BTCUSDT".

    Returns:
        MarketAnalysis: Validated market analysis object.

    Raises:
        requests.HTTPError: if Binance or DeepSeek API fails.
        pydantic.ValidationError: if DeepSeek response doesn't match schema.
    """
    # 1. Fetch data from Binance
    ticker = get_ticker(symbol)
    oi = get_open_interest(symbol)
    premium = get_premium_index(symbol)

    # 2. Deterministic indicators (cached; also warms the 1h candles)
    snapshot = build_snapshot(symbol)
    if not snapshot.timeframes:
        raise RuntimeError(
            "Snapshot indikator kosong: " + "; ".join(snapshot.notes or ["tidak ada data"])
        )
    candles = load_klines(symbol, "1h")[-3:]

    # 3. Read prompt template
    template = PROMPT_FILE.read_text(encoding="utf-8")

    # 4. Fill placeholders
    prompt = _fill_prompt(template, {
        "SYMBOL": symbol,
        "LAST_PRICE": ticker["lastPrice"],
        "PRICE_CHANGE": ticker["priceChangePercent"],
        "VOLUME": ticker["volume"],
        "OPEN_INTEREST": oi["openInterest"],
        "FUNDING": _format_funding(premium),
        "INDICATORS": to_prompt_table(snapshot),
        "CANDLES": _format_klines(candles, count=3),
    })

    # 5. Call DeepSeek
    system = "You are a professional crypto futures market analyst. Respond only with valid JSON."
    response_text = ask(prompt, system=system, temperature=0.2)

    # 6. Parse + validate against schema
    cleaned = _clean_response(response_text)
    return MarketAnalysis.model_validate_json(cleaned)
