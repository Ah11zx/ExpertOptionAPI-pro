# 📊 دليل الأصول المتاحة في ExpertOption

## 🔍 كيف تجد الأصول في الكود؟

### 1️⃣ **في الكود:**
```python
from Expert.api import ExpertOptionAPI

# بعد الاتصال
api = ExpertOptionAPI(token=YOUR_TOKEN, demo=True)
await api.connect()

# الوصول للأصول
assets = api.active_assets  # هنا توجد جميع الأصول

# عرض الأصول
for asset_id, asset_data in assets.items():
    print(f"ID: {asset_id} | Name: {asset_data['name']} | Profit: {asset_data['profit']}%")
```

### 2️⃣ **موقع تخزين الأصول:**
- **الملف:** `Expert/api.py`
- **المتغير:** `self.active_assets` (سطر 43)
- **الدالة:** `fetch_assets()` (سطر 251)

---

## 📁 تصنيف الأصول حسب المجموعة

### 💱 العملات (Currencies) - `asset_group_id = 'currencies'`
أمثلة:
- EUR/USD
- GBP/USD
- USD/JPY
- AUD/CAD
- EUR/GBP

### 📈 الأسهم (Stocks) - `asset_group_id = 'stocks'`
أمثلة:
- Apple (AAPL)
- Microsoft (MSFT)
- Tesla (TSLA)
- Amazon (AMZN)
- Google (GOOG)

### 🥇 السلع (Commodities) - `asset_group_id = 'commodities'`
أمثلة:
- Gold (XAUUSD)
- Silver (SI)
- Brent Oil
- Copper
- Platinum

### 📊 المؤشرات (Indices) - `asset_group_id = 'indices'`
أمثلة:
- Smarty
- Cricket Index
- Football Index
- AI Index
- Camel Race Index

### 🪙 العملات الرقمية (Cryptocurrencies) - `asset_group_id = 'cryptocurrencies'`
أمثلة:
- Bitcoin (BTC/USD)
- Ethereum (ETH/USD)
- Ripple (XRP/USD)
- Cardano (ADA/USD)
- BNB/USD
- DOGE/USD
- SOL/USD

---

## 🔧 كيف تستخدم الأصول في البوت؟

### ✅ الأصول الموصى بها (مستقرة):
```python
# في telegram_bot.py (السطور 62-83)

# الفلاتر المطبقة:
✓ is_active == 1           # نشط
✓ profit > 0               # له ربح
✓ لا يحتوي على "OTC"       # ليس OTC
✓ لا يحتوي على "Index"     # ليس Index
✓ يفضل currencies/commodities
```

### ❌ الأصول التي يتجنبها البوت:
- الأصول غير النشطة (`is_active = 0`)
- الأصول OTC (غير مستقرة)
- المؤشرات (Index)
- الأصول ذات الربح 0%

---

## 📖 بيانات الأصل (Asset Data)

كل أصل يحتوي على:
```python
{
    'id': 142,                      # معرف الأصل
    'name': 'EUR / USD',            # الاسم
    'symbol': 'EURUSD',             # الرمز
    'asset_group_id': 'currencies', # المجموعة
    'is_active': 1,                 # نشط (1) أو غير نشط (0)
    'profit': 88,                   # نسبة الربح %
    'purchase_time': 5,             # وقت الشراء بالثواني
    'expiration_step': 5,           # خطوة الانتهاء
    'min_bet': 1,                   # الحد الأدنى للرهان
    'max_bet': 1000,                # الحد الأقصى للرهان
}
```

---

## 🎯 أمثلة عملية

### مثال 1: عرض جميع العملات النشطة
```python
currencies = {
    aid: data for aid, data in api.active_assets.items()
    if data['asset_group_id'] == 'currencies' and data['is_active'] == 1
}
```

### مثال 2: البحث عن أصل معين
```python
# البحث بالاسم
for aid, data in api.active_assets.items():
    if 'EUR/USD' in data['name']:
        print(f"Found: {aid} - {data['name']}")
```

### مثال 3: اختيار أفضل 5 أصول
```python
top_5 = sorted(
    api.active_assets.items(),
    key=lambda x: x[1]['profit'],
    reverse=True
)[:5]
```

---

## 📞 كيف تحصل على قائمة الأصول؟

### الطريقة 1: من البوت
1. شغل البوت: `python3 telegram_bot.py`
2. أرسل `/run` في تيليجرام
3. البوت سيختار أفضل أصل ويخبرك به

### الطريقة 2: من run_bot.py
```bash
python3 run_bot.py
```

### الطريقة 3: يدوياً
```python
import asyncio
from Expert.api import ExpertOptionAPI

async def main():
    api = ExpertOptionAPI(token="YOUR_TOKEN", demo=True)
    await api.connect()
    await asyncio.sleep(5)  # انتظار تحميل البيانات

    print(f"Total assets: {len(api.active_assets)}")
    for aid, data in api.active_assets.items():
        if data['is_active'] == 1:
            print(f"{aid}: {data['name']} - {data['profit']}%")

    await api.disconnect()

asyncio.run(main())
```

---

## 💡 نصائح

1. **للتداول الآمن:** استخدم العملات الرئيسية (EUR/USD, GBP/USD)
2. **تجنب OTC:** الأصول OTC غير مستقرة وقد تسبب أخطاء
3. **تحقق من is_active:** بعض الأصول تكون مغلقة في أوقات معينة
4. **راقب نسبة الربح:** الأصول ذات الربح الأعلى تعطي عوائد أفضل

---

✅ **لعرض الأصول الحالية المتاحة:**
- افتح تيليجرام
- أرسل `/run` للبوت
- سيظهر لك الأصل المختار مع نسبة الربح
