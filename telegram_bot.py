import asyncio
import logging
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from Expert.api import ExpertOptionAPI

# ================= 1. SECURITY & CONFIG =================
# تحميل المتغيرات من ملف .env لضمان الأمان
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))
EXPERT_TOKEN = os.getenv("EXPERT_TOKEN")
SERVER_REGION = "wss://fr24g1us.expertoption.finance/ws/v40"

# التحقق من وجود التوكنات
if not TELEGRAM_TOKEN or not EXPERT_TOKEN:
    print("❌ FATAL ERROR: Tokens not found in .env file!")
    sys.exit(1)

# ================= 2. CLEAN LOGGING =================
# ضبط السجلات لإخفاء "الضجيج" وإظهار المهم فقط (توصية التدقيق)
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO
)
# إسكات المكتبات المزعجة
for lib in ["Expert", "urllib3", "websockets", "asyncio"]:
    logging.getLogger(lib).setLevel(logging.WARNING)

# ================= 3. GLOBAL STATE =================
# إدارة حالة البوت للتحكم في الأوضاع (يدوي/تلقائي)
GLOBAL_STATE = {
    "running": False,
    "mode": "AUTO",       # AUTO or MANUAL
    "target_id": None,    # ID للأصل المختار يدوياً
    "current_asset_name": "None",
    "api": None
}

# دالة مساعدة لحساب RSI
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

# التحقق من الصلاحية (الأمان)
def authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

