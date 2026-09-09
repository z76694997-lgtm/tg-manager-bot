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

# Фикс для корректного создания цикла событий до импорта Pyrogram
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client

# Импортируем наши настройки и функции бд
import config
import database

logging.basicConfig(level=logging.INFO)

# Инициализируем базу данных
database.init_db()

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
active_clients = {}

# --- ВЕБ-ЗАГЛУШКА ДЛЯ SERVA ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot, Database, and Login Engine are Running Live!")
    def log_message(self, format, *args): return

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthCheckHandler).serve_forever()

# --- КЛАВИАТУРЫ ---
def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика базы", callback_data="stats")],
        [InlineKeyboardButton(text="📱 Список всех номеров", callback_data="admin_view_all")],
        [InlineKeyboardButton(text="📥 Инструкция", callback_data="help")]
    ])

def user_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Мои аккаунты", callback_data="user_my_accs")]
    ])

# --- ОБРАБОТЧИКИ (ХЕНДЛЕРЫ) ---

@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id == config.ADMIN_ID:
        await message.answer("👑 Админ-панель активна. Доступен авточек спамблока, ручной ввод 2FA и подарки по номерам.", reply_markup=admin_kb())
    else:
        await message.answer("👋 Привет! Это бот хранения и раздачи аккаунтов.\nПосмотреть список своих подарков можно по кнопке ниже:", reply_markup=user_kb())

