#!/usr/bin/env python3
"""
Скрипт мониторинга здоровья VPN системы
- Проверяет статус сервиса Xray
- Проверяет доступность Xray API
- Проверяет доступность бота
- Отправляет уведомления администратору при проблемах
"""

import subprocess
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# --- НАСТРОЙКИ ---
LOG_FILE = "/root/vpn-bot/monitoring.log"
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

# Xray API settings
XRAY_BIN = "/usr/local/bin/xray"
API_SERVER = "127.0.0.1"
API_PORT = 10085

def log(message):
    """Пишет сообщения в лог-файл с датой"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{now}] {message}"
    with open(LOG_FILE, "a") as f:
        f.write(log_message + "\n")
    print(log_message)

def send_telegram_alert(message):
    """Отправка критического уведомления администратору"""
    if not BOT_TOKEN or not ADMIN_ID:
        log("WARN: BOT_TOKEN или ADMIN_ID не найден, уведомление не отправлено")
        return False

    try:
        import telebot
        bot = telebot.TeleBot(BOT_TOKEN)
        alert_text = f"🚨 **ALERT: Проблема с VPN системой**\n\n{message}"
        bot.send_message(ADMIN_ID, alert_text, parse_mode="Markdown")
        return True
    except Exception as e:
        log(f"Ошибка отправки Telegram уведомления: {e}")
        return False

def check_xray_service():
    """Проверяет статус systemd сервиса Xray"""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "xray"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip() == "active":
            log("✅ Xray service: ACTIVE")
            return True
        else:
            log(f"❌ Xray service: INACTIVE (status: {result.stdout.strip()})")
            send_telegram_alert(
                f"Сервис Xray не активен!\n"
                f"Статус: {result.stdout.strip()}\n\n"
                f"Попробуйте перезапустить: `systemctl restart xray`"
            )
            return False
    except subprocess.TimeoutExpired:
        log("❌ Xray service check: TIMEOUT")
        send_telegram_alert("Не удалось проверить статус Xray (таймаут)")
        return False
    except Exception as e:
        log(f"❌ Xray service check: ERROR - {e}")
        send_telegram_alert(f"Ошибка проверки Xray сервиса: {e}")
        return False

def check_xray_api():
    """Проверяет доступность Xray API"""
    try:
        cmd = [XRAY_BIN, "api", "statsquery", f"--server={API_SERVER}:{API_PORT}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            log("✅ Xray API: RESPONSIVE")
            return True
        else:
            log(f"❌ Xray API: NOT RESPONDING (returncode: {result.returncode})")
            log(f"   stderr: {result.stderr}")
            send_telegram_alert(
                f"Xray API не отвечает!\n"
                f"Return code: {result.returncode}\n"
                f"Error: {result.stderr[:200]}"
            )
            return False
    except subprocess.TimeoutExpired:
        log("❌ Xray API check: TIMEOUT")
        send_telegram_alert("Xray API не отвечает (таймаут 10 секунд)")
        return False
    except Exception as e:
        log(f"❌ Xray API check: ERROR - {e}")
        send_telegram_alert(f"Ошибка проверки Xray API: {e}")
        return False

def check_bot_process():
    """Проверяет, запущен ли процесс бота"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "bot.py"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            log(f"✅ Bot process: RUNNING (PID: {result.stdout.strip()})")
            return True
        else:
            log("❌ Bot process: NOT RUNNING")
            send_telegram_alert(
                "Telegram бот не запущен!\n\n"
                "Попробуйте перезапустить: `systemctl restart vpn-bot`"
            )
            return False
    except subprocess.TimeoutExpired:
        log("❌ Bot process check: TIMEOUT")
        return False
    except Exception as e:
        log(f"❌ Bot process check: ERROR - {e}")
        return False

def check_database():
    """Проверяет доступность базы данных"""
    import sqlite3

    db_path = "/root/vpn-bot/vpn_users.db"

    try:
        if not os.path.exists(db_path):
            log(f"❌ Database: NOT FOUND at {db_path}")
            send_telegram_alert(f"База данных не найдена: {db_path}")
            return False

        conn = sqlite3.connect(db_path, timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()

        log(f"✅ Database: ACCESSIBLE ({user_count} users)")
        return True
    except Exception as e:
        log(f"❌ Database check: ERROR - {e}")
        send_telegram_alert(f"Ошибка доступа к базе данных: {e}")
        return False

def check_disk_space():
    """Проверяет свободное место на диске"""
    try:
        result = subprocess.run(
            ["df", "-h", "/root"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 5:
                    usage_percent = parts[4].rstrip('%')
                    log(f"✅ Disk space: {parts[3]} available ({usage_percent}% used)")

                    # Предупреждение если больше 90% заполнено
                    if int(usage_percent) > 90:
                        send_telegram_alert(
                            f"⚠️ Мало места на диске!\n\n"
                            f"Использовано: {usage_percent}%\n"
                            f"Свободно: {parts[3]}"
                        )
                    return True

        log("⚠️ Disk space check: UNKNOWN")
        return True
    except Exception as e:
        log(f"⚠️ Disk space check: ERROR - {e}")
        return True  # Не критично

def main():
    log("=" * 60)
    log("Запуск проверки здоровья VPN системы")
    log("=" * 60)

    checks = {
        "Xray Service": check_xray_service(),
        "Xray API": check_xray_api(),
        "Bot Process": check_bot_process(),
        "Database": check_database(),
        "Disk Space": check_disk_space()
    }

    log("\n" + "=" * 60)
    log("РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    log("=" * 60)

    all_ok = True
    for check_name, status in checks.items():
        status_text = "✅ OK" if status else "❌ FAIL"
        log(f"{check_name}: {status_text}")
        if not status:
            all_ok = False

    log("=" * 60)
    if all_ok:
        log("✅ Все проверки пройдены успешно")
        exit_code = 0
    else:
        log("❌ Обнаружены проблемы, требуется внимание")
        exit_code = 1

    log("=" * 60)
    return exit_code

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        log(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        send_telegram_alert(f"Критическая ошибка в monitoring.py: {e}")
        sys.exit(1)
