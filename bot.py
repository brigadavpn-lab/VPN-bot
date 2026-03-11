import telebot
import sqlite3
from telebot import types
import subprocess
import json
import uuid
from datetime import datetime, timedelta
import qrcode
import io
import urllib.parse
import os
from dotenv import load_dotenv
import random
import time

# Загружаем секреты из файла .env
load_dotenv()

# ----- НАСТРОЙКИ -----
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not TOKEN or not ADMIN_ID:
    print("ОШИБКА: Не найдены BOT_TOKEN или ADMIN_ID в файле .env")
    exit()

# Пути к файлам
DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE_PATH = "/usr/local/etc/xray/config.json"
PDF_PATH = "/root/vpn-bot/instruction.pdf"

# Настройки VLESS
SERVER_ADDRESS = "141.105.143.224"
SERVER_PORT = 443
REALITY_PUBLIC_KEY = "O_actbJXCoMijlOyrLMWWKQQ7a3tEYZe3Hix86Yr3kM"
REALITY_SHORT_ID = "a028507ab5b114b4"
REALITY_SNI = "www.yahoo.com"

# Цена услуги
SERVICE_PRICE = 99

# YooKassa
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", f"http://{SERVER_ADDRESS}")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "5000"))

# PDF file_id для договора и политики конфиденциальности
PDF_AGREEMENT_FILE_ID = os.getenv("PDF_AGREEMENT_FILE_ID", "")
PDF_PRIVACY_FILE_ID = os.getenv("PDF_PRIVACY_FILE_ID", "")

# Память состояний пользователей
user_states = {}

bot = telebot.TeleBot(TOKEN)

# --- ФУНКЦИИ ---

def generate_vless_link(user_uuid, tag="BetaTest"):
    """Генерация ссылки VLESS Reality"""
    params = {
        "security": "reality",
        "sni": REALITY_SNI,
        "pbk": REALITY_PUBLIC_KEY,
        "sid": REALITY_SHORT_ID,
        "flow": "xtls-rprx-vision",
        "type": "tcp"
    }
    query_string = urllib.parse.urlencode(params)
    link = f"vless://{user_uuid}@{SERVER_ADDRESS}:{SERVER_PORT}?{query_string}#{tag}"
    return link


def generate_qr_code(link):
    """Генерация QR-кода"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = io.BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio


def create_xray_user(email_prefix="beta_user"):
    """Создание пользователя в конфиге Xray"""
    try:
        new_uuid = str(uuid.uuid4())
        new_email = f"{email_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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


def add_user_to_db(user_id, xray_uuid, email, payment_type='beta'):
    """Добавление в базу"""
    try:
        trial_end = datetime.now() + timedelta(days=30)
        trial_end_str = trial_end.strftime('%Y-%m-%d')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, xray_uuid, email, trial_end_date, status, payment_type) "
            "VALUES (?, ?, ?, ?, 'active', ?)",
            (user_id, xray_uuid, email, trial_end_str, payment_type)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"ОШИБКА БД: {e}")
        return False


def check_user_exists(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return True if user else False


def count_total_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_user_vless_link(user_id):
    """Получить существующую VLESS-ссылку пользователя"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT xray_uuid FROM users WHERE telegram_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return generate_vless_link(result[0], tag="VPN1Month")
    return None


