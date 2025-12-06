import json
import subprocess
import sqlite3
from datetime import datetime

# --- НАСТРОЙКИ ---
LIMIT_GB = 50
BYTES_LIMIT = LIMIT_GB * 1024 * 1024 * 1024

API_PORT = 10085
API_SERVER = "127.0.0.1"
XRAY_BIN = "/usr/local/bin/xray"
CONFIG_FILE = "/usr/local/etc/xray/config.json"
LOG_FILE = "/root/vpn-bot/traffic.log"
DB_NAME = "/root/vpn-bot/vpn_users.db"

def log(message):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{now}] {message}\n")

def get_and_reset_xray_stats():
    """Запрашивает статистику И СБРАСЫВАЕТ её в Xray"""
    try:
        cmd = [XRAY_BIN, "api", "statsquery", f"--server={API_SERVER}:{API_PORT}", "--reset=true"]
        result = subprocess.run(cmd, capture_output=True, text=True)
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
            continue # Если там не число, тоже пропускаем

        if email not in traffic_delta:
            traffic_delta[email] = 0
        traffic_delta[email] += value

    if not traffic_delta:
        return 

    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        for email, delta_bytes in traffic_delta.items():
            cursor.execute("UPDATE users SET traffic_used = traffic_used + ? WHERE email = ?", (delta_bytes, email))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"Ошибка записи в БД: {e}")

def check_limits_and_block():
    """Проверяет лимиты и меняет статус на BANNED"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("SELECT email, traffic_used FROM users WHERE traffic_used > ? AND status = 'active'", (BYTES_LIMIT,))
        over_limit_users = cursor.fetchall()
        
        emails_to_block = []
        for user in over_limit_users:
            email = user[0]
            used = user[1]
            if "admin" in email:
                continue
            
            gb_used = used / (1024**3)
            log(f"Пользователь {email} превысил лимит: {gb_used:.2f} ГБ. Блокирую...")
            emails_to_block.append(email)
        
        conn.close()
        
        if emails_to_block:
            block_users_in_config(emails_to_block)
            
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
        
        subprocess.run(["systemctl", "restart", "xray"], check=True)

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
    stats = get_and_reset_xray_stats()
    update_db_traffic(stats)
    check_limits_and_block()

if __name__ == "__main__":
    main()