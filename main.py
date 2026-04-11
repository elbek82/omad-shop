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

# ------------------ NETWORK ------------------
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

async def download_image(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status == 200:
                    return await resp.read()
    except:
        return None
    return None

# ------------------ UZUM PARSER (PRO) ------------------
def extract_uzum(soup):
    try:
        script = soup.find("script", string=re.compile("__INITIAL_STATE__"))
        if not script:
            return None

        match = re.search(r'window\\.__INITIAL_STATE__\\s*=\\s*(\\{.*?\\});', script.string, re.DOTALL)
        if not match:
            return None

        data = json.loads(match.group(1))
        product = data.get('product', {}).get('payload', {}).get('data', {})

        photos = product.get("photos", [])
        img = None
        if photos:
            img = photos[0].get("high") or photos[0].get("low")

        return {
            "name": product.get("title"),
            "price": product.get("sellPrice") or product.get("lowPrice") or 0,
            "img": img
        }
    except Exception as e:
        print("UZUM ERROR:", e)
        return None

# ------------------ UNIVERSAL PARSER ------------------
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

    price = int(re.sub(r"\\D", "", price_text)) if price_text else 0

    return {"name": name, "price": price, "img": img}


async def parse_product(url):
    html = await fetch_html(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # 1. Uzum maxsus
    if "uzum.uz" in url:
        data = extract_uzum(soup)
        if data:
            return data

    # 2. JSON-LD universal
    data = extract_json_ld(soup)
    if data and data.get("name"):
        return data

    # 3. META fallback
    data = extract_meta(soup)
    if data.get("name"):
        return data

    return None

# ------------------ BOT ------------------
@dp.message()
async def handle_link(message: types.Message):
    print("📩 KELGAN XABAR:", message.text)
    print("👤 USER ID:", message.from_user.id)

    await message.answer("⏳ Ishlayapman...")

    url = message.text.strip()

    if "http" not in url:
        await message.answer("❌ Bu link emas")
        return

    try:
        info = await parse_product(url)
        print("📦 PARSED INFO:", info)

        if not info or not info.get("name"):
            await message.answer("❌ Parse bo‘lmadi")
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

        print("💾 SAQLANDI")

        img_bytes = await download_image(product["img"]) if product.get("img") else None

        if img_bytes:
            await message.answer_photo(
                photo=img_bytes,
                caption=f"✅ Qo‘shildi!\n\n{product['name']}\n💰 {product['price']}"
            )
        else:
            await message.answer(
                f"✅ Qo‘shildi (rasmsiz)\n\n{product['name']}\n💰 {product['price']}"
            )

    except Exception as e:
        print("❌ ERROR:", e)
        await message.answer(f"❌ Xato: {e}")

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
