import os
import json
import asyncio
import re
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo

# --- KONFIGURATSIYA (TOKEN QO'YILDI) ---
API_TOKEN = "8353606263:AAFdwZSNdYmK5Qfaj8TAlmfj-RIG-JiuKpU"   # <-- SIZNING TOKENINGIZ
ADMIN_ID = int(os.getenv("ADMIN_ID", "797324958"))  # O'z ID-raqamingizni qo'ying
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://omad-shop.vercel.app")
DATA_FILE = "products.json"

# --- GLOBAL O'ZGARUVCHILAR ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
lock = asyncio.Lock()
session = None

# --- YORDAMCHI FUNKSIYALAR ---
async def load_products():
    async with lock:
        if not os.path.exists(DATA_FILE):
            return []
        try:
            async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Faylni o'qishda xato: {e}")
            return []

async def save_products(data):
    async with lock:
        async with aiofiles.open(DATA_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))

def is_valid_uzum_url(url: str) -> bool:
    pattern = r'https?://(www\.)?uzum\.uz/uz/product/[a-zA-Z0-9\-]+'
    return re.match(pattern, url) is not None

# --- UZUM PARSER ---
async def get_uzum_info(url: str):
    global session
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200:
                print(f"HTTP {response.status}: {url}")
                return None
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            script = soup.find('script', string=re.compile('__INITIAL_STATE__'))
            if script:
                match = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', script.string, re.DOTALL)
                if match:
                    try:
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
                    except json.JSONDecodeError:
                        pass
            
            # Fallback
            name_tag = soup.find('meta', property='og:title')
            name = name_tag['content'] if name_tag else None
            price_tag = soup.find('span', class_=re.compile(r'price'))
            price = None
            if price_tag:
                price_text = re.sub(r'[^\d]', '', price_tag.text)
                price = int(price_text) if price_text else None
            img_tag = soup.find('meta', property='og:image')
            img = img_tag['content'] if img_tag else None
            
            if name and price:
                return {"name": name, "price": price, "img": img}
            return None
    except Exception as e:
        print(f"Parser xatosi: {e}")
        return None

# --- TELEGRAM HANDLERLAR ---
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True
    )
    await message.answer("Assalomu alaykum! Admin Uzum marketdan mahsulot linkini yuborsin.", reply_markup=markup)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith("http"))
async def handle_link(message: types.Message):
    if not is_valid_uzum_url(message.text):
        await message.answer("❌ Faqat Uzum market mahsulot linklarini yuboring!\nMasalan: https://uzum.uz/uz/product/...")
        return
    
    wait_msg = await message.answer("🔄 Ma'lumot olinmoqda...")
    info = await get_uzum_info(message.text)
    
    if info and info.get('name') and info.get('price'):
        products = await load_products()
        new_id = max([p.get('id', 0) for p in products], default=0) + 1
        info['id'] = new_id
        products.append(info)
        await save_products(products)
        
        caption = f"✅ Qo'shildi!\n\n📦 {info['name']}\n💰 {info['price']:,} so'm"
        if info.get('img'):
            await message.answer_photo(photo=info['img'], caption=caption)
        else:
            await message.answer(caption)
        await wait_msg.delete()
    else:
        await wait_msg.edit_text("❌ Mahsulot ma'lumotlarini topib bo'lmadi. Linkni tekshiring yoki keyinroq urinib ko'ring.")

@dp.message(F.from_user.id == ADMIN_ID)
async def unknown_admin_message(message: types.Message):
    await message.answer("Iltimos, Uzum market mahsulot linkini yuboring.")

# --- API HANDLER ---
async def handle_api(request):
    products = await load_products()
    return web.json_response(products, headers={
        'Access-Control-Allow-Origin': '*'
        # Content-Type ni qo'lda yozish shart emas, json_response o'zi qo'shadi
    })

# --- ASOSIY FUNKSIYA ---
async def main():
    global session, lock
    lock = asyncio.Lock()
    session = aiohttp.ClientSession()
    
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"API server {port}-portda ishga tushdi")
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    try:
        await dp.start_polling(bot)
    finally:
        await session.close()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
