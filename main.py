import os
import json
import asyncio
import re
import uuid
import aiohttp
from bs4 import BeautifulSoup
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://example.com")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DATA_FILE = "products.json"
LOCK = asyncio.Lock()

# ------------------ STORAGE ------------------
async def load_products():
    if not os.path.exists(DATA_FILE):
        return []
    async with LOCK:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

async def save_products(data):
    async with LOCK:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

# ------------------ UNIVERSAL PARSER ------------------
async def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=20) as resp:
            if resp.status != 200:
                return None
            return await resp.text()


def extract_json_ld(soup):
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "Product":
                return {
                    "name": data.get("name"),
                    "price": int(float(data.get("offers", {}).get("price", 0))),
                    "img": data.get("image")
                }
        except:
            continue
    return None


def extract_meta(soup):
    def get(prop):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return tag.get("content") if tag else None

    name = get("og:title")
    img = get("og:image")
    price_text = get("product:price:amount")

    price = int(re.sub(r"\D", "", price_text)) if price_text else 0

    return {"name": name, "price": price, "img": img}


async def parse_product(url):
    html = await fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # 1. JSON-LD (best universal method)
    data = extract_json_ld(soup)
    if data and data.get("name"):
        return data

    # 2. Meta fallback
    data = extract_meta(soup)
    if data.get("name"):
        return data

    return None

# ------------------ BOT ------------------
@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="🛒 Open Shop")]],
        resize_keyboard=True
    )
    await message.answer("Send product link (any site)", reply_markup=markup)


@dp.message(F.from_user.id == ADMIN_ID)
async def handle_link(message: types.Message):
    if not message.text.startswith("http"):
        return

    wait = await message.answer("⏳ Loading...")

    try:
        info = await parse_product(message.text)

        if not info:
            await wait.edit_text("❌ Could not parse this site")
            return

        products = await load_products()

        product = {
            "id": str(uuid.uuid4()),
            "name": info["name"],
            "price": info.get("price", 0),
            "img": info.get("img"),
        }

        products.append(product)
        await save_products(products)

        await message.answer_photo(
            photo=product["img"],
            caption=f"✅ Added\n\n{product['name']}\n💰 {product['price']}"
        )
        await wait.delete()

    except Exception as e:
        await wait.edit_text(f"❌ Error: {e}")

# ------------------ API ------------------
async def handle_api(request):
    products = await load_products()
    return web.json_response(products)


async def main():
    app = web.Application()
    app.router.add_get("/api/products", handle_api)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
