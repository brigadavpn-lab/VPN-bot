import sqlite3
import json
import subprocess
from datetime import datetime

# --- НАСТРОЙКИ ---
DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE = "/usr/local/etc/xray/config.json"
LOG_FILE = "/root/vpn-bot/cleanup.log"

def log(message):
    """Пишет сообщения в лог-файл с датой"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{now}] {message}\n")
    print(f"[{now}] {message}")

def remove_expired_users():
    # 1. Подключаемся к БД
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
    except Exception as e:
        log(f"ОШИБКА: Не могу открыть БД: {e}")
        return

    # 2. Ищем тех, у кого дата МЕНЬШЕ (<) чем сегодня
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT telegram_id, xray_uuid, email FROM users WHERE trial_end_date < ?", (today,))
    expired_users = cursor.fetchall()

    if not expired_users:
        log("Нет пользователей с истекшим сроком.")
        conn.close()
        return

    log(f"Найдено {len(expired_users)} просроченных пользователей. Начинаю удаление...")

    # 3. Удаляем из конфига Xray (из всех VLESS inbound-ов)
    try:
        from xray_config import load_config, save_config, remove_clients_by_email, restart_xray

        config_data = load_config()
    except Exception as e:
        log(f"ОШИБКА: Не могу прочитать config.json: {e}")
        conn.close()
        return

    emails_to_remove = [u[2] for u in expired_users]
    removed = remove_clients_by_email(config_data, emails_to_remove)

    if removed == 0:
        log("Внимание: Пользователи найдены в БД, но не найдены в Config.json. Удаляю только из БД.")
    else:
        save_config(config_data)
        try:
            restart_xray()
            log("Xray успешно перезапущен.")
        except Exception as e:
            log(f"ОШИБКА при перезапуске Xray: {e}")

    # 5. Удаляем из БД
    for user in expired_users:
        telegram_id = user[0]
        cursor.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        log(f"Пользователь {telegram_id} ({user[2]}) удален.")

    conn.commit()
    conn.close()
    log("Чистка завершена.")

if __name__ == "__main__":
    remove_expired_users()
