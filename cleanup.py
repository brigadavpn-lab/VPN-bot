import sqlite3
import json
import subprocess
from datetime import datetime

from proxy_routing import update_xray_proxy_routing

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

    # 3. Читаем конфиг Xray
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
    except Exception as e:
        log(f"ОШИБКА: Не могу прочитать config.json: {e}")
        conn.close()
        return

    # 4. Удаляем из конфига
    # Получаем список клиентов
    clients = config_data['inbounds'][1]['settings']['clients']

    # Собираем emails тех, кого надо удалить (для удобства фильтрации)
    emails_to_remove = [u[2] for u in expired_users]
    # Оставляем только тех, кого НЕТ в списке на удаление
    # (Фильтруем список: оставляем клиента, ТОЛЬКО ЕСЛИ его email НЕ в списке удаления)
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
            subprocess.run(["systemctl", "restart", "xray"], check=True)
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

    # Перестраиваем routing rule, чтобы email удалённых юзеров не остались
    # в bot_managed_proxy. Дёргаем только если фактически что-то удалили.
    if expired_users:
        if update_xray_proxy_routing():
            log("Routing rule bot_managed_proxy пересобран.")
        else:
            log("ВНИМАНИЕ: не удалось пересобрать routing rule bot_managed_proxy.")

    log("Чистка завершена.")

if __name__ == "__main__":
    remove_expired_users()
