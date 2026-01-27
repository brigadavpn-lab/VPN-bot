#!/usr/bin/env python3
"""
Скрипт мониторинга трафика пользователей VPN
- Получает статистику из Xray API
- Обновляет traffic_used в БД
- Блокирует пользователей при превышении лимита
- Отправляет уведомления через Telegram
"""

import json
import subprocess
import sqlite3
from datetime import datetime
import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# --- НАСТРОЙКИ ---
# Лимит трафика (читаем из .env или используем значение по умолчанию)
LIMIT_GB = int(os.getenv("TRAFFIC_LIMIT_GB", "50"))
BYTES_LIMIT = LIMIT_GB * 1024 * 1024 * 1024

# Порог уведомления (80% от лимита)
WARNING_THRESHOLD = 0.8
WARNING_BYTES = int(BYTES_LIMIT * WARNING_THRESHOLD)

# Пути и настройки
API_PORT = 10085
API_SERVER = "127.0.0.1"
XRAY_BIN = "/usr/local/bin/xray"
CONFIG_FILE = "/usr/local/etc/xray/config.json"
LOG_FILE = "/root/vpn-bot/traffic.log"
DB_NAME = "/root/vpn-bot/vpn_users.db"

# Telegram Bot (для уведомлений)
BOT_TOKEN = os.getenv("BOT_TOKEN")

def log(message):
    """Пишет сообщения в лог-файл с датой"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{now}] {message}"
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")
    print(log_message)

def send_telegram_notification(telegram_id, message):
    """Отправка уведомления пользователю через Telegram"""
    if not BOT_TOKEN:
        log("WARN: BOT_TOKEN не найден, уведомление не отправлено")
        return False

    try:
        import telebot
        bot = telebot.TeleBot(BOT_TOKEN)
        bot.send_message(telegram_id, message)
        return True
    except Exception as e:
        log(f"Ошибка отправки Telegram уведомления: {e}")
        return False

def get_and_reset_xray_stats():
    """Запрашивает статистику И СБРАСЫВАЕТ её в Xray"""
    try:
        cmd = [XRAY_BIN, "api", "statsquery", f"--server={API_SERVER}:{API_PORT}", "--reset=true"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            log(f"Ошибка API Xray: {result.stderr}")
            return {}

        # Если вывод пустой
        if not result.stdout.strip():
            return {}

        data = json.loads(result.stdout)
        if "stat" not in data:
            return {}
        return data["stat"]
    except subprocess.TimeoutExpired:
        log("Таймаут при запросе статистики Xray")
        return {}
    except Exception as e:
        log(f"Ошибка при получении статистики: {e}")
        return {}

def update_db_traffic(stats):
    """Считает новый трафик и плюсует его в БД"""
    if not stats:
        return

    traffic_delta = {}
    for item in stats:
        # ЗАЩИТА ОТ ОШИБКИ: Если нет ключа 'value', пропускаем
        if "value" not in item:
            continue

        name_parts = item["name"].split(">>>")
        if len(name_parts) < 4 or name_parts[0] != "user":
            continue

        email = name_parts[1]
        try:
            value = int(item["value"])
        except ValueError:
            continue  # Если там не число, тоже пропускаем

        if email not in traffic_delta:
            traffic_delta[email] = 0
        traffic_delta[email] += value

    if not traffic_delta:
        return

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        for email, delta_bytes in traffic_delta.items():
            # Обновляем traffic_used
            cursor.execute(
                "UPDATE users SET traffic_used = traffic_used + ? WHERE email = ?",
                (delta_bytes, email)
            )

            # Записываем в историю
            cursor.execute(
                "SELECT telegram_id FROM users WHERE email = ?",
                (email,)
            )
            result = cursor.fetchone()
            if result:
                telegram_id = result[0]
                cursor.execute(
                    "INSERT INTO traffic_history (telegram_id, bytes_used) VALUES (?, ?)",
                    (telegram_id, delta_bytes)
                )

        conn.commit()
        conn.close()
        log(f"Обновлен трафик для {len(traffic_delta)} пользователей")
    except Exception as e:
        log(f"Ошибка записи в БД: {e}")

def check_warnings():
    """Проверяет пользователей на 80% лимита и отправляет предупреждения"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Ищем пользователей, которые превысили 80% но еще не заблокированы
        cursor.execute("""
            SELECT telegram_id, email, traffic_used
            FROM users
            WHERE traffic_used > ? AND traffic_used < ? AND status = 'active'
        """, (WARNING_BYTES, BYTES_LIMIT))

        warning_users = cursor.fetchall()
        conn.close()

        for user in warning_users:
            telegram_id, email, used_bytes = user
            used_gb = used_bytes / (1024**3)
            remaining_gb = (BYTES_LIMIT - used_bytes) / (1024**3)

            message = (
                f"⚠️ **Предупреждение о трафике**\n\n"
                f"Вы использовали {used_gb:.2f} ГБ из {LIMIT_GB} ГБ\n"
                f"Осталось: {remaining_gb:.2f} ГБ\n\n"
                f"При превышении лимита доступ будет автоматически заблокирован."
            )

            if send_telegram_notification(telegram_id, message):
                log(f"Отправлено предупреждение пользователю {email} ({telegram_id})")

    except Exception as e:
        log(f"Ошибка при проверке предупреждений: {e}")

