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
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/vpn-bot/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загружаем секреты из файла .env
load_dotenv()

# ----- НАСТРОЙКИ -----
# Берем токен из .env
TOKEN = os.getenv("BOT_TOKEN")
# Берем ID админа из .env и превращаем в число
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

# Проверка, что файл .env прочитался
if not TOKEN or not ADMIN_ID:
    logger.error("ОШИБКА: Не найдены BOT_TOKEN или ADMIN_ID в файле .env")
    exit(1)

# Пути к файлам
DB_NAME = "/root/vpn-bot/vpn_users.db"
CONFIG_FILE_PATH = "/usr/local/etc/xray/config.json"
PDF_PATH = "/root/vpn-bot/instruction.pdf"

# Лимиты
BETA_LIMIT = 30

# Текст для оплаты (ЗАПОЛНИ ЗДЕСЬ СВОИ РЕКВИЗИТЫ)
PAYMENT_INFO = """
💳 **Реквизиты для продления:**

Перевод по СБП (Сбер/Тинькофф):
`+7 999 000-00-00`
Получатель: Иван И.

💰 Стоимость: 100р / месяц
❗️ В комментарии к платежу укажите ваш ID телеграм.
"""

# Настройки VLESS Reality (синхронизированы с config.json)
SERVER_ADDRESS = "141.105.143.224"
SERVER_PORT = 443
REALITY_PUBLIC_KEY = "O_actbJXCoMijlOyrLMWWKQQ7a3tEYZe3Hix86Yr3kM"
REALITY_SHORT_ID = "a028507ab5b114b4"
REALITY_SNI = "www.yahoo.com"

# Память для отзывов
user_states = {}

bot = telebot.TeleBot(TOKEN)

# --- ФУНКЦИИ ---

def init_database():
    """Инициализация базы данных при запуске"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    xray_uuid TEXT NOT NULL,
                    email TEXT NOT NULL,
                    trial_end_date TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("База данных инициализирована успешно")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise

def generate_vless_link(user_uuid):
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
    link = f"vless://{user_uuid}@{SERVER_ADDRESS}:{SERVER_PORT}?{query_string}#BetaTest"
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

        # Читаем конфиг
        with open(CONFIG_FILE_PATH, 'r') as f:
            data = json.load(f)

        new_client = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
            "email": new_email,
            "level": 0
        }

        # Проверяем структуру конфига
        if 'inbounds' not in data or len(data['inbounds']) < 2:
            logger.error("Некорректная структура конфига Xray")
            return None, None

        # Добавляем клиента
        data['inbounds'][1]['settings']['clients'].append(new_client)

        # Записываем обратно
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(data, f, indent=2)

        # Перезапускаем Xray
        subprocess.run(["systemctl", "restart", "xray"], check=True, timeout=10)
        logger.info(f"Создан пользователь Xray: {new_email}")
        return new_uuid, new_email
    except subprocess.TimeoutExpired:
        logger.error("Таймаут при перезапуске Xray")
        return None, None
    except Exception as e:
        logger.error(f"Ошибка создания пользователя Xray: {e}")
        return None, None

def add_user_to_db(user_id, xray_uuid, email):
    """Добавление в базу"""
    try:
        trial_end = datetime.now() + timedelta(days=30)
        trial_end_str = trial_end.strftime('%Y-%m-%d')

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (telegram_id, xray_uuid, email, trial_end_date, status) VALUES (?, ?, ?, ?, 'active')",
                (user_id, xray_uuid, email, trial_end_str)
            )
            conn.commit()
        logger.info(f"Пользователь {user_id} добавлен в БД")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"Пользователь {user_id} уже существует в БД")
        return False
    except Exception as e:
        logger.error(f"Ошибка добавления в БД: {e}")
        return False

def check_user_exists(user_id):
    """Проверка существования пользователя"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE telegram_id = ?", (user_id,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка проверки пользователя: {e}")
        return False

def count_total_users():
    """Подсчет активных пользователей (только для лимита бета-теста)"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            # Считаем только активных пользователей
            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'active'")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Ошибка подсчета пользователей: {e}")
        return 0

def extend_user_trial(target_user_id, days):
    """Продление подписки (для админа)"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT trial_end_date FROM users WHERE telegram_id = ?", (target_user_id,))
            result = cursor.fetchone()

            if not result:
                return False, "Пользователь не найден."

            current_end_str = result[0]
            try:
                current_end_date = datetime.strptime(current_end_str, '%Y-%m-%d')
            except ValueError as ve:
                logger.warning(f"Некорректный формат даты для пользователя {target_user_id}: {ve}")
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
            logger.info(f"Подписка пользователя {target_user_id} продлена до {new_end_str}")
            return True, new_end_str
    except Exception as e:
        logger.error(f"Ошибка продления подписки: {e}")
        return False, f"Ошибка: {e}"

