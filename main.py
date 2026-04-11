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
        try: 
            data = json.load(f)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            return []
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

def clean_text(text):
    if not text: return ""
    text = text.split(' - ')[0].split(' | ')[0].split(' – ')[0]
    stop_words = ["uzum marketda", "uzum market", "sotib oling", "arzon narxlarda", "toshkentda", "ozon.ru", "ozon", "wildberries", "yandex market", "internet magazin", "dastavka"]
    lower_text = text.lower()
    for word in stop_words:
        text = re.sub(word, "", text, flags=re.IGNORECASE)
    return re.sub(' +', ' ', text).strip()

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
                if og_title: name = clean_text(og_title['content'])
                
                og_img = soup.find('meta', property='og:image')
                if og_img: img = og_img['content']
                
                og_desc = soup.find('meta', property='og:description')
                if og_desc: desc = clean_text(og_desc['content'])

                if shop_type == "uzum":
                    for script in soup.find_all('script', type='application/ld+json'):
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, list): data = data[0]
                            if data.get('@type') == 'Product':
                                name = clean_text(data.get('name', name))
                                desc = clean_text(data.get('description', desc))
                                offers = data.get('offers', {})
                                if isinstance(offers, dict):
                                    price = int(float(offers.get('price', 0)))
                                break
                        except: pass
                
                if name:
                    if not desc: desc = f"AVTO 6707 maxsus taklifi."
                    return {"name": name, "price": price, "img": img, "description": desc, "source": shop_type}
        except Exception as e:
            print(f"Parse xato: {e}")
    return None

