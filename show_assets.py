import asyncio
from Expert.api import ExpertOptionAPI

async def show_assets():
    """عرض جميع الأصول المتاحة"""

    # الإعدادات
    TOKEN = "f4232b804dbd446d5cea0c46e6faeb9c"
    SERVER = "wss://fr24g1us.expertoption.finance/ws/v40"

    print("🔄 جاري الاتصال بالسيرفر...")

    # الاتصال بالـ API
    api = ExpertOptionAPI(token=TOKEN, demo=True, server_region=SERVER)
    await api.connect()

    # الانتظار لتحميل البيانات
    await asyncio.sleep(5)

    # عرض الأصول
    assets = api.active_assets

    print(f"\n📊 إجمالي الأصول المتاحة: {len(assets)}\n")
    print("=" * 80)

    # تصنيف الأصول حسب المجموعة
    groups = {}
    for aid, data in assets.items():
        group = data.get('asset_group_id', 'other')
        if group not in groups:
            groups[group] = []
        groups[group].append((aid, data))

    # عرض كل مجموعة
    for group_name, group_assets in groups.items():
        print(f"\n📁 {group_name.upper()}")
        print("-" * 80)

        for aid, data in sorted(group_assets, key=lambda x: x[1]['profit'], reverse=True):
            status = "✅" if data['is_active'] == 1 else "❌"
            name = data['name']
            profit = data['profit']
            symbol = data.get('symbol', 'N/A')

            print(f"{status} ID: {aid:4d} | {name:30s} | Profit: {profit:3.0f}% | Symbol: {symbol}")

    print("\n" + "=" * 80)

    # إحصائيات
    active_count = sum(1 for d in assets.values() if d['is_active'] == 1)
    inactive_count = len(assets) - active_count

    print(f"\n📈 إحصائيات:")
    print(f"   - أصول نشطة: {active_count}")
    print(f"   - أصول غير نشطة: {inactive_count}")

    # عرض أفضل 10 أصول نشطة
    print(f"\n🏆 أفضل 10 أصول نشطة (حسب الربح):")
    print("-" * 80)

    active_assets = [(aid, data) for aid, data in assets.items() if data['is_active'] == 1]
    top_10 = sorted(active_assets, key=lambda x: x[1]['profit'], reverse=True)[:10]

    for i, (aid, data) in enumerate(top_10, 1):
        print(f"{i:2d}. ID: {aid:4d} | {data['name']:30s} | Profit: {data['profit']:3.0f}%")

    # قطع الاتصال
    await api.disconnect()
    print("\n✅ تم قطع الاتصال بنجاح")

if __name__ == "__main__":
    asyncio.run(show_assets())
