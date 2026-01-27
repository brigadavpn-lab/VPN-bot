#!/usr/bin/env python3
"""
Альтернативная версия мониторинга трафика
Работает через парсинг access логов Xray вместо stats API
"""

import sqlite3
import os
import re
from datetime import datetime
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# --- НАСТРОЙКИ ---
DB_PATH = "/root/vpn-bot/vpn_users.db"
LOG_FILE = "/root/vpn-bot/traffic_check.log"
XRAY_ACCESS_LOG = "/var/log/xray/access.log"

# Лимиты
LIMIT_GB = int(os.getenv("TRAFFIC_LIMIT_GB", "50"))
BYTES_LIMIT = LIMIT_GB * 1024 * 1024 * 1024
WARNING_THRESHOLD = 0.8
WARNING_BYTES = int(BYTES_LIMIT * WARNING_THRESHOLD)

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

def log(message):
    """Пишет сообщение в лог"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{now}] {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def send_telegram_notification(telegram_id, message):
    """Отправка уведомления через Telegram"""
    if not BOT_TOKEN:
        log("WARN: BOT_TOKEN не найден, уведомление не отправлено")
        return False

    try:
        import telebot
        bot = telebot.TeleBot(BOT_TOKEN)
        bot.send_message(telegram_id, message, parse_mode="Markdown")
        return True
    except Exception as e:
        log(f"Ошибка отправки Telegram: {e}")
        return False

def parse_xray_logs():
    """
    Парсинг access логов Xray для подсчета трафика
    Формат лога: [timestamp] [email] accepted connection from ...
    """
    if not os.path.exists(XRAY_ACCESS_LOG):
        log(f"WARN: Лог файл не найден: {XRAY_ACCESS_LOG}")
        return {}

    traffic_data = {}

    try:
        with open(XRAY_ACCESS_LOG, 'r') as f:
            for line in f:
                # Пример: 2026/01/27 10:00:00 [Info] [1234567890@test.com] accepted tcp:1.2.3.4:443
                # Ищем email в логах
                match = re.search(r'\[([^\]]+@[^\]]+)\]', line)
                if match:
                    email = match.group(1)
                    # Для упрощения считаем каждое соединение ~1MB
                    # В реальности нужен более точный подсчет через netstat или iptables
                    if email not in traffic_data:
                        traffic_data[email] = 0
                    traffic_data[email] += 1024 * 1024  # 1MB за соединение

        return traffic_data
    except Exception as e:
        log(f"Ошибка парсинга логов: {e}")
        return {}

def update_traffic_simple():
    """
    Упрощенный метод обновления трафика
    ПРИМЕЧАНИЕ: Это заглушка до реализации полного мониторинга
    """
    log(f"Запуск проверки трафика (лимит: {LIMIT_GB} ГБ)...")

    # Подключение к БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Получаем всех активных пользователей
    cursor.execute("SELECT telegram_id, email, traffic_used FROM users WHERE status='active'")
    users = cursor.fetchall()

    log(f"Найдено активных пользователей: {len(users)}")

    # Пока используем базовый подсчет
    # TODO: Реализовать точный подсчет через iptables или системные метрики

    conn.close()
    log("Проверка трафика завершена (упрощенный режим)")
    log("INFO: Для точного мониторинга трафика требуется настройка iptables")

def main():
    """Основная функция"""
    try:
        update_traffic_simple()
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
