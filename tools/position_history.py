"""Build closed round trips from raw Binance futures trade rows.

Binance reports fills, not positions: a closed position is a sequence of
opens of one side followed by closes of the opposite side. Trades are walked
in order per symbol and matched FIFO so LONG and SHORT are both handled.
"""
from collections import defaultdict

FLAT_EPSILON = 1e-12


def _new_round_trip(side: str, timestamp: int) -> dict:
    return {
        "side": side,
        "qty": 0.0,             # open quantity still unmatched
        "cost": 0.0,            # cost of that unmatched quantity
        "open_qty": 0.0,        # total quantity ever opened
        "open_cost": 0.0,       # total cost ever opened
        "close_qty": 0.0,
        "close_cost": 0.0,
        "fee": 0.0,             # all fees charged to this round trip
        "fee_open": 0.0,        # fees allocated to the unmatched quantity
        "realized_pnl": 0.0,
        "open_time": timestamp,
        "close_time": None,
    }


def _finalize(symbol: str, trip: dict) -> dict:
    net_pnl = trip["realized_pnl"] - trip["fee"]
    notional = trip["open_cost"]
    return {
        "symbol": symbol,
        "side": trip["side"],
        "realized_pnl": net_pnl,
        "roi": (net_pnl / notional) * 100 if notional else 0.0,
        "closed_vol": trip["open_qty"],
        "entry_price": notional / trip["open_qty"] if trip["open_qty"] else 0.0,
        "avg_close_price": (
            trip["close_cost"] / trip["close_qty"] if trip["close_qty"] else 0.0
        ),
        "open_time": trip["open_time"],
        "close_time": trip["close_time"],
    }


def _round_trips(symbol: str, trades: list) -> list:
    closed = []
    trip = None

    for trade in trades:
        side = str(trade.get("side", "")).upper()
        if side not in ("BUY", "SELL"):
            continue

        qty = float(trade.get("qty", 0) or 0)
        price = float(trade.get("price", 0) or 0)
        fee = float(trade.get("commission", 0) or 0)
        timestamp = int(trade.get("time", 0) or 0)
        if qty <= 0:
            continue

        direction = "LONG" if side == "BUY" else "SHORT"

        if trip is None:
            trip = _new_round_trip(direction, timestamp)

        if direction == trip["side"]:
            trip["qty"] += qty
            trip["cost"] += price * qty
            trip["open_qty"] += qty
            trip["open_cost"] += price * qty
            trip["fee"] += fee
            trip["fee_open"] += fee
            continue

        # Opposite side closes what is open; anything left over flips the side.
        closed_qty = min(qty, trip["qty"])
        ratio = closed_qty / qty
        entry_cost_removed = trip["cost"] * (closed_qty / trip["qty"])
        fee_removed = trip["fee_open"] * (closed_qty / trip["qty"])

        if "realizedPnl" in trade:
            # Binance caps realizedPnl at the quantity that actually closed, so
            # on a flip the whole value belongs to this round trip.
            trade_pnl = float(trade.get("realizedPnl") or 0)
        else:
            entry_price = trip["cost"] / trip["qty"]
            sign = 1 if trip["side"] == "LONG" else -1
            trade_pnl = (price - entry_price) * closed_qty * sign

        trip["qty"] -= closed_qty
        trip["cost"] -= entry_cost_removed
        trip["fee_open"] -= fee_removed
        trip["close_qty"] += closed_qty
        trip["close_cost"] += price * closed_qty
        trip["fee"] += fee * ratio
        trip["realized_pnl"] += trade_pnl
        trip["close_time"] = timestamp

        if trip["qty"] <= FLAT_EPSILON:
            closed.append(_finalize(symbol, trip))
            remainder = qty - closed_qty
            trip = None
            if remainder > FLAT_EPSILON:
                trip = _new_round_trip(direction, timestamp)
                trip["qty"] = remainder
                trip["cost"] = price * remainder
                trip["open_qty"] = remainder
                trip["open_cost"] = price * remainder
                trip["fee"] = fee * (remainder / qty)
                trip["fee_open"] = trip["fee"]

    return closed


def aggregate_positions(trades: list) -> list:
    """Aggregate raw trade fills into closed round trips, newest first."""
    by_symbol = defaultdict(list)
    for trade in trades:
        by_symbol[trade.get("symbol", "")].append(trade)

    closed = []
    for symbol, items in by_symbol.items():
        items.sort(key=lambda t: int(t.get("time", 0) or 0))
        closed.extend(_round_trips(symbol, items))

    closed.sort(key=lambda c: c["close_time"] or 0, reverse=True)
    return closed