def extend_user_trial(target_user_id, days):
    """Продление подписки"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("SELECT trial_end_date FROM users WHERE telegram_id = ?", (target_user_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return False, "Пользователь не найден."

        current_end_str = result[0]
        try:
            current_end_date = datetime.strptime(current_end_str, '%Y-%m-%d')
        except:
            current_end_date = datetime.now()

        now = datetime.now()
        if current_end_date < now:
            new_end_date = now + timedelta(days=days)
        else:
            new_end_date = current_end_date + timedelta(days=days)

        new_end_str = new_end_date.strftime('%Y-%m-%d')

        cursor.execute(
            "UPDATE users SET trial_end_date = ?, status = 'active' WHERE telegram_id = ?",
            (new_end_str, target_user_id,)
        )
        conn.commit()
        conn.close()
        return True, new_end_str
    except Exception as e:
        return False, f"Ошибка: {e}"


def create_yookassa_payment(telegram_id):
    """Создание платежа в YooKassa"""
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        return None, None
    try:
        from yookassa import Configuration, Payment as YKPayment
        Configuration.account_id = YOOKASSA_SHOP_ID
        Configuration.secret_key = YOOKASSA_SECRET_KEY

        bot_info = bot.get_me()
        return_url = f"https://t.me/{bot_info.username}"

        idempotency_key = str(uuid.uuid4())
        payment = YKPayment.create({
            "amount": {
                "value": f"{SERVICE_PRICE}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url
            },
            "capture": True,
            "description": "VPN подписка на 1 месяц",
            "metadata": {
                "telegram_id": str(telegram_id)
            }
        }, idempotency_key)

        # Сохраняем платёж в БД
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO pending_payments (payment_id, telegram_id, created_at, status) "
            "VALUES (?, ?, ?, 'pending')",
            (payment.id, telegram_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        conn.close()

        return payment.id, payment.confirmation.confirmation_url
    except Exception as e:
        print(f"ОШИБКА YooKassa: {e}")
        return None, None


def save_pdf_file_id(key, file_id):
    """Сохранение file_id в .env файл"""
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        with open(env_path, 'r') as f:
            lines = f.readlines()

        updated = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={file_id}\n")
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(f"{key}={file_id}\n")

        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        # Обновляем глобальную переменную
        os.environ[key] = file_id
        return True
    except Exception as e:
        print(f"Ошибка сохранения file_id: {e}")
        return False


# --- ОБРАБОТЧИКИ БОТА ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    user_data = check_user_exists(user_id)

    keyboard = types.InlineKeyboardMarkup()

    if user_data:
        btn_profile = types.InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile")
        btn_pay_service = types.InlineKeyboardButton("🛡 VPN на месяц — 99 руб", callback_data="vpn_service")
        btn_instruction = types.InlineKeyboardButton("📖 Инструкция", callback_data="get_instruction")
        btn_support = types.InlineKeyboardButton("🆘 Поддержка", callback_data="ask_support")
        btn_matrix = types.InlineKeyboardButton("🕶 Матрица", callback_data="show_matrix")

        keyboard.add(btn_profile)
        keyboard.add(btn_pay_service)
        keyboard.add(btn_instruction, btn_support)
        keyboard.add(btn_matrix)

        text = "С возвращением! 👋\nГлавное меню:"
    else:
        btn_get = types.InlineKeyboardButton("🚀 Получить VPN (бесплатно)", callback_data="get_vpn")
        btn_pay_service = types.InlineKeyboardButton("🛡 VPN на месяц — 99 руб", callback_data="vpn_service")
        keyboard.add(btn_get)
        keyboard.add(btn_pay_service)
        text = (
            "Привет! Это частный VPN бот Олегыч. 🛡\n\n"
            "Жми кнопку, чтобы получить доступ 👇"
        )

    bot.send_message(user_id, text, reply_markup=keyboard)


@bot.message_handler(commands=['matrix'])
def send_matrix_status(message):
    traffic_gb = 14.5
    matrix_x = random.randint(10, 99)
    matrix_y = random.randint(10, 99)
    matrix_z = random.randint(10, 99)
    matrix_code = hex(random.getrandbits(32)).upper()[2:]
    ping_ms = random.randint(25, 110)

    kana = ["ｸ", "ﾗ", "ｽ", "ﾂ", "ﾇ", "ﾎ", "ﾑ", "ｴ", "ｷ", "ﾏ", "ﾅ", "ﾔ"]
    deco = random.choice(kana) + random.choice(kana) + random.choice(kana)

    user_label = message.from_user.username or message.from_user.first_name or "NEO"

    matrix_text = f"""```
┌── 🈯️ M A T R I X 🈯️ ───────────────┐
│  SYS.ROOT: ENABLED                 │
└────────────────────────────────────┘
 ❇️ NEURAL LINK: ESTABLISHED
 ❇️ ENCRYPTION: {deco}

 👤 USER: {user_label[:10]}...
 🌐 NODE: [{matrix_x}.{matrix_y}.{matrix_z}]
 🔑 KEY:  {matrix_code}

 ╔═══════════════════════════════════╗
 ║  🟢 TRAFFIC ANALYSIS              ║
 ╠═══════════════════════════════════╣
 ║                                   ║
 ║  ⬇️ USED:    {traffic_gb:6.2f} GB          ║
 ║  📶 LATENCY: {ping_ms} ms               ║
 ║  ⚡️ STATUS:  {'CONNECTED 🟢' if traffic_gb < 40 else 'OVERLOAD 🔴'}      ║
 ║                                   ║
 ╚═══════════════════════════════════╝

 🧩 01001000 01000101 01001100 01001111

 "Follow the white rabbit. 🐇"
```"""

    msg = bot.send_message(message.chat.id, "🔌 Connecting to the Source...")
    time.sleep(1)
    bot.edit_message_text("💾 Uploading consciousness...", chat_id=message.chat.id, message_id=msg.message_id)
    time.sleep(1.5)

    bot.send_message(message.chat.id, matrix_text, parse_mode="Markdown")

    jokes = [
        "🧪 Есть только два способа написать код без багов... но третий тебе не понравится.",
        "🕶️ Wake up, Neo. Твой VPN подключен.",
        "💊 Это твой последний шанс. После этого пути назад нет. Синяя таблетка — пинг 300мс. Красная таблетка — пинг 30мс. Выбирай.",
        "🐇 Тук-тук, это провайдер. Шучу, мы зашифрованы.",
        "😎 Я не сказал, что будет легко. Я лишь обещал открыть правду"
    ]
    time.sleep(1)
    bot.send_message(message.chat.id, random.choice(jokes))




# --- КОМАНДА АДМИНА ---
@bot.message_handler(commands=['add_time'])
def add_time_handler(message):
    if message.chat.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "⚠️ Формат: `/add_time ID ДНИ`")
            return

        target_id = int(parts[1])
        days = int(parts[2])

        success, result_text = extend_user_trial(target_id, days)

        if success:
            bot.send_message(message.chat.id, f"✅ Подписка продлена до {result_text}")
            try:
                bot.send_message(target_id, f"🎉 Ваша подписка продлена на {days} дней!\nДействует до: {result_text}")
            except:
                pass
        else:
            bot.send_message(message.chat.id, f"❌ Ошибка: {result_text}")

    except ValueError:
        bot.send_message(message.chat.id, "❌ ID и дни должны быть числами!")


@bot.message_handler(commands=['set_agreement'])
def set_agreement_handler(message):
    """Команда для регистрации PDF договора. Используется только админом."""
    if message.chat.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "waiting_agreement_pdf"
    bot.send_message(ADMIN_ID, "📄 Отправьте PDF-файл договора об оказании услуг.")


@bot.message_handler(commands=['set_privacy'])
def set_privacy_handler(message):
    """Команда для регистрации PDF политики конфиденциальности. Используется только админом."""
    if message.chat.id != ADMIN_ID:
        return
    user_states[ADMIN_ID] = "waiting_privacy_pdf"
    bot.send_message(ADMIN_ID, "📄 Отправьте PDF-файл политики конфиденциальности.")


@bot.message_handler(commands=['confirm_payment'])
def confirm_payment_handler(message):
    """Ручное подтверждение оплаты (резервный вариант)."""
    if message.chat.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(ADMIN_ID, "⚠️ Формат: `/confirm_payment USER_ID`")
        return

    try:
        target_id = int(parts[1])
        _process_successful_payment_for_user(target_id, payment_id=f"manual_{target_id}")
        bot.send_message(ADMIN_ID, f"✅ Оплата подтверждена для пользователя {target_id}")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ USER_ID должен быть числом!")


# --- ОБРАБОТКА ДОКУМЕНТОВ (PDF для договора/политики) ---
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.chat.id
    state = user_states.get(user_id)

    if user_id == ADMIN_ID and state in ("waiting_agreement_pdf", "waiting_privacy_pdf"):
        doc = message.document
        if doc.mime_type != 'application/pdf':
            bot.send_message(ADMIN_ID, "❌ Нужен файл PDF.")
            return

        file_id = doc.file_id

        if state == "waiting_agreement_pdf":
            global PDF_AGREEMENT_FILE_ID
            PDF_AGREEMENT_FILE_ID = file_id
            save_pdf_file_id("PDF_AGREEMENT_FILE_ID", file_id)
            bot.send_message(ADMIN_ID, f"✅ Договор сохранён!\nfile_id: `{file_id}`", parse_mode="Markdown")
        else:
            global PDF_PRIVACY_FILE_ID
            PDF_PRIVACY_FILE_ID = file_id
            save_pdf_file_id("PDF_PRIVACY_FILE_ID", file_id)
            bot.send_message(ADMIN_ID, f"✅ Политика конфиденциальности сохранена!\nfile_id: `{file_id}`", parse_mode="Markdown")

        del user_states[user_id]


# --- ОБРАБОТКА ОТЗЫВОВ ---
@bot.message_handler(commands=['Обратная связь'])
def request_feedback(message):
    user_id = message.chat.id
    user_states[user_id] = "waiting_feedback"
    bot.send_message(user_id, "Я готов слушать! ✍️\nНапишите свой отзыв одним сообщением.")


@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.chat.id
    if user_states.get(user_id) == "waiting_feedback":
        feedback_text = message.text
        admin_message = (
            f"🔔 Новый фидбэк от {user_id} (@{message.from_user.username}):\n\n"
            f"{feedback_text}"
        )
        bot.send_message(ADMIN_ID, admin_message)
        del user_states[user_id]
        bot.send_message(user_id, "Спасибо! Передал админу 👍")
    else:
        pass


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ОПЛАТЫ ---

def _process_successful_payment_for_user(telegram_id, payment_id=None):
    """Обработка успешной оплаты: создаёт или продлевает подписку и выдаёт ключ."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT xray_uuid, trial_end_date FROM users WHERE telegram_id = ?", (telegram_id,))
    existing = cursor.fetchone()

    if existing:
        # Продлеваем существующую подписку
        xray_uuid = existing[0]
        current_end_str = existing[1]
        try:
            current_end = datetime.strptime(current_end_str, '%Y-%m-%d')
        except:
            current_end = datetime.now()

        now = datetime.now()
        new_end = (current_end if current_end > now else now) + timedelta(days=30)
        new_end_str = new_end.strftime('%Y-%m-%d')

        cursor.execute(
            "UPDATE users SET trial_end_date = ?, status = 'active', payment_type = 'paid' WHERE telegram_id = ?",
            (new_end_str, telegram_id)
        )
        conn.commit()

        if payment_id:
            cursor.execute(
                "UPDATE pending_payments SET status = 'paid' WHERE payment_id = ?",
                (payment_id,)
            )
            conn.commit()

        conn.close()

        vless_link = generate_vless_link(xray_uuid, tag="VPN1Month")
        qr_image = generate_qr_code(vless_link)

        bot.send_message(
            telegram_id,
            f"✅ *Оплата получена!*\n\n"
            f"Подписка продлена до: *{new_end_str}*\n\n"
            f"Ваш ключ VPN:\n`{vless_link}`",
            parse_mode="Markdown"
        )
        bot.send_photo(telegram_id, qr_image, caption="QR-код для подключения")

    else:
        # Создаём нового пользователя
        conn.close()
        new_uuid, new_email = create_xray_user(email_prefix="paid_user")
        if not new_uuid:
            bot.send_message(telegram_id, "❌ Ошибка сервера при создании ключа. Обратитесь в поддержку.")
            return

        add_user_to_db(telegram_id, new_uuid, new_email, payment_type='paid')

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        if payment_id:
            cursor.execute(
                "UPDATE pending_payments SET status = 'paid' WHERE payment_id = ?",
                (payment_id,)
            )
            conn.commit()
        conn.close()

        trial_end_str = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        vless_link = generate_vless_link(new_uuid, tag="VPN1Month")
        qr_image = generate_qr_code(vless_link)

        bot.send_message(
            telegram_id,
            f"✅ *Оплата получена! Добро пожаловать!*\n\n"
            f"Подписка активна до: *{trial_end_str}*\n\n"
            f"Ваш ключ VPN:\n`{vless_link}`",
            parse_mode="Markdown"
        )
        bot.send_photo(telegram_id, qr_image, caption="QR-код для подключения")

        try:
            with open(PDF_PATH, 'rb') as pdf_file:
                bot.send_document(telegram_id, pdf_file, caption="Инструкция по настройке 🤓")
        except Exception as e:
            print(f"Ошибка отправки инструкции: {e}")


