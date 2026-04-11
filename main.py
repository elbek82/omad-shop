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
BOT_TOKEN = os.environ.get("BOT_TOKEN") 
ADMIN_ID = 797324958   # O'z ID raqamingiz
WEB_APP_URL = "https://omad-shop.vercel.app"   # VERCEL do'kon manzili
DATA_FILE = "products.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

def load_products():
    if not os.path.exists(DATA_FILE): return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return []

def save_products(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def check_url_type(url):
    if "uzum.uz" in url: return "uzum"
    if "ozon.ru" in url or "ozon.uz" in url: return "ozon"
    if "wildberries.ru" in url or "wildberries.uz" in url: return "wildberries"
    if "market.yandex.ru" in url: return "yandex"
    return None

# ========== UNIVERSAL PARSER ==========
async def parse_universal(url, shop_type):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'uz,ru;q=0.9,en;q=0.8'
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, timeout=20) as resp:
                if resp.status != 200: return None
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                name, price, img, desc = "", 0, "", ""
                
                og_title = soup.find('meta', property='og:title')
                if og_title: 
                    raw_name = og_title['content']
                    name = raw_name.split(' - ')[0].split(' | ')[0].split(' – ')[0].strip()
                
                og_img = soup.find('meta', property='og:image')
                if og_img: img = og_img['content']
                
                og_desc = soup.find('meta', property='og:description')
                if og_desc: desc = og_desc['content']

                if shop_type == "uzum":
                    for script in soup.find_all('script', type='application/ld+json'):
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, list): data = data[0]
                            if data.get('@type') == 'Product':
                                name = data.get('name', name)
                                img = data.get('image', img)
                                desc = data.get('description', desc)
                                offers = data.get('offers', {})
                                if isinstance(offers, dict):
                                    price = int(float(offers.get('price', 0)))
                                break
                        except: pass
                
                if name:
                    if not desc: desc = f"AVTO 6707 do'koni maxsus taklifi."
                    return {"name": name, "price": price, "img": img, "description": desc, "source": shop_type}
                    
        except Exception as e:
            print(f"Parse xatosi ({shop_type}): {e}")
    return None

# ========== BOT HANDLERLARI ==========
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    button = KeyboardButton("🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(button)
    await message.reply("Assalomu alaykum! AVTO 6707 do'koniga xush kelibsiz.\nAdmin: Uzum, Ozon, Wildberries yoki Yandex linkini yuboring.", reply_markup=markup)

# YAngi: Narxni qo'lda o'zgartirish buyrug'i
@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('/narx'))
async def update_price(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("❌ Xato format. Bunday yozing: /narx ID SUMMA\nMasalan: /narx 1 150000")
            return
            
        product_id = int(parts[1])
        new_price = int(parts[2])
        
        products = load_products()
        found = False
        for p in products:
            if p['id'] == product_id:
                p['price'] = new_price
                found = True
                break
                
        if found:
            save_products(products)
            await message.reply(f"✅ Zo'r! {product_id}-raqamli mahsulot narxi {new_price:,} so'm etib belgilandi.\nDo'konga kirib tekshirib ko'ring!")
        else:
            await message.reply("❌ Bunday ID raqamli mahsulot topilmadi.")
    except Exception as e:
        await message.reply("❌ Xatolik ketdi. ID va narx faqat raqamlardan iborat bo'lsin.")

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('http'))
async def handle_link(message: types.Message):
    url = message.text
    shop_type = check_url_type(url)
    
    if not shop_type:
        await message.reply("❌ Noto'g'ri ssilka! Faqat Uzum, Ozon, Wildberries yoki Yandex ssilkalarini yuboring.")
        return
        
    wait_msg = await message.reply(f"🔄 Yuklanmoqda ({shop_type.capitalize()})...")
    info = await parse_universal(url, shop_type)
    
    if info and info.get('name'):
        products = load_products()
        new_id = max([p.get('id', 0) for p in products], default=0) + 1
        new_product = {
            "id": new_id,
            "name": info['name'],
            "price": info.get('price', 0),
            "img": info.get('img', ''),
            "description": info.get('description', ''),
            "source": info.get('source', '')
        }
        products.append(new_product)
        save_products(products)
        
        # Narx xabarini shakllantirish
        if new_product['price'] > 0:
            narx_matni = f"{new_product['price']:,} so'm"
        else:
            narx_matni = f"0 so'm ⚠️\n\n✏️ Qo'lda narx qo'yish uchun quyidagini yozing:\n/narx {new_id} 150000"
            
        caption_text = f"✅ Magazinga qo‘shildi!\n🆔 Mahsulot ID: {new_id}\n🌐 Manba: {new_product['source'].capitalize()}\n\n🛍 {new_product['name']}\n💰 Narx: {narx_matni}"
        
        if new_product['img']:
            await message.reply_photo(photo=new_product['img'], caption=caption_text)
        else:
            await message.reply(caption_text)
        await wait_msg.delete()
    else:
        await wait_msg.edit_text(f"❌ Ma'lumot olinmadi. {shop_type.capitalize()} sayti blokladi.")

# ========== API SERVER ==========
async def handle_api(request):
    products = load_products()
    return web.json_response(products, headers={'Access-Control-Allow-Origin': '*'})

async def handle_index(request):
    return web.Response(text="API ishlayapti. Frontend Vercel'da.", status=200)

async def run_api():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/products", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Server {port}-portda ishlayapti")
    await asyncio.Event().wait()

async def main():
    asyncio.create_task(run_api())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
