#!/bin/bash
#
# Скрипт настройки Xray для работы через Cloudflare WARP
# Маршрутизирует весь исходящий трафик через WARP SOCKS5 proxy
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
echo "   Настройка Xray для работы через WARP"
echo "================================================================"
echo

# Проверка установки WARP
log_step "Проверка установки WARP"
if ! command -v warp-cli &> /dev/null; then
    log_error "WARP не установлен!"
    log_error "Сначала запустите: ./install_warp.sh"
    exit 1
fi

# Проверка статуса WARP
WARP_STATUS=$(warp-cli status | grep "Status" || echo "Unknown")
log_info "Статус WARP: $WARP_STATUS"

if [[ "$WARP_STATUS" != *"Connected"* ]]; then
    log_warn "WARP не подключен, пытаюсь подключить..."
    warp-cli connect
    sleep 3
    WARP_STATUS=$(warp-cli status | grep "Status" || echo "Unknown")
    if [[ "$WARP_STATUS" != *"Connected"* ]]; then
        log_error "Не удалось подключить WARP"
        exit 1
    fi
fi

log_info "✓ WARP подключен"

# Проверка WARP proxy
log_info "Проверка WARP SOCKS5 proxy на 127.0.0.1:40000..."
if curl -s --socks5 127.0.0.1:40000 --max-time 5 ifconfig.me > /dev/null; then
    log_info "✓ WARP proxy работает"
else
    log_error "WARP proxy не отвечает на 127.0.0.1:40000"
    exit 1
fi

# Пути к конфигурации
CONFIG_SOURCE="/root/vpn-bot/config.json"
CONFIG_TARGET="/usr/local/etc/xray/config.json"

# Проверка наличия исходной конфигурации
if [ ! -f "$CONFIG_SOURCE" ]; then
    log_error "Исходная конфигурация не найдена: $CONFIG_SOURCE"
    exit 1
fi

# Резервная копия текущей конфигурации
log_step "Создание резервной копии конфигурации"
BACKUP_FILE="${CONFIG_TARGET}.backup.$(date +%Y%m%d_%H%M%S)"
if [ -f "$CONFIG_TARGET" ]; then
    cp "$CONFIG_TARGET" "$BACKUP_FILE"
    log_info "Резервная копия: $BACKUP_FILE"
fi

# Создание новой конфигурации с WARP outbound
log_step "Создание конфигурации с WARP outbound"

# Читаем текущую конфигурацию и модифицируем
python3 - <<'PYTHON_SCRIPT'
import json
import sys

config_file = "/root/vpn-bot/config.json"

try:
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Добавляем WARP outbound
    warp_outbound = {
        "tag": "warp",
        "protocol": "socks",
        "settings": {
            "servers": [{
                "address": "127.0.0.1",
                "port": 40000
            }]
        }
    }

    # Проверяем, есть ли уже warp outbound
    has_warp = False
    for outbound in config.get("outbounds", []):
        if outbound.get("tag") == "warp":
            has_warp = True
            break

    if not has_warp:
        # Добавляем warp outbound на первое место (приоритет)
        config["outbounds"].insert(0, warp_outbound)
        print("✓ Добавлен WARP outbound")
    else:
        print("✓ WARP outbound уже существует")

    # Модифицируем routing: весь трафик через WARP
    # Добавляем правило по умолчанию для использования WARP
    routing_rules = config.get("routing", {}).get("rules", [])

    # Проверяем, есть ли уже правило для WARP
    has_warp_rule = False
    for rule in routing_rules:
        if rule.get("outboundTag") == "warp" and rule.get("type") == "field":
            has_warp_rule = True
            break

    if not has_warp_rule:
        # Добавляем правило: весь tcp/udp трафик через WARP
        # Находим правило с "direct" и меняем на "warp"
        for rule in routing_rules:
            if rule.get("network") == "tcp,udp" and rule.get("outboundTag") == "direct":
                rule["outboundTag"] = "warp"
                print("✓ Изменен outbound с 'direct' на 'warp' для tcp/udp")
                break
    else:
        print("✓ Правило маршрутизации через WARP уже существует")

    # Сохраняем модифицированную конфигурацию
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print("✓ Конфигурация обновлена")
    sys.exit(0)

except Exception as e:
    print(f"ОШИБКА: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -ne 0 ]; then
    log_error "Ошибка модификации конфигурации"
    exit 1
fi

# Копируем модифицированную конфигурацию
cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
log_info "✓ Конфигурация скопирована в $CONFIG_TARGET"

# Проверка валидности конфигурации
log_step "Проверка конфигурации Xray"
if /usr/local/bin/xray -test -config="$CONFIG_TARGET" > /dev/null 2>&1; then
    log_info "✓ Конфигурация корректна"
else
    log_error "Конфигурация содержит ошибки!"
    log_error "Восстановление из резервной копии..."
    cp "$BACKUP_FILE" "$CONFIG_TARGET"
    exit 1
fi

# Перезапуск Xray
log_step "Перезапуск Xray"
systemctl restart xray
sleep 2

if systemctl is-active --quiet xray; then
    log_info "✓ Xray успешно перезапущен"
else
    log_error "Xray не запустился!"
    log_error "Проверьте логи: journalctl -u xray -n 50"
    exit 1
fi

# Финальная проверка
echo
log_step "Проверка маршрутизации через WARP"
echo
log_info "Подключитесь к VPN и проверьте IP:"
log_info "  https://whoer.net"
log_info "  https://browserleaks.com/ip"
echo
log_info "IP должен соответствовать Cloudflare (AS13335)"
echo

echo "================================================================"
echo "   ✅ Настройка завершена успешно!"
echo "================================================================"
echo
echo "Теперь весь трафик через VPN идет через Cloudflare WARP"
echo
echo "Проверка:"
echo "  1. Подключитесь к VPN"
echo "  2. Откройте https://gemini.google.com"
echo "  3. Gemini должен работать без блокировки по стране"
echo
echo "Если возникли проблемы:"
echo "  - Проверьте статус WARP: warp-cli status"
echo "  - Проверьте логи Xray: journalctl -u xray -n 50"
echo "  - Откатите конфигурацию: cp $BACKUP_FILE $CONFIG_TARGET && systemctl restart xray"
echo
echo "================================================================"