# ========== BOT HANDLERLARI ==========
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    button = KeyboardButton("🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add(button)
    
    # MUHIM O'ZGARISH: Mijozga boshqa, Adminga boshqa xabar ketadi!
    if message.from_user.id == ADMIN_ID:
        await message.reply("👨‍💻 Assalomu alaykum, Admin!\n\nDo'kon boshqaruviga xush kelibsiz. Mahsulot qo'shish uchun ssilkani yuboring.", reply_markup=markup)
    else:
        await message.reply("👋 Assalomu alaykum! AVTO 6707 onlayn do'koniga xush kelibsiz!\n\n🚗 Avtomobilingiz uchun eng sifatli aksessuarlar va jihozlar aynan bizda.\n\n👇 Xaridni boshlash uchun pastdagi «🛒 Do'konni ochish» tugmasini bosing!", reply_markup=markup)

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('/narx'))
async def update_price(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        product_id = int(parts[1])
        new_price = int(parts[2])
        products = load_products()
        for p in products:
            if isinstance(p, dict) and p.get('id') == product_id:
                p['price'] = new_price
                save_products(products)
                await message.reply(f"✅ Narx {new_price:,} so'm bo'ldi.")
                return
    except: await message.reply("❌ Xato: /narx ID SUMMA")

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('/nom'))
async def update_name(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        product_id = int(parts[1])
        new_name = parts[2]
        products = load_products()
        for p in products:
            if isinstance(p, dict) and p.get('id') == product_id:
                p['name'] = new_name
                save_products(products)
                await message.reply(f"✅ Nom o'zgardi:\n{new_name}")
                return
    except: await message.reply("❌ Xato: /nom ID YANGI_NOM")

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('/tavsif'))
async def update_desc(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        product_id = int(parts[1])
        new_desc = parts[2]
        products = load_products()
        for p in products:
            if isinstance(p, dict) and p.get('id') == product_id:
                p['description'] = new_desc
                save_products(products)
                await message.reply(f"✅ Tavsif o'zgardi.")
                return
    except: await message.reply("❌ Xato: /tavsif ID YANGI_MATN")

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('/kat'))
async def update_category(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        product_id = int(parts[1])
        new_cat = parts[2]
        products = load_products()
        for p in products:
            if isinstance(p, dict) and p.get('id') == product_id:
                p['category'] = new_cat
                save_products(products)
                await message.reply(f"✅ {product_id}-mahsulot '{new_cat}' kategoriyasiga o'tdi.")
                return
        await message.reply("❌ Bunday ID topilmadi.")
    except: await message.reply("❌ Xato format. Misol: /kat 1 Asboblar")

@dp.message_handler(lambda msg: msg.from_user.id == ADMIN_ID and msg.text.startswith('http'))
async def handle_link(message: types.Message):
    url = message.text
    shop_type = check_url_type(url)
    if not shop_type: return
        
    wait_msg = await message.reply(f"🔄 Yuklanmoqda...")
    info = await parse_universal(url, shop_type)
    
    if info and info.get('name'):
        products = load_products()
        new_id = max([p.get('id', 0) for p in products if isinstance(p, dict)], default=0) + 1
        new_product = {
            "id": new_id,
            "name": info['name'],
            "price": info.get('price', 0),
            "img": info.get('img', ''),
            "description": info.get('description', ''),
            "source": info.get('source', ''),
            "category": "Boshqa" 
        }
        products.append(new_product)
        save_products(products)
        
        # TAVSIF BU YERGA QO'SHILDI
        caption = f"✅ Qo‘shildi!\n🆔 ID: {new_id}\n🛍 {new_product['name']}\n\nO'zgartirish uchun:\n/narx {new_id} SUMMA\n/nom {new_id} NOM\n/tavsif {new_id} TAVSIF MATNI\n/kat {new_id} KATEGORIYA"
        
        if new_product['img']: await message.reply_photo(photo=new_product['img'], caption=caption)
        else: await message.reply(caption)
        await wait_msg.delete()

# Faqat mijozlarning adashib yozgan xabarlari uchun
@dp.message_handler(lambda msg: msg.from_user.id != ADMIN_ID)
async def ignore_others(message: types.Message):
    # Mijoz nimadir yozsa bot indamaydi, faqat knopka turadi
    pass
# ===== YANGI: BUYURTMALARNI QABUL QILISH =====
@dp.message_handler(content_types=['web_app_data'])
async def web_app_data_handler(message: types.Message):
    try:
        # Web App dan kelgan JSON ma'lumotni o'qiymiz
        data = json.loads(message.web_app_data.data)
        
        if data.get('action') == 'new_order':
            phone = data.get('phone')
            address = data.get('address')
            items = data.get('items', [])
            
            # Adminga (Sizga) boradigan chek
            text = f"🆕 YANGI BUYURTMA!\n\n"
            text += f"👤 Mijoz: {message.from_user.full_name} (@{message.from_user.username})\n"
            text += f"📞 Tel: {phone}\n"
            text += f"📍 Manzil: {address}\n\n"
            text += "🛍 Sotib olindi:\n"
            
            total = 0
            for item in items:
                text += f"▫️ {item['name']} x1 ({item['price']:,} so'm)\n"
                total += int(item['price'])
                
            text += f"\n💰 Jami to'lov: {total:,} so'm"
            
            # Sizga (Adminga) xabar yuborish
            await bot.send_message(ADMIN_ID, text)
            
            # Mijozning o'ziga tasdiq xabari yuborish
            if message.from_user.id != ADMIN_ID:
                await message.reply(f"✅ Buyurtmangiz qabul qilindi!\nTez orada {phone} raqamiga aloqaga chiqamiz.")
            else:
                await message.reply("✅ Test buyurtma: O'zingizga o'zingiz buyurtma berdingiz!")
                
    except Exception as e:
        print(f"Buyurtma qabul qilishda xato: {e}")
# ========== API VA SERVER QISMI ==========
async def handle_api(request):
    products = load_products()
    return web.json_response(products, headers={'Access-Control-Allow-Origin': '*'})

async def handle_index(request):
    return web.Response(text="API ishlayapti.", status=200)

async def run_api():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/products", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    await asyncio.Event().wait()

async def main():
    asyncio.create_task(run_api())
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