# --- НАЖАТИЕ КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    print(f"[CALLBACK] user_id={user_id} data={call.data!r}")
    try:
        _handle_callback_inner(call, user_id)
    except Exception as e:
        print(f"[CALLBACK ERROR] data={call.data!r} error={e}")
        try:
            bot.answer_callback_query(call.id, "⚠️ Ошибка. Попробуйте ещё раз.")
        except:
            pass


def _handle_callback_inner(call, user_id):
    # 0. МАТРИЦА
    if call.data == "show_matrix":
        bot.answer_callback_query(call.id)
        send_matrix_status(call.message)
        return

    # 1. КНОПКА "ПОЛУЧИТЬ VPN (бесплатно)"
    if call.data == "get_vpn":
        bot.answer_callback_query(call.id, text="Проверяю базу...")

        if check_user_exists(user_id):
            bot.send_message(user_id, "Вы уже получили свой ключ. 😕")
            return

        bot.send_message(user_id, "Создаю личный ключ... ⚙️")

        new_uuid, new_email = create_xray_user()

        if new_uuid:
            add_user_to_db(user_id, new_uuid, new_email, payment_type='beta')
            bot.send_message(user_id, "✅ Ключ создан!")

            vless_link = generate_vless_link(new_uuid)
            qr_image = generate_qr_code(vless_link)

            bot.send_photo(user_id, qr_image, caption="Отсканируйте QR-код в v2rayNG / V2Box")
            bot.send_message(user_id, f"Или скопируйте ссылку:\n`{vless_link}`", parse_mode="Markdown")

            try:
                if PDF_PATH:
                    with open(PDF_PATH, 'rb') as pdf_file:
                        bot.send_document(user_id, pdf_file, caption="Инструкция по настройке 🤓")
            except Exception as e:
                print(f"Ошибка PDF: {e}")
        else:
            bot.send_message(user_id, "❌ Ошибка сервера. Напишите админу.")

    # 2. УСЛУГА "VPN НА МЕСЯЦ"
    elif call.data == "vpn_service":
        bot.answer_callback_query(call.id)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Оформить заказ", callback_data="place_order"))
        kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_menu"))

        text = (
            "🛡 *VPN на месяц*\n\n"
            "💰 Цена услуги: *99 рублей в месяц*\n\n"
            "• Безлимитный трафик\n"
            "• Протокол VLESS/Reality\n"
            "• Высокая скорость\n"
            "• Поддержка 24/7"
        )
        try:
            bot.edit_message_text(
                chat_id=user_id, message_id=call.message.message_id,
                text=text, reply_markup=kb, parse_mode="Markdown"
            )
        except:
            bot.send_message(user_id, text, reply_markup=kb, parse_mode="Markdown")

    # 3. ОФОРМЛЕНИЕ ЗАКАЗА (экран согласия)
    elif call.data == "place_order":
        bot.answer_callback_query(call.id)
        kb = types.InlineKeyboardMarkup()

        agreement_file_id = os.getenv("PDF_AGREEMENT_FILE_ID", PDF_AGREEMENT_FILE_ID)
        privacy_file_id = os.getenv("PDF_PRIVACY_FILE_ID", PDF_PRIVACY_FILE_ID)

        if agreement_file_id:
            kb.add(types.InlineKeyboardButton("📄 Договор об оказании услуг", callback_data="pdf_agreement"))
        if privacy_file_id:
            kb.add(types.InlineKeyboardButton("📄 Политика конфиденциальности", callback_data="pdf_privacy"))

        kb.add(types.InlineKeyboardButton("✅ Согласен — перейти к оплате", callback_data="agree_and_pay"))
        kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="vpn_service"))

        text = (
            "📋 *Перед оплатой*\n\n"
            "Продолжая, я соглашаюсь с:\n"
            "• Договором об оказании услуг\n"
            "• Политикой конфиденциальности\n\n"
            "_Нажмите на документ выше, чтобы ознакомиться_"
        )
        try:
            bot.edit_message_text(
                chat_id=user_id, message_id=call.message.message_id,
                text=text, reply_markup=kb, parse_mode="Markdown"
            )
        except:
            bot.send_message(user_id, text, reply_markup=kb, parse_mode="Markdown")

    # 4. ОТПРАВКА PDF ДОГОВОРА
    elif call.data == "pdf_agreement":
        bot.answer_callback_query(call.id)
        file_id = os.getenv("PDF_AGREEMENT_FILE_ID", PDF_AGREEMENT_FILE_ID)
        if file_id:
            try:
                bot.send_document(user_id, file_id, caption="📄 Договор об оказании услуг")
            except Exception as e:
                print(f"Ошибка отправки договора: {e}")
                bot.answer_callback_query(call.id, "Документ временно недоступен", show_alert=True)
        else:
            bot.answer_callback_query(
                call.id,
                "Документ ещё не загружен. Обратитесь к администратору.",
                show_alert=True
            )

    # 5. ОТПРАВКА PDF ПОЛИТИКИ КОНФИДЕНЦИАЛЬНОСТИ
    elif call.data == "pdf_privacy":
        bot.answer_callback_query(call.id)
        file_id = os.getenv("PDF_PRIVACY_FILE_ID", PDF_PRIVACY_FILE_ID)
        if file_id:
            try:
                bot.send_document(user_id, file_id, caption="📄 Политика конфиденциальности")
            except Exception as e:
                print(f"Ошибка отправки политики: {e}")
                bot.answer_callback_query(call.id, "Документ временно недоступен", show_alert=True)
        else:
            bot.answer_callback_query(
                call.id,
                "Документ ещё не загружен. Обратитесь к администратору.",
                show_alert=True
            )

    # 6. СОГЛАСИЕ И ПЕРЕХОД К ОПЛАТЕ
    elif call.data == "agree_and_pay":
        if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
            bot.answer_callback_query(
                call.id,
                "⚠️ Оплата временно недоступна. Напишите в поддержку.",
                show_alert=True
            )
            return

        bot.answer_callback_query(call.id, "Создаю платёж...")

        payment_id, payment_url = create_yookassa_payment(user_id)

        if payment_url:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(f"💳 Оплатить {SERVICE_PRICE} руб", url=payment_url))
            kb.add(types.InlineKeyboardButton("🔙 Отмена", callback_data="vpn_service"))

            bot.send_message(
                user_id,
                f"💳 *Оплата VPN на 1 месяц*\n\n"
                f"Сумма: *{SERVICE_PRICE} рублей*\n\n"
                "После оплаты ключ будет выдан автоматически.\n"
                "Ссылка действует 1 час.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(user_id, "❌ Ошибка создания платежа. Напишите в поддержку.")

    # 7. МОЙ ПРОФИЛЬ
    elif call.data == "my_profile":
        bot.answer_callback_query(call.id)
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT trial_end_date, status FROM users WHERE telegram_id=?", (user_id,))
        data = cur.fetchone()
        conn.close()

        if not data:
            bot.send_message(user_id, "Ошибка: профиль не найден.")
            return

        end_date_str = data[0]
        status = data[1]

        status_emoji = "✅ Активен" if status == 'active' else "🔴 Отключен"
        if status == 'banned':
            status_emoji = "🚫 Заблокирован"

        profile_text = (
            f"👤 *Личный кабинет*\n\n"
            f"🔑 Текущий статус: {status_emoji}\n"
            f"📅 Подписка истекает: *{end_date_str}*\n\n"
            f"🆔 Ваш ID: `{user_id}`"
        )

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🛡 VPN на месяц — 99 руб", callback_data="vpn_service"))
        kb.add(types.InlineKeyboardButton("🔑 Мой ключ VPN", callback_data="get_my_key"))
        kb.add(types.InlineKeyboardButton("🔙 В меню", callback_data="back_menu"))

        try:
            bot.edit_message_text(
                chat_id=user_id, message_id=call.message.message_id,
                text=profile_text, reply_markup=kb, parse_mode="Markdown"
            )
        except:
            bot.send_message(user_id, profile_text, reply_markup=kb, parse_mode="Markdown")

    # 8. ПОЛУЧИТЬ МОЙ КЛЮЧ
    elif call.data == "get_my_key":
        bot.answer_callback_query(call.id)
        vless_link = get_user_vless_link(user_id)
        if vless_link:
            qr_image = generate_qr_code(vless_link)
            bot.send_photo(user_id, qr_image, caption="QR-код для подключения")
            bot.send_message(user_id, f"Ваш ключ VPN:\n`{vless_link}`", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "Ключ не найден. Обратитесь в поддержку.", show_alert=True)

    # 9. НАЗАД В МЕНЮ
    elif call.data == "back_menu":
        bot.answer_callback_query(call.id)
        kb = types.InlineKeyboardMarkup()
        user_exists = check_user_exists(user_id)
        if user_exists:
            kb.add(types.InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile"))
            kb.add(types.InlineKeyboardButton("🛡 VPN на месяц — 99 руб", callback_data="vpn_service"))
            kb.add(
                types.InlineKeyboardButton("📖 Инструкция", callback_data="get_instruction"),
                types.InlineKeyboardButton("🆘 Поддержка", callback_data="ask_support")
            )
        else:
            kb.add(types.InlineKeyboardButton("🚀 Получить VPN (бесплатно)", callback_data="get_vpn"))
            kb.add(types.InlineKeyboardButton("🛡 VPN на месяц — 99 руб", callback_data="vpn_service"))

        try:
            bot.edit_message_text(
                chat_id=user_id, message_id=call.message.message_id,
                text="Главное меню:", reply_markup=kb
            )
        except:
            bot.send_message(user_id, "Главное меню:", reply_markup=kb)

    # 10. ИНСТРУКЦИЯ
    elif call.data == "get_instruction":
        bot.answer_callback_query(call.id)
        try:
            with open(PDF_PATH, 'rb') as f:
                bot.send_document(user_id, f, caption="Инструкция по настройке")
        except:
            bot.send_message(user_id, "Файл инструкции пока не загружен.")

    # 11. ПОДДЕРЖКА
    elif call.data == "ask_support":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "✍️ Напишите свой вопрос следующим сообщением, я передам его Админу.")
        user_states[user_id] = "waiting_feedback"


# --- ЗАПУСК ---
print("Бот запущен...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
