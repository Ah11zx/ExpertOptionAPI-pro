code_content = r"""import asyncio
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from Expert.api import ExpertOptionAPI

# --- إعدادات المستخدم (يجب تعديلها بعد التحديث) ---
TELEGRAM_TOKEN = "8412918483:AAFGvl-WVu_8E3eqRXXujPP8pn6lJ5Wa7kA"
ALLOWED_USER_ID = 1158674572  # معرفك في تيليجرام
EXPERT_TOKEN = "f4232b804dbd446d5cea0c46e6faeb9c"

# إعدادات السيرفر
SERVER_REGION = "wss://fr24g1us.expertoption.finance/ws/v40"

# --- المتغيرات العامة ---
trading_active = False
current_task = None
api_instance = None

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- دالة مساعدة لحساب RSI يدوياً ---
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50  # قيمة محايدة عند نقص البيانات
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
            
    # حساب المتوسط الأسي (EMA) البسيط للسرعة
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# --- التحقق من الصلاحية ---
def authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID

# --- حلقة التداول الرئيسية ---
async def trading_loop(bot, chat_id):
    global trading_active, api_instance
    
    # إعدادات الاستراتيجية
    ASSET_ID = 240   # EUR/USD (تأكد من المعرف)
    AMOUNT = 50      # مبلغ الصفقة
    
    await bot.send_message(chat_id, "🚀 تم تشغيل استراتيجية RSI...")

    try:
        api_instance = ExpertOptionAPI(token=EXPERT_TOKEN, demo=True, server_region=SERVER_REGION)
        await api_instance.connect()
        await bot.send_message(chat_id, "✅ متصل بالمنصة.")

        while trading_active:
            try:
                # 1. جلب الشموع (آخر 20 شمعة تكفي لحساب RSI سريع)
                # ملاحظة: تعتمد الطريقة على كيفية استجابة المكتبة، هنا نفترض أنها تعيد قائمة
                candles = await api_instance.get_candles(ASSET_ID, 0, 20)
                
                # استخراج أسعار الإغلاق فقط
                # الهيكل المتوقع للشمعة: {'close': 1.054, ...} أو قائمة
                # سيتم استخدام محاولة استخراج آمنة
                close_prices = []
                if candles:
                    for c in candles:
                        # نحاول الوصول للسعر سواء كان كائن أو قاموس
                        price = c.get('close') if isinstance(c, dict) else getattr(c, 'close', None)
                        if price: close_prices.append(float(price))

                if len(close_prices) > 14:
                    rsi = calculate_rsi(close_prices)
                    print(f"RSI: {rsi:.2f}") # للمراقبة
                    
                    direction = None
                    msg = ""
                    
                    if rsi < 30:
                        direction = 'call'
                        msg = f"🟢 شراء! RSI منخفض جداً ({rsi:.2f})"
                    elif rsi > 70:
                        direction = 'put'
                        msg = f"🔴 بيع! RSI مرتفع جداً ({rsi:.2f})"
                    
                    if direction:
                        await bot.send_message(chat_id, f"⚡ إشارة: {msg}")
                        
                        # تنفيذ الصفقة
                        order = await api_instance.place_order(ASSET_ID, AMOUNT, direction)
                        await bot.send_message(chat_id, f"تم فتح الصفقة بنجاح. ID: {order}")
                        
                        # انتظار دقيقة لتجنب التكرار
                        await asyncio.sleep(60)
                else:
                    print("جاري جمع بيانات الشموع...")
                
                await asyncio.sleep(2) # فحص كل ثانيتين

            except Exception as e:
                print(f"Error in loop: {e}")
                await asyncio.sleep(5)

    except Exception as e:
        await bot.send_message(chat_id, f"⚠️ خطأ: {e}")
    finally:
        if api_instance:
            await api_instance.disconnect()
        await bot.send_message(chat_id, "🛑 تم إيقاف الروبوت.")

# --- أوامر تيليجرام ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await update.message.reply_text("أهلاً بك. الأوامر: /run, /stop, /status")

async def run_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    global trading_active, current_task
    if not trading_active:
        trading_active = True
        current_task = asyncio.create_task(trading_loop(context.bot, update.effective_chat.id))
    else:
        await update.message.reply_text("يعمل بالفعل.")

async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    global trading_active
    trading_active = False
    await update.message.reply_text("جاري الإيقاف...")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return
    msg = "🟢 متصل" if trading_active else "🔴 مفصول"
    if trading_active and api_instance:
        try:
            bal = api_instance.get_balance()
            msg += f"\n💰 الرصيد: {bal}"
        except: pass
    await update.message.reply_text(msg)

if __name__ == '__main__':
    if TELEGRAM_TOKEN == "ضع_توكن_تيليجرام_هنا":
        print("⚠️ خطأ: يجب عليك تعديل ملف telegram_bot.py ووضع التوكن الخاص بك!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("run", run_bot))
        app.add_handler(CommandHandler("stop", stop_bot))
        app.add_handler(CommandHandler("status", status))
        print("Bot Started...")
        app.run_polling()
"""

with open("telegram_bot.py", "w", encoding="utf-8") as f:
    f.write(code_content)

print("✅ تم تحديث ملف telegram_bot.py بنجاح!")
print("🔔 الآن: افتح الملف، أضف التوكن الخاص بك، ثم شغله.")
