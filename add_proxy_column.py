import sqlite3

DB_NAME = "/root/vpn-bot/vpn_users.db"

def add_proxy_enabled_column():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE users ADD COLUMN proxy_enabled INTEGER DEFAULT 0")
        conn.commit()
        conn.close()
        print("✅ Успешно! Колонка 'proxy_enabled' добавлена.")
    except Exception as e:
        print(f"⚠️ Ошибка (возможно, колонка уже есть): {e}")

if __name__ == "__main__":
    add_proxy_enabled_column()
