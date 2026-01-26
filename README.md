# 🛡️ VPN Telegram Bot

Автоматизированный Telegram бот для управления VPN подключениями на базе Xray-core с протоколом VLESS Reality.

---

## 🚀 Быстрое развертывание

### Вариант 1: Автоматический скрипт (рекомендуется)

```bash
# На вашем сервере выполните:
ssh root@ваш_IP

# Скачайте и запустите скрипт
wget https://raw.githubusercontent.com/brigadavpn-lab/VPN-bot/claude/telegram-bot-setup-0swBs/QUICK_DEPLOY.sh
chmod +x QUICK_DEPLOY.sh
bash QUICK_DEPLOY.sh
```

Скрипт автоматически:
- ✅ Установит все зависимости
- ✅ Установит Xray-core
- ✅ Склонирует репозиторий
- ✅ Настроит конфигурацию
- ✅ Запустит бота и Xray

**Время: ~5 минут**

---

### Вариант 2: Ручная установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/brigadavpn-lab/VPN-bot.git vpn-bot
cd vpn-bot
git checkout claude/telegram-bot-setup-0swBs

# 2. Следуйте инструкциям
cat DEPLOY_FROM_GITHUB.md
```

**Время: ~15 минут**

---

## 📖 Документация

| Файл | Описание |
|------|----------|
| **QUICK_DEPLOY.sh** | Автоматический скрипт развертывания |
| **DEPLOY_FROM_GITHUB.md** | Пошаговая инструкция ручного развертывания |
| **SETUP_INSTRUCTIONS.md** | Детальная настройка и конфигурация |
| **CONFIG_CHANGES.md** | Описание изменений конфигурации |
| **README_VARIANT_A.md** | Информация о варианте упрощенного конфига |

---

## 🎯 Возможности

- 🔐 **VLESS Reality** - Современный протокол обхода блокировок
- 🤖 **Telegram управление** - Создание VPN ключей через бота
- 📊 **База данных** - Учет пользователей и подписок
- 💳 **Система оплаты** - Автоматические напоминания о продлении
- 🎨 **Matrix стиль** - Красивая статистика `/matrix`
- 👤 **Личный кабинет** - Просмотр статуса подписки
- 📱 **QR коды** - Быстрая настройка клиентов

---

## ⚙️ Технологии

- **Xray-core** - VPN сервер с Reality протоколом
- **Python 3** - Telegram бот (pyTelegramBotAPI)
- **SQLite** - База данных пользователей
- **systemd** - Автозапуск сервисов

---

## 🔧 Требования

- Ubuntu/Debian сервер
- Python 3.7+
- Root доступ
- Открытый порт 443

---

## 📋 Быстрая шпаргалка

### На сервере (после установки):

```bash
# Просмотр логов
tail -f /root/vpn-bot/bot.log           # Логи бота
tail -f /var/log/xray/error.log         # Логи Xray

# Управление сервисами
systemctl status xray vpn-bot           # Статус
systemctl restart xray vpn-bot          # Перезапуск
systemctl stop xray vpn-bot             # Остановка

# База данных
sqlite3 /root/vpn-bot/vpn_users.db "SELECT * FROM users;"

# Обновление с GitHub
cd /root/vpn-bot
git pull origin claude/telegram-bot-setup-0swBs
systemctl restart xray vpn-bot
```

### В Telegram (команды админа):

```
/start                    # Главное меню
/matrix                   # Статистика в стиле Matrix
/add_time USER_ID DAYS    # Продлить подписку
/feedback                 # Обратная связь
```

---

## 🔐 Настройка перед запуском

### 1. Получите токен бота:
- Напишите @BotFather в Telegram
- Создайте бота: `/newbot`
- Сохраните токен

### 2. Узнайте свой Telegram ID:
- Напишите @userinfobot
- Скопируйте ваш ID

### 3. При установке введите эти данные

---

## 📱 Для пользователей

### Android (v2rayNG):
1. Установите [v2rayNG](https://github.com/2dust/v2rayNG/releases)
2. Откройте бота → "Получить VPN"
3. Отсканируйте QR код

### iOS (V2Box):
1. Установите V2Box из App Store
2. Откройте бота → "Получить VPN"
3. Скопируйте ссылку VLESS

---

## 🐛 Решение проблем

### Бот не отвечает:
```bash
systemctl status vpn-bot
tail -50 /root/vpn-bot/bot.log
```

### Клиент не подключается:
```bash
systemctl status xray
tail -50 /var/log/xray/error.log
ss -tlnp | grep 443
```

### Подробнее:
См. `DEPLOY_FROM_GITHUB.md` → раздел Troubleshooting

---

## 🔄 Обновление

```bash
cd /root/vpn-bot
git pull origin claude/telegram-bot-setup-0swBs
cp config.json /usr/local/etc/xray/config.json
systemctl restart xray vpn-bot
```

---

## 📞 Структура проекта

```
VPN-bot/
├── bot.py                      # Telegram бот
├── config.json                 # Конфигурация Xray
├── .env                        # Секреты (создается при установке)
├── .gitignore                  # Git исключения
├── QUICK_DEPLOY.sh             # Скрипт автоустановки
├── DEPLOY_FROM_GITHUB.md       # Ручная установка
├── SETUP_INSTRUCTIONS.md       # Детальная настройка
├── CONFIG_CHANGES.md           # Описание изменений
└── README_VARIANT_A.md         # Информация о варианте А
```

---

## ⚡️ Быстрый старт

### 3 команды для запуска:

```bash
wget https://raw.githubusercontent.com/brigadavpn-lab/VPN-bot/claude/telegram-bot-setup-0swBs/QUICK_DEPLOY.sh
chmod +x QUICK_DEPLOY.sh
bash QUICK_DEPLOY.sh
```

### Введите при запросе:
1. BOT_TOKEN (от @BotFather)
2. ADMIN_ID (от @userinfobot)

### Готово! 🎉

---

## 📊 Статус

| Компонент | Статус |
|-----------|--------|
| Xray конфиг | ✅ Упрощен (Вариант А) |
| Бот | ✅ Оптимизирован |
| Совместимость | ✅ Полная |
| Документация | ✅ Полная |
| Автоустановка | ✅ Готова |

---

## 🌟 Особенности Варианта А

- **TCP транспорт** - Полная совместимость с ботом
- **Порт 443** - Стандартный HTTPS порт
- **Без зависимостей** - Работает автономно (нет WARP/Tor/I2P)
- **Reality протокол** - Современная защита от обнаружения

---

## 📝 Лицензия

Проект для личного использования.

---

## 🤝 Поддержка

Вопросы и баги: [GitHub Issues](https://github.com/brigadavpn-lab/VPN-bot/issues)

---

**Сделано с ❤️ для обхода блокировок**
