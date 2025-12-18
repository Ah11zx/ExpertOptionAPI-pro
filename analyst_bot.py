import asyncio
import logging
import os
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from Expert.api import ExpertOptionAPI

# ================= إعدادات التحليل =================
# يمكنك تعديل هذه الأرقام حسب استراتيجيتك
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
BB_LENGTH = 20
BB_STD = 2.0
# =================================================

# تحميل التوكنات
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
EXPERT_TOKEN = os.getenv("EXPERT_TOKEN")
SERVER_REGION = "wss://fr24g1us.expertoption.finance/ws/v40"

# إعداد السجلات (نظيف)
logging.basicConfig(format='%(asctime)s | %(message)s', level=logging.INFO)
for lib in ["Expert", "urllib3", "websockets"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

GLOBAL_STATE = {"running": False, "target_id": None, "api": None}

# ================= دالة التحليل الاحترافي (المحرك) =================
def analyze_market_data(candles):
    """
    تحويل البيانات الخام إلى توصيات باستخدام pandas-ta
    """
    if not candles or len(candles) < 50:
        return None, "Not enough data"

    # 1. تحويل البيانات إلى DataFrame (جدول)
    # ExpertOption returns candles as objects or dicts
    data = []
    for c in candles:
        # استخراج السعر بمرونة
        close = c.get('close') if isinstance(c, dict) else getattr(c, 'close', 0)
        high = c.get('high') if isinstance(c, dict) else getattr(c, 'high', 0)
        low = c.get('low') if isinstance(c, dict) else getattr(c, 'low', 0)
        
        if close > 0:
            data.append({"close": float(close), "high": float(high), "low": float(low)})

    df = pd.DataFrame(data)

    # 2. حساب المؤشرات (Indicators)
    # RSI
    df['RSI'] = df.ta.rsi(length=RSI_PERIOD)
    
    # Bollinger Bands
    bb = df.ta.bbands(length=BB_LENGTH, std=BB_STD)
    df = pd.concat([df, bb], axis=1) # دمج النتائج
    
    # SuperTrend (مؤشر الاتجاه القوي)
    st = df.ta.supertrend(length=10, multiplier=3.0)
    df = pd.concat([df, st], axis=1)

    # 3. اتخاذ القرار (المنطق)
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    # أسماء الأعمدة الديناميكية في pandas-ta
    bb_lower = last_row[f'BBL_{BB_LENGTH}_{BB_STD}']
    bb_upper = last_row[f'BBU_{BB_LENGTH}_{BB_STD}']
    st_dir = last_row[f'SUPERTd_10_3.0'] # 1 = Up, -1 = Down

    score = 0
    signals = []

    # تحليل RSI
    if last_row['RSI'] < RSI_OVERSOLD:
        score += 2
        signals.append(f"🔵 RSI Oversold ({last_row['RSI']:.1f})")
    elif last_row['RSI'] > RSI_OVERBOUGHT:
        score -= 2
        signals.append(f"🔴 RSI Overbought ({last_row['RSI']:.1f})")
    else:
        signals.append(f"⚪ RSI Neutral ({last_row['RSI']:.1f})")

    # تحليل Bollinger
    if last_row['close'] <= bb_lower:
        score += 1
        signals.append("🔵 Price touched Lower Band")
    elif last_row['close'] >= bb_upper:
        score -= 1
        signals.append("🔴 Price touched Upper Band")

    # تحليل الاتجاه (SuperTrend)
    if st_dir == 1:
        score += 1
        signals.append("📈 Trend: Bullish (Up)")
    else:
        score -= 1
        signals.append("📉 Trend: Bearish (Down)")

    # النتيجة النهائية
    recommendation = "WAIT ✋"
    color = "⚪"
    
    if score >= 3:
        recommendation = "STRONG BUY 🟢"
        color = "🟢"
    elif score >= 1:
        recommendation = "BUY (Weak) 🍏"
        color = "🍏"
    elif score <= -3:
        recommendation = "STRONG SELL 🔴"
        color = "🔴"
    elif score <= -1:
        recommendation = "SELL (Weak) 🍎"
        color = "🍎"

    report = f"{color} **{recommendation}**\n" + "\n".join([f"- {s}" for s in signals])
    return recommendation, report

# ================= منطق البوت =================
async def analysis_loop(bot, chat_id):
    GLOBAL_STATE["running"] = True
    api = None
    
    try:
        # الاتصال
        api = ExpertOptionAPI(token=EXPERT_TOKEN, demo=True, server_region=SERVER_REGION)
        await api.connect()
        GLOBAL_STATE["api"] = api
        await asyncio.sleep(2)

        # اختيار أصل يدوي أو تلقائي (سنركز على Bitcoin كمثال للتحليل)
        # يمكنك تغيير هذا لاحقاً ليكون ديناميكياً
        target_asset = None

        # البحث عن Bitcoin أو اليورو دولار
        for aid, data in api.active_assets.items():
            name_lower = data.get('name', '').lower()
            if data.get('is_active', False):
                if 'bitcoin' in name_lower or 'eur/usd' in name_lower or 'eurusd' in name_lower:
                    target_asset = {'id': aid, 'name': data['name']}
                    print(f"✅ Found preferred asset: {data['name']}")
                    break

        # FALLBACK 1: If Bitcoin/EURUSD not found, use ANY active asset with profit > 70%
        if not target_asset:
            print("⚠️ Preferred asset not found. Searching for fallback (profit > 70%)...")
            for aid, data in api.active_assets.items():
                if data.get('is_active', False) and data.get('profit', 0) > 70:
                    target_asset = {'id': aid, 'name': data['name']}
                    print(f"✅ Using fallback asset: {data['name']} (Profit: {data['profit']}%)")
                    break

        # FALLBACK 2: If still None, use ANY active asset regardless of profit
        if not target_asset:
            print("⚠️ No high-profit assets found. Using any active asset...")
            for aid, data in api.active_assets.items():
                if data.get('is_active', False):
                    target_asset = {'id': aid, 'name': data['name']}
                    print(f"✅ Using any available asset: {data['name']}")
                    break

        # FAIL-SAFE: If target_asset is STILL None, stop gracefully
        if not target_asset:
            error_msg = "❌ No active assets found! Cannot start analysis."
            print(error_msg)
            await bot.send_message(chat_id, error_msg)
            return

        await bot.send_message(chat_id, f"🔬 **Analyst Mode Activated**\nTarget: {target_asset['name']}\nCollecting data for analysis...")

        # اشتراك مع آلية إعادة المحاولة
        max_retries = 3
        candles_fetched = False

        for attempt in range(1, max_retries + 1):
            try:
                await api.get_candles(target_asset['id'], 60)
                candles_fetched = True
                break  # نجحت العملية، نخرج من الحلقة
            except (asyncio.TimeoutError, Exception) as e:
                if attempt < max_retries:
                    print(f"⚠️ Data timeout. Retrying (Attempt {attempt}/{max_retries})...")
                    await asyncio.sleep(3)
                else:
                    print("❌ Failed to get data for this asset. Switching...")
                    # محاولة إيجاد أصل بديل
                    old_asset_id = target_asset['id']
                    target_asset = None

                    for aid, data in api.active_assets.items():
                        if aid != old_asset_id and data.get('is_active', False):
                            target_asset = {'id': aid, 'name': data['name']}
                            print(f"✅ Switching to new asset: {data['name']}")
                            await bot.send_message(chat_id, f"🔄 Switched to: {target_asset['name']}")
                            break

                    # إذا لم نجد أصل بديل، نوقف التحليل
                    if not target_asset:
                        error_msg = "❌ No alternative assets available. Stopping analysis."
                        print(error_msg)
                        await bot.send_message(chat_id, error_msg)
                        return

                    # محاولة جلب البيانات للأصل الجديد
                    try:
                        await api.get_candles(target_asset['id'], 60)
                        candles_fetched = True
                        break
                    except:
                        print("❌ Failed to get data for alternative asset as well.")
                        await bot.send_message(chat_id, "❌ Unable to fetch data. Please try again later.")
                        return

        if not candles_fetched:
            await bot.send_message(chat_id, "❌ Could not fetch data after retries.")
            return

        last_recommendation = ""
        
        while GLOBAL_STATE["running"]:
            candles = api.candle_cache.get(target_asset['id'], [])
            
            # نحتاج بيانات كافية للمؤشرات
            if len(candles) > 30:
                rec, report = analyze_market_data(candles)
                
                # طباعة في التيرمينال للمراقبة
                print(f"\r📊 Analysis: {rec} | Candles: {len(candles)}", end="", flush=True)

                # إرسال تنبيه فقط إذا تغيرت التوصية لقوية
                # أو يمكنك إرسال تقرير كل دقيقة
                if "STRONG" in rec and rec != last_recommendation:
                    await bot.send_message(chat_id, f"🚨 **SIGNAL DETECTED**\nAsset: {target_asset['name']}\n\n{report}")
                    last_recommendation = rec
                    await asyncio.sleep(60) # انتظار دقيقة قبل التنبيه التالي لمنع الإزعاج
            else:
                 print(f"\r⏳ Collecting data... ({len(candles)}/50)", end="", flush=True)

            await asyncio.sleep(1)

    except Exception as e:
        print(f"\nError: {e}")
        await bot.send_message(chat_id, "⚠️ Analysis stopped due to error.")
    finally:
        if api: await api.disconnect()

# ================= أوامر تيليجرام =================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to Expert Analyst Bot.\nUse `/analyze` to start watching the market.")

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if GLOBAL_STATE["running"]:
        await update.message.reply_text("Analyst is already working! 🔬")
        return
    asyncio.create_task(analysis_loop(context.bot, update.effective_chat.id))

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    GLOBAL_STATE["running"] = False
    await update.message.reply_text("🛑 Analyst stopped.")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        print("Error: .env file not loaded!")
        exit()
        
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    
    print("🔬 Analyst Bot is Ready...")
    app.run_polling()
