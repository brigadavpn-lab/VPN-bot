#!/bin/bash
# 🚀 Скрипт быстрого развертывания VPN бота с GitHub

set -e  # Остановка при ошибке

echo "================================================"
echo "🚀 Развертывание VPN бота с GitHub"
echo "================================================"
echo ""

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Проверка root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Запустите скрипт от root: sudo bash QUICK_DEPLOY.sh${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Запуск от root${NC}"
echo ""

# Шаг 1: Обновление системы
echo "================================================"
echo "📦 Шаг 1/9: Обновление системы"
echo "================================================"
apt update && apt upgrade -y
apt install -y curl wget git python3 python3-pip sqlite3 ufw
echo -e "${GREEN}✅ Система обновлена${NC}"
echo ""

# Шаг 2: Установка Xray
echo "================================================"
echo "📦 Шаг 2/9: Установка Xray"
echo "================================================"
if command -v xray &> /dev/null; then
    echo -e "${YELLOW}⚠️  Xray уже установлен${NC}"
else
    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
    echo -e "${GREEN}✅ Xray установлен${NC}"
fi
mkdir -p /var/log/xray
echo ""

# Шаг 3: Клонирование репозитория
echo "================================================"
echo "📦 Шаг 3/9: Клонирование репозитория"
echo "================================================"
cd /root
if [ -d "vpn-bot" ]; then
    echo -e "${YELLOW}⚠️  Директория vpn-bot уже существует${NC}"
    read -p "Удалить и клонировать заново? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf vpn-bot
        git clone https://github.com/brigadavpn-lab/VPN-bot.git vpn-bot
        cd vpn-bot
        git checkout claude/telegram-bot-setup-0swBs
        echo -e "${GREEN}✅ Репозиторий склонирован${NC}"
    else
        cd vpn-bot
        git pull origin claude/telegram-bot-setup-0swBs
        echo -e "${GREEN}✅ Репозиторий обновлен${NC}"
    fi
else
    git clone https://github.com/brigadavpn-lab/VPN-bot.git vpn-bot
    cd vpn-bot
    git checkout claude/telegram-bot-setup-0swBs
    echo -e "${GREEN}✅ Репозиторий склонирован${NC}"
fi
echo ""

# Шаг 4: Установка конфига Xray
echo "================================================"
echo "📦 Шаг 4/9: Установка конфига Xray"
echo "================================================"
cp /root/vpn-bot/config.json /usr/local/etc/xray/config.json
chmod 644 /usr/local/etc/xray/config.json
if xray run -test -config /usr/local/etc/xray/config.json; then
    echo -e "${GREEN}✅ Конфиг Xray валидный${NC}"
else
    echo -e "${RED}❌ Ошибка в конфиге Xray${NC}"
    exit 1
fi
echo ""

# Шаг 5: Установка зависимостей Python
echo "================================================"
echo "📦 Шаг 5/9: Установка зависимостей Python"
echo "================================================"
cd /root/vpn-bot
pip3 install pyTelegramBotAPI python-dotenv qrcode[pil]
echo -e "${GREEN}✅ Зависимости установлены${NC}"
echo ""

# Шаг 6: Создание .env файла
echo "================================================"
echo "📦 Шаг 6/9: Настройка .env файла"
echo "================================================"
if [ -f "/root/vpn-bot/.env" ]; then
    echo -e "${YELLOW}⚠️  Файл .env уже существует${NC}"
    cat /root/vpn-bot/.env
    read -p "Оставить текущий? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        rm /root/vpn-bot/.env
    else
        echo -e "${GREEN}✅ Используем существующий .env${NC}"
    fi
fi

if [ ! -f "/root/vpn-bot/.env" ]; then
    echo ""
    echo "Введите токен бота от @BotFather:"
    read -r BOT_TOKEN
    echo "Введите ваш Telegram ID (узнать у @userinfobot):"
    read -r ADMIN_ID

    cat > /root/vpn-bot/.env << EOF
BOT_TOKEN=$BOT_TOKEN
ADMIN_ID=$ADMIN_ID
EOF
    chmod 600 /root/vpn-bot/.env
    echo -e "${GREEN}✅ Файл .env создан${NC}"
fi
echo ""

# Шаг 7: Настройка Firewall
echo "================================================"
echo "📦 Шаг 7/9: Настройка Firewall"
echo "================================================"
ufw allow 22/tcp
ufw allow 443/tcp
ufw --force enable
echo -e "${GREEN}✅ Firewall настроен${NC}"
ufw status
echo ""

# Шаг 8: Запуск Xray
echo "================================================"
echo "📦 Шаг 8/9: Запуск Xray"
echo "================================================"
systemctl enable xray
systemctl restart xray
sleep 2
if systemctl is-active --quiet xray; then
    echo -e "${GREEN}✅ Xray запущен${NC}"
else
    echo -e "${RED}❌ Ошибка запуска Xray${NC}"
    systemctl status xray
    exit 1
fi
echo ""

# Шаг 9: Создание и запуск сервиса бота
echo "================================================"
echo "📦 Шаг 9/9: Запуск бота"
echo "================================================"

cat > /etc/systemd/system/vpn-bot.service << 'EOF'
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
EOF

systemctl daemon-reload
systemctl enable vpn-bot
systemctl restart vpn-bot
sleep 3

if systemctl is-active --quiet vpn-bot; then
    echo -e "${GREEN}✅ Бот запущен${NC}"
else
    echo -e "${RED}❌ Ошибка запуска бота${NC}"
    systemctl status vpn-bot
    tail -20 /root/vpn-bot/bot.log
    exit 1
fi
echo ""

# Финальная проверка
echo "================================================"
echo "🎉 УСТАНОВКА ЗАВЕРШЕНА!"
echo "================================================"
echo ""
echo -e "${GREEN}Статус сервисов:${NC}"
systemctl status xray --no-pager | grep "Active:"
systemctl status vpn-bot --no-pager | grep "Active:"
echo ""
echo -e "${GREEN}Проверка порта 443:${NC}"
ss -tlnp | grep 443 || echo -e "${RED}⚠️  Порт 443 не слушается!${NC}"
echo ""
echo -e "${GREEN}База данных:${NC}"
ls -lh /root/vpn-bot/vpn_users.db 2>/dev/null || echo -e "${YELLOW}⚠️  БД будет создана при первом запуске бота${NC}"
echo ""
echo "================================================"
echo "📋 Следующие шаги:"
echo "================================================"
echo "1. Откройте Telegram и найдите вашего бота"
echo "2. Отправьте /start"
echo "3. Нажмите '🚀 Получить VPN'"
echo ""
echo "📊 Мониторинг:"
echo "  Логи Xray:  tail -f /var/log/xray/error.log"
echo "  Логи бота:  tail -f /root/vpn-bot/bot.log"
echo ""
echo "🔧 Управление:"
echo "  systemctl restart xray vpn-bot"
echo "  systemctl status xray vpn-bot"
echo ""
echo -e "${GREEN}✅ ВСЁ ГОТОВО!${NC}"
