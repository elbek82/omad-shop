import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart, Command
from urllib.parse import urljoin

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
ADMIN_ID = 797324958  # Sizning ID raqamingiz
WEB_APP_URL = "https://omad-shop.vercel.app"

# Mahsulotlarni yuklash va saqlash
def load_products():
    if not os.path.exists('products.json'):
        return []
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []

def save_products(data):
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- YANGILANGAN UNIVERSAL PARSER ---
def get_product_info(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Accept-Language': 'uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Nomi (Title)
        title_tag = soup.find('meta', property='og:title') or soup.find('h1')
        name = title_tag['content'] if title_tag and title_tag.has_attr('content') else title_tag.get_text(strip=True)

        # 2. RASMNI ANIQLASH (Eng muhim qismi)
        img = None
        # Uzum Market uchun rasm qidirish
        if "uzum.uz" in url:
            # Asosiy rasm ko'pincha 'img' tegida 'srcset' yoki 'src' bilan keladi
            main_img = soup.find('img', {'srcset': True}) or soup.find('img', class_='_1G6mH')
            if main_img:
                img = main_img.get('src') or main_img.get('srcset', '').split(' ')[0]
        
        # Agar maxsus topilmasa, Meta tegdan olamiz
        if not img:
            img_tag = soup.find('meta', property='og:image')
            img = img_tag['content'] if img_tag else "https://via.placeholder.com/600x400.png?text=Rasm+Topilmadi"

        # Rasmni formatlash (https: qo'shish)
        if img.startswith('//'):
            img = 'https:' + img
        elif not img.startswith('http'):
            img = urljoin(url, img)

        # 3. NARXNI ANIQLASH
        price = 0
        price_tag = None
        if "uzum.uz" in url:
            price_tag = soup.find('span', {'data-test-id': 'text-price'})
        elif "olcha.uz" in url:
            price_tag = soup.find('div', class_='current-price') or soup.find('span', class_='price_content')

        if price_tag:
            price_text = price_tag.get_text().replace('\xa0', '').replace(' ', '')
            price_digits = ''.join(filter(str.isdigit, price_text))
            price = int(price_digits) if price_digits else 0

        # 4. Xususiyatlar
        specs = {}
        if "uzum.uz" in url:
            items = soup.find_all('div', class_='item-characteristic')
            for i in items[:10]:
                k = i.find('span', class_='characteristic-name')
                v = i.find('span', class_='characteristic-value')
                if k and v:
                    specs[k.get_text(strip=True)] = v.get_text(strip=True)

        return {"name": name, "price": price, "img": img, "specs": specs}
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
        return None

# --- BOT HANDLERS ---
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True
    )
    msg = "Xush kelibsiz! Uzum Market linkini yuboring va men uni do'koningizga qo'shaman."
    await message.answer(msg, reply_markup=markup)

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith("http"))
async def auto_parser(message: types.Message):
    wait = await message.answer("🔄 Mahsulot ma'lumotlari tahlil qilinmoqda...")
    info = get_product_info(message.text)
    
    if info and info['name']:
        products = load_products()
        info['id'] = len(products) + 1
        products.append(info)
        save_products(products)
        
        # Telegramda natijani ko'rsatish
        res_text = f"✅ Savatga qo'shildi!\n\n📦 **{info['name']}**\n💰 Narxi: {info['price']:,} so'm"
        await wait.delete()
        await message.answer_photo(photo=info['img'], caption=res_text, parse_mode="Markdown")
    else:
        await wait.edit_text("❌ Xato: Ma'lumotlarni olib bo'lmadi. Linkni tekshiring.")

# --- API SERVER ---
async def handle_api(request):
    return web.json_response(load_products(), headers={
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    })

async def main():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    app.router.add_options("/api/products", handle_api)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
