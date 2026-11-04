"""Deterministic Risk Manager: turn a decision into a sized trade plan.

The LLM never picks size, stop, or leverage. Those come from account equity,
ATR, and the exchange filters. The manager can veto the decision entirely, so
a plan is either a fully computed proposal or a list of failed guards.
"""
import math

from config import settings
from models.market_decision import MarketDecision
from models.market_snapshot import MarketSnapshot, TimeframeSnapshot
from models.trade_plan import TradePlan
from tools.binance_tool import get_account_state, get_symbol_filters

STOP_TIMEFRAME = "1h"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _decimals_for(step: float) -> int:
    text = f"{step:.10f}".rstrip("0")
    return len(text.split(".")[1]) if "." in text else 0


def _floor_to_step(value: float, step: float) -> float:
    """Round down to a multiple of the exchange step size."""
    if step <= 0:
        return round(value, 8)
    steps = math.floor(value / step + 1e-9)
    return round(steps * step, _decimals_for(step))


def _round_to_tick(value: float, tick: float) -> float:
    if tick <= 0:
        return round(value, 8)
    return round(round(value / tick) * tick, _decimals_for(tick))


def _stop_timeframe(snapshot: MarketSnapshot) -> TimeframeSnapshot | None:
    """Prefer 1h ATR; fall back to any timeframe that produced one."""
    preferred = snapshot.by_timeframe(STOP_TIMEFRAME)
    if preferred is not None and preferred.atr:
        return preferred
    for item in snapshot.timeframes:
        if item.atr:
            return item
    return preferred


def _reject(symbol: str, guards: list[str], equity: float | None = None) -> TradePlan:
    return TradePlan(
        symbol=symbol,
        approved=False,
        equity=equity,
        guards=guards,
        reason="; ".join(guards),
    )


def _blocking_guards(
    decision: MarketDecision, snapshot: MarketSnapshot, account: dict, equity: float
) -> list[str]:
    guards: list[str] = []

    if decision.action == "WAIT":
        guards.append("keputusan engine WAIT")
    if decision.confidence < settings.MIN_CONVICTION:
        guards.append(
            f"conviction {decision.confidence} di bawah minimum {settings.MIN_CONVICTION}"
        )
    if equity <= 0:
        guards.append(f"equity tidak valid ({equity:.2f} USDT)")
    if float(account.get("available_balance") or 0) <= 0:
        guards.append("saldo tersedia kosong")

    open_positions = int(account.get("open_positions") or 0)
    if open_positions >= settings.MAX_OPEN_POSITIONS:
        guards.append(
            f"posisi terbuka {open_positions} mencapai batas {settings.MAX_OPEN_POSITIONS}"
        )
    if snapshot.symbol in (account.get("open_symbols") or []):
        guards.append(f"{snapshot.symbol} sudah punya posisi terbuka")

    today_pnl = account.get("today_realized_pnl")
    if today_pnl is None:
        guards.append("realized PnL hari ini tidak bisa dibaca")
    elif equity > 0 and today_pnl <= -equity * settings.DAILY_LOSS_LIMIT_PCT / 100:
        guards.append(
            f"rugi hari ini {today_pnl:.2f} USDT mencapai batas "
            f"{settings.DAILY_LOSS_LIMIT_PCT:g}% equity"
        )

    timeframe = _stop_timeframe(snapshot)
    if timeframe is None:
        guards.append("snapshot harga tidak tersedia")
    elif timeframe.atr is None or timeframe.atr <= 0:
        guards.append(f"ATR {timeframe.timeframe} tidak tersedia")

    return guards


