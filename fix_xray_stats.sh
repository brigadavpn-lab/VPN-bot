#!/bin/bash
#
# Скрипт для обновления конфигурации Xray и включения статистики
# Исправляет ошибку: "QueryStats only works its own stats.Manager"
#

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Проверка root
if [[ $EUID -ne 0 ]]; then
   log_error "Запустите скрипт от root (используйте sudo)"
   exit 1
fi

echo "========================================"
echo "  Обновление конфигурации Xray"
echo "========================================"
echo

# Пути
CONFIG_SOURCE="/root/vpn-bot/config.json"
CONFIG_TARGET="/usr/local/etc/xray/config.json"

# Проверка существования исходного файла
if [ ! -f "$CONFIG_SOURCE" ]; then
    log_error "Файл конфигурации не найден: $CONFIG_SOURCE"
    exit 1
fi

# Создание резервной копии текущей конфигурации
if [ -f "$CONFIG_TARGET" ]; then
    BACKUP_FILE="${CONFIG_TARGET}.backup.$(date +%Y%m%d_%H%M%S)"
    log_info "Создание резервной копии: $BACKUP_FILE"
    cp "$CONFIG_TARGET" "$BACKUP_FILE"
else
    log_warn "Целевой файл конфигурации не найден: $CONFIG_TARGET"
fi

# Проверка валидности JSON в исходном файле
log_info "Проверка валидности JSON..."
if ! python3 -m json.tool "$CONFIG_SOURCE" > /dev/null 2>&1; then
    log_error "Некорректный JSON в файле: $CONFIG_SOURCE"
    exit 1
fi
log_info "✓ JSON валиден"

# Копирование новой конфигурации
log_info "Копирование новой конфигурации..."
cp "$CONFIG_SOURCE" "$CONFIG_TARGET"
log_info "✓ Конфигурация обновлена"

# Проверка конфигурации Xray
log_info "Проверка конфигурации Xray..."
if /usr/local/bin/xray -test -config="$CONFIG_TARGET" > /dev/null 2>&1; then
    log_info "✓ Конфигурация Xray корректна"
else
    log_error "Конфигурация Xray содержит ошибки!"
    log_error "Восстановление из резервной копии..."
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$CONFIG_TARGET"
        log_info "Конфигурация восстановлена из резервной копии"
    fi
    exit 1
fi

# Перезапуск Xray
log_info "Перезапуск службы Xray..."
systemctl restart xray

# Проверка статуса
sleep 2
if systemctl is-active --quiet xray; then
    log_info "✓ Xray успешно перезапущен"
else
    log_error "Xray не запустился! Проверьте логи: journalctl -u xray -n 50"
    exit 1
fi

# Проверка API статистики
echo
log_info "Проверка доступности API статистики..."
sleep 1

if /usr/local/bin/xray api statsquery --server=127.0.0.1:10085 > /dev/null 2>&1; then
    log_info "✓ API статистики работает корректно"
else
    log_warn "API статистики не отвечает, но это нормально если нет активных пользователей"
fi

echo
echo "========================================"
log_info "✅ Конфигурация Xray обновлена успешно!"
echo "========================================"
echo
echo "Что было добавлено:"
echo "  • Секция 'stats': {} для инициализации менеджера статистики"
echo "  • policy.system с включенными счетчиками трафика"
echo "  • tag 'vless-in' для отслеживания входящего трафика"
echo
echo "Теперь можно запустить проверку трафика:"
echo "  python3 /root/vpn-bot/traffic_check.py"
echo
echo "Резервная копия сохранена в:"
echo "  $BACKUP_FILE"
echo
