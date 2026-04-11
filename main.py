import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart, Command

# --- SOZLAMALAR ---
API_TOKEN = os.getenv('BOT_TOKEN')
# Botni faqat bir marta yaratamiz
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
ADMIN_ID = 797324958
WEB_APP_URL = "https://omad-shop.vercel.app"

# Mahsulotlarni saqlash va yuklash
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

# --- UZUM PARSER (Yaxshilangan variant) ---
def get_uzum_info(url):
    try:
        # User-Agent bo'lmasa Uzum bot deb o'ylaydi va bloklaydi
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
            'Accept-Language': 'uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7'
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Sarlavha (og:title metadan olish ishonchliroq)
        title_tag = soup.find('meta', property='og:title') or soup.find('h1')
        name = title_tag['content'] if title_tag.has_attr('content') else title_tag.get_text(strip=True)

        # Rasm (og:image metadan olish)
        img_tag = soup.find('meta', property='og:image')
        img = img_tag['content'] if img_tag else "https://via.placeholder.com/300"

        # Narx (Uzumda narx dinamik o'zgarishi mumkin, bir nechta variantni tekshiramiz)
        price_tag = soup.find('span', {'data-test-id': 'text-price'}) or \
                    soup.find('div', class_='price') or \
                    soup.find('meta', property='product:price:amount')
        
        if price_tag and price_tag.has_attr('content'):
            price = int(float(price_tag['content']))
        elif price_tag:
            price_text = price_tag.get_text().replace('\xa0', '').replace(' ', '')
            price = int(''.join(filter(str.isdigit, price_text)))
        else:
            price = 0

        return {"name": name, "price": price, "img": img}
    except Exception as e:
        print(f"Scraping xatosi: {e}")
        return None

# --- BOT BUYRUQLARI ---
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True
    )
    if message.from_user.id == ADMIN_ID:
        await message.answer("Xush kelibsiz, Admin! \n\nUzum linkini yuboring yoki /add orqali qo'shing.", reply_markup=markup)
    else:
        await message.answer("Xush kelibsiz! Do'konimizga marhamat.", reply_markup=markup)

@dp.message(F.from_user.id == ADMIN_ID, Command("add"))
async def manual_add(message: types.Message):
    try:
        text = message.text.replace("/add ", "")
        parts = text.split(" | ")
        products = load_products()
        item = {"id": len(products) + 1, "name": parts[0], "price": int(parts[1]), "img": parts[2]}
        products.append(item)
        save_products(products)
        await message.answer("✅ Mahsulot qo'lda muvaffaqiyatli qo'shildi!")
    except:
        await message.answer("❌ Xato! Format: `/add Nomi | Narxi | Rasm_linki`")

@dp.message(F.from_user.id == ADMIN_ID, F.text.contains("uzum.uz"))
async def parser_handler(message: types.Message):
    wait = await message.answer("🔄 Uzum Marketdan ma'lumot o'qilyapti...")
    info = get_uzum_info(message.text)
    if info and info['name']:
        products = load_products()
        info['id'] = len(products) + 1
        products.append(info)
        save_products(products)
        await wait.edit_text(f"✅ Savatga qo'shildi!\n\n📦 **{info['name']}**\n💰 Narxi: {info['price']:,} so'm")
    else:
        await wait.edit_text("❌ Uzumdan ma'lumot olib bo'lmadi. Sahifa o'zgargan bo'lishi mumkin.")

# --- SERVER QISMI ---
async def handle_api(request):
    data = load_products()
    return web.json_response(data, headers={
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
    
    # Conflict oldini olish uchun webhookni o'chirib yuboramiz
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
