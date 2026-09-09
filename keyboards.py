import sqlite3
import database
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика базы", callback_data="stats")],
        [InlineKeyboardButton(text="📱 Список всех номеров", callback_data="admin_view_all")],
        [InlineKeyboardButton(text="📥 Инструкция", callback_data="help")]
    ])

def user_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазин аккаунтов", callback_data="user_shop")],
        [InlineKeyboardButton(text="🎁 Мои покупки", callback_data="user_my_accs")]
    ])

def shop_kb():
    """Генерирует витрину со всеми доступными номерами и их ценами"""
    conn = sqlite3.connect(database.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, phone, price FROM accounts WHERE status='free'")
    rows = cursor.fetchall()
    conn.close()
    
    buttons = []
    for row in rows:
        # Кнопка вида: "+79991234567 | 150 руб."
        buttons.append([InlineKeyboardButton(text=f"📱 +{row[1]} | 💰 {row[2]} руб.", callback_data=f"buy_acc_{row[0]}")])
        
    if not buttons:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📭 Аккаунтов нет в наличии", callback_data="empty_shop")]])
        
    return InlineKeyboardMarkup(inline_keyboard=buttons)
    
