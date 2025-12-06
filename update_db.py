import sqlite3

# Путь к твоей базе
DB_NAME = "/root/vpn-bot/vpn_users.db"

def add_status_column():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Магическая команда SQL: "Добавь колонку status, и пусть у всех она сначала будет 'active'"
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        
        conn.commit()
        conn.close()
        print("✅ Успешно! Колонка 'status' добавлена.")
        
    except Exception as e:
        print(f"⚠️ Ошибка (возможно, колонка уже есть): {e}")

if __name__ == "__main__":
    add_status_column()