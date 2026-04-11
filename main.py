import os
import json
import asyncio
import requests
import re
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
ADMIN_ID = 797324958 
WEB_APP_URL = "https://omad-shop.vercel.app"

def load_products():
    if not os.path.exists('products.json'): return []
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_products(data):
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- UZUM MARKET UCHUN YANGI "AQLLI" PARSER ---
def get_uzum_info(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7',
        }
        
        # Linkni tozalash (agar ortiqcha parametrlar bo'lsa)
        url = url.split('?')[0]
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Skriptlar ichidan JSON ma'lumotni qidirish (Eng ishonchli yo'l)
        # Uzum mahsulot ma'lumotlarini 'window.__INITIAL_STATE__' ichida saqlaydi
        script_tag = soup.find('script', string=re.compile('__INITIAL_STATE__'))
        
        name, price, img = None, 0, None

        if script_tag:
            json_text = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', script_tag.string)
            if json_text:
                data = json.loads(json_text.group(1))
                # JSON ichidan mahsulotni topamiz
                product_data = data.get('product', {}).get('payload', {}).get('data', {})
                if product_data:
                    name = product_data.get('title')
                    # Rasmlardan birinchisini olish
                    photos = product_data.get('photos', [])
                    if photos:
                        img = photos[0].get('high') or photos[0].get('low')
                    # Narx
                    price = product_data.get('lowPrice') or product_data.get('sellPrice')

        # 2. Agar JSON dan topilmasa, Meta va Selektorlar orqali (Zaxira varianti)
        if not name:
            name_tag = soup.find('h1') or soup.find('meta', property='og:title')
            name = name_tag.get_text(strip=True) if hasattr(name_tag, 'get_text') else name_tag.get('content', '')

        if not img:
            img_tag = soup.find('meta', property='og:image') or soup.find('img', {'srcset': True})
            img = img_tag.get('content') if img_tag.has_attr('content') else img_tag.get('src')
        
        if not price:
            price_tag = soup.find('span', {'data-test-id': 'text-price'})
            if price_tag:
                price = int(''.join(filter(str.isdigit, price_tag.get_text())))

        # Rasmni to'g'irlash
        if img and img.startswith('//'):
            img = 'https:' + img
        
        if name and img:
            return {"name": name, "price": price, "img": img, "specs": {}}
        
        return None
    except Exception as e:
        print(f"Xato: {e}")
        return None

# --- BOT HANDLERS ---
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True
    )
    await message.answer("Uzum Market linkini yuboring, men uni do'koningizga qo'shaman.", reply_markup=markup)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith("http"))
async def handle_link(message: types.Message):
    wait = await message.answer("🔄 Uzum Marketdan ma'lumot olinmoqda...")
    info = get_uzum_info(message.text)
    
    if info:
        products = load_products()
        info['id'] = len(products) + 1
        products.append(info)
        save_products(products)
        
        # Bot rasm bilan javob qaytarsa, demak hammasi OK
        await message.answer_photo(photo=info['img'], caption=f"✅ Qo'shildi!\n\n📦 {info['name']}\n💰 {info['price']:,} so'm")
        await wait.delete()
    else:
        await wait.edit_text("❌ Kechirasiz, bu linkdan ma'lumot ololmadim. Sayt himoyasi kuchaytirilgan bo'lishi mumkin.")

# --- API ---
async def handle_api(request):
    return web.json_response(load_products(), headers={'Access-Control-Allow-Origin': '*'})

async def main():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000)))
    await site.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
