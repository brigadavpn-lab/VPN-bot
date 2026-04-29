"""
webhook.py — Flask-сервер для приёма уведомлений об оплате от YooKassa.

Запуск:
    python3 webhook.py

Запуск в фоне через systemd или screen:
    screen -S webhook python3 /root/vpn-bot/webhook.py

YooKassa webhook нужно настроить в личном кабинете:
    URL: http://141.105.143.224:5000/webhook/yookassa
    События: payment.succeeded
"""

import json
import sqlite3
import subprocess
import uuid
import urllib.parse
import os
import io
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- НАСТРОЙКИ (копируются из bot.py) ---
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE_PATH = "/usr/local/etc/xray/config.json"
PDF_PATH = "/root/vpn-bot/instruction.pdf"

YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))

SERVER_ADDRESS = "141.105.143.224"
SERVER_PORT = 443
REALITY_PUBLIC_KEY = "O_actbJXCoMijlOyrLMWWKQQ7a3tEYZe3Hix86Yr3kM"
REALITY_SHORT_ID = "a028507ab5b114b4"
REALITY_SNI = "www.yahoo.com"


# --- TELEGRAM API ---

def tg_send_message(chat_id, text, parse_mode="Markdown"):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }, timeout=10)
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")


def tg_send_photo(chat_id, photo_bytes, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        requests.post(url, data={
            "chat_id": chat_id,
            "caption": caption
        }, files={
            "photo": ("qr.png", photo_bytes, "image/png")
        }, timeout=15)
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")


def tg_send_document(chat_id, file_path, caption=""):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    try:
        with open(file_path, 'rb') as f:
            requests.post(url, data={
                "chat_id": chat_id,
                "caption": caption
            }, files={
                "document": f
            }, timeout=15)
    except Exception as e:
        print(f"Ошибка отправки документа: {e}")


# --- VPN ФУНКЦИИ ---

def generate_vless_link(user_uuid, tag="VPN1Month"):
    params = {
        "security": "reality",
        "sni": REALITY_SNI,
        "pbk": REALITY_PUBLIC_KEY,
        "sid": REALITY_SHORT_ID,
        "flow": "xtls-rprx-vision",
        "type": "tcp"
    }
    query_string = urllib.parse.urlencode(params)
    return f"vless://{user_uuid}@{SERVER_ADDRESS}:{SERVER_PORT}?{query_string}#{tag}"


def generate_qr_code(link):
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


def create_xray_user():
    try:
        new_uuid = str(uuid.uuid4())
        new_email = f"paid_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        new_client = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
            "email": new_email,
            "level": 0
        }
        with open(CONFIG_FILE_PATH, 'r') as f:
            data = json.load(f)
        data['inbounds'][1]['settings']['clients'].append(new_client)
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=2)
        subprocess.run(["systemctl", "restart", "xray"], check=True)
        return new_uuid, new_email
    except Exception as e:
        print(f"ОШИБКА Xray: {e}")
        return None, None


def add_user_to_db(telegram_id, xray_uuid, email, hours=24):
    try:
        trial_end = datetime.now() + timedelta(hours=hours)
        trial_end_str = trial_end.strftime('%Y-%m-%d %H:%M')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, xray_uuid, email, trial_end_date, status, payment_type) "
            "VALUES (?, ?, ?, ?, 'active', 'paid')",
            (telegram_id, xray_uuid, email, trial_end_str)
        )
        conn.commit()
        conn.close()
        return trial_end_str
    except Exception as e:
        print(f"ОШИБКА БД: {e}")
        return None


