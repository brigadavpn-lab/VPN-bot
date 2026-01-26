# 🚀 Развертывание VPN бота с GitHub на сервер

## 📋 Предварительные требования

- ✅ Сервер на Ubuntu/Debian с root доступом
- ✅ IP: 141.105.143.224 (из конфига)
- ✅ Открытый порт 443
- ✅ Токен бота от @BotFather
- ✅ Ваш Telegram ID

---

## 🔧 Шаг 1: Подготовка сервера

```bash
# Подключитесь к серверу
ssh root@141.105.143.224

# Обновите систему
apt update && apt upgrade -y

# Установите необходимые пакеты
apt install -y curl wget git python3 python3-pip sqlite3 ufw
```

---

## 📦 Шаг 2: Установка Xray

```bash
# Скачайте и установите Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Проверьте установку
xray version

# Создайте директорию для логов
mkdir -p /var/log/xray
```

---

## 🔐 Шаг 3: Клонирование репозитория

```bash
# Клонируйте репозиторий
cd /root
git clone https://github.com/brigadavpn-lab/VPN-bot.git vpn-bot

# Перейдите в директорию
cd vpn-bot

# Переключитесь на рабочую ветку (если нужно)
git checkout claude/telegram-bot-setup-0swBs

# Проверьте содержимое
ls -la
```

**Должны увидеть:**
- bot.py
- config.json
- SETUP_INSTRUCTIONS.md
- CONFIG_CHANGES.md
- README_VARIANT_A.md
- .gitignore

---

## ⚙️ Шаг 4: Установка конфигурации Xray

```bash
# Скопируйте конфиг Xray
cp /root/vpn-bot/config.json /usr/local/etc/xray/config.json

# Установите права
chmod 644 /usr/local/etc/xray/config.json

# Проверьте конфиг на ошибки
xray run -test -config /usr/local/etc/xray/config.json
```

**Ожидаемый вывод:**
```
Configuration OK
```

Если ошибка - проверьте JSON синтаксис:
```bash
python3 -m json.tool /usr/local/etc/xray/config.json
```

---

## 🐍 Шаг 5: Установка зависимостей Python

```bash
cd /root/vpn-bot

# Установите зависимости бота
pip3 install pyTelegramBotAPI python-dotenv qrcode[pil]

# Проверьте установку
python3 -c "import telebot; print('✅ pyTelegramBotAPI OK')"
python3 -c "import qrcode; print('✅ qrcode OK')"
python3 -c "from dotenv import load_dotenv; print('✅ python-dotenv OK')"
```

---

## 🔑 Шаг 6: Создание файла .env

```bash
cd /root/vpn-bot

# Создайте .env файл
nano .env
```

**Содержимое .env:**
```env
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_ID=123456789
```

**Замените:**
- `BOT_TOKEN` - токен от @BotFather
- `ADMIN_ID` - ваш Telegram ID (узнать можно у @userinfobot)

**Сохраните:** Ctrl+O → Enter → Ctrl+X

**Установите права:**
```bash
chmod 600 /root/vpn-bot/.env
```

---

## 🔥 Шаг 7: Настройка Firewall

```bash
# Включите UFW
ufw allow 22/tcp     # SSH (чтобы не потерять доступ!)
ufw allow 443/tcp    # Xray Reality
ufw --force enable

# Проверьте статус
ufw status
```

**Должно быть:**
```
443/tcp    ALLOW    Anywhere
22/tcp     ALLOW    Anywhere
```

---

## 🚀 Шаг 8: Запуск Xray

```bash
# Включите автозапуск
systemctl enable xray

# Запустите Xray
systemctl start xray

# Проверьте статус
systemctl status xray
```

**Должно быть:**
```
● xray.service - Xray Service
   Active: active (running)
```

**Проверьте логи:**
```bash
tail -f /var/log/xray/error.log
```

Если ошибок нет - Ctrl+C для выхода.

**Проверьте порт:**
```bash
ss -tlnp | grep 443
```

Должно быть: `LISTEN ... *:443 ... users:(("xray"...))`

---

## 🤖 Шаг 9: Создание systemd сервиса для бота

```bash
# Создайте файл сервиса
nano /etc/systemd/system/vpn-bot.service
```

**Содержимое:**
```ini
[Unit]
Description=VPN Telegram Bot
After=network.target xray.service
Requires=xray.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/vpn-bot
ExecStart=/usr/bin/python3 /root/vpn-bot/bot.py
Restart=always
RestartSec=10
StandardOutput=append:/root/vpn-bot/bot.log
StandardError=append:/root/vpn-bot/bot.log

[Install]
WantedBy=multi-user.target
```

**Сохраните:** Ctrl+O → Enter → Ctrl+X

---

## 🎯 Шаг 10: Запуск бота

```bash
# Перезагрузите systemd
systemctl daemon-reload

# Включите автозапуск
systemctl enable vpn-bot

# Запустите бота
systemctl start vpn-bot

# Проверьте статус
systemctl status vpn-bot
```

**Должно быть:**
```
● vpn-bot.service - VPN Telegram Bot
   Active: active (running)
```

**Проверьте логи бота:**
```bash
tail -f /root/vpn-bot/bot.log
```

Должно быть:
```
INFO - Инициализация базы данных...
INFO - База данных инициализирована успешно
INFO - Бот запущен...
```

---

## 🧪 Шаг 11: Тестирование

### 11.1 Проверьте базу данных
```bash
ls -la /root/vpn-bot/vpn_users.db
```

Файл должен существовать.

### 11.2 Откройте Telegram
1. Найдите вашего бота
2. Отправьте `/start`
3. Нажмите "🚀 Получить VPN"

