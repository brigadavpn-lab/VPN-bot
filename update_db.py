import sqlite3

# Путь к базе данных
DB_NAME = "/root/vpn-bot/vpn_users.db"


def add_status_column():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        conn.commit()
        conn.close()
        print("✅ Колонка 'status' добавлена.")
    except Exception as e:
        print(f"⚠️ Колонка 'status' уже есть или ошибка: {e}")


def add_payment_type_column():
    """Добавляет колонку payment_type в таблицу users"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE users ADD COLUMN payment_type TEXT DEFAULT 'beta'")
        conn.commit()
        conn.close()
        print("✅ Колонка 'payment_type' добавлена.")
    except Exception as e:
        print(f"⚠️ Колонка 'payment_type' уже есть или ошибка: {e}")


def create_pending_payments_table():
    """Создаёт таблицу для хранения ожидающих платежей"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_payments (
                payment_id TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()
        conn.close()
        print("✅ Таблица 'pending_payments' создана.")
    except Exception as e:
        print(f"⚠️ Ошибка создания таблицы pending_payments: {e}")


def add_duration_hours_column():
    """Добавляет колонку duration_hours в pending_payments для хранения длительности тарифа"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE pending_payments ADD COLUMN duration_hours INTEGER DEFAULT 24")
        conn.commit()
        conn.close()
        print("✅ Колонка 'duration_hours' добавлена в pending_payments.")
    except Exception as e:
        print(f"⚠️ Колонка 'duration_hours' уже есть или ошибка: {e}")


if __name__ == "__main__":
    add_status_column()
    add_payment_type_column()
    create_pending_payments_table()
    add_duration_hours_column()
    print("✅ Миграция базы данных завершена.")
