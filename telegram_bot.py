import asyncio
import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from Expert.api import ExpertOptionAPI

# ================= SECURITY & CONFIG =================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
EXPERT_TOKEN = os.getenv("EXPERT_TOKEN")
SERVER_REGION = "wss://fr24g1us.expertoption.finance/ws/v40"

if not TELEGRAM_TOKEN or not EXPERT_TOKEN:
    print("❌ ERROR: Tokens missing in .env file")
    exit(1)

# إعدادات السجلات
logging.basicConfig(format='%(asctime)s | %(message)s', level=logging.INFO)
for lib in ["Expert", "urllib3", "websockets"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

# متغيرات التحكم العالمية
GLOBAL_STATE = {
    "running": False,
    "mode": "AUTO",       # AUTO or MANUAL
    "target_id": None,    # ID of manually selected asset
    "api": None           # Holds the active API connection
}

# ================= HELPER FUNCTIONS =================
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

# ================= TRADING LOGIC =================
async def trading_logic(bot, chat_id):
    GLOBAL_STATE["running"] = True
    
    while GLOBAL_STATE["running"]:
        api = None
        try:
            # 1. الاتصال
            if not GLOBAL_STATE["api"]:
                api = ExpertOptionAPI(token=EXPERT_TOKEN, demo=True, server_region=SERVER_REGION)
                await api.connect()
                GLOBAL_STATE["api"] = api
                await asyncio.sleep(2)
            else:
                api = GLOBAL_STATE["api"]

            # 2. اختيار الأصل (تلقائي أو يدوي)
            best_asset = None
            
            if GLOBAL_STATE["mode"] == "MANUAL" and GLOBAL_STATE["target_id"]:
                # الوضع اليدوي
                raw_asset = api.active_assets.get(GLOBAL_STATE["target_id"])
                if raw_asset:
                    best_asset = {'id': raw_asset['id'], 'name': raw_asset['name'], 'profit': raw_asset['profit']}
                else:
                    await bot.send_message(chat_id, "⚠️ Asset ID not found or inactive. Switching to AUTO.")
                    GLOBAL_STATE["mode"] = "AUTO"
            
            if GLOBAL_STATE["mode"] == "AUTO":
                # الوضع التلقائي (خوارزمية الفلترة)
                assets = api.active_assets
                max_profit = 0
                for aid, data in assets.items():
                    if data['is_active'] == 0: continue
                    name = data['name'].lower()
                    profit = data['profit']
                    
                    if 'smarty' in name or 'otc' in name or 'index' in name: continue
                    if profit < 70: continue

                    score = profit
                    if 'bitcoin' in name: score += 50
                    elif 'ethereum' in name: score += 40
                    elif 'eur' in name or 'usd' in name: score += 20
                    
                    if score > max_profit:
                        max_profit = score
                        best_asset = {'id': aid, 'name': data['name'], 'profit': profit}

            if not best_asset:
                print("⏳ No assets found, retrying...")
                await asyncio.sleep(5)
                continue

            # إرسال رسالة الهدف (مرة واحدة فقط عند تغيير الهدف)
            # (يمكن تخزين آخر أصل لتجنب التكرار، لكن للتبسيط سنتركها)
            status_msg = f"🎯 Tracking: {best_asset['name']} ({GLOBAL_STATE['mode']})\n💰 Profit: {best_asset['profit']}%\n⏳ Waiting for data..."
            await bot.send_message(chat_id, status_msg)
            
            # 3. الاشتراك في البيانات
            try: await api.get_candles(best_asset['id'], 60)
            except: pass

            # 4. حلقة التحليل (The Analysis Loop)
            # زدنا الصبر هنا لمعالجة مشكلتك
            empty_count = 0
            
            while GLOBAL_STATE["running"]:
                # إذا تغير المود فجأة، نكسر الحلقة لإعادة الاختيار
                if GLOBAL_STATE["mode"] == "MANUAL" and best_asset['id'] != GLOBAL_STATE["target_id"]:
                    break

                candles = api.candle_cache.get(best_asset['id'], [])
                prices = []
                for c in candles:
                    p = c.get('close') if isinstance(c, dict) else getattr(c, 'close', 0)
                    if p: prices.append(float(p))
                
                # --- إصلاح مشكلة البيانات ---
                if len(prices) == 0:
                    empty_count += 1
                    print(f"\r⏳ Waiting data ({empty_count}/30)...", end="", flush=True)
                    
                    # إعادة طلب الاشتراك كل 10 ثواني للتنشيط
                    if empty_count % 10 == 0:
                        try: await api.get_candles(best_asset['id'], 60)
                        except: pass
                        
                    # إذا انتظرنا 30 ثانية ولم يحدث شيء، نغير العملة
                    if empty_count > 30:
                        await bot.send_message(chat_id, "⚠️ No data received. Rotating asset...")
                        break 
                    
                    await asyncio.sleep(1)
                    continue
                else:
                    empty_count = 0 # تصفير العداد عند وصول بيانات

                # التحليل
                last_price = prices[-1]
                rsi_val = calculate_rsi(prices) if len(prices) >= 14 else 50
                
                # طباعة للمراقبة (اختياري)
                # print(f"\r📊 {best_asset['name']} | RSI: {rsi_val:.2f}", end="", flush=True)

                direction = None
                if rsi_val < 25: direction = 'call'
                elif rsi_val > 75: direction = 'put'
                
                if direction:
                    txt = "🟢 BUY (Call)" if direction == 'call' else "🔴 SELL (Put)"
                    await bot.send_message(chat_id, f"⚡ Signal on {best_asset['name']}\nAction: {txt}\nRSI: {rsi_val:.2f}")
                    
                    try:
                        # جلب الرصيد قبل الصفقة
                        bal_before = 0
                        if hasattr(api.profile, 'balance'): bal_before = api.profile.balance
                        elif isinstance(api.profile, dict): bal_before = api.profile.get('balance', 0)

                        # تنفيذ
                        order = await api.place_order(best_asset['id'], 50, direction)
                        await bot.send_message(chat_id, f"✅ Order #{order} Placed. Waiting 60s...")
                        
                        await asyncio.sleep(62)
                        
                        # جلب الرصيد بعد الصفقة
                        bal_after = 0
                        # تحديث البروفايل (قد يتطلب هذا خدعة بسيطة أو الاعتماد على التحديث التلقائي)
                        if hasattr(api.profile, 'balance'): bal_after = api.profile.balance
                        elif isinstance(api.profile, dict): bal_after = api.profile.get('balance', 0)

                        diff = bal_after - bal_before
                        res_txt = f"💵 Result: ${diff:.2f}"
                        if diff > 0: res_txt = f"🏆 WIN (+${diff:.2f})"
                        elif diff < 0: res_txt = f"❌ LOSS (-${abs(diff):.2f})"
                        
                        await bot.send_message(chat_id, f"{res_txt}\n💰 Balance: ${bal_after}")
                        
                    except Exception as e:
                        await bot.send_message(chat_id, f"⚠️ Execution Failed: {e}")
                
                await asyncio.sleep(1)

        except Exception as e:
            if "Timeout" not in str(e): 
                print(f"Error: {e}")
                await bot.send_message(chat_id, "⚠️ Connection glitch. Reconnecting...")
            
            # تدمير الاتصال القديم لإعادة البناء
            if GLOBAL_STATE["api"]:
                try: await GLOBAL_STATE["api"].disconnect()
                except: pass
                GLOBAL_STATE["api"] = None
            
            await asyncio.sleep(5)

# ================= COMMAND HANDLERS =================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    menu = (
        "🤖 **Expert Bot Control Panel**\n\n"
        "▶️ `/run` - Start Auto Trading\n"
        "🛑 `/stop` - Stop Trading\n"
        "📜 `/list` - List Best Assets (IDs)\n"
        "🎯 `/trade <ID>` - Force Trade Specific Asset\n"
        "🔄 `/auto` - Switch back to Auto Mode\n"
        "💰 `/balance` - Show Current Balance"
    )
    await update.message.reply_text(menu, parse_mode='Markdown')

