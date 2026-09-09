import os
import asyncio
import sqlite3
import base64
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logging.basicConfig(level=logging.INFO)

# Ваши данные
BOT_TOKEN = "8876639758:AAFXOoDLyFd2C9B90QQlGRsd4-RnUMvqiZo"
ADMIN_ID = 8669477816

# --- ЗАГЛУШКА ДЛЯ RENDER (ВЕБ-СЕРВЕР) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

    def log_message(self, format, *args):
        return  # Отключаем лишние логи в консоли Render

def run_health_server():
    # Render автоматически дает порт в переменную PORT, если её нет - берем 8080
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logging.info(f"Фоновый веб-сервер запущен на порту {port}")
    server.serve_forever()

# --- БАЗА ДАННЫХ ---
conn = sqlite3.connect("manager.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT,
    session_data_b64 TEXT, 
    status TEXT DEFAULT 'free',
    owner_id INTEGER DEFAULT NULL
)
""")
conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика базы", callback_data="stats")],
        [InlineKeyboardButton(text="📥 Инструкция", callback_data="help")]
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Привет, Админ! Я успешно запущен в облаке Render и готов к работе.", reply_markup=admin_kb())
    else:
        await message.answer("👋 Привет! Я бот раздачи аккаунтов. Жди подарок от админа!")

@dp.callback_query()
async def call_queries(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    
    if callback.data == "stats":
        cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='free'")
        free = cursor.fetchone()
        await callback.message.answer(f"🟢 Свободных аккаунтов в базе: {free[0]}")
    elif callback.data == "help":
        await callback.message.answer("Просто отправь мне файл `.session` как документ. Я переведу его в текст и сохраню навсегда!")
    await callback.answer()

@dp.message(F.document)
async def get_document(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.document.file_name.endswith(".session"):
        await message.answer("❌ Нужен только файл `.session`!")
        return
        
    file_info = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    
    b64_string = base64.b64encode(file_bytes.read()).decode('utf-8')
    
    try:
        cursor.execute(
            "INSERT INTO accounts (file_name, session_data_b64) VALUES (?, ?)", 
            (message.document.file_name, b64_string)
        )
        conn.commit()
        await message.answer(f"✅ Аккаунт `{message.document.file_name}` успешно засейвлен в текстовую базу!")
    except Exception as e:
        await message.answer(f"❌ Ошибка сохранения: {e}")

async def main():
    # Запускаем веб-сервер в отдельном независимом потоке
    threading.Thread(target=run_health_server, daemon=True).start()
    
    # Запускаем самого Telegram бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