def assess(
    decision: MarketDecision,
    snapshot: MarketSnapshot,
    account: dict,
    filters: dict,
) -> TradePlan:
    """Size the decision, or reject it with the list of failed guards."""
    equity = float(account.get("total_wallet_balance") or 0)
    available = float(account.get("available_balance") or 0)

    guards = _blocking_guards(decision, snapshot, account, equity)
    if guards:
        return _reject(snapshot.symbol, guards, equity)

    timeframe = _stop_timeframe(snapshot)
    price = timeframe.close
    atr = timeframe.atr

    step = float(filters.get("step_size") or 0)
    min_qty = float(filters.get("min_qty") or 0)
    max_qty = float(filters.get("max_qty") or 0)
    min_notional = float(filters.get("min_notional") or 0)
    tick = float(filters.get("price_tick") or 0)

    stop_distance = _clamp(
        atr * settings.STOP_ATR_MULT,
        price * settings.STOP_MIN_PCT / 100,
        price * settings.STOP_MAX_PCT / 100,
    )
    risk_budget = equity * settings.RISK_PER_TRADE_PCT / 100

    # Size from the risk budget, then cap by notional/leverage limits.
    qty = risk_budget / stop_distance
    notional_cap = min(
        equity * settings.MAX_NOTIONAL_PCT / 100,
        available * settings.MAX_LEVERAGE,
    )
    qty = min(qty, notional_cap / price)
    qty = _floor_to_step(qty, step)
    if max_qty > 0:
        qty = min(qty, max_qty)

    if qty <= 0 or qty < min_qty:
        return _reject(
            snapshot.symbol,
            [f"quantity {qty:g} di bawah minimum exchange ({min_qty:g})"],
            equity,
        )

    notional = qty * price
    if notional < min_notional:
        return _reject(
            snapshot.symbol,
            [
                f"notional {notional:.2f} USDT di bawah minimum "
                f"{min_notional:.2f} USDT"
            ],
            equity,
        )

    side = decision.action
    if side == "LONG":
        stop_loss = price - stop_distance
        take_profit = price + stop_distance * settings.REWARD_RATIO
    else:
        stop_loss = price + stop_distance
        take_profit = price - stop_distance * settings.REWARD_RATIO

    risk_amount = qty * stop_distance
    required_leverage = math.ceil(notional / equity)
    leverage = max(1, min(settings.MAX_LEVERAGE, required_leverage))

    return TradePlan(
        symbol=snapshot.symbol,
        approved=True,
        side=side,
        entry=_round_to_tick(price, tick),
        stop_loss=_round_to_tick(stop_loss, tick),
        take_profit=_round_to_tick(take_profit, tick),
        quantity=qty,
        notional=round(notional, 2),
        leverage=leverage,
        risk_amount=round(risk_amount, 2),
        risk_pct=round(risk_amount / equity * 100, 3),
        equity=round(equity, 2),
        stop_timeframe=timeframe.timeframe,
        reason=(
            f"{side} {qty:g} {snapshot.symbol} @ {price:g}, "
            f"stop {stop_distance / price * 100:.2f}% ({timeframe.timeframe} ATR), "
            f"RR {settings.REWARD_RATIO:g}, risiko {risk_amount:.2f} USDT"
        ),
    )


def assess_symbol(decision: MarketDecision, snapshot: MarketSnapshot) -> TradePlan:
    """Fetch account and filters, then assess. Never raises on API problems."""
    try:
        account = get_account_state()
        filters = get_symbol_filters(snapshot.symbol)
    except Exception as exc:
        return _reject(
            snapshot.symbol,
            [f"data akun/filter tidak tersedia ({type(exc).__name__}: {exc})"],
        )

    return assess(decision, snapshot, account, filters)


def to_lines(plan: TradePlan) -> list[str]:
    """Human-readable plan for the CLI and GUI."""
    lines = [f"{'Trade Plan':<16}: {'APPROVED' if plan.approved else 'REJECTED'}"]

    if not plan.approved:
        for guard in plan.guards:
            lines.append(f"{'Guard':<16}: {guard}")
        return lines

    lines += [
        f"{'Side':<16}: {plan.side}",
        f"{'Entry':<16}: {plan.entry:,.6g}",
        f"{'Stop Loss':<16}: {plan.stop_loss:,.6g}",
        f"{'Take Profit':<16}: {plan.take_profit:,.6g}",
        f"{'Quantity':<16}: {plan.quantity:g}",
        f"{'Notional':<16}: {plan.notional:,.2f} USDT",
        f"{'Leverage':<16}: {plan.leverage}x",
        f"{'Risk':<16}: {plan.risk_amount:,.2f} USDT ({plan.risk_pct:.2f}% equity)",
        f"{'Equity':<16}: {plan.equity:,.2f} USDT",
        f"{'Stop Basis':<16}: ATR {plan.stop_timeframe}",
    ]
    return lines
