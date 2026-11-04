"""Application configuration loaded from environment variables.

Single responsibility: read .env and expose settings.
Other modules import from here — this is the only place
that knows where config comes from.
"""
import os

from dotenv import load_dotenv

# Load variables from .env file into os.environ
load_dotenv()

# --- Binance Futures ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# --- DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# --- App settings ---
# true = Testnet (safe), false = Mainnet (real money)
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"

# --- Risk manager (conservative defaults) ---
# All percentages are in percent (0.5 = 0.5%).
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.5"))
MAX_LEVERAGE = int(os.getenv("MAX_LEVERAGE", "5"))
MAX_NOTIONAL_PCT = float(os.getenv("MAX_NOTIONAL_PCT", "20"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "3"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
MIN_CONVICTION = int(os.getenv("MIN_CONVICTION", "60"))

# Stop distance = STOP_ATR_MULT * ATR(1h), clamped to the min/max price %.
STOP_ATR_MULT = float(os.getenv("STOP_ATR_MULT", "1.5"))
STOP_MIN_PCT = float(os.getenv("STOP_MIN_PCT", "0.3"))
STOP_MAX_PCT = float(os.getenv("STOP_MAX_PCT", "3"))
REWARD_RATIO = float(os.getenv("REWARD_RATIO", "2"))