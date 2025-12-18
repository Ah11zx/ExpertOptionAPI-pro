import asyncio
import logging
import time
import os
from dotenv import load_dotenv
from Expert.api import ExpertOptionAPI
from Expert.indicators import AlligatorIndicator, RSIIndicator

# Load environment variables
load_dotenv()

# إعداد السجلات بشكل نظيف
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('ExpertOptionAPI').setLevel(logging.INFO)

async def main():
    # ---------------------------------------------------------
    token = os.getenv("EXPERT_TOKEN")  # Load from .env file
    # ---------------------------------------------------------
    
    api = ExpertOptionAPI(token=token, demo=True, server_region="wss://fr24g1us.expertoption.finance/ws/v40")
    
    try:
        print("\n" + "="*50)
        print("🚀 جاري بدء تشغيل البوت الذكي...")
        print("="*50)
        
        await api.connect()
        print("✅ تم إرسال طلب الاتصال...")

        # --- الحل السحري: الانتظار 8 ثوانٍ حتى تصل قائمة العملات من السيرفر ---
        print("⏳ جاري تحميل قائمة العملات (يرجى الانتظار)...")
        await asyncio.sleep(8)
        
        # طباعة عدد الأصول التي تم العثور عليها
        print(f"📊 عدد الأصول المتاحة الآن: {len(api.active_assets)}")

        # جلب الرصيد
        balance = api.get_balance()
        print(f"💰 الرصيد الحالي: {balance} $")
        print("-" * 30)

        # --- منطق ذكي لاختيار العملة لضمان عدم توقف البوت ---
        selected_asset_id = None
        asset_name = "Unknown"

        # 1. المحاولة الأولى: البحث عن EUR/USD (ID: 142)
        if 142 in api.active_assets and api.active_assets[142]['is_active']:
            selected_asset_id = 142
            asset_name = "EUR/USD"
        
        # 2. المحاولة الثانية: البحث عن Crypto IDX (عادة متاح دائماً)
        if not selected_asset_id:
            for aid, asset in api.active_assets.items():
                if asset['name'] == 'Crypto IDX' and asset['is_active']:
                    selected_asset_id = aid
                    asset_name = "Crypto IDX"
                    break
        
        # 3. المحاولة الثالثة: أي أصل متاح (ملاذ أخير)
        if not selected_asset_id:
            # نأخذ أول أصل نشط نجده في القائمة
            active_list = [k for k, v in api.active_assets.items() if v.get('is_active')]
            if active_list:
                selected_asset_id = active_list[0]
                asset_name = api.active_assets[selected_asset_id]['name']

        # إذا لم نجد أي أصل، هنا نتوقف بأمان بدلاً من الخطأ البرمجي
        if not selected_asset_id:
            print("❌ للأسف، السيرفر لا يعطي أي عملات متاحة للتداول حالياً.")
            print("ملاحظة: قد يكون السوق مغلقاً أو الحساب يحتاج تحديث.")
            await api.disconnect()
            return

        print(f"🎯 تم اختيار العملة: {asset_name} (ID: {selected_asset_id})")
        print("-" * 30)

        # الاشتراك في الشموع
        await api.get_candles(selected_asset_id, timeframes=[60])
        print("🕯️ تم طلب بيانات الشموع، جاري بدء التحليل...")

        # حلقة العمل المستمرة
        while True:
            try:
                now = int(time.time())
                periods = [[now - 1200, now]] # آخر 20 دقيقة
                
                historical = await api.get_historical_candles(selected_asset_id, periods)

                if historical and len(historical) > 0:
                    rsi = RSIIndicator(historical)
                    rsi_val = rsi.evaluate_market_condition()
                    
                    # طباعة الوقت والتحليل
                    current_time = time.strftime('%H:%M:%S')
                    
                    rsi_status = "😐 محايد"
                    if "Overbought" in str(rsi_val): rsi_status = "🔴 بيع (تشبع شرائي)"
                    elif "Oversold" in str(rsi_val): rsi_status = "🟢 شراء (تشبع بيعي)"
                    
                    # طباعة سطر واحد نظيف يتم تحديثه
                    print(f"⏰ {current_time} | {asset_name} | RSI: {rsi_val} | النتيجة: {rsi_status}")

                else:
                    print("⚠️ جاري انتظار البيانات...")

                await asyncio.sleep(5) # تحديث كل 5 ثواني

            except Exception as loop_error:
                print(f"⚠️ خطأ بسيط: {loop_error}")
                await asyncio.sleep(2)

    except Exception as e:
        print(f"\n❌ خطأ في الاتصال: {e}")
    finally:
        await api.disconnect()
        print("🛑 تم إنهاء الجلسة.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 وداعاً!")
