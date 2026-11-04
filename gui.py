"""Simple GUI for Agentic Binance (Tkinter, no new dependency).

Usage:
    python gui.py
"""
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk

from agents.market_agent import analyze
from engines.decision_engine import decide
from engines.snapshot import build_snapshot, to_summary_lines
from tools.binance_tool import (
    get_ticker,
    get_premium_index,
    get_open_interest,
    get_positions,
    get_trade_history,
)
from tools.storage import init_db, save_analysis, get_history


def format_volume(value: float) -> str:
    """Format volume to human-readable (B, M, K)."""
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B USDT"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M USDT"
    if value >= 1_000:
        return f"{value / 1_000:.2f}K USDT"
    return f"{value:.2f} USDT"


def format_oi(value: str) -> str:
    """Format open interest with comma separator."""
    try:
        return f"{float(value):,.0f}"
    except (ValueError, TypeError):
        return value or ""


def format_funding(value: str) -> str:
    """Format funding rate as percentage."""
    try:
        rate = float(value)
        return f"{rate * 100:.4f}%"
    except (ValueError, TypeError):
        return value or ""


def format_price_change(value: str) -> str:
    """Format price change with + or - sign."""
    try:
        return f"{float(value):+.2f}"
    except (ValueError, TypeError):
        return value or ""


def format_price_change_percent(value: str) -> str:
    """Format price change percent with + or - sign."""
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return value or ""


def format_analysis(symbol: str, analysis, decision, snapshot=None) -> str:
    """Format the AI analysis, the deterministic indicators, and the decision."""
    lines = [
        "=" * 50,
        symbol,
        "=" * 50,
        "",
        f"{'Market Bias':<16}: {analysis.trend.capitalize()}",
        f"{'Momentum':<16}: {analysis.momentum.capitalize()}",
        f"{'Risk':<16}: {analysis.risk.capitalize()}",
        "",
    ]
    if snapshot is not None:
        lines.append("INDICATORS (dihitung sistem)")
        lines.extend(to_summary_lines(snapshot))
        lines.append("")
    lines += [
        f"{'AI Bias':<16}: {analysis.trade_bias}",
        f"{'AI Action':<16}: {analysis.action}",
        f"{'AI Confidence':<16}: {analysis.confidence}",
        "",
        f"{'Decision':<16}: {decision.action}",
        f"{'Conviction':<16}: {decision.confidence}",
        "",
        f"{'Reason':<16}: {analysis.reason}",
        f"{'Rule Detail':<16}: {decision.reason}",
        "=" * 50,
    ]
    return "\n".join(lines)


