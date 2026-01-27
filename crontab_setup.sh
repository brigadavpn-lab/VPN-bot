#!/bin/bash
#
# Скрипт настройки автоматизации для VPN бота
# Устанавливает cron задачи для:
# - Мониторинга трафика (каждые 10 минут)
# - Очистки просроченных пользователей (ежедневно в 3:00)
# - Проверки здоровья системы (каждый час)
# - Бэкапа базы данных (ежедневно в 4:00, опционально)
#

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для вывода с цветом
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка, что скрипт запущен от root
if [[ $EUID -ne 0 ]]; then
   log_error "Этот скрипт должен быть запущен от root (используйте sudo)"
   exit 1
fi

echo "========================================"
echo "   Настройка автоматизации VPN бота"
echo "========================================"
echo

# Пути к скриптам
SCRIPT_DIR="/root/vpn-bot"
TRAFFIC_CHECK="$SCRIPT_DIR/traffic_check.py"
CLEANUP="$SCRIPT_DIR/cleanup.py"
MONITORING="$SCRIPT_DIR/monitoring.py"
BACKUP="$SCRIPT_DIR/backup.py"
LOG_FILE="$SCRIPT_DIR/cron.log"

# Проверка существования файлов
log_info "Проверка наличия скриптов..."

scripts_ok=true
for script in "$TRAFFIC_CHECK" "$CLEANUP" "$MONITORING"; do
    if [ ! -f "$script" ]; then
        log_error "Файл не найден: $script"
        scripts_ok=false
    else
        log_info "✓ Найден: $script"
        # Делаем исполняемым
        chmod +x "$script"
    fi
done

if [ "$scripts_ok" = false ]; then
    log_error "Не все необходимые скрипты найдены. Прервано."
    exit 1
fi

# Проверка backup.py (опционально)
if [ -f "$BACKUP" ]; then
    log_info "✓ Найден: $BACKUP (бэкап будет включен)"
    chmod +x "$BACKUP"
    BACKUP_ENABLED=true
else
    log_warn "Файл backup.py не найден, бэкапы не будут настроены"
    BACKUP_ENABLED=false
fi

# Создаем лог-файл если его нет
touch "$LOG_FILE"
log_info "Лог-файл: $LOG_FILE"

# Резервная копия текущего crontab
log_info "Создание резервной копии текущего crontab..."
crontab -l > /tmp/crontab.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# Создаем новый crontab (добавляем к существующему)
log_info "Настройка cron задач..."

# Получаем текущий crontab
CURRENT_CRON=$(crontab -l 2>/dev/null || echo "")

# Удаляем старые записи VPN бота если есть
CURRENT_CRON=$(echo "$CURRENT_CRON" | grep -v "vpn-bot/traffic_check.py" || true)
CURRENT_CRON=$(echo "$CURRENT_CRON" | grep -v "vpn-bot/cleanup.py" || true)
CURRENT_CRON=$(echo "$CURRENT_CRON" | grep -v "vpn-bot/monitoring.py" || true)
CURRENT_CRON=$(echo "$CURRENT_CRON" | grep -v "vpn-bot/backup.py" || true)

# Создаем новый crontab с нашими задачами
NEW_CRON="$CURRENT_CRON

# ===== VPN Bot Automation =====
# Мониторинг трафика пользователей (каждые 10 минут)
*/10 * * * * /usr/bin/python3 $TRAFFIC_CHECK >> $LOG_FILE 2>&1

# Очистка просроченных пользователей (ежедневно в 3:00)
0 3 * * * /usr/bin/python3 $CLEANUP >> $LOG_FILE 2>&1

# Проверка здоровья системы (каждый час)
0 * * * * /usr/bin/python3 $MONITORING >> $LOG_FILE 2>&1
"

# Добавляем бэкап если файл существует
if [ "$BACKUP_ENABLED" = true ]; then
    NEW_CRON="$NEW_CRON
# Бэкап базы данных (ежедневно в 4:00)
0 4 * * * /usr/bin/python3 $BACKUP >> $LOG_FILE 2>&1
"
fi

# Устанавливаем новый crontab
echo "$NEW_CRON" | crontab -

log_info "✓ Cron задачи установлены"

# Проверяем результат
echo
log_info "Текущие cron задачи для VPN бота:"
echo "----------------------------------------"
crontab -l | grep -A 10 "VPN Bot Automation"
echo "----------------------------------------"

# Проверка статуса cron сервиса
echo
log_info "Проверка статуса cron сервиса..."
if systemctl is-active --quiet cron || systemctl is-active --quiet crond; then
    log_info "✓ Cron сервис активен"
else
    log_warn "Cron сервис не активен, пытаюсь запустить..."
    systemctl start cron 2>/dev/null || systemctl start crond 2>/dev/null || log_error "Не удалось запустить cron"
fi

# Информация о расписании
echo
echo "========================================"
echo "   Расписание автоматических задач"
echo "========================================"
echo
echo "📊 Мониторинг трафика:"
echo "   Каждые 10 минут (*/10 * * * *)"
echo "   Проверяет использование трафика и блокирует пользователей при превышении лимита"
echo
echo "🧹 Очистка просроченных:"
echo "   Ежедневно в 3:00 (0 3 * * *)"
echo "   Удаляет пользователей с истекшей подпиской"
echo
echo "🏥 Проверка здоровья:"
echo "   Каждый час (0 * * * *)"
echo "   Проверяет статус Xray, API, бота и базы данных"
echo

if [ "$BACKUP_ENABLED" = true ]; then
    echo "💾 Бэкап базы данных:"
    echo "   Ежедневно в 4:00 (0 4 * * *)"
    echo "   Создает резервную копию БД и отправляет в Telegram"
    echo
fi

echo "📝 Логи: $LOG_FILE"
echo

# Рекомендации
echo "========================================"
echo "   Полезные команды"
echo "========================================"
echo
echo "Просмотр логов:"
echo "  tail -f $LOG_FILE"
echo
echo "Просмотр cron задач:"
echo "  crontab -l"
echo
echo "Удалить все cron задачи VPN бота:"
echo "  crontab -l | grep -v 'vpn-bot' | crontab -"
echo
echo "Ручной запуск проверки трафика:"
echo "  python3 $TRAFFIC_CHECK"
echo
echo "Ручной запуск очистки:"
echo "  python3 $CLEANUP"
echo
echo "Ручной запуск мониторинга:"
echo "  python3 $MONITORING"
echo
echo "========================================"
log_info "✅ Автоматизация настроена успешно!"
echo "========================================"
