PAYMENT_INFO = "Для продления подписки напишите @admin"
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
import os  # <-- НОВЫЙ ИМПОРТ
from dotenv import load_dotenv # <-- НОВЫЙ ИМПОРТ
import random
import time

from proxy_routing import update_xray_proxy_routing

# Загружаем секреты из файла .env
load_dotenv()

# ----- НАСТРОЙКИ -----
# Берем токен из .env
TOKEN = os.getenv("BOT_TOKEN")
# Берем ID админа из .env и превращаем в число
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Проверка, что файл .env прочитался
if not TOKEN or not ADMIN_ID:
    print("ОШИБКА: Не найдены BOT_TOKEN или ADMIN_ID в файле .env")
    exit()

# Пути к файлам (ЛУЧШЕ ИСПОЛЬЗОВАТЬ ПОЛНЫЕ ПУТИ)
DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE_PATH = "/usr/local/etc/xray/config.json"
PDF_PATH = "/root/vpn-bot/instruction.pdf"

# Лимиты
BETA_LIMIT = 30

# Настройки VLESS (Твои данные)
SERVER_ADDRESS = "141.105.143.224"
SERVER_PORT = 443
REALITY_PUBLIC_KEY = "O_actbJXCoMijlOyrLMWWKQQ7a3tEYZe3Hix86Yr3kM"
REALITY_SHORT_ID = "a028507ab5b114b4"
REALITY_SNI = "www.microsoft.com"

# Память для отзывов
user_states = {}

bot = telebot.TeleBot(TOKEN)

# ── Mini App ──────────────────────────────────────────────────
# Заглушка для PAYMENT_INFO (используется в callback pay_extend)
PAYMENT_INFO = "Для продления подписки откройте приложение или напишите @admin"
MINI_APP_URL = "https://olegych.org/app/index.html"

# --- ФУНКЦИИ ---

