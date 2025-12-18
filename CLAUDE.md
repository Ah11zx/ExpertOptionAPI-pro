# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

ExpertOptionAPI-pro is a production-ready algorithmic trading bot framework for ExpertOption binary options platform. The codebase provides three distinct bot implementations with different trading strategies, all built on a custom async WebSocket API wrapper.

## Bot Entry Points

### 1. `telegram_bot.py` - Professional Dual-Mode Trading Bot
**Run:** `python telegram_bot.py`

**Modes:**
- `AUTO`: Intelligent asset selection with dynamic scoring (profit % + crypto preference bonuses)
- `MANUAL`: User-specified asset trading via `/trade <asset_id>`

**Telegram Commands:**
- `/run` - Start auto trading mode
- `/stop` - Stop all trading
- `/list` - Show top profitable assets
- `/trade <ID>` - Switch to manual mode for specific asset
- `/auto` - Return to auto mode
- `/balance` - Check current balance

**Key Features:**
- RSI-based signals: oversold < 25 = BUY, overbought > 75 = SELL
- Asset filtering blocks risky instruments (OTC, SMARTY, INDEX markets)
- Data Watchdog: Rotates assets if no candle data received for 40+ seconds
- Real-time P&L tracking and balance updates

### 2. `analyst_bot.py` - Advanced Technical Analysis Bot
**Run:** `python analyst_bot.py`

**Strategy:** Multi-indicator scoring system
- RSI (14-period, overbought 70, oversold 30)
- Bollinger Bands (20-period, 2.0 std dev)
- SuperTrend (10-period, 3.0 multiplier)

**Signal Logic:**
- Scoring: +2 RSI oversold, -2 overbought, +1 BB touch, +1 bullish trend
- STRONG BUY (≥3), BUY (≥1), SELL (≤-1), STRONG SELL (≤-3)
- Only sends Telegram alerts on STRONG signals

**Telegram Commands:**
- `/analyze` - Start market analysis
- `/stop` - Stop analysis

### 3. `run_bot.py` - Simple Baseline Bot
**Run:** `python run_bot.py`

Basic RSI indicator with 3-tier asset fallback (EUR/USD → Crypto IDX → any active). Clean terminal output, 5-second update intervals.

### 4. `ex.py` - API Connectivity Test
**Run:** `python ex.py`

Minimal example: connect → fetch balance → disconnect. Use for testing API credentials.

## Configuration

**Required `.env` file:**
```
TELEGRAM_TOKEN=<bot_token_from_@BotFather>
ALLOWED_USER_ID=<numeric_telegram_user_id>
EXPERT_TOKEN=<expert_option_api_token>
```

**Security:**
- Only `ALLOWED_USER_ID` can execute Telegram commands
- Demo/Real mode toggled via `demo=True/False` parameter in API initialization
- **Warning:** `run_bot.py:14` contains hardcoded test token - replace before production use

## API Architecture

### Core Class: `Expert.api.ExpertOptionAPI`

**Initialization:**
```python
api = ExpertOptionAPI(
    token="your_token",
    demo=True,  # True for demo account, False for real money
    server_region="wss://fr24g1us.expertoption.finance/ws/v40"
)
await api.connect()
```

**Key Methods:**

| Method | Purpose | Typical Timeout |
|--------|---------|-----------------|
| `connect()` | WebSocket handshake, fetch assets/profile | 8-10 seconds |
| `place_order(asset_id, amount, direction)` | Execute trade ("call" or "put") | 20 seconds |
| `get_candles(asset_id, timeframes)` | Subscribe to real-time candle updates | 30 seconds |
| `get_historical_candles(asset_id, periods)` | Fetch past data for analysis | 30 seconds |
| `check_order_status(order_id)` | Poll trade result (status, profit) | 20 seconds |
| `get_balance()` | Current account balance | Instant (cached) |

**Data Structures:**
- `api.active_assets`: `Dict[int, {id, name, profit, is_active, rates: [{expirations}]}]`
- `api.candle_cache`: `Dict[int, {candles: [OHLC arrays]}]`
- `api.order_cache`: `Dict[int, Order{status, profit, exp_time}]`
- `api.profile`: `Profile{balance, demo_balance, user_id, nickname}`

