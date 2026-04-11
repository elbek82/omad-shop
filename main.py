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
API_TOKEN = '8353606263:AAHLPpnuv5wCEmGHJexg1PAYAQomKpny-PY' # Botfather bergan token
ADMIN_ID =797324958
WEB_APP_URL = "https://omad-shop.vercel.app" # Vercel-dagi sayt linki

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Mahsulotlarni yuklash va saqlash
def load_products():
    if not os.path.exists('products.json'): return []
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def save_products(data):
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# --- UZUM PARSER ---
def get_uzum_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Uzumdan ma'lumot olish (Uzum dizayni o'zgarsa, buni yangilash kerak)
        name = soup.find('h1').get_text(strip=True)
        
        # Narxni topish (barcha raqamlarni ajratib olish)
        price_tag = soup.find('span', {'data-test-id': 'text-price'}) or soup.find('div', {'class': 'price'})
        price_text = price_tag.get_text() if price_tag else "0"
        price = int(''.join(filter(str.isdigit, price_text)))
        
        # Rasmni topish
        img_tag = soup.find('meta', property="og:image")
        img = img_tag['content'] if img_tag else "https://via.placeholder.com/300"
        
        return {"name": name, "price": price, "img": img}
    except Exception as e:
        print(f"Xato yuz berdi: {e}")
        return None

# --- BOT BUYRUQLARI ---

# 1. AVVAL QO'LDA QO'SHISHNI TEKSHIRAMIZ
@dp.message(F.from_user.id == ADMIN_ID, Command("add"))
async def manual_add(message: types.Message):
    try:
        data = message.text.split("/add ")[1].split(" | ")
        products = load_products()
        item = {"id": len(products)+1, "name": data[0], "price": int(data[1]), "img": data[2]}
        products.append(item)
        save_products(products)
        await message.answer("✅ Mahsulot qo'lda muvaffaqiyatli qo'shildi!")
    except:
        await message.answer("❌ Xato! Format: /add Nomi | Narxi | Rasm_linki")

# 2. KEYIN UZUM LINKINI TEKSHIRAMIZ (faqat /add bo'lmasa ishlaydi)
@dp.message(F.from_user.id == ADMIN_ID, F.text.contains("uzum.uz"), ~F.text.startswith("/add"))
async def parser_handler(message: types.Message):
    wait = await message.answer("🔄 Uzum Marketdan ma'lumot o'qilyapti...")
    info = get_uzum_info(message.text)
    
    if info:
        products = load_products()
        info['id'] = len(products) + 1
        products.append(info)
        save_products(products)
        await wait.edit_text(f"✅ Savatga qo'shildi!\n\n📦 {info['name']}\n💰 Narxi: {info['price']:,} so'm")
    else:
        await wait.edit_text("❌ Kechirasiz, Uzumdan ma'lumotni olib bo'lmadi. Sayt bizni bloklagan bo'lishi mumkin.")

# Qo'lda qo'shish
@dp.message(F.from_user.id == ADMIN_ID, Command("add"))
async def manual_add(message: types.Message):
    try:
        # Format: /add iPhone 15 | 15000000 | https://image.jpg
        data = message.text.split("/add ")[1].split(" | ")
        products = load_products()
        item = {"id": len(products)+1, "name": data[0], "price": int(data[1]), "img": data[2]}
        products.append(item)
        save_products(products)
        await message.answer("✅ Mahsulot qo'lda muvaffaqiyatli qo'shildi!")
    except:
        await message.answer("❌ Xato! Format: `/add Nomi | Narxi | Rasm_linki`")

# --- SERVER QISMI (Render uchun) ---
async def handle_api(request):
    return web.json_response(load_products(), headers={"Access-Control-Allow-Origin": "*"})

async def main():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