# --- ОБРАБОТЧИКИ БОТА ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    logger.info(f"Пользователь {user_id} использовал /start")

    # Проверяем, знает ли бот этого человека
    user_exists = check_user_exists(user_id)

    keyboard = types.InlineKeyboardMarkup()

    if user_exists:
        # ВАРИАНТ А: СТАРЫЙ ДРУГ
        btn_profile = types.InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile")
        btn_instruction = types.InlineKeyboardButton("📖 Инструкция", callback_data="get_instruction")
        btn_support = types.InlineKeyboardButton("🆘 Поддержка", callback_data="ask_support")
        btn_matrix = types.InlineKeyboardButton("🕶 Матрица", callback_data="show_matrix")

        keyboard.add(btn_profile)
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
    """Показать статус в стиле Matrix"""
    # Заглушка трафика
    traffic_gb = random.uniform(10.0, 25.0)

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
        "💊 Это твой последний шанс. Синяя таблетка — пинг 300мс. Красная таблетка — пинг 30мс. Выбирай.",
        "🐇 Тук-тук, это провайдер. Шучу, мы зашифрованы.",
        "😎 Я не сказал, что будет легко. Я лишь обещал открыть правду"
    ]
    time.sleep(1)
    bot.send_message(message.chat.id, random.choice(jokes))

# Обработчик нажатия на кнопку "Матрица"
@bot.callback_query_handler(func=lambda call: call.data == 'show_matrix')
def callback_matrix(call):
    bot.answer_callback_query(call.id)
    send_matrix_status(call.message)

