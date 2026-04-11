import os
import json
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.utils import executor

# ========== SOZLAMALAR ==========
BOT_TOKEN = "8353606263:AAHImyDaiU8G18ZSxwiV9shAyZ8s29WEK3s"   # Sizning yangi token
ADMIN_ID = 797324958   # O‘z ID-raqamingizni yozing (telegramdan /id qilib oling)
WEB_APP_URL = "https://omad-shop-1.onrender.com"   # Render URL
DATA_FILE = "products.json"

# ========== BOT VA DISPATCHER ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ========== YORDAMCHI FUNKSIYALAR ==========
def load_products():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return []

def save_products(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def is_uzum_url(url):
    return re.match(r'https?://(www\.)?uzum\.uz/uz/product/[a-zA-Z0-9\-]+', url) is not None

async def parse_uzum(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                script = soup.find('script', string=re.compile('__INITIAL_STATE__'))
                if script:
                    match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', script.string, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        product = data.get('product', {}).get('payload', {}).get('data', {})
                        if product:
                            name = product.get('title')
                            price = product.get('lowPrice') or product.get('sellPrice')
                            photos = product.get('photos', [])
                            img = photos[0].get('high') if photos else None
                            if img and img.startswith('//'):
                                img = 'https:' + img
                            return {"name": name, "price": price, "img": img}
        except Exception as e:
            print(f"Parse xatosi: {e}")
    return None

# ========== BOT HANDLERLAR ==========
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    button = KeyboardButton("🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(button)
    await message.reply("Assalomu alaykum! Admin Uzum linki yuboring.", reply_markup=markup)

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('http'))
async def handle_link(message: types.Message):
    url = message.text
    if not is_uzum_url(url):
        await message.reply("❌ Faqat Uzum mahsulot linki.")
        return
    wait_msg = await message.reply("🔄 Parse qilinmoqda...")
    info = await parse_uzum(url)
    if info and info.get('name'):
        products = load_products()
        new_id = max([p.get('id', 0) for p in products], default=0) + 1
        new_product = {
            "id": new_id,
            "name": info['name'],
            "price": info.get('price', 0),
            "img": info.get('img', ''),
            "description": f"{info['name']} — sifatli avto aksessuar"
        }
        products.append(new_product)
        save_products(products)
        # Rasm bilan javob berish
        if new_product['img']:
            await message.reply_photo(photo=new_product['img'], caption=f"✅ Qo‘shildi!\n\n{new_product['name']}\n💰 {new_product['price']:,} so'm")
        else:
            await message.reply(f"✅ Qo‘shildi!\n\n{new_product['name']}\n💰 {new_product['price']:,} so'm")
        await wait_msg.delete()
    else:
        await wait_msg.edit_text("❌ Ma'lumot olinmadi.")

@dp.message_handler(lambda msg: msg.from_user.id != ADMIN_ID)
async def not_admin(message: types.Message):
    await message.reply("Siz admin emassiz.")

# ========== API SERVER ==========
async def handle_api(request):
    products = load_products()
    return web.json_response(products, headers={'Access-Control-Allow-Origin': '*'})

async def run_api():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ API server {port}-portda ishlayapti")
    # Cheksiz kutish
    await asyncio.Event().wait()

# ========== MAIN ==========
async def main():
    # API ni alohida taskda ishga tushirish
    asyncio.create_task(run_api())
    # Botni ishga tushirish (polling)
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
