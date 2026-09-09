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
    await callback.message.answer(f"📈 **Состояние базы:**\n\n🟢 В наличии: `{free}` шт.\n🔴 Продано/Подарено: `{gifted}` шт.")
    await callback.answer()

@router.callback_query(F.data == "admin_view_all")
async def admin_view_all(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID: return
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, price, spamblock, status FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.answer("❌ В базе пока нет ни одного аккаунта.")
        await callback.answer()
        return
        
    text = "📋 **Список всех аккаунтов в системе:**\n\n"
    for row in rows:
        icon = "🟢" if row[3] == 'free' else "🔴"
        text += f"{icon} `+{row[0]}` | Цена: {row[1]}₽ | СБ: {row[2]}\n"
    await callback.message.answer(text)
    await callback.answer()

@router.callback_query(F.data == "help")
async def call_help(callback: types.CallbackQuery):
    await callback.message.answer("📝 **Памятка для Админа:**\n\n1. **Добавление:** Скинь файл `.session`.\n\n2. **Установка ЦЕНЫ:**\n`/setprice [номер] [цена]`\nПример: `/setprice 79991234567 150`\n\n3. **Установка ПАРОЛЯ 2FA:**\n`/setpass [номер] [пароль]`\n\n4. **ПОДАРЯТЬ БЕСПЛАТНО:**\n`/gift [ID_ЮЗЕРА] [НОМЕР]`\n\n5. **ПОДТВЕРДИТЬ ОПЛАТУ (ВЫДАЧА):**\n`/confirm [НОМЕР] [ID_ЮЗЕРА]`")
    await callback.answer()

@router.callback_query(F.data == "user_my_accs")
async def user_my_accounts(callback: types.CallbackQuery):
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, password, spamblock FROM accounts WHERE owner_id=?", (callback.from_user.id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.answer("😢 У вас пока нет купленных или полученных аккаунтов.")
        await callback.answer()
        return
        
    text = "🎁 **Ваши аккаунты:**\n\n"
    for row in rows:
        text += f"📱 Номер: `+{row[0]}`\n🔑 Пароль 2FA: `{row[1]}`\n⚠️ СБ: {row[2]}\n-------------------\n"
    await callback.message.answer(text)
    await callback.answer()
    
