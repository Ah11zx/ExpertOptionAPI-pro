# Telegram Bot Testing Guide

## ✅ Bot Status: RUNNING

**Process ID:** 46065
**Status:** Active and polling for messages
**Log File:** `/tmp/telegram_bot.log`

---

## 🤖 Bot Information

**Bot Name:** Your ExpertOption Trading Bot
**Authorized User ID:** 1158674572
**Mode:** Demo Trading
**Server:** wss://fr24g1us.expertoption.finance/ws/v40

---

## 📱 How to Test the Bot

### Step 1: Find Your Bot on Telegram
1. Open Telegram app on your phone/computer
2. Search for your bot (using the bot username from @BotFather)
3. Start a chat with the bot

### Step 2: Test Commands in This Order

#### 1. **Start Command** - Get the menu
```
/start
```
**Expected Response:**
```
🤖 **Professional Bot Control**

▶️ /run - تشغيل الوضع التلقائي
🛑 /stop - إيقاف النظام
📜 /list - قائمة أفضل الفرص
🎯 /trade <ID> - تداول يدوي لعملة محددة
🔄 /auto - العودة للوضع التلقائي
💰 /balance - كشف الرصيد
```

#### 2. **Balance Check** - Test API connection (before trading)
```
/balance
```
**Expected Response:**
```
💰 الرصيد الحالي: $9903.14
```
or
```
⚠️ البوت غير متصل. اضغط /run أولاً.
```

#### 3. **Run Command** - Start auto trading mode
```
/run
```
**Expected Response:**
```
🚀 تم تشغيل المحرك (الوضع التلقائي)...
```

**Then within 10-15 seconds:**
```
🎯 Tracking: <Asset Name> (AUTO)
💰 Profit: XX%
🚀 Engine Started.
```

#### 4. **List Command** - View available assets
```
/list
```
**Expected Response:**
```
📊 **أفضل الأصول المتاحة حالياً:**
🆔 142 : EUR / USD (43%)
🆔 462 : BNB / USD (50%)
🆔 463 : DOGE / USD (52%)
...
للتداول اليدوي: /trade ID
```

#### 5. **Manual Trade** - Switch to specific asset
```
/trade 142
```
**Expected Response:**
```
🎯 تم التحويل للوضع اليدوي. الهدف: 142
```

**Then:**
```
🎯 Tracking: EUR / USD (MANUAL)
💰 Profit: 43%
🚀 Engine Started.
```

#### 6. **Auto Mode** - Return to automatic mode
```
/auto
```
**Expected Response:**
```
🔄 تم تفعيل الوضع التلقائي الذكي.
```

#### 7. **Stop Command** - Stop trading
```
/stop
```
**Expected Response:**
```
🛑 تم إرسال إشارة التوقف.
```

---

## 🎯 Trading Signal Test

When the bot detects a trading opportunity, you'll see:

```
⚡ Signal Detected!
Asset: EUR / USD
Action: 🟢 BUY (Call)  or  🔴 SELL (Put)
RSI: 23.45
```

**Then:**
```
✅ Order #123456 Placed. Waiting 60s...
```

**After 60 seconds:**
```
🏆 WIN (+$85.50)
💰 Balance: $9988.64
```
or
```
❌ LOSS (-$50.00)
💰 Balance: $9853.14
```

---

## 🔍 Expected Bot Behavior

### AUTO Mode Logic:
1. **Asset Selection:**
   - Filters out: OTC, SMARTY, INDEX assets
   - Requires: Profit ≥ 70%
   - Scoring:
     - Bitcoin: +50 bonus
     - Ethereum: +40 bonus
     - EUR/USD: +20 bonus

2. **Trading Signals:**
   - **BUY (Call):** RSI < 25 (oversold)
   - **SELL (Put):** RSI > 75 (overbought)

3. **Data Watchdog:**
   - If no candle data for 40+ seconds → Rotate to different asset
   - Auto-reconnect on connection failures

### MANUAL Mode:
- Trades only the specified asset ID
- Uses same RSI signals (< 25 or > 75)
- Falls back to AUTO if asset becomes unavailable

---

## 🛡️ Safety Features

1. **Authorization:** Only user ID `1158674572` can control the bot
2. **Demo Mode:** All trades use demo balance ($9,903.14)
3. **Asset Filtering:** Blocks risky OTC/SMARTY instruments
4. **Auto-Recovery:** Reconnects automatically on connection loss
5. **Data Validation:** Skips trades if insufficient candle data

---

## 📊 Monitoring Commands

### Check if bot is running:
```bash
ps aux | grep telegram_bot.py | grep -v grep
```

### View real-time logs:
```bash
tail -f /tmp/telegram_bot.log
```

### Stop the bot:
```bash
pkill -f telegram_bot.py
```

### Restart the bot:
```bash
cd /home/ubuntu/ExpertOptionAPI-pro
source env/bin/activate
python3 telegram_bot.py > /tmp/telegram_bot.log 2>&1 &
```

---

## 🧪 Test Scenarios

### Scenario 1: Quick Test (No Trading)
```
/start    → Get menu
/balance  → Check balance
/list     → View assets
/stop     → Done
```
**Time:** ~30 seconds

### Scenario 2: AUTO Mode Test
```
/run      → Start auto mode
<wait 5 minutes for signal>
/balance  → Check balance
/stop     → Stop trading
```
**Time:** 5-10 minutes

### Scenario 3: MANUAL Mode Test
```
/list     → Get asset ID (e.g., 142)
/trade 142 → Start manual trading EUR/USD
<wait for signal>
/auto     → Switch back to auto
/stop     → Stop
```
**Time:** 5-10 minutes

### Scenario 4: Full Trading Test
```
/run      → Start bot
<wait for trade execution ~60-90 seconds>
/balance  → Verify P&L updated
/stop     → Stop bot
```
**Time:** 2-3 minutes

---

## ⚠️ Troubleshooting

### Bot not responding:
1. Check if bot is running: `ps aux | grep telegram_bot`
2. Check logs: `tail -50 /tmp/telegram_bot.log`
3. Verify your user ID matches: `1158674572`
4. Restart bot if needed

### "البوت غير متصل" message:
- Bot needs to connect to ExpertOption first
- Send `/run` to initialize connection
- Wait 10-15 seconds for connection

### No trading signals:
- RSI must be < 25 or > 75 (extreme conditions)
- Markets may be neutral (RSI 30-70)
- Try different assets with `/trade <ID>`

### Connection errors:
- Check internet connection
- Verify EXPERT_TOKEN in .env is valid
- Check ExpertOption server status

---

## 📈 Success Criteria

✅ Bot responds to all commands
✅ Balance retrieval works
✅ Asset list displays correctly
✅ AUTO mode connects and selects asset
✅ MANUAL mode switches to specified asset
✅ Trading signals are detected
✅ Orders are placed successfully
✅ P&L is tracked correctly
✅ Bot auto-recovers from errors

---

## 🔐 Security Reminders

- Only user ID `1158674572` can use the bot
- All trades use DEMO balance (no real money)
- API tokens stored securely in `.env`
- Bot logs saved to `/tmp/telegram_bot.log`

---

**Test Start Time:** 2025-12-18 21:03 UTC
**Bot PID:** 46065
**Status:** ✅ ACTIVE AND READY FOR TESTING