def main() -> None:
    init_db()

    root = tk.Tk()
    root.title("Agentic Binance")
    root.geometry("750x550")
    root.resizable(True, True)

    # Menu bar
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    view_menu = tk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="View", menu=view_menu)

    # Always on Top
    topmost_var = tk.BooleanVar(value=True)

    def toggle_topmost() -> None:
        root.attributes("-topmost", topmost_var.get())

    view_menu.add_checkbutton(
        label="Always on Top", variable=topmost_var, command=toggle_topmost
    )
    root.attributes("-topmost", True)

    # Dark Mode
    dark_var = tk.BooleanVar(value=False)

    def toggle_theme() -> None:
        style = ttk.Style()
        style.theme_use("clam")
        if dark_var.get():
            bg, fg = "#2b2b2b", "#e0e0e0"
            eb = "#3c3f41"
        else:
            bg, fg = "#f0f0f0", "#000000"
            eb = "#ffffff"
        root.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=eb, foreground=fg)
        style.configure("TEntry", fieldbackground=eb, foreground=fg)
        style.configure("Treeview", background=eb, fieldbackground=eb, foreground=fg)
        style.configure("Treeview.Heading", background=bg, foreground=fg)
        for w in [output, watch_output]:
            w.configure(bg=eb, fg=fg, insertbackground=fg)

    view_menu.add_checkbutton(label="Dark Mode", variable=dark_var, command=toggle_theme)

    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)

    # ========== Tab 1: Analyze ==========
    tab_analyze = ttk.Frame(notebook, padding=10)
    notebook.add(tab_analyze, text="Analyze")

    input_frame = ttk.Frame(tab_analyze)
    input_frame.pack(fill=tk.X, pady=(0, 5))

    ttk.Label(input_frame, text="Pair:").pack(side=tk.LEFT)
    entry = ttk.Entry(input_frame, width=15, font=("Consolas", 11))
    entry.pack(side=tk.LEFT, padx=5)
    entry.insert(0, "BTCUSDT")

    btn_analyze = ttk.Button(input_frame, text="Analyze")
    btn_analyze.pack(side=tk.LEFT, padx=(0, 5))

    btn_copy = ttk.Button(input_frame, text="Copy", state=tk.DISABLED)
    btn_copy.pack(side=tk.LEFT)

    def on_copy() -> None:
        text = output.get(1.0, tk.END)
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        status.config(text="Copied to clipboard.")

    btn_copy.config(command=on_copy)

    status = ttk.Label(tab_analyze, text="Ready.", font=("Segoe UI", 9))
    status.pack(pady=(0, 5), anchor=tk.W)

    output = scrolledtext.ScrolledText(
        tab_analyze, wrap=tk.WORD, font=("Consolas", 10)
    )
    output.pack(fill=tk.BOTH, expand=True)

    def show_result(text: str, status_text: str) -> None:
        output.delete(1.0, tk.END)
        output.insert(tk.END, text)
        status.config(text=status_text)
        btn_analyze.config(state=tk.NORMAL)
        btn_copy.config(state=tk.NORMAL)

    def format_ticker(ticker: dict, premium: dict, oi: dict) -> str:
        """Format raw ticker data from Binance."""
        vol = float(ticker.get("quoteVolume", 0))
        price_change = format_price_change(ticker.get("priceChange", ""))
        price_change_pct = format_price_change_percent(ticker.get("priceChangePercent", ""))
        funding = format_funding(premium.get("lastFundingRate", ""))
        oi_val = format_oi(oi.get("openInterest", ""))
        vol_str = format_volume(vol)

        lines = [
            "",
            "=" * 50,
            "MARKET DATA",
            "=" * 50,
            f"{'Price':<16}: {ticker.get('lastPrice', '')}",
            f"{'24H Change':<16}: {price_change} ({price_change_pct})",
            f"{'Funding':<16}: {funding}",
            f"{'Open Interest':<16}: {oi_val}",
            f"{'Volume':<16}: {vol_str}",
            "=" * 50,
        ]
        return "\n".join(lines)

    def worker(symbol: str) -> None:
        try:
            root.after(0, lambda: status.config(text="Fetching Binance data..."))
            analysis = analyze(symbol)
            decision = decide(analysis)
            snapshot = build_snapshot(symbol)

            root.after(0, lambda: status.config(text="Fetching market data..."))
            ticker = get_ticker(symbol)
            premium = get_premium_index(symbol)
            oi = get_open_interest(symbol)
            ticker_text = format_ticker(ticker, premium, oi)

            full_result = (
                format_analysis(symbol, analysis, decision, snapshot) + "\n" + ticker_text
            )
            root.after(0, lambda: show_result(full_result, "Done."))
        except Exception as exc:
            msg = f"[ERROR] {type(exc).__name__}: {exc}"
            root.after(0, lambda: show_result(msg, "Error."))

    def on_analyze() -> None:
        symbol = entry.get().strip().upper() or "BTCUSDT"
        btn_analyze.config(state=tk.DISABLED)
        btn_copy.config(state=tk.DISABLED)
        output.delete(1.0, tk.END)
        status.config(text="Analyzing market...")
        threading.Thread(target=worker, args=(symbol,), daemon=True).start()

    btn_analyze.config(command=on_analyze)
    entry.bind("<Return>", lambda _: on_analyze())

    # ========== Tab 2: Scan ==========
    tab_scan = ttk.Frame(notebook, padding=10)
    notebook.add(tab_scan, text="Scan")

    scan_status = ttk.Label(tab_scan, text="Ready.", font=("Segoe UI", 9))
    scan_status.pack(pady=(0, 5), anchor=tk.W)

    scan_display = ttk.Notebook(tab_scan)
    scan_display.pack(fill=tk.BOTH, expand=True)

    # --- Tab: All (All coins) ---
    tab_all = ttk.Frame(scan_display, padding=5)
    scan_display.add(tab_all, text="All")

    columns = ("symbol", "price", "change", "bias", "trade_bias", "confidence")
    tree = ttk.Treeview(tab_all, columns=columns, show="headings", height=15)
    tree.heading("symbol", text="Symbol")
    tree.heading("price", text="Price")
    tree.heading("change", text="5M %")
    tree.heading("bias", text="Market Bias")
    tree.heading("trade_bias", text="Trade Bias")
    tree.heading("confidence", text="Confidence")

    tree.column("symbol", width=90)
    tree.column("price", width=80)
    tree.column("change", width=70)
    tree.column("bias", width=80)
    tree.column("trade_bias", width=70)
    tree.column("confidence", width=70)
    tree.pack(fill=tk.BOTH, expand=True)

    tree.tag_configure("LONG", foreground="green")
    tree.tag_configure("SHORT", foreground="red")
    tree.tag_configure("WAIT", foreground="orange")

    # --- Tab: Naik (5M) ---
    tab_gainers = ttk.Frame(scan_display, padding=5)
    scan_display.add(tab_gainers, text="Naik (5M)")

    gainers_cols = ("symbol", "price", "change", "bias", "trade_bias", "confidence")
    tree_gainers = ttk.Treeview(tab_gainers, columns=gainers_cols, show="headings", height=15)
    tree_gainers.heading("symbol", text="Symbol")
    tree_gainers.heading("price", text="Price")
    tree_gainers.heading("change", text="5M %")
    tree_gainers.heading("bias", text="Market Bias")
    tree_gainers.heading("trade_bias", text="Trade Bias")
    tree_gainers.heading("confidence", text="Confidence")

    tree_gainers.column("symbol", width=90)
    tree_gainers.column("price", width=80)
    tree_gainers.column("change", width=70)
    tree_gainers.column("bias", width=80)
    tree_gainers.column("trade_bias", width=70)
    tree_gainers.column("confidence", width=70)
    tree_gainers.pack(fill=tk.BOTH, expand=True)

    tree_gainers.tag_configure("LONG", foreground="green")
    tree_gainers.tag_configure("SHORT", foreground="red")
    tree_gainers.tag_configure("WAIT", foreground="orange")

    # --- Tab: Turun (5M) ---
    tab_losers = ttk.Frame(scan_display, padding=5)
    scan_display.add(tab_losers, text="Turun (5M)")

    losers_cols = ("symbol", "price", "change", "bias", "trade_bias", "confidence")
    tree_losers = ttk.Treeview(tab_losers, columns=losers_cols, show="headings", height=15)
    tree_losers.heading("symbol", text="Symbol")
    tree_losers.heading("price", text="Price")
    tree_losers.heading("change", text="5M %")
    tree_losers.heading("bias", text="Market Bias")
    tree_losers.heading("trade_bias", text="Trade Bias")
    tree_losers.heading("confidence", text="Confidence")

    tree_losers.column("symbol", width=90)
    tree_losers.column("price", width=80)
    tree_losers.column("change", width=70)
    tree_losers.column("bias", width=80)
    tree_losers.column("trade_bias", width=70)
    tree_losers.column("confidence", width=70)
    tree_losers.pack(fill=tk.BOTH, expand=True)

    tree_losers.tag_configure("LONG", foreground="green")
    tree_losers.tag_configure("SHORT", foreground="red")
    tree_losers.tag_configure("WAIT", foreground="orange")

    btn_frame = ttk.Frame(tab_scan)
    btn_frame.pack(pady=(5, 0))

    def on_analyze_selected() -> None:
        # Check which tree currently has the selection
        for tgt_tree in [tree, tree_gainers, tree_losers]:
            selected = tgt_tree.selection()
            if selected:
                symbol = tgt_tree.item(selected[0])["values"][0]
                notebook.select(tab_analyze)
                entry.delete(0, tk.END)
                entry.insert(0, symbol)
                on_analyze()
                return
        scan_status.config(text="Pilih coin dari tabel terlebih dahulu.")

    btn_analyze_selected = ttk.Button(btn_frame, text="Analyze Selected", command=on_analyze_selected)
    btn_analyze_selected.pack(side=tk.LEFT, padx=(0, 5))

    def on_scan() -> None:
        btn_scan.config(state=tk.DISABLED)
        scan_status.config(text="Scanning market...")
        threading.Thread(target=scan_worker, daemon=True).start()

    def fill_tree(tgt_tree, rows) -> None:
        """Fill a treeview with scan rows."""
        for item in tgt_tree.get_children():
            tgt_tree.delete(item)
        for row in rows:
            trend = row["trend"]
            if trend == "BULLISH":
                bias = "BULLISH"
                trade = "LONG"
                conf = "MEDIUM"
                tag = "LONG"
            elif trend == "BEARISH":
                bias = "BEARISH"
                trade = "SHORT"
                conf = "MEDIUM"
                tag = "SHORT"
            elif trend == "PULLBACK":
                bias = "PULLBACK"
                trade = "WAIT"
                conf = "MEDIUM"
                tag = "WAIT"
            else:
                bias = "NEUTRAL"
                trade = "WAIT"
                conf = "LOW"
                tag = "WAIT"

            tgt_tree.insert("", tk.END, values=(
                row["symbol"],
                f"{row['price']:.4f}",
                f"{row['change']:+.2f}%",
                bias,
                trade,
                conf,
            ), tags=(tag,))

    def scan_worker() -> None:
        try:
            import scanner
            data = scanner.get_scan_data(10)

            rows = data.get("rows", [])
            gainers = data.get("gainers", [])
            losers = data.get("losers", [])

            fill_tree(tree, rows)
            fill_tree(tree_gainers, gainers)
            fill_tree(tree_losers, losers)

            scan_status.config(text=f"Scan complete. Naik: {len(gainers)}, Turun: {len(losers)}")
        except Exception as exc:
            scan_status.config(text=f"Error: {exc}")
        finally:
            btn_scan.config(state=tk.NORMAL)

    btn_scan = ttk.Button(btn_frame, text="Scan", command=on_scan)
    btn_scan.pack(side=tk.LEFT)

    # ========== Tab 3: Watch ==========
    tab_watch = ttk.Frame(notebook, padding=10)
    notebook.add(tab_watch, text="Watch")

    watch_input = ttk.Frame(tab_watch)
    watch_input.pack(fill=tk.X, pady=(0, 5))

    ttk.Label(watch_input, text="Pair:").pack(side=tk.LEFT)
    watch_entry = ttk.Entry(watch_input, width=15, font=("Consolas", 11))
    watch_entry.pack(side=tk.LEFT, padx=5)
    watch_entry.insert(0, "BTCUSDT")

    ttk.Label(watch_input, text="Interval (min):").pack(side=tk.LEFT, padx=(10, 0))
    interval_entry = ttk.Entry(watch_input, width=5, font=("Consolas", 11))
    interval_entry.pack(side=tk.LEFT, padx=5)
    interval_entry.insert(0, "5")

    btn_watch = ttk.Button(watch_input, text="Start")
    btn_watch.pack(side=tk.LEFT, padx=(10, 0))

    watch_status = ttk.Label(tab_watch, text="Ready.", font=("Segoe UI", 9))
    watch_status.pack(pady=(0, 5), anchor=tk.W)

    ttk.Label(tab_watch, text="Latest Analysis:").pack(anchor=tk.W)
    watch_output = scrolledtext.ScrolledText(
        tab_watch, wrap=tk.WORD, font=("Consolas", 10), height=10
    )
    watch_output.pack(fill=tk.BOTH, expand=True)

    ttk.Label(tab_watch, text="History:").pack(anchor=tk.W, pady=(5, 0))
    hist_cols = ("timestamp", "bias", "trade", "action", "conf")
    hist_tree = ttk.Treeview(tab_watch, columns=hist_cols, show="headings", height=8)
    hist_tree.heading("timestamp", text="Time")
    hist_tree.heading("bias", text="Market Bias")
    hist_tree.heading("trade", text="Trade Bias")
    hist_tree.heading("action", text="Action")
    hist_tree.heading("conf", text="Confidence")
    hist_tree.column("timestamp", width=140)
    hist_tree.column("bias", width=80)
    hist_tree.column("trade", width=70)
    hist_tree.column("action", width=120)
    hist_tree.column("conf", width=70)
    hist_tree.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    hist_tree.tag_configure("LONG", foreground="green")
    hist_tree.tag_configure("SHORT", foreground="red")
    hist_tree.tag_configure("WAIT", foreground="orange")

    watch_running = {"active": False}

    def refresh_history(symbol: str) -> None:
        for item in hist_tree.get_children():
            hist_tree.delete(item)
        rows = get_history(symbol, 20)
        for r in rows:
            ts, bias, trade, action, conf = r[2], r[3], r[7], r[8], r[9]
            tag = trade if trade in ("LONG", "SHORT", "WAIT") else ""
            hist_tree.insert("", tk.END, values=(ts, bias, trade, action, conf), tags=(tag,))

    def watch_worker(symbol: str) -> None:
        try:
            root.after(0, lambda: watch_status.config(text=f"Analyzing {symbol}..."))
            analysis = analyze(symbol)
            decision = decide(analysis)
            snapshot = build_snapshot(symbol)
            save_analysis(symbol, analysis)

            result = format_analysis(symbol, analysis, decision, snapshot)
            root.after(0, lambda: watch_output.delete(1.0, tk.END))
            root.after(0, lambda: watch_output.insert(tk.END, result))
            root.after(0, lambda: refresh_history(symbol))
            root.after(0, lambda: watch_status.config(text=f"Updated. Next in {interval_entry.get()} min."))
        except Exception as exc:
            msg = f"[ERROR] {type(exc).__name__}: {exc}"
            root.after(0, lambda: watch_status.config(text=msg))

    def watch_loop(symbol: str) -> None:
        if not watch_running["active"]:
            return
        from datetime import datetime
        now = datetime.now()
        try:
            minutes = int(interval_entry.get())
        except ValueError:
            minutes = 5
        interval_seconds = minutes * 60
        seconds_into_hour = now.minute * 60 + now.second
        seconds_until = interval_seconds - (seconds_into_hour % interval_seconds)
        if seconds_until == 0:
            seconds_until = interval_seconds
        m, s = seconds_until // 60, seconds_until % 60
        watch_status.config(text=f"Next analysis in {m}m {s}s...")
        root.after(seconds_until * 1000, lambda: watch_run(symbol))

    def watch_run(symbol: str) -> None:
        if not watch_running["active"]:
            return
        threading.Thread(target=watch_worker, args=(symbol,), daemon=True).start()
        try:
            minutes = int(interval_entry.get())
        except ValueError:
            minutes = 5
        root.after(minutes * 60 * 1000, lambda: watch_run(symbol))

    def on_watch_toggle() -> None:
        if watch_running["active"]:
            watch_running["active"] = False
            btn_watch.config(text="Start")
            watch_status.config(text="Stopped.")
        else:
            symbol = watch_entry.get().strip().upper() or "BTCUSDT"
            watch_running["active"] = True
            btn_watch.config(text="Stop")
            watch_status.config(text=f"Watching {symbol}...")
            refresh_history(symbol)
            watch_loop(symbol)

    btn_watch.config(command=on_watch_toggle)

    # ========== Tab 4: Positions ==========
    tab_pos = ttk.Frame(notebook, padding=10)
    notebook.add(tab_pos, text="Positions")

    pos_btn_frame = ttk.Frame(tab_pos)
    pos_btn_frame.pack(fill=tk.X, pady=(0, 5))

    ttk.Button(pos_btn_frame, text="Refresh Positions", command=lambda: load_positions()).pack(side=tk.LEFT)
    ttk.Button(pos_btn_frame, text="Refresh History", command=lambda: load_position_history()).pack(side=tk.LEFT, padx=(5, 0))

    def on_copy_positions() -> None:
        headers = ["Symbol", "Side", "Size", "Entry Price", "Mark Price", "Unrealized PnL", "ROE %"]
        lines = ["\t".join(headers)]
        for item in pos_tree.get_children():
            vals = pos_tree.item(item)["values"]
            lines.append("\t".join(str(v) for v in vals))
        text = "\n".join(lines)
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        pos_status.config(text="Positions copied to clipboard.")

    def on_copy_history() -> None:
        headers = ["Time (WIB)", "Symbol", "Side", "Qty", "Price", "Realized PnL", "Fee"]
        lines = ["\t".join(headers)]
        from datetime import datetime, timezone, timedelta
        wib = timezone(timedelta(hours=7))
        for item in hist_tree2.get_children():
            vals = hist_tree2.item(item)["values"]
            time_val = vals[0]
            if isinstance(time_val, (int, float)) and time_val > 1e12:
                dt = datetime.fromtimestamp(time_val / 1000, tz=wib)
                time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = str(time_val)
            new_vals = (time_str,) + tuple(vals[1:])
            lines.append("\t".join(str(v) for v in new_vals))
        text = "\n".join(lines)
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
        pos_status.config(text="History copied to clipboard.")

    ttk.Button(pos_btn_frame, text="Copy Positions", command=on_copy_positions).pack(side=tk.LEFT, padx=(5, 0))
    ttk.Button(pos_btn_frame, text="Copy History", command=on_copy_history).pack(side=tk.LEFT, padx=(5, 0))

    pos_status = ttk.Label(tab_pos, text="Ready.", font=("Segoe UI", 9))
    pos_status.pack(pady=(0, 5), anchor=tk.W)

    # Open Positions
    ttk.Label(tab_pos, text="Open Positions:").pack(anchor=tk.W)
    pos_cols = ("symbol", "side", "size", "entry", "mark", "pnl", "roe")
    pos_tree = ttk.Treeview(tab_pos, columns=pos_cols, show="headings", height=6)
    pos_tree.heading("symbol", text="Symbol")
    pos_tree.heading("side", text="Side")
    pos_tree.heading("size", text="Size")
    pos_tree.heading("entry", text="Entry Price")
    pos_tree.heading("mark", text="Mark Price")
    pos_tree.heading("pnl", text="Unrealized PnL")
    pos_tree.heading("roe", text="ROE %")
    pos_tree.column("symbol", width=90)
    pos_tree.column("side", width=60)
    pos_tree.column("size", width=70)
    pos_tree.column("entry", width=80)
    pos_tree.column("mark", width=80)
    pos_tree.column("pnl", width=90)
    pos_tree.column("roe", width=60)
    pos_tree.pack(fill=tk.BOTH, expand=True)

    pos_tree.tag_configure("LONG", foreground="green")
    pos_tree.tag_configure("SHORT", foreground="red")

    # Position History
    ttk.Label(tab_pos, text="Position History:").pack(anchor=tk.W, pady=(5, 0))
    hist_frame2 = ttk.Frame(tab_pos)
    hist_frame2.pack(fill=tk.X, pady=(2, 0))

    ttk.Label(hist_frame2, text="Symbol:").pack(side=tk.LEFT)
    hist_symbol_var = tk.StringVar(value="All")
    hist_symbol_combo = ttk.Combobox(hist_frame2, textvariable=hist_symbol_var, state="normal", width=12)
    hist_symbol_combo.pack(side=tk.LEFT, padx=5)

    ttk.Button(hist_frame2, text="Refresh", command=lambda: load_position_history(hist_symbol_var.get())).pack(side=tk.LEFT)
    ttk.Label(hist_frame2, text="All = posisi terbuka, atau ketik symbol lain").pack(side=tk.LEFT, padx=(8, 0))

    hist_cols2 = ("symbol", "side", "realized_pnl", "roi", "closed_vol", "entry_price", "avg_close")
    hist_tree2 = ttk.Treeview(tab_pos, columns=hist_cols2, show="headings", height=6)
    hist_tree2.heading("symbol", text="Symbol")
    hist_tree2.heading("side", text="Side")
    hist_tree2.heading("realized_pnl", text="Realized PnL (USDT)")
    hist_tree2.heading("roi", text="ROI %")
    hist_tree2.heading("closed_vol", text="Volume")
    hist_tree2.heading("entry_price", text="Entry Price")
    hist_tree2.heading("avg_close", text="Avg Close Price")
    hist_tree2.column("symbol", width=90)
    hist_tree2.column("side", width=60)
    hist_tree2.column("realized_pnl", width=90)
    hist_tree2.column("roi", width=70)
    hist_tree2.column("closed_vol", width=90)
    hist_tree2.column("entry_price", width=80)
    hist_tree2.column("avg_close", width=80)
    hist_tree2.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    hist_tree2.tag_configure("LONG", foreground="green")
    hist_tree2.tag_configure("SHORT", foreground="red")

    def render_positions(positions: list) -> None:
        for item in pos_tree.get_children():
            pos_tree.delete(item)
        if not positions:
            pos_status.config(text="No open positions.")
            hist_symbol_combo["values"] = ["All"]
            return
        for p in positions:
            symbol = p.get("symbol", "")
            amt = float(p.get("positionAmt", 0) or 0)
            side = "LONG" if amt > 0 else "SHORT"
            unrealized = float(p.get("unRealizedProfit", 0) or 0)
            margin = float(p.get("initialMargin", 0) or 0)
            roe = f"{unrealized / margin * 100:.2f}%" if margin else ""
            pos_tree.insert("", tk.END, values=(
                symbol,
                side,
                f"{abs(amt):.4f}",
                p.get("entryPrice", ""),
                p.get("markPrice", ""),
                p.get("unRealizedProfit", ""),
                roe,
            ), tags=(side,))
        symbols = [p.get("symbol", "") for p in positions]
        hist_symbol_combo["values"] = ["All"] + symbols
        pos_status.config(text=f"Loaded {len(positions)} positions.")

    def positions_worker() -> None:
        try:
            positions = get_positions()
        except Exception as exc:
            msg = f"Error: {exc}"
            root.after(0, lambda: pos_status.config(text=msg))
            return
        root.after(0, lambda: render_positions(positions))

    def load_positions() -> None:
        pos_status.config(text="Loading positions...")
        threading.Thread(target=positions_worker, daemon=True).start()

    def render_history(closed: list) -> None:
        for item in hist_tree2.get_children():
            hist_tree2.delete(item)
        for c in closed:
            hist_tree2.insert("", tk.END, values=(
                c["symbol"],
                c["side"],
                f"{c['realized_pnl']:.2f}",
                f"{c['roi']:.2f}%",
                f"{c['closed_vol']:.2f}",
                f"{c['entry_price']:.6f}",
                f"{c['avg_close_price']:.6f}",
            ), tags=(c["side"],))
        pos_status.config(text=f"Loaded {len(closed)} closed positions.")

    def history_worker(symbol: str) -> None:
        try:
            from tools.position_history import aggregate_positions
            # Binance userTrades requires a symbol, so "All" means all symbols
            # that currently hold a position.
            if symbol == "All":
                targets = [p.get("symbol", "") for p in get_positions()]
            else:
                targets = [symbol]
            if not targets:
                root.after(0, lambda: pos_status.config(
                    text="Tidak ada posisi terbuka — ketik symbol untuk melihat riwayat."
                ))
                return
            all_trades = []
            for sym in targets:
                all_trades.extend(get_trade_history(sym, 200))
            closed = aggregate_positions(all_trades)
        except Exception as exc:
            msg = f"Error: {exc}"
            root.after(0, lambda: pos_status.config(text=msg))
            return
        root.after(0, lambda: render_history(closed))

    def load_position_history(symbol: str = "All") -> None:
        symbol = symbol.strip().upper() or "All"
        pos_status.config(text="Loading history...")
        threading.Thread(target=history_worker, args=(symbol,), daemon=True).start()

    root.mainloop()


if __name__ == "__main__":
    main()