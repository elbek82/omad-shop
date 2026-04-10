import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

# TOKEN va URL ni o'zingiznikiga almashtiring
API_TOKEN = '8353606263:AAHLPpnuv5wCEmGHJexg1PAYAQomKpny-PY'
WEB_APP_URL = "https://omad-shop.vercel.app/"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: types.Message):
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🛒 Do'kon", web_app=WebAppInfo(url=WEB_APP_URL))]
        ],
        resize_keyboard=True
    )
    await message.answer("Salom! Do'konimizga xush kelibsiz!", reply_markup=markup)

# --- RENDER UCHUN MAXSUS QISM ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    # Render portini sozlash
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Bot {port}-portda ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
