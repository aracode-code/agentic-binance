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