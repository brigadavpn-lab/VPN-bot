#!/usr/bin/env python3
"""
Скрипт очистки просроченных пользователей VPN
- Находит пользователей с истекшей подпиской
- Удаляет их из конфига Xray
- Удаляет из базы данных
- Отправляет уведомления
"""

import sqlite3
import json
import subprocess
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# --- НАСТРОЙКИ ---
DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE = "/usr/local/etc/xray/config.json"
LOG_FILE = "/root/vpn-bot/cleanup.log"

# Дней до истечения для предупреждения
NOTIFICATION_DAYS_BEFORE = int(os.getenv("NOTIFICATION_DAYS_BEFORE_EXPIRY", "3"))

# Telegram Bot (для уведомлений)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

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
        bot.send_message(telegram_id, message, parse_mode="Markdown")
        return True
    except Exception as e:
        log(f"Ошибка отправки Telegram уведомления: {e}")
        return False

def notify_expiring_users():
    """Уведомляет пользователей о скором истечении подписки"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Дата через N дней
        warning_date = (datetime.now() + timedelta(days=NOTIFICATION_DAYS_BEFORE)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        # Ищем пользователей, у которых подписка истекает через N дней
        cursor.execute("""
            SELECT telegram_id, email, trial_end_date
            FROM users
            WHERE trial_end_date <= ? AND trial_end_date >= ? AND status = 'active'
        """, (warning_date, today))

        expiring_users = cursor.fetchall()
        conn.close()

        for user in expiring_users:
            telegram_id, email, end_date = user

            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                days_left = (end_datetime - datetime.now()).days

                message = (
                    f"⏰ **Напоминание о подписке**\n\n"
                    f"Ваша подписка истекает через **{days_left} дней**\n"
                    f"Дата окончания: {end_date}\n\n"
                    f"Для продления свяжитесь с администратором или используйте команду /start в боте."
                )

                if send_telegram_notification(telegram_id, message):
                    log(f"Отправлено напоминание пользователю {email} ({telegram_id})")

            except Exception as e:
                log(f"Ошибка обработки пользователя {email}: {e}")

    except Exception as e:
        log(f"Ошибка при отправке напоминаний: {e}")

def remove_expired_users():
    """Удаляет просроченных пользователей"""
    # 1. Подключаемся к БД
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
    except Exception as e:
        log(f"ОШИБКА: Не могу открыть БД: {e}")
        return 0

    # 2. Ищем тех, у кого дата МЕНЬШЕ (<) чем сегодня
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT telegram_id, xray_uuid, email
        FROM users
        WHERE trial_end_date < ? AND status != 'banned'
    """, (today,))

    expired_users = cursor.fetchall()

    if not expired_users:
        log("Нет пользователей с истекшим сроком.")
        conn.close()
        return 0

    log(f"Найдено {len(expired_users)} просроченных пользователей. Начинаю удаление...")

    # 3. Читаем конфиг Xray
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
    except Exception as e:
        log(f"ОШИБКА: Не могу прочитать config.json: {e}")
        conn.close()
        return 0

    # 4. Удаляем из конфига
    clients = config_data['inbounds'][1]['settings']['clients']
    emails_to_remove = [u[2] for u in expired_users]
    new_clients = [c for c in clients if c.get('email') not in emails_to_remove]

    # Проверяем, изменилось ли что-то
    if len(new_clients) == len(clients):
        log("Внимание: Пользователи найдены в БД, но не найдены в Config.json. Удаляю только из БД.")
    else:
        # Записываем обновленный список обратно
        config_data['inbounds'][1]['settings']['clients'] = new_clients

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)

        # Перезапускаем Xray
        try:
            subprocess.run(["systemctl", "restart", "xray"], check=True, timeout=10)
            log("Xray успешно перезапущен.")
        except Exception as e:
            log(f"ОШИБКА при перезапуске Xray: {e}")

    # 5. Отправляем уведомления удаленным пользователям
    for user in expired_users:
        telegram_id, uuid, email = user

        message = (
            f"🔴 **Подписка истекла**\n\n"
            f"Ваш доступ к VPN был отключен из-за истечения срока подписки.\n\n"
            f"Для возобновления доступа свяжитесь с администратором."
        )

        send_telegram_notification(telegram_id, message)

    # 6. Удаляем из БД
    for user in expired_users:
        telegram_id = user[0]
        email = user[2]
        cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        log(f"Пользователь {telegram_id} ({email}) удален из БД.")

    conn.commit()
    conn.close()

    removed_count = len(expired_users)
    log(f"Чистка завершена. Удалено пользователей: {removed_count}")

    return removed_count

def notify_admin(removed_count):
    """Уведомляет администратора о результатах очистки"""
    if not ADMIN_ID or not BOT_TOKEN:
        return

    message = (
        f"🧹 **Автоматическая очистка выполнена**\n\n"
        f"Удалено просроченных пользователей: {removed_count}\n"
        f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    send_telegram_notification(ADMIN_ID, message)
    log(f"Уведомление отправлено администратору")

def main():
    log("=" * 60)
    log("Запуск автоматической очистки просроченных пользователей")
    log("=" * 60)

    # 1. Отправляем напоминания пользователям
    log(f"\nОтправка напоминаний (за {NOTIFICATION_DAYS_BEFORE} дней)...")
    notify_expiring_users()

    # 2. Удаляем просроченных
    log("\nУдаление просроченных пользователей...")
    removed_count = remove_expired_users()

    # 3. Уведомляем администратора
    notify_admin(removed_count)

    log("=" * 60)
    log("Очистка завершена")
    log("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
