#!/bin/bash
#
# Скрипт автоматической установки и настройки Cloudflare WARP
# Для изменения геолокации VPN сервера и доступа к Gemini
#

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Проверка root
if [[ $EUID -ne 0 ]]; then
   log_error "Запустите скрипт от root (используйте sudo)"
   exit 1
fi

echo "================================================================"
echo "   Установка Cloudflare WARP для изменения геолокации"
echo "================================================================"
echo

# Шаг 1: Проверка текущей геолокации
log_step "Шаг 1/6: Проверка текущей геолокации сервера"
echo
CURRENT_IP=$(curl -s ifconfig.me)
log_info "Текущий IP: $CURRENT_IP"

GEO_INFO=$(curl -s "https://ipapi.co/$CURRENT_IP/json/")
COUNTRY=$(echo "$GEO_INFO" | grep -o '"country_name":"[^"]*"' | cut -d'"' -f4)
CITY=$(echo "$GEO_INFO" | grep -o '"city":"[^"]*"' | cut -d'"' -f4)
ORG=$(echo "$GEO_INFO" | grep -o '"org":"[^"]*"' | cut -d'"' -f4)

log_info "Страна: $COUNTRY"
log_info "Город: $CITY"
log_info "Провайдер: $ORG"
echo

# Проверка на заблокированные страны
BLOCKED_COUNTRIES=("Russia" "Belarus" "China" "Iran" "North Korea")
IS_BLOCKED=false

for blocked in "${BLOCKED_COUNTRIES[@]}"; do
    if [[ "$COUNTRY" == *"$blocked"* ]]; then
        IS_BLOCKED=true
        log_warn "⚠️  Обнаружена заблокированная страна: $COUNTRY"
        log_warn "Gemini не работает в этой стране, WARP поможет обойти блокировку"
        break
    fi
done

if [ "$IS_BLOCKED" = false ]; then
    log_info "✓ Страна не в списке блокировки Gemini"
    log_info "Продолжаем установку WARP для дополнительной маршрутизации"
fi

echo
read -p "Продолжить установку WARP? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Установка отменена"
    exit 0
fi

# Шаг 2: Установка зависимостей
log_step "Шаг 2/6: Установка зависимостей"
apt-get update -qq
apt-get install -y curl gnupg lsb-release

# Шаг 3: Добавление репозитория Cloudflare
log_step "Шаг 3/6: Добавление репозитория Cloudflare"

# Добавляем ключ
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg

# Добавляем репозиторий
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list > /dev/null

log_info "✓ Репозиторий добавлен"

# Шаг 4: Установка WARP
log_step "Шаг 4/6: Установка Cloudflare WARP"
apt-get update -qq
apt-get install -y cloudflare-warp

log_info "✓ WARP установлен"

# Шаг 5: Регистрация и подключение WARP
log_step "Шаг 5/6: Регистрация и подключение к WARP"

# Регистрация
log_info "Регистрация устройства..."
warp-cli registration delete 2>/dev/null || true
warp-cli register

# Установка режима proxy
log_info "Настройка режима SOCKS5 proxy..."
warp-cli mode proxy

# Подключение
log_info "Подключение к WARP..."
warp-cli connect

# Ожидание подключения
sleep 5

# Проверка статуса
STATUS=$(warp-cli status | grep "Status" || echo "Unknown")
log_info "Статус WARP: $STATUS"

if [[ "$STATUS" == *"Connected"* ]]; then
    log_info "✓ WARP подключен успешно"
else
    log_warn "⚠️  WARP может быть не полностью подключен, проверьте: warp-cli status"
fi

# Шаг 6: Проверка новой геолокации через WARP
log_step "Шаг 6/6: Проверка геолокации через WARP"
echo
log_info "Проверка IP через WARP SOCKS5 proxy (127.0.0.1:40000)..."

WARP_IP=$(curl -s --socks5 127.0.0.1:40000 ifconfig.me)
if [ -z "$WARP_IP" ]; then
    log_error "Не удалось получить IP через WARP proxy"
    log_error "Проверьте: curl --socks5 127.0.0.1:40000 ifconfig.me"
    exit 1
fi

log_info "IP через WARP: $WARP_IP"

WARP_GEO=$(curl -s --socks5 127.0.0.1:40000 "https://ipapi.co/$WARP_IP/json/")
WARP_COUNTRY=$(echo "$WARP_GEO" | grep -o '"country_name":"[^"]*"' | cut -d'"' -f4)
WARP_CITY=$(echo "$WARP_GEO" | grep -o '"city":"[^"]*"' | cut -d'"' -f4)
WARP_ORG=$(echo "$WARP_GEO" | grep -o '"org":"[^"]*"' | cut -d'"' -f4)

log_info "Страна через WARP: $WARP_COUNTRY"
log_info "Город через WARP: $WARP_CITY"
log_info "Провайдер через WARP: $WARP_ORG"

echo
echo "================================================================"
echo "   Сравнение геолокации"
echo "================================================================"
printf "%-20s | %-30s | %-30s\n" "" "БЕЗ WARP" "С WARP"
echo "----------------------------------------------------------------"
printf "%-20s | %-30s | %-30s\n" "IP адрес" "$CURRENT_IP" "$WARP_IP"
printf "%-20s | %-30s | %-30s\n" "Страна" "$COUNTRY" "$WARP_COUNTRY"
printf "%-20s | %-30s | %-30s\n" "Город" "$CITY" "$WARP_CITY"
echo "================================================================"
echo

# Финальные инструкции
echo
echo "================================================================"
echo "   ✅ Установка завершена успешно!"
echo "================================================================"
echo
log_info "WARP SOCKS5 proxy работает на: 127.0.0.1:40000"
echo
echo "Следующий шаг: Настройка Xray для использования WARP"
echo
echo "Выполните:"
echo "  cd /root/vpn-bot"
echo "  ./configure_xray_warp.sh"
echo
echo "Полезные команды:"
echo "  warp-cli status          - Проверить статус"
echo "  warp-cli connect         - Подключиться"
echo "  warp-cli disconnect      - Отключиться"
echo "  warp-cli account         - Информация об аккаунте"
echo
echo "Проверка работы WARP:"
echo "  curl --socks5 127.0.0.1:40000 ifconfig.me"
echo
echo "================================================================"