def generate_vless_link(user_uuid, tag="olegych"):
    """Генерация ссылки VLESS Reality"""
    params = {
        "security": "reality",
        "sni": REALITY_SNI,
        "pbk": REALITY_PUBLIC_KEY,
        "sid": REALITY_SHORT_ID,
        "flow": "xtls-rprx-vision",
        "type": "tcp",
        "fp": "firefox"
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

def create_xray_user():
    """Создание пользователя в конфиге Xray"""
    try:
        new_uuid = str(uuid.uuid4())
        new_email = f"beta_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
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

def add_user_to_db(user_id, xray_uuid, email):
    """Добавление в базу"""
    try:
        trial_end = datetime.now() + timedelta(days=30)
        trial_end_str = trial_end.strftime('%Y-%m-%d')
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (telegram_id, xray_uuid, email, trial_end_date, status) VALUES (?, ?, ?, ?, 'active')",
            (user_id, xray_uuid, email, trial_end_str)
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

def extend_user_trial(target_user_id, days):
    """Продление подписки (для админа)"""
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

        cursor.execute("UPDATE users SET trial_end_date = ?, status = 'active' WHERE telegram_id = ?", (new_end_str, target_user_id,))
        conn.commit()
        conn.close()
        return True, new_end_str
    except Exception as e:
        return False, f"Ошибка: {e}"

def get_user_proxy_status(user_id):
    """Возвращает текущий статус прокси для пользователя: 0 или 1"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT proxy_enabled FROM users WHERE telegram_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else 0

def toggle_user_proxy(user_id):
    """Переключает proxy_enabled для юзера. Возвращает новый статус (0 или 1)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT proxy_enabled FROM users WHERE telegram_id=?", (user_id,))
    row = cursor.fetchone()
    current = row[0] if row and row[0] is not None else 0
    new_status = 0 if current else 1
    cursor.execute(
        "UPDATE users SET proxy_enabled=? WHERE telegram_id=?",
        (new_status, user_id),
    )
    conn.commit()
    conn.close()
    return new_status

def build_profile_view(user_id):
    """
    Собирает текст и клавиатуру карточки «Личный кабинет».
    Возвращает (profile_text, kb) или None если юзер не найден в БД.
    Единая точка сборки — используется и в my_profile, и в proxy_toggle.
    """
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT trial_end_date, status FROM users WHERE telegram_id=?", (user_id,))
    data = cur.fetchone()
    conn.close()
    if not data:
        return None

    end_date_str, status = data[0], data[1]
    status_emoji = "✅ Активен" if status == "active" else "🔴 Отключен"
    if status == "banned":
        status_emoji = "🚫 Заблокирован"

    proxy_status = get_user_proxy_status(user_id)
    proxy_emoji = "🟢" if proxy_status else "🔴"
    proxy_label = "ВКЛ" if proxy_status else "ВЫКЛ"
    proxy_note = "IP меняется при каждом соединении" if proxy_status else "Прямое соединение"

    profile_text = (
        f"👤 **Личный кабинет**\n\n"
        f"🔑 Текущий статус: {status_emoji}\n"
        f"📅 Подписка истекает: **{end_date_str}**\n"
        f"{proxy_emoji} Прокси: **{proxy_label}** — {proxy_note}\n\n"
        f"🆔 Ваш ID: `{user_id}`"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💳 Продлить подписку", callback_data="pay_extend"))
    kb.add(types.InlineKeyboardButton(
        f"{proxy_emoji} Прокси (смена IP): {proxy_label}",
        callback_data="proxy_toggle",
    ))
    kb.add(types.InlineKeyboardButton("🔙 В меню", callback_data="back_menu"))
    return profile_text, kb

# --- ОБРАБОТЧИКИ БОТА ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    # Проверяем, знает ли бот этого человека
    user_data = check_user_exists(user_id)

    keyboard = types.InlineKeyboardMarkup()

    if user_data:
        if user_data:
        # ВАРИАНТ А: СТАРЫЙ ДРУГ
        # Создаем кнопки
            btn_profile = types.InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile")
            btn_webapp = types.InlineKeyboardButton(
                "🌐 Открыть приложение",
                web_app=types.WebAppInfo(url=MINI_APP_URL),
            )
            btn_instruction = types.InlineKeyboardButton("📖 Инструкция", callback_data="get_instruction")
            btn_support = types.InlineKeyboardButton("🆘 Поддержка", callback_data="ask_support")
            btn_matrix = types.InlineKeyboardButton("🕶 Матрица", callback_data="show_matrix")

            # Добавляем их на клавиатуру (СТРОГО ПО ОДНОМУ РАЗУ)
            keyboard.add(btn_profile)
            keyboard.add(btn_webapp)
            keyboard.add(btn_instruction, btn_support)
            keyboard.add(btn_matrix)

            text = "С возвращением! 👋\nГлавное меню:"
    else:
        # ВАРИАНТ Б: НОВИЧОК
        btn_get = types.InlineKeyboardButton("🚀 Получить VPN (подписка на 30 дней)", callback_data="get_vpn")
        keyboard.add(btn_get)
        text = (
            "Привет! Это частный VPN бот Олегыч. 🛡\n\n"
            "Жми кнопку, чтобы получить доступ 👇"
        )

    bot.send_message(user_id, text, reply_markup=keyboard)

@bot.message_handler(commands=['matrix'])
def send_matrix_status(message):
    # Заглушка трафика
    traffic_gb = 14.5

    # 1. Генерация данных
    matrix_x = random.randint(10, 99)
    matrix_y = random.randint(10, 99)
    matrix_z = random.randint(10, 99)
    matrix_code = hex(random.getrandbits(32)).upper()[2:]

    # Генерируем "Пинг" (от 25 до 110 мс) для вида
    ping_ms = random.randint(25, 110)

    kana = ["ｸ", "ﾗ", "ｽ", "ﾂ", "ﾇ", "ﾎ", "ﾑ", "ｴ", "ｷ", "ﾏ", "ﾅ", "ﾔ"]
    deco = random.choice(kana) + random.choice(kana) + random.choice(kana)

    user_label = message.from_user.username or message.from_user.first_name or "NEO"

    # 2. Арт с добавленным ПИНГОМ
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

    # 3. Анимация
    msg = bot.send_message(message.chat.id, "🔌 Connecting to the Source...")
    time.sleep(1)
    bot.edit_message_text("💾 Uploading consciousness...", chat_id=message.chat.id, message_id=msg.message_id)
    time.sleep(1.5)

    # 4. Отправка
    bot.send_message(message.chat.id, matrix_text, parse_mode="Markdown")

    # 5. Шутка
    jokes = [
        "🧪 Есть только два способа написать код без багов... но третий тебе не понравится.",
        "🕶️ Wake up, Neo. Твой VPN подключен.",
        "💊 Это твой последний шанс. После этого пути назад нет.Синяя таблетка — пинг 300мс. Красная таблетка — пинг 30мс. Выбирай.",
        "🐇 Тук-тук, это провайдер. Шучу, мы зашифрованы.",
        "😎 Я не сказал, что будет легко. Я лишь обещал открыть правду"
    ]
    time.sleep(1)
    bot.send_message(message.chat.id, random.choice(jokes))

# Обработчик нажатия на кнопку "Матрица"
@bot.callback_query_handler(func=lambda call: call.data == 'show_matrix')
def callback_matrix(call):
    # Чтобы кнопка не "крутилась", отвечаем телеграму, что мы приняли сигнал
    bot.answer_callback_query(call.id)
    # И просто запускаем ту же самую функцию, что и для команды /matrix
    send_matrix_status(call.message)

# --- КОМАНДА АДМИНА (КОТОРУЮ ТЫ ИСКАЛА) ---
@bot.message_handler(commands=['add_time'])
def add_time_handler(message):
    if message.chat.id != ADMIN_ID:
        return # Игнорируем чужаков

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

# --- ОБРАБОТКА ОТЗЫВОВ ---
@bot.message_handler(commands=['Обратная связь'])
def request_feedback(message):
    user_id = message.chat.id
    user_states[user_id] = "waiting_feedback"
    bot.send_message(user_id, "Я готов слушать! ✍️\nНапишите свой отзыв одним сообщением.")

# ВНИМАНИЕ: Эта функция теперь СНАРУЖИ, как и должно быть
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

# --- НАЖАТИЕ КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id

    if call.data == "get_vpn":
        bot.answer_callback_query(call.id, text="Проверяю базу...")

        if check_user_exists(user_id):
            bot.send_message(user_id, "Вы уже получили свой ключ. 😕")
            return

        if count_total_users() >= BETA_LIMIT:
            bot.send_message(user_id, "Лимит бета-тестеров исчерпан. 😥")
            return

        bot.send_message(user_id, "Создаю личный ключ... ⚙️")

        new_uuid, new_email = create_xray_user()

        if new_uuid:
            add_user_to_db(user_id, new_uuid, new_email)
            bot.send_message(user_id, "✅ Ключ создан!")

            # Ссылка и QR
            vless_link = generate_vless_link(new_uuid)
            qr_image = generate_qr_code(vless_link)

            bot.send_photo(user_id, qr_image, caption="Отсканируйте QR-код в v2rayNG / V2Box")
            bot.send_message(user_id, f"Или скопируйте ссылку:\n`{vless_link}`", parse_mode="Markdown")

            # Отправка Инструкции (PDF)
            try:
                if PDF_PATH: # Проверяем, задан ли путь
                    with open(PDF_PATH, 'rb') as pdf_file:
                        bot.send_document(user_id, pdf_file, caption="Инструкция по настройке 🤓")
            except Exception as e:
                print(f"Ошибка PDF: {e}")
                # Не пугаем юзера ошибкой, просто молчим про PDF
        else:
            bot.send_message(user_id, "❌ Ошибка сервера. Напишите админу.")
# ... (тут выше был код для "get_vpn", его не трогаем) ...

    # --- НОВАЯ ЧАСТЬ НАЧИНАЕТСЯ ЗДЕСЬ ---

    # 2. КНОПКА "МОЙ ПРОФИЛЬ"
    elif call.data == "my_profile":
        view = build_profile_view(user_id)
        if view is None:
            bot.send_message(user_id, "Ошибка: профиль не найден.")
            return
        profile_text, kb = view
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=profile_text,
            reply_markup=kb,
            parse_mode="Markdown",
        )

    # 2b. КНОПКА "ПРОКСИ"
    elif call.data == "proxy_toggle":
        if not check_user_exists(user_id):
            bot.answer_callback_query(call.id, "Сначала получите доступ к VPN")
            return

        bot.answer_callback_query(call.id, "⏳ Переключаю прокси...")
        toggle_user_proxy(user_id)

        ok = update_xray_proxy_routing()
        if not ok:
            # Откатываем флаг строго через toggle_user_proxy — единая точка входа.
            toggle_user_proxy(user_id)
            bot.send_message(
                user_id,
                "❌ Ошибка при переключении прокси. Напишите в поддержку.",
            )
            return

        view = build_profile_view(user_id)
        if view is None:
            return
        profile_text, kb = view
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=profile_text,
            reply_markup=kb,
            parse_mode="Markdown",
        )

    # 3. КНОПКА "ПРОДЛИТЬ" (Показываем реквизиты)
    elif call.data == "pay_extend":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="my_profile"))

        # Берем текст из переменной PAYMENT_INFO (которую мы задали вверху)
        bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text=PAYMENT_INFO, reply_markup=kb, parse_mode="Markdown")

    # 4. КНОПКА "НАЗАД В МЕНЮ"
    elif call.data == "back_menu":
        # Рисуем то же самое меню, что и в /start
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile"))
        kb.add(types.InlineKeyboardButton("📖 Инструкция", callback_data="get_instruction"), types.InlineKeyboardButton("🆘 Поддержка", callback_data="ask_support"))

        bot.edit_message_text(chat_id=user_id, message_id=call.message.message_id, text="Главное меню:", reply_markup=kb)

    # 5. ИНСТРУКЦИЯ (Если у тебя есть файл PDF)
    elif call.data == "get_instruction":
        try:
            with open(PDF_PATH, 'rb') as f:
                bot.send_document(user_id, f, caption="Инструкция по настройке")
        except:
            bot.answer_callback_query(call.id, "Файл инструкции пока не загружен")

    # 6. ПОДДЕРЖКА
    elif call.data == "ask_support":
        bot.send_message(user_id, "✍️ Напишите свой вопрос следующим сообщением, я передам его Админу.")
        # Запоминаем, что этот человек хочет написать админу
        user_states[user_id] = "waiting_feedback"
# --- ЗАПУСК ---
print("Бот запущен...")
bot.infinity_polling(timeout=10, long_polling_timeout=5)