"""SQLite storage for watch history.

Single responsibility: save and retrieve analysis results.
"""
import sqlite3
from datetime import datetime

DB_PATH = "agentic_binance.db"


def init_db() -> None:
    """Create table if not exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watch_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            trend TEXT,
            momentum TEXT,
            strength TEXT,
            risk TEXT,
            trade_bias TEXT,
            action TEXT,
            confidence TEXT,
            reason TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_analysis(symbol: str, analysis) -> None:
    """Save analysis result to database.

    Args:
        symbol: Trading pair, e.g. "BTCUSDT".
        analysis: MarketAnalysis object from DeepSeek.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO watch_history
        (symbol, timestamp, trend, momentum, strength, risk,
         trade_bias, action, confidence, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            symbol,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            analysis.trend,
            analysis.momentum,
            analysis.strength,
            analysis.risk,
            analysis.trade_bias,
            analysis.action,
            analysis.confidence,
            analysis.reason,
        ),
    )
    conn.commit()
    conn.close()


def get_history(symbol: str, limit: int = 20) -> list:
    """Get analysis history for a symbol.

    Args:
        symbol: Trading pair, e.g. "BTCUSDT".
        limit: Max records to return.

    Returns:
        list: Rows of (id, symbol, timestamp, trend, momentum, strength,
              risk, trade_bias, action, confidence, reason).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        SELECT * FROM watch_history
        WHERE symbol = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (symbol, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows