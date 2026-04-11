import os
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command

# --- SOZLAMALAR ---
API_TOKEN = '8353606263:AAHLPpnuv5wCEmGHJexg1PAYAQomKpny-PY'
ADMIN_ID = 797324958  # Sizning ID raqamingiz
WEB_APP_URL = "https://omad-shop.vercel.app"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- MAHSULOTLARNI SAQLASH TIZIMI ---
def load_products():
    if os.path.exists('products.json'):
        with open('products.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_products(products):
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=4)

# --- UZUM PARSER ---
def get_uzum_info(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        name = soup.find('h1').get_text(strip=True)
        price_tag = soup.find('span', {'data-test-id': 'text-price'}) or soup.find('div', {'class': 'price'})
        price = int(''.join(filter(str.isdigit, price_tag.get_text())))
        img = soup.find('meta', property="og:image")['content']
        return {"name": name, "price": price, "img": img}
    except: return None

# --- ADMIN KLAVIATURASI ---
def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))],
            [KeyboardButton(text="➕ Mahsulot qo'shish (Uzum link)")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🗑 Hammasini o'chirish")]
        ],
        resize_keyboard=True
    )

# --- BUYRUQLAR ---
@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Xush kelibsiz, Admin!", reply_markup=get_admin_keyboard())
    else:
        markup = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
            resize_keyboard=True
        )
        await message.answer("Xush kelibsiz! Omad Auto do'koniga marhamat.", reply_markup=markup)

@dp.message(F.from_user.id == ADMIN_ID, Command("add"))
async def manual_add(message: types.Message):
    try:
        parts = message.text.replace("/add ", "").split(" | ")
        products = load_products()
        new_item = {"id": len(products)+1, "name": parts[0], "price": int(parts[1]), "img": parts[2]}
        products.append(new_item)
        save_products(products)
        await message.answer("✅ Qo'shildi! Endi saytni yangilang.")
    except:
        await message.answer("Xato! Format: `/add Nomi | Narxi | Rasm_linki`")

@dp.message(F.from_user.id == ADMIN_ID, F.text.contains("uzum.uz"))
async def auto_add(message: types.Message):
    wait = await message.answer("🔄 Uzumdan o'qilmoqda...")
    info = get_uzum_info(message.text)
    if info:
        products = load_products()
        info['id'] = len(products) + 1
        products.append(info)
        save_products(products)
        await wait.edit_text(f"✅ Qo'shildi: {info['name']}")
    else:
        await wait.edit_text("❌ Ma'lumot topilmadi.")

# --- API (SAYT UCHUN) ---
async def handle_api(request):
    return web.json_response(load_products(), headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

async def main():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    app.router.add_get("/", lambda r: web.Response(text="Bot is online!"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