# --- КОМАНДА АДМИНА ---
@bot.message_handler(commands=['add_time'])
def add_time_handler(message):
    """Команда админа для продления подписки пользователю"""
    if message.chat.id != ADMIN_ID:
        logger.warning(f"Попытка использовать /add_time от {message.chat.id}")
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "⚠️ Формат: `/add_time ID ДНИ`", parse_mode="Markdown")
            return

        target_id = int(parts[1])
        days = int(parts[2])

        if days <= 0:
            bot.send_message(message.chat.id, "❌ Количество дней должно быть положительным числом!")
            return

        success, result_text = extend_user_trial(target_id, days)

        if success:
            bot.send_message(message.chat.id, f"✅ Подписка продлена до {result_text}")
            try:
                bot.send_message(
                    target_id,
                    f"🎉 Ваша подписка продлена на {days} дней!\nДействует до: {result_text}"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление пользователю {target_id}: {e}")
        else:
            bot.send_message(message.chat.id, f"❌ Ошибка: {result_text}")

    except ValueError:
        bot.send_message(message.chat.id, "❌ ID и дни должны быть числами!")
    except Exception as e:
        logger.error(f"Ошибка в /add_time: {e}")
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")

# --- ОБРАБОТКА ОТЗЫВОВ ---
@bot.message_handler(commands=['feedback'])
def request_feedback(message):
    """Запрос обратной связи от пользователя"""
    user_id = message.chat.id
    user_states[user_id] = "waiting_feedback"
    bot.send_message(user_id, "Я готов слушать! ✍️\nНапишите свой отзыв одним сообщением.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    """Обработка текстовых сообщений (для обратной связи)"""
    user_id = message.chat.id
    if user_states.get(user_id) == "waiting_feedback":
        feedback_text = message.text
        username = message.from_user.username or "нет username"
        admin_message = (
            f"🔔 Новый фидбэк от {user_id} (@{username}):\n\n"
            f"{feedback_text}"
        )
        try:
            bot.send_message(ADMIN_ID, admin_message)
            del user_states[user_id]
            bot.send_message(user_id, "Спасибо! Передал админу 👍")
            logger.info(f"Получен фидбек от {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки фидбека админу: {e}")
            bot.send_message(user_id, "Произошла ошибка при отправке сообщения. Попробуйте позже.")

# --- НАЖАТИЕ КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Обработчик всех inline-кнопок"""
    user_id = call.message.chat.id  # ВАЖНО: определяем user_id в начале

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
            if add_user_to_db(user_id, new_uuid, new_email):
                bot.send_message(user_id, "✅ Ключ создан!")

                # Ссылка и QR
                vless_link = generate_vless_link(new_uuid)
                qr_image = generate_qr_code(vless_link)

                bot.send_photo(user_id, qr_image, caption="Отсканируйте QR-код в v2rayNG / V2Box")
                bot.send_message(user_id, f"Или скопируйте ссылку:\n`{vless_link}`", parse_mode="Markdown")

                # Отправка Инструкции (PDF)
                try:
                    if PDF_PATH and os.path.exists(PDF_PATH):
                        with open(PDF_PATH, 'rb') as pdf_file:
                            bot.send_document(user_id, pdf_file, caption="Инструкция по настройке 🤓")
                except FileNotFoundError:
                    logger.warning(f"PDF инструкция не найдена: {PDF_PATH}")
                except Exception as e:
                    logger.error(f"Ошибка отправки PDF: {e}")
            else:
                bot.send_message(user_id, "❌ Ошибка добавления в базу данных.")
        else:
            bot.send_message(user_id, "❌ Ошибка сервера. Напишите админу.")

    # 2. КНОПКА "МОЙ ПРОФИЛЬ"
    elif call.data == "my_profile":
        bot.answer_callback_query(call.id)

        try:
            with sqlite3.connect(DB_NAME) as conn:
                cur = conn.cursor()
                cur.execute("SELECT trial_end_date, status FROM users WHERE telegram_id=?", (user_id,))
                data = cur.fetchone()

            if not data:
                bot.send_message(user_id, "Ошибка: профиль не найден.")
                return

            end_date_str = data[0]
            status = data[1]

            # Выбираем красивый значок
            status_emoji = "✅ Активен" if status == 'active' else "🔴 Отключен"
            if status == 'banned':
                status_emoji = "🚫 Заблокирован"

            profile_text = (
                f"👤 **Личный кабинет**\n\n"
                f"🔑 Текущий статус: {status_emoji}\n"
                f"📅 Подписка истекает: **{end_date_str}**\n\n"
                f"🆔 Ваш ID: `{user_id}`"
            )

            kb = types.InlineKeyboardMarkup()
            btn_pay = types.InlineKeyboardButton("💳 Продлить подписку", callback_data="pay_extend")
            btn_back = types.InlineKeyboardButton("🔙 В меню", callback_data="back_menu")
            kb.add(btn_pay)
            kb.add(btn_back)

            bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text=profile_text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ошибка в my_profile: {e}")
            bot.send_message(user_id, "Произошла ошибка при загрузке профиля.")

    # 3. КНОПКА "ПРОДЛИТЬ"
    elif call.data == "pay_extend":
        bot.answer_callback_query(call.id)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="my_profile"))

        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=PAYMENT_INFO,
            reply_markup=kb,
            parse_mode="Markdown"
        )

    # 4. КНОПКА "НАЗАД В МЕНЮ"
    elif call.data == "back_menu":
        bot.answer_callback_query(call.id)

        kb = types.InlineKeyboardMarkup()
        btn_profile = types.InlineKeyboardButton("👤 Мой профиль", callback_data="my_profile")
        btn_instruction = types.InlineKeyboardButton("📖 Инструкция", callback_data="get_instruction")
        btn_support = types.InlineKeyboardButton("🆘 Поддержка", callback_data="ask_support")
        btn_matrix = types.InlineKeyboardButton("🕶 Матрица", callback_data="show_matrix")

        kb.add(btn_profile)
        kb.add(btn_instruction, btn_support)
        kb.add(btn_matrix)

        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="Главное меню:",
            reply_markup=kb
        )

    # 5. ИНСТРУКЦИЯ
    elif call.data == "get_instruction":
        try:
            if os.path.exists(PDF_PATH):
                with open(PDF_PATH, 'rb') as f:
                    bot.send_document(user_id, f, caption="Инструкция по настройке")
                bot.answer_callback_query(call.id)
            else:
                bot.answer_callback_query(call.id, "Файл инструкции пока не загружен", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка отправки инструкции: {e}")
            bot.answer_callback_query(call.id, "Ошибка загрузки файла", show_alert=True)

    # 6. ПОДДЕРЖКА
    elif call.data == "ask_support":
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "✍️ Напишите свой вопрос следующим сообщением, я передам его Админу.")
        user_states[user_id] = "waiting_feedback"

# --- ЗАПУСК ---
if __name__ == "__main__":
    try:
        logger.info("Инициализация базы данных...")
        init_database()
        logger.info("Бот запущен...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        raise