### WebSocket Message Flow
1. Connect with custom headers (Origin, User-Agent)
2. Send 3x `multipleAction` bundles (auth, profile, assets, timezone, history, tournaments)
3. Wait for assets list (max 10s with 200ms polling)
4. Spawn persistent `_auto_ping()` task (15-second keep-alive)
5. Route incoming messages to action-specific `asyncio.Queue` objects
6. Channels format/send typed payloads, wait for responses with configurable timeout

**Channel System** (`Expert/ws/channels/`):
- `BaseChannel` - Abstract base with `send()` and `call()` methods
- `AuthChannel` - Authentication handshake
- `CandlesChannel` - Real-time OHLC subscription
- `BuyChannel` - Order placement and confirmation
- `HistoryChannel` - Historical data fetching
- `PingChannel` - Connection keep-alive (15s intervals)
- `TradersChoiceChannel` - Sentiment indicator

## Asset Selection Patterns

**Available Asset Types:**
- Forex: EURUSD, GBPUSD, USDJPY, USDCAD (24 pairs)
- Crypto: BTCUSD, ETHUSD, BTCLTC, BCHUSD (8 assets)
- Commodities: GOLD, SILVER, COPPER, OILBRENT (5 assets)
- Indices: SP500, QQQ, RUSSELL2000 (20+ ETFs)
- Stocks: META, GOOGL, AAPL, MSFT, TSLA, NFLX (80+ stocks)

**Filtering Logic (telegram_bot.py):**
```python
# Blocks risky instruments that cause "zero candles" or disconnects
filtered_assets = [
    asset for asset in api.active_assets.values()
    if asset.get('is_active', False)
    and 'otc' not in asset['name'].lower()
    and 'smarty' not in asset['name'].lower()
    and 'index' not in asset['name'].lower()
]

# Preference scoring for AUTO mode
score = asset['profit']  # Base score = profit percentage
if 'bitcoin' in name: score += 50
if 'ethereum' in name: score += 40
if 'eur/usd' in name: score += 20
```

**3-Tier Fallback Strategy:**
1. Preferred: Bitcoin / EUR-USD
2. Fallback: Any active asset with profit > 70%
3. Last resort: Any active asset

## Error Handling & Resilience

**Connection Retry:**
- 3 attempts with 3-second delays between retries
- Graceful degradation: switches to alternative asset on repeated failures
- Catches `asyncio.TimeoutError` and generic `Exception`

**Data Watchdog Pattern (telegram_bot.py):**
```python
if time.time() - last_candle_time > 40:
    print("⚠️ Asset has no data. Rotating...")
    # Trigger asset re-selection logic
```

**Custom Exceptions (Expert/exceptions.py):**
- `ConnectionError` - WebSocket connection failed
- `InvalidAssetError` - Asset ID not in active list
- `InvalidExpirationTimeError` - Expiration time in past
- `OrderPlacementError` - Trade execution failed
- `DataFetchError` - Candle/profile fetch timeout

## State Management

**Global State Pattern:**
```python
GLOBAL_STATE = {
    "running": Bool,           # Trading loop active
    "mode": "AUTO|MANUAL",     # Strategy selection
    "target_id": Asset ID,     # Manual mode asset
    "current_asset_name": Str, # Display name
    "api": ExpertOptionAPI     # Shared API instance
}
```

**Task Management:**
- Each bot instance spawns via `asyncio.create_task()` from Telegram command handler
- Telegram polling loop runs in main thread
- Trading loops run in background tasks with shared `GLOBAL_STATE` dict
- State updates are simple assignments (no race conditions/locks needed)

## Indicators & Technical Analysis

**Built-in Indicators (Expert/indicators.py):**

1. **RSIIndicator:**
   ```python
   rsi = RSIIndicator(historical_candles, period=14)
   condition = rsi.evaluate_market_condition()  # "Overbought", "Oversold", "Neutral"
   ```

2. **AlligatorIndicator:**
   ```python
   alligator = AlligatorIndicator(historical_candles)
   trend = await alligator.evaluate_market_trend(api, asset_id)  # "Bullish", "Bearish"
   ```

**pandas-ta Integration (analyst_bot.py):**
```python
import pandas_ta as ta

df['RSI'] = df.ta.rsi(length=14)
bb = df.ta.bbands(length=20, std=2.0)  # Bollinger Bands
st = df.ta.supertrend(length=10, multiplier=3.0)  # SuperTrend
```

