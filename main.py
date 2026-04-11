import os
import json
import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from aiohttp import web
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== KONFIG ==========
BOT_TOKEN = "8353606263:AAFdwZSNdYmK5Qfaj8TAlmfj-RIG-JiuKpU"
ADMIN_ID = 797324958  # O‘z ID-raqamingiz
WEB_APP_URL = "https://omad-shop-1.onrender.com"
DATA_FILE = "products.json"

# ========== YORDAMCHI ==========
async def load_products():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except:
            return []

async def save_products(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def is_uzum_url(url):
    return re.match(r'https?://(www\.)?uzum\.uz/uz/product/[a-zA-Z0-9\-]+', url) is not None

async def parse_uzum(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession() as session:
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
            return None

# ========== BOT HANDLERLAR ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button = KeyboardButton(text="🛒 Do'konni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True)
    await update.message.reply_text("Assalomu alaykum! Admin Uzum linki yuboring.", reply_markup=reply_markup)

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Siz admin emassiz.")
        return
    url = update.message.text
    if not is_uzum_url(url):
        await update.message.reply_text("❌ Faqat Uzum mahsulot linki.")
        return
    wait = await update.message.reply_text("🔄 Parse qilinmoqda...")
    info = await parse_uzum(url)
    if info and info.get('name') and info.get('price'):
        products = await load_products()
        new_id = max([p.get('id',0) for p in products], default=0) + 1
        new_product = {
            "id": new_id,
            "name": info['name'],
            "price": info['price'],
            "img": info.get('img', ''),
            "description": f"{info['name']} — sifatli avto aksessuar"
        }
        products.append(new_product)
        await save_products(products)
        await update.message.reply_photo(
            photo=new_product['img'],
            caption=f"✅ Qo‘shildi!\n\n{new_product['name']}\n💰 {new_product['price']:,} so'm"
        )
        await wait.delete()
    else:
        await wait.edit_text("❌ Ma'lumot olinmadi.")

# ========== API ==========
async def handle_api(request):
    products = await load_products()
    return web.json_response(products, headers={'Access-Control-Allow-Origin': '*'})

async def run_api():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"API server {port}-portda ishlayapti")
    await asyncio.Future()  # abadiy ishlaydi

# ========== MAIN ==========
async def main():
    # Bot
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    # API ni parallel ishga tushirish
    loop = asyncio.get_event_loop()
    loop.create_task(run_api())
    # Bot polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Future()  # to‘xtamasin

if __name__ == "__main__":
    asyncio.run(main())