@dp.callback_query(F.data == "stats")
async def call_stats(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID: return
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='free'")
    free = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='gifted'")
    gifted = cursor.fetchone()[0]
    conn.close()
    
    await callback.message.answer(f"📈 **Состояние базы:**\n\n🟢 Готовы к выдаче: `{free}` шт.\n🔴 Уже подарены: `{gifted}` шт.")
    await callback.answer()

@dp.callback_query(F.data == "admin_view_all")
async def admin_view_all(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID: return
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, spamblock, status FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.answer("❌ В базе пока нет ни одного аккаунта.")
        await callback.answer()
        return
        
    text = "📋 **Список всех аккаунтов в системе:**\n\n"
    for row in rows:
        icon = "🟢" if row[2] == 'free' else "🔴"
        text += f"{icon} `+{row[0]}` | СБ: {row[1]} | {row[2]}\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "help")
async def call_help(callback: types.CallbackQuery):
    await callback.message.answer("📝 **Памятка для Админа:**\n\n1. **Добавление:** Скинь файл `.session` как документ. Бот зайдет в него, считает номер, ID и проверит спамблок.\n\n2. **Установка пароля 2FA:**\n`/setpass [номер_без_плюса] [пароль]`\nПример: `/setpass 79991234567 pass123`\n\n3. **Подарок по номеру:**\n`/gift [ID_ПОЛЬЗОВАТЕЛЯ] [НОМЕР_БЕЗ_ПЛЮСА]`\nПример: `/gift 8669477816 79991234567`")
    await callback.answer()

@dp.message(Command("setpass"))
async def set_password(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат команды: `/setpass [номер_без_плюса] [пароль]`")
        return
    database.set_account_password(args[1], args[2])
    await message.answer(f"✅ Пароль 2FA для аккаунта `+{args[1]}` успешно сохранен!")

@dp.message(F.document)
async def handle_document_upload(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    if not message.document.file_name.endswith(".session"):
        await message.answer("❌ Бот принимает только файлы `.session`!")
        return
        
    status_msg = await message.answer("⏳ Анализирую файл, подключаюсь к Telegram и проверяю спамблок...")
    
    file_info = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    b64_string = base64.b64encode(file_bytes.read()).decode('utf-8')
    
    temp_path = "check_temp"
    with open(f"{temp_path}.session", "wb") as f:
        f.write(base64.b64decode(b64_string))
        
    try:
        app = Client(temp_path, api_id=config.API_ID, api_hash=config.API_HASH)
        await app.start()
        
        me = await app.get_me()
        phone = me.phone_number
        tg_id = str(me.id)
        
        spamblock = "Чистый"
        try:
            await app.send_message("SpamBot", "/start")
            await asyncio.sleep(1)
            async for msg in app.get_chat_history("SpamBot", limit=1):
                if "ограничения" in msg.text.lower() or "ограничен" in msg.text.lower():
                    spamblock = "Есть спамблок"
        except Exception:
            spamblock = "Неизвестно"
            
        await app.stop()
        
        database.add_account(message.document.file_name, b64_string, phone, tg_id, spamblock)
        
        await status_msg.edit_text(
            f"✅ **Аккаунт успешно занесен в базу!**\n\n"
            f"📱 Номер: `+{phone}`\n"
            f"🆔 ID: `{tg_id}`\n"
            f"⚠️ Спамблок: **{spamblock}**\n\n"
            f"Если нужен пароль 2FA, привяжи его: `/setpass {phone} ПАРОЛЬ`"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка проверки сессии (возможно, файл невалидный): {e}")
        
    if os.path.exists(f"{temp_path}.session"):
        os.remove(f"{temp_path}.session")

@dp.message(Command("gift"))
async def gift_by_phone(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат команды: `/gift [ID_ПОЛЬЗОВАТЕЛЯ] [НОМЕР_БЕЗ_ПЛЮСА]`")
        return
        
    target_user, phone = int(args[1]), args[2]
    res = database.get_free_account_by_phone(phone)
    
    if not res:
        await message.answer(f"❌ Свободный аккаунт с номером `+{phone}` не найден в базе!")
        return
        
    acc_id, password = res
    database.gift_account_to_user(acc_id, target_user)
    
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Начать вход в аккаунт", callback_data=f"user_start_{acc_id}")]
        ])
        await bot.send_message(
            chat_id=target_user,
            text=f"🎉 **Вам сделали подарок!**\nАдмин передал вам аккаунт: `+{phone}`\n\nПароль двухфакторки (2FA): `{password}`\n\nНажми кнопку под сообщением, чтобы начать авторизацию на устройстве!",
            reply_markup=kb
        )
        await message.answer(f"✅ Номер `+{phone}` успешно передан пользователю `{target_user}`!")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки уведомления: {e}")

@dp.callback_query(F.data == "user_my_accs")
async def user_my_accounts(callback: types.CallbackQuery):
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, password, spamblock, tg_id FROM accounts WHERE owner_id=?", (callback.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.answer("😢 У вас пока нет полученных аккаунтов.")
        await callback.answer()
        return
        
    text = "🎁 **Ваши полученные аккаунты:**\n\n"
    for row in rows:
        text += (
            f"📱 Номер: `+{row[0]}`\n"
            f"🆔 ID аккаунта: `{row[3]}`\n"
            f"🔑 Пароль 2FA: `{row[1]}`\n"
            f"⚠️ Статус СБ: {row[2]}\n"
            f"---------------------------\n"
        )
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data.startswith("user_start_"))
async def user_start_login(callback: types.CallbackQuery):
    acc_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT session_data_b64, owner_id, phone FROM accounts WHERE id=?", (acc_id,))
    res = cursor.fetchone()
    conn.close()
    
    if not res or res[1] != callback.from_user.id:
        await callback.answer("❌ Доступ ограничен.", show_alert=True)
        return
        
    await callback.message.edit_text("⏳ Подключаемся к серверам Telegram для выдачи кодов...")
    
    temp_path = f"user_{callback.from_user.id}"
    with open(f"{temp_path}.session", "wb") as f:
        f.write(base64.b64decode(res[0]))
        
    try:
        app = Client(temp_path, api_id=config.API_ID, api_hash=config.API_HASH)
        await app.start()
        active_clients[callback.from_user.id] = app
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Получить код подтверждения", callback_data=f"user_getcode_{acc_id}")]
        ])
        await callback.message.answer(
