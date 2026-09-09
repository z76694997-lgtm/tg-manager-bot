import psycopg2

# Твоя вечная облачная база данных со вшитым паролем
DB_URI = "postgresql://postgres:ZSadSad55%26%26%26@db.vldwbyvskptwubpvhuxn.supabase.co:5432/postgres"

def get_conn():
    return psycopg2.connect(DB_URI)

def init_db():
    """Создает таблицу в вечной облачной базе данных Supabase"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY,
        file_name TEXT,
        session_data_b64 TEXT, 
        phone TEXT DEFAULT 'Неизвестно',
        password TEXT DEFAULT 'Отсутствует',
        spamblock TEXT DEFAULT 'Не проверен',
        tg_id TEXT DEFAULT 'Неизвестно',
        status TEXT DEFAULT 'free',
        owner_id BIGINT DEFAULT NULL
    )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def add_account(file_name, b64_data, phone, tg_id, spamblock):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO accounts (file_name, session_data_b64, phone, tg_id, spamblock) VALUES (%s, %s, %s, %s, %s)",
        (file_name, b64_data, phone, tg_id, spamblock)
    )
    conn.commit()
    cursor.close()
    conn.close()

def set_account_password(phone, password):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET password=%s WHERE phone=%s", (password, phone))
    conn.commit()
    cursor.close()
    conn.close()

def get_free_account_by_phone(phone):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password FROM accounts WHERE phone=%s AND status='free'", (phone,))
    res = cursor.fetchone()
    cursor.close()
    conn.close()
    return res

def gift_account_to_user(acc_id, user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET status='gifted', owner_id=%s WHERE id=%s", (user_id, acc_id))
    conn.commit()
    cursor.close()
    conn.close()
    
