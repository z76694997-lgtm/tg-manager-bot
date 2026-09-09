import sqlite3

DB_NAME = "manager.db"

def init_db():
    """Создает локальную таблицу прямо на сервере Render"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_name TEXT,
        session_data_b64 TEXT, 
        phone TEXT DEFAULT 'Неизвестно',
        password TEXT DEFAULT 'Отсутствует',
        spamblock TEXT DEFAULT 'Не проверен',
        tg_id TEXT DEFAULT 'Неизвестно',
        status TEXT DEFAULT 'free',
        owner_id INTEGER DEFAULT NULL
    )
    """)
    conn.commit()
    conn.close()

def add_account(file_name, b64_data, phone, tg_id, spamblock):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO accounts (file_name, session_data_b64, phone, tg_id, spamblock) VALUES (?, ?, ?, ?, ?)",
        (file_name, b64_data, phone, tg_id, spamblock)
    )
    conn.commit()
    conn.close()

def set_account_password(phone, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET password=? WHERE phone=?", (password, phone))
    conn.commit()
    conn.close()

def get_free_account_by_phone(phone):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM accounts WHERE phone=? AND status='free'", (phone,))
    res = cursor.fetchone()
    conn.close()
    return res

def gift_account_to_user(acc_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET status='gifted', owner_id=? WHERE id=?", (user_id, acc_id))
    conn.commit()
    conn.close()
    