# ================= 4. CORE TRADING ENGINE =================
async def trading_logic(bot, chat_id):
    GLOBAL_STATE["running"] = True
    reconnect_attempts = 0
    
    while GLOBAL_STATE["running"]:
        api = None
        try:
            # --- أ. مرحلة الاتصال ---
            if not GLOBAL_STATE["api"]:
                print("🔄 Connecting to Server...")
                api = ExpertOptionAPI(token=EXPERT_TOKEN, demo=True, server_region=SERVER_REGION)
                await api.connect()
                GLOBAL_STATE["api"] = api
                await asyncio.sleep(3) # انتظار استقرار الاتصال
            else:
                api = GLOBAL_STATE["api"]

            # --- ب. مرحلة اختيار الأصل (Smart Filtering) ---
            best_asset = None
            
            # الوضع اليدوي
            if GLOBAL_STATE["mode"] == "MANUAL" and GLOBAL_STATE["target_id"]:
                raw = api.active_assets.get(GLOBAL_STATE["target_id"])
                if raw and raw['is_active']:
                    best_asset = {'id': raw['id'], 'name': raw['name'], 'profit': raw['profit']}
                else:
                    await bot.send_message(chat_id, "⚠️ الأصل المحدد غير متاح. العودة للوضع التلقائي.")
                    GLOBAL_STATE["mode"] = "AUTO"

            # الوضع التلقائي (الذكاء الاصطناعي)
            if GLOBAL_STATE["mode"] == "AUTO":
                max_score = 0
                for aid, data in api.active_assets.items():
                    if not data['is_active']: continue
                    
                    name = data['name'].lower()
                    profit = data['profit']
                    
                    # 🛡️ الفلترة الصارمة (توصية التدقيق: منع الشموع الصفرية)
                    if 'otc' in name: continue           # خطر جداً - Keep OTC blocked
                    # if 'smarty' in name: continue      # Allow SMARTY (user request)
                    # if 'index' in name: continue       # Allow INDEX (user request)
                    if profit < 70: continue             # ربح ضعيف

                    # نظام النقاط
                    score = profit
                    if 'bitcoin' in name: score += 50
                    elif 'ethereum' in name: score += 40
                    elif 'eur' in name or 'usd' in name: score += 20
                    
                    if score > max_score:
                        max_score = score
                        best_asset = {'id': aid, 'name': data['name'], 'profit': profit}

            if not best_asset:
                print("⚠️ No valid assets found. Retrying in 5s...")
                await asyncio.sleep(5)
                continue

            GLOBAL_STATE["current_asset_name"] = best_asset['name']
            
            # إرسال تنبيه للمستخدم
            msg = f"🎯 Tracking: {best_asset['name']} ({GLOBAL_STATE['mode']})\n💰 Profit: {best_asset['profit']}%\n🚀 Engine Started."
            await bot.send_message(chat_id, msg)
            
            # الاشتراك في البيانات
            try: await api.get_candles(best_asset['id'], 60)
            except: pass

            # --- ج. حلقة التحليل والمراقبة (The Watchdog Loop) ---
            no_data_counter = 0
            
            while GLOBAL_STATE["running"]:
                # كسر الحلقة إذا تغير الوضع اليدوي
                if GLOBAL_STATE["mode"] == "MANUAL" and best_asset['id'] != GLOBAL_STATE["target_id"]:
                    break

                candles = api.candle_cache.get(best_asset['id'], [])
                prices = []
                for c in candles:
                    p = c.get('close') if isinstance(c, dict) else getattr(c, 'close', 0)
                    if p: prices.append(float(p))
                
                # 🛡️ مراقب البيانات (Watchdog) - توصية التدقيق رقم 4
                if len(prices) == 0:
                    no_data_counter += 1
                    print(f"\r⏳ Waiting for data ({no_data_counter}s)...", end="", flush=True)
                    
                    # محاولة تنشيط الاشتراك
                    if no_data_counter % 10 == 0:
                        try: await api.get_candles(best_asset['id'], 60)
                        except: pass
                    
                    # إذا مر 40 ثانية بلا بيانات -> الأصل ميت -> تدوير
                    if no_data_counter > 40:
                        print("\n⚠️ Data Watchdog Triggered: No data! Rotating asset.")
                        await bot.send_message(chat_id, f"⚠️ فقدان البيانات في {best_asset['name']}. جاري البحث عن بديل...")
                        break 
                    
                    await asyncio.sleep(1)
                    continue
                else:
                    no_data_counter = 0 # تصفير العداد

                # تحليل RSI
                rsi = calculate_rsi(prices) if len(prices) >= 14 else 50
                
                # اتخاذ القرار
                direction = None
                if rsi < 25: direction = 'call'  # تشبع بيعي -> شراء
                elif rsi > 75: direction = 'put'   # تشبع شرائي -> بيع
                
                if direction:
                    action_txt = "🟢 BUY (Call)" if direction == 'call' else "🔴 SELL (Put)"
                    await bot.send_message(chat_id, f"⚡ Signal Detected!\nAsset: {best_asset['name']}\nAction: {action_txt}\nRSI: {rsi:.2f}")
                    
                    try:
                        # جلب الرصيد قبل الصفقة
                        profile = api.profile
                        bal_start = profile.balance if hasattr(profile, 'balance') else profile.get('balance', 0)
                        
                        # تنفيذ الصفقة
                        order = await api.place_order(best_asset['id'], 50, direction)
                        await bot.send_message(chat_id, f"✅ Order #{order} Placed. Waiting 60s...")
                        
                        await asyncio.sleep(62) # انتظار نتيجة الصفقة
                        
                        # جلب الرصيد بعد الصفقة وحساب النتيجة
                        bal_end = api.profile.balance if hasattr(api.profile, 'balance') else api.profile.get('balance', 0)
                        diff = bal_end - bal_start
                        
                        result_txt = f"💵 Result: ${diff:.2f}"
                        if diff > 0: result_txt = f"🏆 WIN (+${diff:.2f})"
                        elif diff < 0: result_txt = f"❌ LOSS (-${abs(diff):.2f})"
                        
                        await bot.send_message(chat_id, f"{result_txt}\n💰 Balance: ${bal_end:.2f}")
                        
                    except Exception as e:
                        await bot.send_message(chat_id, f"⚠️ Execution Error: {e}")
                
                await asyncio.sleep(1)

        except Exception as e:
            # 🛡️ معالجة الانهيار وإعادة الاتصال الذاتي
            if "Timeout" not in str(e):
                print(f"\n⚠️ System Error: {e}")
                await bot.send_message(chat_id, "⚠️ خلل في الاتصال، جاري الإصلاح الذاتي...")
            
            # تنظيف الاتصال القديم
            if GLOBAL_STATE["api"]:
                try: await GLOBAL_STATE["api"].disconnect()
                except: pass
                GLOBAL_STATE["api"] = None
            
            await asyncio.sleep(5)
            reconnect_attempts += 1

