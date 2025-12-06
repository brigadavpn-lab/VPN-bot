import sqlite3

DB_NAME = "/root/vpn-bot/vpn_users.db"

try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Добавляем колонку traffic_used (целое число, по умолчанию 0)
    cursor.execute("ALTER TABLE users ADD COLUMN traffic_used INTEGER DEFAULT 0")
    conn.commit()
    conn.close()
    print("Успешно! Колонка traffic_used добавлена.")
except Exception as e:
    print(f"Ошибка (возможно, колонка уже есть): {e}")