### 11.3 Если получили QR и ссылку
✅ **ВСЁ РАБОТАЕТ!**

### 11.4 Проверьте пользователей в БД
```bash
sqlite3 /root/vpn-bot/vpn_users.db "SELECT telegram_id, email, status, trial_end_date FROM users;"
```

---

## 📊 Мониторинг и управление

### Просмотр логов в реальном времени:

**Xray:**
```bash
tail -f /var/log/xray/error.log
```

**Бот:**
```bash
tail -f /root/vpn-bot/bot.log
# или
journalctl -u vpn-bot -f
```

### Перезапуск сервисов:

```bash
# Перезапуск Xray
systemctl restart xray

# Перезапуск бота
systemctl restart vpn-bot

# Перезапуск обоих
systemctl restart xray vpn-bot
```

### Статус сервисов:

```bash
systemctl status xray vpn-bot
```

### Остановка сервисов:

```bash
systemctl stop vpn-bot
systemctl stop xray
```

---

## 🔄 Обновление с GitHub

Если в репозитории появились изменения:

```bash
cd /root/vpn-bot

# Сохраните .env (если есть изменения)
cp .env .env.backup

# Получите изменения
git fetch origin
git pull origin claude/telegram-bot-setup-0swBs

# Восстановите .env (если нужно)
cp .env.backup .env

# Обновите конфиг Xray (если изменился)
cp config.json /usr/local/etc/xray/config.json

# Перезапустите сервисы
systemctl restart xray vpn-bot
```

---

## 🛠 Команды администратора

### Добавить время пользователю:
```bash
# В Telegram напишите боту:
/add_time USER_ID DAYS

# Пример: продлить подписку пользователю 123456789 на 30 дней
/add_time 123456789 30
```

### Просмотр всех пользователей:
```bash
sqlite3 /root/vpn-bot/vpn_users.db "SELECT * FROM users;"
```

### Удаление пользователя из Xray config:
```bash
nano /usr/local/etc/xray/config.json
# Найдите и удалите клиента
systemctl restart xray
```

---

## 🐛 Troubleshooting

### Проблема: "Бот не отвечает"

```bash
# Проверьте статус
systemctl status vpn-bot

# Проверьте логи
tail -50 /root/vpn-bot/bot.log

# Проверьте .env файл
cat /root/vpn-bot/.env

# Перезапустите
systemctl restart vpn-bot
```

### Проблема: "Ключ создан, но не работает"

```bash
# Проверьте Xray
systemctl status xray
tail -50 /var/log/xray/error.log

# Проверьте порт
ss -tlnp | grep 443

# Проверьте firewall
ufw status

# Проверьте конфиг
xray run -test -config /usr/local/etc/xray/config.json
```

### Проблема: "База данных не создается"

```bash
# Проверьте права
ls -la /root/vpn-bot/

# Создайте вручную
cd /root/vpn-bot
python3 << EOF
import sqlite3
conn = sqlite3.connect('vpn_users.db')
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
conn.close()
print("База создана!")
EOF

# Перезапустите бота
systemctl restart vpn-bot
```

### Проблема: "Ошибка при добавлении в config.json"

```bash
# Проверьте JSON синтаксис
python3 -m json.tool /usr/local/etc/xray/config.json

# Если есть ошибки - исправьте их
nano /usr/local/etc/xray/config.json

# Проверьте снова
xray run -test -config /usr/local/etc/xray/config.json
```

---

## 📱 Установка клиента (для пользователей)

### Android (v2rayNG):
1. Установите из Google Play / APK
2. Нажмите `+` → Сканировать QR
3. Или: Нажмите `+` → Вставьте ссылку VLESS

### iOS (V2Box):
1. Установите из App Store (требуется non-China ID)
2. Нажмите `+` → Сканировать QR
3. Или: Нажмите `+` → Вставьте ссылку VLESS

### Windows (v2rayN):
1. Скачайте с GitHub: https://github.com/2dust/v2rayN/releases
2. Сервера → Импорт → Вставьте ссылку VLESS

---

## 🔒 Безопасность

### Рекомендации:

1. **Измените SSH порт**
```bash
nano /etc/ssh/sshd_config
# Port 22 → Port 2222
systemctl restart sshd
ufw allow 2222/tcp
```

2. **Отключите root логин по паролю**
```bash
nano /etc/ssh/sshd_config
# PermitRootLogin yes → PermitRootLogin prohibit-password
```

3. **Настройте fail2ban**
```bash
apt install fail2ban
systemctl enable fail2ban
systemctl start fail2ban
```

4. **Регулярно обновляйте систему**
```bash
apt update && apt upgrade -y
```

---

## ✅ Чеклист после установки

- [ ] Xray запущен и работает (`systemctl status xray`)
- [ ] Бот запущен и работает (`systemctl status vpn-bot`)
- [ ] Порт 443 открыт (`ss -tlnp | grep 443`)
- [ ] База данных создана (`ls -la /root/vpn-bot/vpn_users.db`)
- [ ] Бот отвечает на `/start` в Telegram
- [ ] Можно создать ключ через "Получить VPN"
- [ ] QR-код и ссылка генерируются
- [ ] Клиент может подключиться к VPN
- [ ] Логи не содержат ошибок

---

## 📞 Полезные ссылки

- **Репозиторий**: https://github.com/brigadavpn-lab/VPN-bot
- **Xray документация**: https://xtls.github.io/
- **Telegram Bot API**: https://core.telegram.org/bots/api

---

**🎉 Готово! Ваш VPN бот развернут и работает!**
