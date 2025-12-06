import sqlite3

# --- НАСТРОЙКИ ---
DB_NAME = "/root/vpn-bot/vpn_users.db"

def get_size(bytes_value):
    """Превращает байты в красивые МБ или ГБ"""
    if bytes_value is None: bytes_value = 0
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0

def main():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        # Берем email и накопленный трафик
        cursor.execute("SELECT email, traffic_used FROM users")
        users = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Ошибка чтения БД: {e}")
        return

    if not users:
        print("База данных пуста.")
        return

    print(f"{'ПОЛЬЗОВАТЕЛЬ (EMAIL)':<40} | {'ТРАФИК (В БАЗЕ)':<20}")
    print("-" * 65)

    # Сортируем
    sorted_users = sorted(users, key=lambda x: x[1] if x[1] else 0, reverse=True)

    for email, total_bytes in sorted_users:
        human_size = get_size(total_bytes)
        print(f"{email:<40} | {human_size:<20}")

if __name__ == "__main__":
    main()
