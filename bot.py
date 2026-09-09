import os, asyncio, sqlite3, base64, logging, threading, re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client
import config, database, keyboards, handlers

logging.basicConfig(level=logging.INFO)
database.init_db()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()
dp.include_router(handlers.router)
active_clients = {}

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-type", "text/plain"); self.end_headers()
        self.wfile.write(b"Live!")
    def log_message(self, format, *args): return

@dp.message(CommandStart())
async def start(message: types.Message):
    if message.from_user.id == config.ADMIN_ID:
        await message.answer("👑 Панель запущена. Все торговые и подарочные функции активны.", reply_markup=keyboards.admin_kb())
    else:
        await message.answer("👋 Привет! Добро пожаловать в магазин аккаунтов Telegram.", reply_markup=keyboards.user_kb())

@dp.message(Command("setprice"))
async def set_price(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат: `/setprice [номер_без_плюса] [цена]`")
        return
    database.set_account_price(args[1], int(args[2]))
    await message.answer(f"💰 Цена для аккаунта `+{args[1]}` успешно установлена: {args[2]} руб.")

@dp.message(F.document)
async def handle_document_upload(message: types.Message):
    if message.from_user.id != config.ADMIN_ID or not message.document.file_name.endswith(".session"): return
    status_msg = await message.answer("⏳ Проверяю спамблок...")
    file_info = await bot.get_file(message.document.file_id)
    file_bytes = await bot.download_file(file_info.file_path)
    b64_string = base64.b64encode(file_bytes.read()).decode('utf-8')
    temp_path = f"check_{message.from_user.id}"
    with open(f"{temp_path}.session", "wb") as f: f.write(base64.b64decode(b64_string))
    try:
        app = Client(temp_path, api_id=config.API_ID, api_hash=config.API_HASH)
        await app.start(); me = await app.get_me(); phone, tg_id = me.phone_number, str(me.id)
        spamblock = "Чистый"
        try:
            await app.send_message("SpamBot", "/start"); await asyncio.sleep(1)
            async for m in app.get_chat_history("SpamBot", limit=1):
                if "ограничения" in m.text.lower(): spamblock = "Есть спамблок"
        except: spamblock = "Неизвестно"
        await app.stop()
        database.add_account(message.document.file_name, b64_string, phone, tg_id, spamblock)
        await status_msg.edit_text(f"✅ Добавлен! `+{phone}` | СБ: {spamblock}\nНе забудь поставить цену: `/setprice {phone} ЦЕНА`")
    except Exception as e: await status_msg.edit_text(f"❌ Ошибка: {e}")
    if os.path.exists(f"{temp_path}.session"): os.remove(f"{temp_path}.session")

@dp.callback_query(F.data == "user_shop")
async def open_shop(callback: types.CallbackQuery):
    await callback.message.answer("🛒 **Выберите аккаунт для покупки:**", reply_markup=keyboards.shop_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_acc_"))
async def process_buy_account(callback: types.CallbackQuery):
    acc_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect(database.DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT phone, price FROM accounts WHERE id=?", (acc_id,))
    res = cursor.fetchone(); conn.close()
    if not res:
        await callback.answer("❌ Аккаунт уже продан или недоступен.", show_alert=True)
        return
    phone, price = res
    pay_url = f"https://yoomoney.ru{acc_id}&amount={price}&receiver=4100118578111088"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате (Карты/СБП)", url=pay_url)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="user_shop")]
    ])
    await callback.message.answer(
        f"💳 **Оформление заказа:**\n\n"
        f"📱 Выбранный номер: `+{phone}`\n"
        f"💰 Сумма к оплате: **{price} руб.**\n\n"
        f"⚠️ **ВАЖНО:** После оплаты напишите админу ваш ID: `{callback.from_user.id}` и номер `+{phone}`, чтобы он мгновенно выдал товар!",
        reply_markup=kb
    )
    await callback.answer()

@dp.message(Command("gift"))
async def gift_by_phone(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3: return
    target_user, phone = int(args[1]), args[2]
    res = database.get_free_account_by_phone(phone)
    if not res: return
    acc_id, password, _ = res
    database.gift_account_to_user(acc_id, target_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎁 Начать вход", callback_data=f"user_start_{acc_id}")]])
    await bot.send_message(chat_id=target_user, text=f"🎉 Вам сделан бесплатный подарок: `+{phone}`\n🔑 2FA Пароль: `{password}`", reply_markup=kb)
    await message.answer("✅ Аккаунт успешно подарен!")

@dp.message(Command("confirm"))
async def confirm_payment_and_issue(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат: `/confirm [номер_без_плюса] [ID_покупателя]`")
        return
    phone, target_user = args[1], int(args[2])
    res = database.get_free_account_by_phone(phone)
    if not res:
        await message.answer("❌ Свободный аккаунт с таким номером не найден.")
        return
    acc_id, password, _ = res
    database.gift_account_to_user(acc_id, target_user)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Начать вход в аккаунт", callback_data=f"user_start_{acc_id}")]])
    await bot.send_message(
        chat_id=target_user, 
        text=f"🛍 **Ваша оплата успешно подтверждена!**\n\n📱 Номер аккаунта: `+{phone}`\n🔑 Пароль двухфакторки (2FA): `{password}`\n\nНажмите кнопку ниже, чтобы запустить процедуру получения кода входа!",
        reply_markup=kb
    )
    await message.answer(f"✅ Оплата подтверждена. Аккаунт `+{phone}` успешно выдан покупателю `{target_user}`!")

@dp.callback_query(F.data.startswith("user_start_"))
async def user_start_login(callback: types.CallbackQuery):
    acc_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect(database.DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT session_data_b64, owner_id, phone FROM accounts WHERE id=?", (acc_id,))
    res = cursor.fetchone(); conn.close()
    if not res or res[1] != callback.from_user.id: return
    await callback.message.edit_text("⏳ Подключаемся к серверам Telegram...")
    temp_path = f"user_{callback.from_user.id}"
    with open(f"{temp_path}.session", "wb") as f: f.write(base64.b64decode(res[0]))
    try:
        app = Client(temp_path, api_id=config.API_ID, api_hash=config.API_HASH)
        await app.start(); active_clients[callback.from_user.id] = app
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔑 Получить код", callback_data=f"user_getcode_{acc_id}")]])
        await callback.message.answer(f"📱 Вводи номер `+{res[2]}` в приложении, дождись отправки СМС и жми кнопку:", reply_markup=kb)
    except Exception as e: await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()

@dp.callback_query(F.data.startswith("user_getcode_"))
async def user_get_code_msg(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in active_clients: return
    app = active_clients[user_id]
    try:
        async for dialog in app.get_dialogs(limit=10):
            if dialog.chat.id == 777000:
                code_match = re.search(r'\b\d{5}\b', dialog.top_message.text)
                if code_match:
                    await callback.message.answer(f"✉️ **Ваш код авторизации найден:** `{code_match.group(0)}`")
                    await app.stop(); del active_clients[user_id]
                    if os.path.exists(f"user_{user_id}.session"): os.remove(f"user_{user_id}.session")
                    return
        await callback.message.answer("⏳ Код еще не пришел, жми кнопку снова через 10 сек.")
    except Exception as e: await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.getenv("PORT", 8080))), HealthHandler).serve_forever(), daemon=True).start()
    asyncio.run(dp.start_polling(bot))
