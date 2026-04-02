#!/bin/bash
# =============================================================================
# update_xray.sh — Обновление REALITY-настроек Xray без потери пользователей
#
# Запуск: bash /root/vpn-bot/scripts/update_xray.sh
#
# Что делает:
#   1. Генерирует новую пару x25519-ключей
#   2. Обновляет realitySettings в config.json (SNI, fingerprint, ключи)
#   3. Существующие клиенты/пользователи НЕ ЗАТРАГИВАЮТСЯ
#   4. Выводит новый Public Key — его нужно вставить в bot.py
#   5. Перезапускает Xray
# =============================================================================

set -e

XRAY_BIN="/usr/local/bin/xray"
CONFIG="/usr/local/etc/xray/config.json"

# Проверяем наличие нужных файлов
if [ ! -f "$XRAY_BIN" ]; then
    echo "ОШИБКА: xray не найден по пути $XRAY_BIN"
    exit 1
fi

if [ ! -f "$CONFIG" ]; then
    echo "ОШИБКА: config.json не найден по пути $CONFIG"
    echo "Используйте xray/config.template.json как основу и скопируйте в $CONFIG"
    exit 1
fi

echo "=== Генерация новых x25519-ключей ==="
KEYS=$("$XRAY_BIN" x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep "Private key:" | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEYS"  | grep "Public key:"  | awk '{print $3}')

if [ -z "$PRIVATE_KEY" ] || [ -z "$PUBLIC_KEY" ]; then
    echo "ОШИБКА: не удалось получить ключи от xray x25519"
    exit 1
fi

echo "Ключи сгенерированы."

echo ""
echo "=== Резервная копия текущего config.json ==="
cp "$CONFIG" "${CONFIG}.bak.$(date +%Y%m%d_%H%M%S)"
echo "Бэкап сохранён."

echo ""
echo "=== Обновление realitySettings ==="
python3 - "$CONFIG" "$PRIVATE_KEY" <<'PYEOF'
import json, sys

config_path = sys.argv[1]
private_key = sys.argv[2]

with open(config_path, 'r') as f:
    cfg = json.load(f)

updated = False
for inbound in cfg.get('inbounds', []):
    if inbound.get('protocol') == 'vless':
        stream = inbound.get('streamSettings', {})
        if stream.get('security') == 'reality':
            rs = stream.setdefault('realitySettings', {})
            rs['dest']        = 'www.microsoft.com:443'
            rs['serverNames'] = ['www.microsoft.com', 'github.com', 'addons.mozilla.org']
            rs['privateKey']  = private_key
            rs['fingerprint'] = 'chrome'
            rs['shortIds']    = ['', 'a028507ab5b114b4']
            updated = True
            print(f"  inbound '{inbound.get('tag', 'vless')}' обновлён.")

if not updated:
    print("ПРЕДУПРЕЖДЕНИЕ: VLESS inbound с security=reality не найден в config.json.")
    print("Проверьте структуру конфига по шаблону xray/config.template.json.")
    sys.exit(1)

with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)

print("config.json успешно обновлён.")
PYEOF

echo ""
echo "================================================================="
echo "  ВАЖНО: вставь этот Public Key в bot.py"
echo ""
echo "  REALITY_PUBLIC_KEY = \"$PUBLIC_KEY\""
echo ""
echo "  Файл: /root/vpn-bot/bot.py, строка ~41"
echo "================================================================="
echo ""

echo "=== Перезапуск Xray ==="
systemctl restart xray
sleep 2
systemctl status xray --no-pager -l

echo ""
echo "=== Готово ==="
echo "Следующий шаг: обнови REALITY_PUBLIC_KEY в bot.py (см. выше) и перезапусти бот."
