#!/usr/bin/env python3
"""
Скрипт миграции базы данных VPN бота
Добавляет необходимые колонки и таблицы для мониторинга трафика
"""

import sqlite3
import os
from datetime import datetime

# Путь к базе данных
DB_NAME = "/root/vpn-bot/vpn_users.db"

def log(message):
    """Вывод сообщений с временной меткой"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_column_exists(cursor, table_name, column_name):
    """Проверка существования колонки в таблице"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]
    return column_name in columns

def check_table_exists(cursor, table_name):
    """Проверка существования таблицы"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def migrate_database():
    """Основная функция миграции"""
    log("Начало миграции базы данных...")

    # Проверка существования БД
    if not os.path.exists(DB_NAME):
        log(f"ОШИБКА: База данных не найдена: {DB_NAME}")
        log("Запустите бота хотя бы один раз для создания БД")
        return False

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Миграция 1: Добавление колонки traffic_used
        if not check_column_exists(cursor, 'users', 'traffic_used'):
            log("Добавление колонки 'traffic_used' в таблицу 'users'...")
            cursor.execute("ALTER TABLE users ADD COLUMN traffic_used BIGINT DEFAULT 0")
            log("✅ Колонка 'traffic_used' добавлена")
        else:
            log("⚠️  Колонка 'traffic_used' уже существует, пропускаем")

        # Миграция 2: Создание таблицы traffic_history
        if not check_table_exists(cursor, 'traffic_history'):
            log("Создание таблицы 'traffic_history'...")
            cursor.execute("""
                CREATE TABLE traffic_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    bytes_used BIGINT NOT NULL,
                    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
                )
            """)
            log("✅ Таблица 'traffic_history' создана")
        else:
            log("⚠️  Таблица 'traffic_history' уже существует, пропускаем")

        # Миграция 3: Создание таблицы admin_actions
        if not check_table_exists(cursor, 'admin_actions'):
            log("Создание таблицы 'admin_actions'...")
            cursor.execute("""
                CREATE TABLE admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    target_user INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            log("✅ Таблица 'admin_actions' создана")
        else:
            log("⚠️  Таблица 'admin_actions' уже существует, пропускаем")

        # Миграция 4: Добавление индексов для оптимизации
        log("Создание индексов для оптимизации запросов...")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_history_telegram_id ON traffic_history(telegram_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_actions_admin_id ON admin_actions(admin_id)")
            log("✅ Индексы созданы")
        except Exception as e:
            log(f"⚠️  Ошибка создания индексов (возможно уже существуют): {e}")

        # Сохранение изменений
        conn.commit()
        log("Сохранение изменений в БД...")

        # Проверка результата
        log("\n--- Проверка структуры базы данных ---")
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        log(f"Колонки таблицы 'users': {', '.join([col[1] for col in columns])}")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        log(f"Таблицы в БД: {', '.join([table[0] for table in tables])}")

        conn.close()

        log("\n✅ Миграция успешно завершена!")
        log("Теперь можно запускать обновленный бот и скрипты мониторинга")
        return True

    except Exception as e:
        log(f"\n❌ ОШИБКА при миграции: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("  VPN Bot - Миграция базы данных")
    print("=" * 60)
    print()

    success = migrate_database()

    print()
    print("=" * 60)
    if success:
        print("  ✅ Миграция завершена успешно")
    else:
        print("  ❌ Миграция завершена с ошибками")
    print("=" * 60)

    exit(0 if success else 1)
