import os
import json
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo

# --- SOZLAMALAR ---
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "797324958"))
WEB_APP_URL = "https://omad-shop.vercel.app"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
DATA_FILE = "products.json"

# Lock obyektini main ichida yaratamiz (Globalda xato beradi)
lock = None

# Mahsulotlarni yuklash va saqlash
async def load_products():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

async def save_products(data):
    async with lock: # Fayl bilan ishlashda xavfsizlik
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# --- UZUM MARKET UCHUN ASINXRON PARSER ---
async def get_uzum_info(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7'
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=15) as response:
                if response.status != 200: return None
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Uzum Market ma'lumotlarini 'INITIAL_STATE' ichidan olish
                script = soup.find('script', string=re.compile('__INITIAL_STATE__'))
                if script:
                    json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', script.string)
                    if json_text:
                        data = json.loads(json_text.group(1))
                        p = data.get('product', {}).get('payload', {}).get('data', {})
                        if p:
                            name = p.get('title')
                            price = p.get('lowPrice') or p.get('sellPrice', 0)
                            # Rasm manzilini to'g'irlash
                            photos = p.get('photos', [])
                            img = photos[0].get('high') if photos else None
                            if img and img.startswith('//'): img = 'https:' + img
                            
                            if name and img:
                                return {"name": name, "price": price, "img": img}
        return None
    except Exception as e:
        print(f"Parsing xatosi: {e}")
        return None

# --- BOT HANDLERS ---
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True
    )
    await message.answer("Uzum Market linkini yuboring!", reply_markup=markup)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith("http"))
async def handle_link(message: types.Message):
    wait = await message.answer("🔄 Ma'lumot olinmoqda...")
    info = await get_uzum_info(message.text)
    
    if info:
        products = await load_products()
        info['id'] = len(products) + 1
        products.append(info)
        await save_products(products)
        
        # Bot rasm bilan javob qaytarishi - rasm ishlayotganining isboti
        await message.answer_photo(photo=info['img'], caption=f"✅ Qo'shildi!\n\n📦 {info['name']}\n💰 {info['price']:,} so'm")
        await wait.delete()
    else:
        await wait.edit_text("❌ Ma'lumotni olib bo'lmadi. Linkni tekshiring.")

# --- API ---
async def handle_api(request):
    data = await load_products()
    return web.json_response(data, headers={'Access-Control-Allow-Origin': '*'})

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    global lock
    lock = asyncio.Lock() # Lockni shu yerda yaratamiz!

    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
