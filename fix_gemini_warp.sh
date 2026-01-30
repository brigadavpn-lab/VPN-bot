#!/bin/bash
#
# Автоматическая установка и настройка WARP для исправления проблемы с Gemini
# Запуск: bash fix_gemini_warp.sh
#

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

# Проверка root
if [[ $EUID -ne 0 ]]; then
   log_error "Запустите скрипт от root: sudo bash $0"
   exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🚀 Автоматическое исправление проблемы с Gemini"
echo "════════════════════════════════════════════════════════════"
echo ""
log_info "Этот скрипт установит Cloudflare WARP и настроит автоматическое переподключение"
echo ""

# ============================================================================
# ШАГ 1: Проверка, установлен ли WARP
# ============================================================================
log_step "ШАГ 1/5: Проверка установки WARP"

if command -v warp-cli &> /dev/null; then
    log_info "WARP уже установлен"
    WARP_INSTALLED=true
else
    log_warn "WARP не установлен, начинаем установку..."
    WARP_INSTALLED=false
fi

# ============================================================================
# ШАГ 2: Установка WARP (если не установлен)
# ============================================================================
if [ "$WARP_INSTALLED" = false ]; then
    log_step "ШАГ 2/5: Установка Cloudflare WARP"

    log_info "Установка зависимостей..."
    apt-get update -qq
    apt-get install -y curl gnupg lsb-release -qq

    log_info "Добавление репозитория Cloudflare..."
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg 2>/dev/null
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/cloudflare-client.list > /dev/null

    log_info "Установка cloudflare-warp..."
    apt-get update -qq
    apt-get install -y cloudflare-warp -qq

    log_info "✓ WARP установлен успешно"
else
    log_step "ШАГ 2/5: Установка WARP (пропущен - уже установлен)"
fi

# ============================================================================
# ШАГ 3: Регистрация и подключение WARP
# ============================================================================
log_step "ШАГ 3/5: Настройка и подключение WARP"

log_info "Удаление старой регистрации (если есть)..."
warp-cli registration delete 2>/dev/null || true

log_info "Регистрация в WARP..."
warp-cli register 2>/dev/null

log_info "Установка режима SOCKS5 proxy..."
warp-cli mode proxy 2>/dev/null

log_info "Подключение к WARP..."
warp-cli connect 2>/dev/null

sleep 5

STATUS=$(warp-cli status 2>/dev/null | grep "Status" || echo "Unknown")
log_info "Статус WARP: $STATUS"

if [[ "$STATUS" == *"Connected"* ]]; then
    log_info "✓ WARP подключен успешно"
else
    log_warn "WARP может быть не полностью подключен"
    log_info "Попытка переподключения..."
    warp-cli disconnect 2>/dev/null || true
    sleep 2
    warp-cli connect 2>/dev/null
    sleep 3
fi

# ============================================================================
# ШАГ 4: Включение автозапуска WARP
# ============================================================================
log_step "ШАГ 4/5: Настройка автозапуска WARP"

log_info "Включение systemd service для WARP..."
systemctl enable warp-svc 2>/dev/null
systemctl start warp-svc 2>/dev/null

log_info "Установка WARP monitor для автоматического переподключения..."

# Создаем скрипт мониторинга
cat > /usr/local/bin/warp-monitor.sh << 'MONITOR_SCRIPT'
#!/bin/bash
LOG_FILE="/var/log/warp-monitor.log"
echo "[$(date)] WARP Monitor started" >> "$LOG_FILE"

while true; do
    STATUS=$(warp-cli status 2>/dev/null | grep "Status" || echo "Unknown")

    if [[ "$STATUS" != *"Connected"* ]]; then
        echo "[$(date)] WARP disconnected! Status: $STATUS - Reconnecting..." >> "$LOG_FILE"
        warp-cli disconnect 2>/dev/null || true
        sleep 2
        warp-cli connect 2>/dev/null
        sleep 3
        NEW_STATUS=$(warp-cli status 2>/dev/null | grep "Status" || echo "Unknown")
        echo "[$(date)] After reconnect: $NEW_STATUS" >> "$LOG_FILE"
    fi

    sleep 30
done
MONITOR_SCRIPT

chmod +x /usr/local/bin/warp-monitor.sh

# Создаем systemd service для монитора
cat > /etc/systemd/system/warp-monitor.service << 'MONITOR_SERVICE'
[Unit]
Description=WARP Connection Monitor and Auto-Reconnect
After=network.target warp-svc.service
Requires=warp-svc.service
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/local/bin/warp-monitor.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
MONITOR_SERVICE

systemctl daemon-reload
systemctl enable warp-monitor 2>/dev/null
systemctl start warp-monitor 2>/dev/null

sleep 2

if systemctl is-active --quiet warp-monitor; then
    log_info "✓ WARP monitor запущен и работает"
else
    log_warn "WARP monitor не запустился, проверьте: systemctl status warp-monitor"
fi

# ============================================================================
# ШАГ 5: Проверка работы WARP
# ============================================================================
log_step "ШАГ 5/5: Проверка работы WARP"

log_info "Проверка WARP SOCKS5 proxy на 127.0.0.1:40000..."
if timeout 5 bash -c "curl -s --socks5 127.0.0.1:40000 icanhazip.com > /dev/null 2>&1"; then
    WARP_IP=$(curl -s --socks5 127.0.0.1:40000 --max-time 10 icanhazip.com 2>/dev/null || echo "Не удалось получить")
    log_info "✓ WARP proxy работает"
    log_info "IP через WARP: $WARP_IP"
else
    log_warn "Не удалось проверить WARP proxy (возможно, сетевые ограничения)"
    log_info "Попробуйте вручную: curl --socks5 127.0.0.1:40000 icanhazip.com"
fi

# ============================================================================
# ФИНАЛЬНЫЙ ОТЧЕТ
# ============================================================================
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ Установка WARP завершена успешно!"
echo "════════════════════════════════════════════════════════════"
echo ""

log_info "Что было сделано:"
echo "  1. ✓ WARP установлен и зарегистрирован"
echo "  2. ✓ WARP подключен в режиме SOCKS5 proxy (127.0.0.1:40000)"
echo "  3. ✓ Автозапуск WARP при перезагрузке включен"
echo "  4. ✓ Автоматический монитор переподключения запущен"
echo ""

log_info "Полезные команды:"
echo "  warp-cli status               - Проверить статус WARP"
echo "  systemctl status warp-monitor - Проверить статус монитора"
echo "  journalctl -u warp-monitor -f - Смотреть логи монитора"
echo "  tail -f /var/log/warp-monitor.log - Логи переподключений"
echo ""

log_warn "ВАЖНО: Теперь нужно настроить Xray для использования WARP"
echo ""
echo "Выполните следующую команду:"
echo "  cd /root/vpn-bot && bash configure_xray_warp.sh"
echo ""
echo "Или выполните вручную:"
echo "  1. Добавьте WARP outbound в config.json"
echo "  2. Измените routing для использования WARP"
echo "  3. Перезапустите Xray: systemctl restart xray"
echo ""

log_info "Проверка работы Gemini:"
echo "  1. Переподключитесь к VPN на телефоне"
echo "  2. Очистите DNS кеш в Chrome: chrome://net-internals/#dns"
echo "  3. Откройте https://gemini.google.com"
echo ""

echo "════════════════════════════════════════════════════════════"
echo ""