def extend_user_subscription(telegram_id, hours=24):
    """Продление подписки существующего пользователя. Возвращает (xray_uuid, new_end_str)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT xray_uuid, trial_end_date FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None, None

    xray_uuid = row[0]
    current_end = None
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            current_end = datetime.strptime(row[1], fmt)
            break
        except ValueError:
            pass
    if current_end is None:
        current_end = datetime.now()

    now = datetime.now()
    new_end = (current_end if current_end > now else now) + timedelta(hours=hours)
    new_end_str = new_end.strftime('%Y-%m-%d %H:%M')

    cursor.execute(
        "UPDATE users SET trial_end_date = ?, status = 'active', payment_type = 'paid' WHERE telegram_id = ?",
        (new_end_str, telegram_id)
    )
    conn.commit()
    conn.close()
    return xray_uuid, new_end_str


def mark_payment_paid(payment_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE pending_payments SET status = 'paid' WHERE payment_id = ?",
            (payment_id,)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка обновления статуса платежа: {e}")


def get_payment_hours(payment_id):
    """Читает duration_hours из pending_payments. Возвращает 24 если не найдено."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT duration_hours FROM pending_payments WHERE payment_id = ?", (payment_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row and row[0] else 24
    except Exception:
        return 24


def handle_successful_payment(payment_id, telegram_id):
    """Основная функция обработки успешного платежа."""
    print(f"[webhook] Обработка платежа {payment_id} для пользователя {telegram_id}")

    hours = get_payment_hours(payment_id)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT xray_uuid FROM users WHERE telegram_id = ?", (telegram_id,))
    existing = cursor.fetchone()
    conn.close()

    if existing:
        # Пользователь уже есть — продлеваем
        xray_uuid, new_end_str = extend_user_subscription(telegram_id, hours=hours)
        if not xray_uuid:
            tg_send_message(telegram_id, "❌ Ошибка продления подписки. Напишите в поддержку.")
            return

        mark_payment_paid(payment_id)

        vless_link = generate_vless_link(xray_uuid)
        qr_image = generate_qr_code(vless_link)

        tg_send_message(
            telegram_id,
            f"✅ *Оплата получена!*\n\n"
            f"Подписка продлена до: *{new_end_str}*\n\n"
            f"Ваш ключ VPN:\n`{vless_link}`"
        )
        tg_send_photo(telegram_id, qr_image, caption="QR-код для подключения")

    else:
        # Новый пользователь — создаём
        new_uuid, new_email = create_xray_user()
        if not new_uuid:
            tg_send_message(telegram_id, "❌ Ошибка создания ключа. Обратитесь в поддержку.")
            tg_send_message(ADMIN_ID, f"⚠️ Ошибка создания Xray-пользователя после оплаты! telegram_id={telegram_id}")
            return

        trial_end_str = add_user_to_db(telegram_id, new_uuid, new_email, hours=hours)
        if not trial_end_str:
            tg_send_message(telegram_id, "❌ Ошибка сохранения данных. Обратитесь в поддержку.")
            return

        mark_payment_paid(payment_id)

        vless_link = generate_vless_link(new_uuid)
        qr_image = generate_qr_code(vless_link)

        tg_send_message(
            telegram_id,
            f"✅ *Оплата получена! Добро пожаловать!*\n\n"
            f"Подписка активна до: *{trial_end_str}*\n\n"
            f"Ваш ключ VPN:\n`{vless_link}`"
        )
        tg_send_photo(telegram_id, qr_image, caption="QR-код для подключения")
        tg_send_document(telegram_id, PDF_PATH, caption="Инструкция по настройке 🤓")

    # Уведомление админу
    tg_send_message(
        ADMIN_ID,
        f"💰 Новая оплата!\ntelegram\\_id: `{telegram_id}`\npayment\\_id: `{payment_id}`",
        parse_mode="Markdown"
    )


# --- WEBHOOK ENDPOINT ---

@app.route('/webhook/yookassa', methods=['POST'])
def yookassa_webhook():
    try:
        body = request.get_data(as_text=True)
        data = json.loads(body)

        event = data.get('event', '')
        print(f"[webhook] Получено событие: {event}")

        if event == 'payment.succeeded':
            payment_obj = data.get('object', {})
            payment_id = payment_obj.get('id', '')
            metadata = payment_obj.get('metadata', {})
            telegram_id_str = metadata.get('telegram_id', '')

            if not telegram_id_str or not payment_id:
                print("[webhook] Ошибка: нет telegram_id или payment_id в metadata")
                return jsonify({"status": "error", "message": "missing metadata"}), 400

            telegram_id = int(telegram_id_str)
            handle_successful_payment(payment_id, telegram_id)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"[webhook] ОШИБКА: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "vpn-bot-webhook"}), 200


if __name__ == '__main__':
    print(f"Webhook-сервер запущен на порту {WEBHOOK_PORT}")
    print(f"URL для YooKassa: {os.getenv('WEBHOOK_HOST', 'http://141.105.143.224')}:{WEBHOOK_PORT}/webhook/yookassa")
    app.run(host='0.0.0.0', port=WEBHOOK_PORT, debug=False)