# ================= 5. TELEGRAM COMMANDS =================

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    menu = (
        "🤖 **Professional Bot Control**\n\n"
        "▶️ `/run` - تشغيل الوضع التلقائي\n"
        "🛑 `/stop` - إيقاف النظام\n"
        "📜 `/list` - قائمة أفضل الفرص\n"
        "🎯 `/trade <ID>` - تداول يدوي لعملة محددة\n"
        "🔄 `/auto` - العودة للوضع التلقائي\n"
        "💰 `/balance` - كشف الرصيد"
    )
    await update.message.reply_text(menu, parse_mode='Markdown')

async def run_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    if GLOBAL_STATE["running"]:
        await update.message.reply_text("⚠️ النظام يعمل بالفعل!")
        return
    
    GLOBAL_STATE["mode"] = "AUTO"
    await update.message.reply_text("🚀 تم تشغيل المحرك (الوضع التلقائي)...")
    asyncio.create_task(trading_logic(context.bot, update.effective_chat.id))

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    GLOBAL_STATE["running"] = False
    await update.message.reply_text("🛑 تم إرسال إشارة التوقف.")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    api = GLOBAL_STATE["api"]
    if api:
        bal = api.profile.balance if hasattr(api.profile, 'balance') else api.profile.get('balance', 'N/A')
        await update.message.reply_text(f"💰 الرصيد الحالي: ${bal}")
    else:
        await update.message.reply_text("⚠️ البوت غير متصل. اضغط /run أولاً.")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    api = GLOBAL_STATE["api"]
    if not api:
        await update.message.reply_text("⚠️ يجب تشغيل البوت /run أولاً لجلب القائمة.")
        return
    
    msg = "📊 **أفضل الأصول المتاحة حالياً:**\n"
    candidates = []
    for aid, data in api.active_assets.items():
        if data['is_active'] and data['profit'] >= 70:
            name = data['name']
            if 'otc' not in name.lower() and 'smarty' not in name.lower():
                candidates.append((aid, name, data['profit']))
    
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    for item in candidates[:10]:
        msg += f"🆔 `{item[0]}` : {item[1]} ({item[2]}%)\n"
    
    msg += "\nللتداول اليدوي: `/trade ID`"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def trade_manual_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    try:
        if not context.args:
            await update.message.reply_text("⚠️ الاستخدام: `/trade <رقم_الأصل>`")
            return
        
        target = int(context.args[0])
        GLOBAL_STATE["target_id"] = target
        GLOBAL_STATE["mode"] = "MANUAL"
        
        await update.message.reply_text(f"🎯 تم التحويل للوضع اليدوي. الهدف: {target}")
        
        if not GLOBAL_STATE["running"]:
            GLOBAL_STATE["running"] = True
            asyncio.create_task(trading_logic(context.bot, update.effective_chat.id))
            
    except ValueError:
        await update.message.reply_text("❌ رقم الأصل غير صحيح.")

async def auto_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    GLOBAL_STATE["mode"] = "AUTO"
    await update.message.reply_text("🔄 تم تفعيل الوضع التلقائي الذكي.")

if __name__ == '__main__':
    # بناء تطبيق التيليجرام
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # ربط الأوامر
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("run", run_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("trade", trade_manual_cmd))
    app.add_handler(CommandHandler("auto", auto_cmd))
    
    print("✅ System Online via Systemd/Console.")
    app.run_polling()
