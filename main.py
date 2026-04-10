import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo
from aiogram.filters import CommandStart

API_TOKEN = '8353606263:AAHLPpnuv5wCEmGHJexg1PAYAQomKpny-PY'
WEB_APP_URL = "https://omad-shop.vercel.app/" # 3-qadamdagi link

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    # Tugma orqali Web App-ni ochish
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(
                text="🛒 Do'konni ochish", 
                web_app=WebAppInfo(url=WEB_APP_URL)
            )]
        ],
        resize_keyboard=True
    )
    await message.answer("Xush kelibsiz! Quyidagi tugmani bosing:", reply_markup=markup)

# Web App ma'lumot yuborganda tutib olish
@dp.message(lambda message: message.web_app_data)
async def handle_webapp_data(message: types.Message):
    data = message.web_app_data.data
    await message.answer(f"Sizdan yangi xabar keldi: {data}\nTez orada operator bog'lanadi!")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())