## Trading Loop Pattern

Standard flow for all bots:

1. **Connection Phase**: Initialize API, fetch assets/profile (8-10s startup)
2. **Asset Selection**: AUTO mode scoring or MANUAL mode target_id
3. **Data Subscription**: `await api.get_candles(asset_id, 60)`
4. **Watchdog Phase**: Poll `candle_cache`, rotate asset if timeout > 40s
5. **Analysis Phase**: Calculate indicators (RSI, BB, SuperTrend)
6. **Signal Phase**: If signal triggered, execute trade
7. **Result Phase**: Wait 60-62s, check order status, update balance
8. **Loop**: Repeat from step 3

## Logging Configuration

**Setup:**
```python
logging.basicConfig(format='%(asctime)s | %(message)s', level=logging.INFO)
for lib in ["Expert", "urllib3", "websockets"]:
    logging.getLogger(lib).setLevel(logging.WARNING)
```

**Levels:**
- INFO: Connection status, trades executed, asset selections
- WARNING: External libraries (avoid spam)
- DEBUG: Raw payload inspection (toggle in `Expert/api.py`)

## Common Development Tasks

### Testing API Connection
```bash
python ex.py
# Should print balance and disconnect cleanly
```

### Running a Bot in Demo Mode
```bash
# Edit .env to set EXPERT_TOKEN
python telegram_bot.py  # Then send /run in Telegram
```

### Debugging Candle Data Issues
```python
# In bot code, after api.connect():
await asyncio.sleep(5)  # Give time for candle cache to populate
print(f"Cached assets: {list(api.candle_cache.keys())}")
print(f"Candles for asset 240: {api.candle_cache.get(240, {}).get('candles', [])}")
```

### Adding a New Indicator
1. Create class in `Expert/indicators.py` inheriting from a base pattern
2. Implement calculation logic using numpy/pandas
3. Import in bot file and call with historical candles
4. Integrate signal into scoring logic (e.g., `score += 1` for bullish)

### Modifying Signal Thresholds
**RSI:**
- telegram_bot.py:84-85 - Change `< 25` or `> 75`
- analyst_bot.py:14-15 - Change `RSI_OVERSOLD` and `RSI_OVERBOUGHT`

**Bollinger Bands:**
- analyst_bot.py:16-17 - Adjust `BB_LENGTH` (periods) and `BB_STD` (standard deviations)

## Known Issues & Workarounds

**Issue: "No candles received for asset X"**
- Cause: OTC markets have irregular data, or asset is temporarily inactive
- Fix: Bot automatically rotates to next best asset (Data Watchdog)

**Issue: `TimeoutError` on `api.get_candles()`**
- Cause: Server overload or network latency
- Fix: Retry mechanism implemented in analyst_bot.py:178-223 (3 retries, 3s delay)

**Issue: "Only 1 user can control the bot"**
- Cause: `ALLOWED_USER_ID` check in command handlers
- Fix: Add multiple user IDs by converting to a list and checking `if user_id in ALLOWED_USERS`

**Issue: Hardcoded token in run_bot.py**
- Security risk if committed to public repo
- Fix: Move to `.env` file and use `os.getenv("EXPERT_TOKEN")`

## Architecture Insights

**Why async/await everywhere?**
- WebSocket communication is inherently async (long-lived connections)
- Telegram bot polling is async (python-telegram-bot v20+)
- Multiple concurrent tasks: ping keep-alive, candle updates, order monitoring

**Why separate bots instead of one unified bot?**
- Different strategies require different dependencies (pandas-ta heavy for analyst_bot)
- Easier to test/debug isolated strategies
- Users can run multiple bots simultaneously on different assets

**Why candle_cache instead of database?**
- Real-time trading needs sub-second access (in-memory faster than DB)
- Candles arrive as WebSocket messages and are appended to arrays
- Historical data can be fetched separately via `get_historical_candles()`

**Why GLOBAL_STATE dict instead of class attributes?**
- Telegram command handlers are async functions (not class methods)
- asyncio.create_task() spawns detached coroutines that need shared state
- Python's GIL makes simple dict updates safe without locks
