# Agentic Binance

AI Trading Agent untuk Binance Futures menggunakan DeepSeek sebagai reasoning engine.

## Fitur

- **Market Analysis** — Ambil data Binance Futures (ticker, klines, funding rate, open interest)
- **Deterministic Indicators** — EMA 9/21/50/200, SMA 7/25/99, RSI, MACD, Bollinger, ATR, volume ratio, HH/HL + BOS/CHoCH, S/R, breakout, multi-timeframe (1d/4h/1h/15m). Dihitung kode, bukan LLM
- **AI Reasoning** — DeepSeek LLM menilai konteks memakai angka indikator yang sudah dihitung
- **Rule Engine** — Trend, Momentum, Volatility rules; keputusan akhir tunduk pada aturan (bias AI yang bertentangan ditahan ke WAIT)
- **Conviction Score** — Skor internal 0-100 dari edge antar-aturan; bukan probabilitas profit
- **Storage** — SQLite untuk history analisa
- **GUI** — Tkinter dengan 4 tab: Analyze, Scan, Watch, Positions
- **Scanner** — Scan top pairs by volume dengan color coding
- **Watch Mode** — Auto-analyze dengan interval yang di-align ke clock marks
- **Positions** — Open positions + riwayat posisi tertutup (agregasi `userTrades`, LONG & SHORT)

## Teknologi

- Python 3.11+
- DeepSeek API (reasoning engine)
- Binance Futures API
- SQLite (storage)
- Tkinter (GUI)

## Setup

1. Clone repository
```bash
git clone https://github.com/aracode-labs/agentic-binance.git
cd agentic-binance
```

2. Buat virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Konfigurasi API keys
```bash
cp .env.example .env
# Edit .env dengan API keys Anda
```

5. Jalankan
```bash
python gui.py      # GUI
python app.py      # CLI
python scanner.py  # Scanner
```

6. Jalankan test
```bash
venv\Scripts\python.exe -m unittest discover -s tests
```

## Struktur Project

```
agentic_binance/
├── gui.py                  # GUI (Tkinter) — 4 tabs
├── app.py                  # CLI entry point
├── scanner.py              # Market scanner
├── config/
│   └── settings.py         # Konfigurasi dari .env
├── tools/
│   ├── binance_tool.py     # Binance Futures API
│   ├── deepseek_tool.py    # DeepSeek LLM
│   ├── storage.py          # SQLite storage
│   ├── cache.py            # TTL cache untuk klines
│   └── position_history.py # Trade aggregation
├── agents/
│   └── market_agent.py     # Market analysis agent
├── engines/
│   ├── indicators.py       # SMA, EMA, RSI, MACD, Bollinger, ATR
│   ├── market_structure.py # Swing, BOS/CHoCH, S/R, breakout
│   ├── snapshot.py         # Snapshot multi-timeframe + format prompt
│   └── decision_engine.py  # Rule engine (veto bias AI)
├── models/
│   ├── market_analysis.py  # Analysis schema
│   ├── market_decision.py  # Decision schema
│   └── market_snapshot.py  # Snapshot contract
├── tests/                  # unittest (indikator, struktur, snapshot, cache)
├── rules/
│   ├── trend_rule.py       # Trend detection
│   ├── momentum_rule.py    # Momentum detection
│   └── volatility_rule.py  # Volatility detection
├── prompts/
│   └── market_prompt.md    # DeepSeek prompt template
└── requirements.txt
```

## Konfigurasi (.env)

```env
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
DEEPSEEK_API_KEY=your_deepseek_key
USE_TESTNET=false
```

## GUI Tabs

| Tab | Fungsi |
|-----|--------|
| **Analyze** | Analisa single pair dengan DeepSeek + market data |
| **Scan** | Scan top pairs by volume, color coded (LONG/SHORT/WAIT) |
| **Watch** | Auto-analyze dengan interval, simpan ke SQLite |
| **Positions** | Open positions + closed position history |

## Output Analysis

```
Market Bias    : BULLISH
Momentum       : STRONG
Risk           : LOW
Trade Bias     : LONG
Action         : LOOK FOR LONG
Confidence     : MEDIUM
Reason         : Price above EMA with rising volume...
```

## License

MIT