async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    if GLOBAL_STATE["running"]:
        await update.message.reply_text("⚠️ Bot is already running!")
        return
    
    GLOBAL_STATE["mode"] = "AUTO"
    await update.message.reply_text("🚀 Starting Engine (Auto Mode)...")
    asyncio.create_task(trading_logic(context.bot, update.effective_chat.id))

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    GLOBAL_STATE["running"] = False
    await update.message.reply_text("🛑 Bot Stopped.")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    api = GLOBAL_STATE["api"]
    if api and api.profile:
        bal = api.profile.balance if hasattr(api.profile, 'balance') else api.profile.get('balance', 'N/A')
        await update.message.reply_text(f"💰 Current Balance: ${bal}")
    else:
        await update.message.reply_text("⚠️ Bot not connected. Run /run first.")

async def list_assets_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    api = GLOBAL_STATE["api"]
    if not api:
        await update.message.reply_text("⚠️ Please run the bot first to fetch assets.")
        return
    
    msg = "📊 **Top Available Assets:**\n"
    # تجميع وفلترة
    valid_assets = []
    for aid, data in api.active_assets.items():
        if data['is_active'] == 1 and data['profit'] > 70:
            name = data['name']
            if 'otc' not in name.lower() and 'smarty' not in name.lower():
                valid_assets.append((aid, name, data['profit']))
    
    # ترتيب حسب الربح
    valid_assets.sort(key=lambda x: x[2], reverse=True)
    
    for item in valid_assets[:15]: # عرض أفضل 15
        msg += f"🆔 `{item[0]}` : {item[1]} ({item[2]}%)\n"
    
    msg += "\nTo trade one, use: `/trade ID`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def trade_manual_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/trade <Asset_ID>`\nUse `/list` to find IDs.")
        return
    
    try:
        target_id = int(context.args[0])
        GLOBAL_STATE["target_id"] = target_id
        GLOBAL_STATE["mode"] = "MANUAL"
        
        # إذا كان البوت لا يعمل، نشغله
        if not GLOBAL_STATE["running"]:
            GLOBAL_STATE["running"] = True
            asyncio.create_task(trading_logic(context.bot, update.effective_chat.id))
            
        await update.message.reply_text(f"🎯 Mode switched to MANUAL. Targeting ID: {target_id}")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Must be a number.")

async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    GLOBAL_STATE["mode"] = "AUTO"
    await update.message.reply_text("🔄 Switched back to AUTO Mode.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("list", list_assets_cmd))
    app.add_handler(CommandHandler("trade", trade_manual_cmd))
    app.add_handler(CommandHandler("auto", auto_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    
    print("🤖 Advanced Bot Listening...")
    app.run_polling()
