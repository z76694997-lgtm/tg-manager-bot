import sqlite3
from aiogram import Router, F, types
from aiogram.filters import Command
import config
import database
import keyboards

router = Router()

@router.callback_query(F.data == "stats")
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

@router.callback_query(F.data == "admin_view_all")
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

@router.callback_query(F.data == "help")
async def call_help(callback: types.CallbackQuery):
    await callback.message.answer("📝 **Памятка для Админа:**\n\n1. **Добавление:** Скинь файл `.session` как документ.\n\n2. **Установка пароля 2FA:**\n`/setpass [номер_без_плюса] [пароль]`\n\n3. **Подарок по номеру:**\n`/gift [ID_ПОЛЬЗОВАТЕЛЯ] [НОМЕР_БЕЗ_ПЛЮСА]`")
    await callback.answer()

@router.message(Command("setpass"))
async def set_password(message: types.Message):
    if message.from_user.id != config.ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("❌ Формат команды: `/setpass [номер] [пароль]`")
        return
    database.set_account_password(args[1], args[2])
    await message.answer(f"✅ Пароль 2FA для аккаунта `+{args[1]}` успешно сохранен!")

@router.callback_query(F.data == "user_my_accs")
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
        text += f"📱 Номер: `+{row[0]}`\n🆔 ID: `{row[3]}`\n🔑 Пароль: `{row[1]}`\n⚠️ СБ: {row[2]}\n-------------------\n"
    await callback.message.answer(text)
    await callback.answer()
  