def check_limits_and_block():
    """Проверяет лимиты и меняет статус на BANNED"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT telegram_id, email, traffic_used
            FROM users
            WHERE traffic_used > ? AND status = 'active'
        """, (BYTES_LIMIT,))

        over_limit_users = cursor.fetchall()

        emails_to_block = []
        telegram_ids_to_notify = []

        for user in over_limit_users:
            telegram_id, email, used = user
            if "admin" in email.lower():
                continue

            gb_used = used / (1024**3)
            log(f"Пользователь {email} превысил лимит: {gb_used:.2f} ГБ. Блокирую...")
            emails_to_block.append(email)
            telegram_ids_to_notify.append((telegram_id, email, gb_used))

        conn.close()

        if emails_to_block:
            block_users_in_config(emails_to_block)

            # Отправляем уведомления заблокированным
            for telegram_id, email, gb_used in telegram_ids_to_notify:
                message = (
                    f"🚫 **Доступ заблокирован**\n\n"
                    f"Вы превысили лимит трафика ({LIMIT_GB} ГБ)\n"
                    f"Использовано: {gb_used:.2f} ГБ\n\n"
                    f"Для продления свяжитесь с администратором."
                )
                send_telegram_notification(telegram_id, message)

    except Exception as e:
        log(f"Ошибка при проверке лимитов: {e}")

def block_users_in_config(emails_to_block):
    """Удаляет из конфига Xray и метит в БД как banned"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        clients = config['inbounds'][1]['settings']['clients']
        new_clients = [c for c in clients if c.get('email') not in emails_to_block]

        if len(new_clients) == len(clients):
            return

        config['inbounds'][1]['settings']['clients'] = new_clients

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

        subprocess.run(["systemctl", "restart", "xray"], check=True, timeout=10)

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        for email in emails_to_block:
            cursor.execute("UPDATE users SET status = 'banned' WHERE email = ?", (email,))
        conn.commit()
        conn.close()

        log(f"Успешно заблокированы (статус banned): {emails_to_block}")

    except Exception as e:
        log(f"Ошибка при блокировке: {e}")

def main():
    log(f"Запуск проверки трафика (лимит: {LIMIT_GB} ГБ)...")

    # 1. Получаем статистику из Xray
    stats = get_and_reset_xray_stats()

    # 2. Обновляем БД
    update_db_traffic(stats)

    # 3. Проверяем предупреждения (80%)
    check_warnings()

    # 4. Проверяем блокировки (100%)
    check_limits_and_block()

    log("Проверка трафика завершена\n" + "-" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
