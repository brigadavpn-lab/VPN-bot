# 🚀 Инструкция по установке VPN бота

## ⚠️ ВАЖНО: Этот конфиг упрощен по Варианту А

Изменения:
- ✅ TCP вместо gRPC (совместимо с ботом)
- ✅ Один порт 443 (вместо диапазона 443-453)
- ✅ Прямое подключение без WARP/Tor/I2P
- ✅ Упрощенная маршрутизация

---

## 📋 Шаг 1: Установка Xray на сервере

```bash
# Установка Xray-core
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# Проверка установки
xray version
```

---

## 🔑 Шаг 2: Генерация ключей Reality

```bash
# Генерация пары ключей X25519
xray x25519

# Вывод будет примерно таким:
# Private key: 1XTxbMFdxpQB1v9AtZLVicppKzVbrs7jTwDl1OvmY84=
# Public key:  XfHLY0yQQ6E/sgo6sY+PqTAy2xOzNKB4vpJDQCW/qYE=
```

**Сохраните оба ключа!**

---

## 📝 Шаг 3: Обновление конфигурации

### 3.1. Обновите `config.json`

Откройте файл `config.json` и замените:

```json
"privateKey": "REPLACE_WITH_PRIVATE_KEY_FROM_XRAY_X25519"
```

на ваш **Private key** из шага 2.

### 3.2. Обновите `bot.py`

Откройте файл `bot.py` и замените (строка ~65):

```python
REALITY_PUBLIC_KEY = "REPLACE_WITH_PUBLIC_KEY_FROM_XRAY_X25519"
```

на ваш **Public key** из шага 2.

### 3.3. Проверьте остальные настройки в bot.py:

```python
SERVER_ADDRESS = "141.105.143.224"  # Ваш IP сервера
SERVER_PORT = 443
REALITY_SHORT_ID = "a028507ab5b114b4"  # Должен совпадать с config.json
REALITY_SNI = "www.yahoo.com"  # Должен совпадать с config.json
```

---

## 📦 Шаг 4: Установка конфигурации Xray

```bash
# Создайте директорию для логов
mkdir -p /var/log/xray

# Скопируйте конфиг
cp config.json /usr/local/etc/xray/config.json

# Установите права
chmod 644 /usr/local/etc/xray/config.json

# Проверьте конфиг
xray run -test -config /usr/local/etc/xray/config.json
```

Если вывод: `Configuration OK` - всё хорошо!

---

## 🐍 Шаг 5: Установка зависимостей Python

```bash
# Установите Python3 и pip (если нет)
apt update && apt install -y python3 python3-pip

# Перейдите в директорию бота
cd /root/vpn-bot

# Установите зависимости
pip3 install pyTelegramBotAPI python-dotenv qrcode[pil]
```

---

## 🔐 Шаг 6: Настройка .env файла

Создайте файл `.env` в `/root/vpn-bot/`:

```bash
nano /root/vpn-bot/.env
```

Содержимое:

```env
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_ID=your_telegram_user_id
```

Сохраните (Ctrl+O, Enter, Ctrl+X).

**Как получить ADMIN_ID:**
- Напишите боту @userinfobot в Telegram
- Он покажет ваш ID

---

## 🚀 Шаг 7: Запуск сервисов

### 7.1. Запустите Xray

```bash
systemctl enable xray
systemctl start xray
systemctl status xray
```

Должно быть: `Active: active (running)`

### 7.2. Запустите бота

**Вариант 1: Тестовый запуск**
```bash
cd /root/vpn-bot
python3 bot.py
```

Проверьте, что бот работает (отправьте /start).

**Вариант 2: Systemd сервис (рекомендуется)**

Создайте файл сервиса:
```bash
nano /etc/systemd/system/vpn-bot.service
```

Содержимое:
```ini
[Unit]
Description=VPN Telegram Bot
After=network.target xray.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/vpn-bot
ExecStart=/usr/bin/python3 /root/vpn-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
systemctl daemon-reload
systemctl enable vpn-bot
systemctl start vpn-bot
systemctl status vpn-bot
```

---

## 🔍 Шаг 8: Проверка работы

### 8.1. Проверьте логи Xray:
```bash
tail -f /var/log/xray/error.log
```

### 8.2. Проверьте логи бота:
```bash
tail -f /root/vpn-bot/bot.log
```

### 8.3. Проверьте порт:
```bash
ss -tlnp | grep 443
```

Должно быть: `LISTEN 0 ... *:443 ... users:(("xray"...))`

---

## 🧪 Шаг 9: Тестирование

1. Откройте Telegram
2. Напишите боту `/start`
3. Нажмите "🚀 Получить VPN"
4. Скопируйте ссылку или отсканируйте QR
5. Вставьте в v2rayNG (Android) или V2Box (iOS)

---

## 🐛 Troubleshooting

### Проблема: "Ключ создан" но подключение не работает

Проверьте:
1. Ключи Reality совпадают (Private в config.json ↔ Public в bot.py)
2. Порт 443 открыт в firewall:
   ```bash
   ufw allow 443/tcp
   ```
3. SNI одинаковый в обоих файлах
4. shortId одинаковый в обоих файлах

### Проблема: Бот не добавляет пользователей

Проверьте права:
```bash
ls -la /root/vpn-bot/vpn_users.db
chmod 644 /root/vpn-bot/vpn_users.db
```

### Проблема: systemctl restart xray не работает

Проверьте JSON синтаксис:
```bash
python3 -m json.tool /usr/local/etc/xray/config.json
```

---

## 📊 Мониторинг

### Просмотр подключенных пользователей:
```bash
sqlite3 /root/vpn-bot/vpn_users.db "SELECT telegram_id, email, status, trial_end_date FROM users;"
```

### Статистика Xray (через API):
```bash
curl http://127.0.0.1:10085/stats/query
```

---

## 🔄 Обновление конфига

После изменения `config.json`:
```bash
xray run -test -config /usr/local/etc/xray/config.json
systemctl restart xray
```

---

## 📞 Команды админа в боте

- `/add_time USER_ID DAYS` - продлить подписку
- `/matrix` - показать статус в стиле Matrix

Пример:
```
/add_time 123456789 30
```

---

## ✅ Всё готово!

Теперь ваш VPN бот полностью настроен и работает с упрощенной конфигурацией Xray Reality.

**Что дальше?**
- Добавьте инструкцию для пользователей (PDF)
- Настройте реквизиты оплаты в `PAYMENT_INFO` (bot.py строка 51)
- Измените лимит пользователей `BETA_LIMIT` (bot.py строка 48)
