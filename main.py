import os
import json
import asyncio
import re
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import WebAppInfo
import uuid

# ========== KONFIGURATSIYA ==========
API_TOKEN = "8353606263:AAEujCWfm17TocnBXZ_TLcfC5DQkcsrV7Q0"
ADMIN_ID = 797324958   # <-- O‘z Telegram ID-raqamingizni yozing (raqam)
WEB_APP_URL = "https://omad-shop-1.onrender.com"   # Frontend URL (Render sizga beradi)
DATA_FILE = "products.json"
STATIC_DIR = "static"

# Papkani avtomatik yaratamiz (agar mavjud bo'lmasa)
os.makedirs(STATIC_DIR, exist_ok=True)

# ========== GLOBAL ==========
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
lock = asyncio.Lock()
session = None

# ========== FSM (qo‘lda qo‘shish) ==========
class AddProductStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_category = State()

# ========== YORDAMCHI FUNKSIYALAR ==========
async def load_products():
    async with lock:
        if not os.path.exists(DATA_FILE):
            return []
        try:
            async with aiofiles.open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else []
        except:
            return []

async def save_products(data):
    async with lock:
        async with aiofiles.open(DATA_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))

def is_valid_uzum_url(url: str) -> bool:
    return re.match(r'https?://(www\.)?uzum\.uz/uz/product/[a-zA-Z0-9\-]+', url) is not None

async def download_image(url: str, filename: str) -> str:
    """Rasmni URL dan yuklab, static papkaga saqlaydi"""
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                filepath = os.path.join(STATIC_DIR, filename)
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(await resp.read())
                return f"/static/{filename}"
    except Exception as e:
        print(f"Rasm yuklashda xato: {e}")
    return None

async def get_uzum_info(url: str):
    global session
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        async with session.get(url, timeout=15) as response:
            if response.status != 200:
                return None
            html = await response.text()
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
            return None
    except Exception as e:
        print(f"Uzum parse xatosi: {e}")
        return None

# ========== TELEGRAM HANDLERLAR ==========
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]],
        resize_keyboard=True
    )
    await message.answer(
        "Assalomu alaykum! Admin:\n• Uzum linki yuboring\n• Yoki /addproduct buyrug‘i bilan qo‘lda mahsulot qo‘shing",
        reply_markup=markup
    )

@dp.message(Command("addproduct"), F.from_user.id == ADMIN_ID)
async def cmd_add_product(message: types.Message, state: FSMContext):
    await message.answer("📸 Mahsulot rasmini yuboring (foto)")
    await state.set_state(AddProductStates.waiting_for_photo)

@dp.message(AddProductStates.waiting_for_photo, F.photo, F.from_user.id == ADMIN_ID)
async def receive_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    ext = file.file_path.split('.')[-1] if '.' in file.file_path else 'jpg'
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    local_path = os.path.join(STATIC_DIR, unique_name)
    await bot.download_file(file.file_path, local_path)
    await state.update_data(img_url=f"/static/{unique_name}")
    await message.answer("✅ Rasm saqlandi. Endi mahsulot **nomi**ni yuboring:")
    await state.set_state(AddProductStates.waiting_for_name)

@dp.message(AddProductStates.waiting_for_name, F.from_user.id == ADMIN_ID)
async def receive_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("💰 **Narxini** faqat raqamda yuboring (so‘m):")
    await state.set_state(AddProductStates.waiting_for_price)

@dp.message(AddProductStates.waiting_for_price, F.from_user.id == ADMIN_ID)
async def receive_price(message: types.Message, state: FSMContext):
    try:
        price = int(re.sub(r'[^\d]', '', message.text))
        await state.update_data(price=price)
        await message.answer("📝 **Tavsif** (description) yozing:")
        await state.set_state(AddProductStates.waiting_for_description)
    except:
        await message.answer("❌ Faqat raqam kiriting. Masalan: 150000")

@dp.message(AddProductStates.waiting_for_description, F.from_user.id == ADMIN_ID)
async def receive_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Salon uchun")],
            [types.KeyboardButton(text="Tashqi ko'rinish")],
            [types.KeyboardButton(text="Elektronika")],
            [types.KeyboardButton(text="Himoya")],
            [types.KeyboardButton(text="Boshqa")]
        ],
        resize_keyboard=True
    )
    await message.answer("🏷️ Kategoriyani tanlang:", reply_markup=markup)
    await state.set_state(AddProductStates.waiting_for_category)

@dp.message(AddProductStates.waiting_for_category, F.from_user.id == ADMIN_ID)
async def receive_category(message: types.Message, state: FSMContext):
    cat_map = {
        "Salon uchun": "interior",
        "Tashqi ko'rinish": "exterior",
        "Elektronika": "electronics",
        "Himoya": "protection",
        "Boshqa": "other"
    }
    cat = cat_map.get(message.text, "other")
    data = await state.get_data()
    products = await load_products()
    new_id = max([p.get('id',0) for p in products], default=0) + 1
    new_product = {
        "id": new_id,
        "name": data['name'],
        "price": data['price'],
        "img": data['img_url'],
        "description": data['description'],
        "category": cat
    }
    products.append(new_product)
    await save_products(products)
    await message.answer(
        f"✅ Mahsulot qo‘shildi!\n\n{new_product['name']}\n💰 {new_product['price']:,} so'm",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith("http"))
async def handle_uzum_link(message: types.Message):
    if not is_valid_uzum_url(message.text):
        await message.answer("❌ Faqat Uzum mahsulot linki qabul qilinadi.")
        return
    wait = await message.answer("🔄 Parse qilinmoqda...")
    info = await get_uzum_info(message.text)
    if info and info.get('name') and info.get('price'):
        products = await load_products()
        new_id = max([p.get('id',0) for p in products], default=0) + 1
        img_url = info['img']
        if img_url and img_url.startswith('http'):
            ext = img_url.split('.')[-1].split('?')[0]
            if ext not in ['jpg','jpeg','png','webp']:
                ext = 'jpg'
            fname = f"{uuid.uuid4().hex}.{ext}"
            saved_path = await download_image(img_url, fname)
            if saved_path:
                img_url = saved_path
        new_product = {
            "id": new_id,
            "name": info['name'],
            "price": info['price'],
            "img": img_url,
            "description": f"{info['name']} — sifatli avto aksessuar",
            "category": "interior"
        }
        products.append(new_product)
        await save_products(products)
        await message.answer_photo(
            photo=new_product['img'],
            caption=f"✅ Uzumdan qo‘shildi!\n\n{new_product['name']}\n💰 {new_product['price']:,} so'm"
        )
        await wait.delete()
    else:
        await wait.edit_text("❌ Uzumdan ma'lumot olinmadi.")

# ========== API VA STATIC HANDLERLAR ==========
async def handle_api(request):
    products = await load_products()
    return web.json_response(products, headers={'Access-Control-Allow-Origin': '*'})

async def handle_static(request):
    filename = request.match_info['filename']
    filepath = os.path.join(STATIC_DIR, filename)
    if os.path.exists(filepath):
        return web.FileResponse(filepath)
    return web.Response(status=404)

# ========== MAIN ==========
async def main():
    global session, lock
    lock = asyncio.Lock()
    session = aiohttp.ClientSession()
    
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    app.router.add_get("/static/{filename}", handle_static)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"API + static server {port}-portda ishga tushdi")
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi")
    try:
        await dp.start_polling(bot)
    finally:
        await session.close()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())
