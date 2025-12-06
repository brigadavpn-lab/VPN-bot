import sqlite3

# Имя нашей будущей базы данных
DB_NAME = "vpn_users.db"

# Создаем соединение (если файла нет, он создастся)
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Пояснение:
# Это SQL-команда для создания таблицы 'users'
# telegram_id: Уникальный ID пользователя в Telegram (чтобы не выдать ему 100 ключей)
# xray_uuid: Тот UUID, который мы сгенерируем и вставим в config.json
# email: Пометка 'test_user' или 'user_123456', которую мы тоже вставим в config.json
# trial_end_date: Дата (в виде текста 'ГГГГ-ММ-ДД'), когда его доступ закончится
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    xray_uuid TEXT NOT NULL,
    email TEXT NOT NULL,
    trial_end_date TEXT NOT NULL
);
""")

# Сохраняем изменения и закрываем соединение
conn.commit()
conn.close()

print(f"База данных {DB_NAME} и таблица 'users' успешно созданы.")

