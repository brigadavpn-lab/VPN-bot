import sqlite3
import json
import subprocess

DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE_PATH = "/usr/local/etc/xray/config.json"
ROUTING_TAG = "bot_managed_proxy"
OUTBOUND_TAG = "dataimpulse"


def update_xray_proxy_routing() -> bool:
    """
    Перечитывает всех активных пользователей с proxy_enabled=1,
    пересоздаёт routing rule с tag='bot_managed_proxy' в Xray config,
    перезапускает Xray. Возвращает True/False.
    """
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT email FROM users WHERE proxy_enabled=1 AND status='active'"
        )
        proxy_emails = [row[0] for row in cursor.fetchall()]
        conn.close()

        with open(CONFIG_FILE_PATH, "r") as f:
            data = json.load(f)

        routing = data.setdefault("routing", {})
        rules = routing.get("rules", [])
        rules = [r for r in rules if r.get("tag") != ROUTING_TAG]

        if proxy_emails:
            proxy_rule = {
                "type": "field",
                "tag": ROUTING_TAG,
                "user": proxy_emails,
                "outboundTag": OUTBOUND_TAG,
            }
            rules.insert(0, proxy_rule)

        routing["rules"] = rules

        with open(CONFIG_FILE_PATH, "w") as f:
            json.dump(data, f, indent=2)

        subprocess.run(["systemctl", "restart", "xray"], check=True)
        return True
    except Exception as e:
        print(f"ОШИБКА update_xray_proxy_routing: {e}")
        return False
