from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
    
