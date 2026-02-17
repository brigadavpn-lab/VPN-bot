"""
xray_config.py — Централизованная работа с конфигом Xray.

Все файлы (bot.py, traffic_check.py, cleanup.py) используют этот модуль
вместо прямого обращения к config['inbounds'][1]. Inbound-ы ищутся
по полю "tag", что позволяет безопасно добавлять новые inbound-ы
(backup-порт, gRPC) без поломки индексов.
"""

import json
import subprocess

CONFIG_FILE_PATH = "/usr/local/etc/xray/config.json"

# Теги inbound-ов — ДОЛЖНЫ совпадать с "tag" в серверном config.json
VLESS_TCP_TAG = "vless-reality-tcp"                 # порт 443
VLESS_TCP_BACKUP_TAG = "vless-reality-tcp-backup"   # порт 8443
VLESS_GRPC_TAG = "vless-reality-grpc"               # gRPC, порт 2053

ALL_VLESS_TAGS = [VLESS_TCP_TAG, VLESS_TCP_BACKUP_TAG, VLESS_GRPC_TAG]
TCP_TAGS = [VLESS_TCP_TAG, VLESS_TCP_BACKUP_TAG]


def load_config():
    """Загрузить серверный конфиг Xray."""
    with open(CONFIG_FILE_PATH, 'r') as f:
        return json.load(f)


def save_config(config):
    """Записать конфиг обратно на диск."""
    with open(CONFIG_FILE_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def find_inbounds_by_tags(config, tags=None):
    """
    Найти inbound-ы по тегам.

    Возвращает список кортежей (index, inbound_dict).
    Если tags=None, возвращает все управляемые VLESS inbound-ы.
    """
    if tags is None:
        tags = ALL_VLESS_TAGS
    results = []
    for i, inbound in enumerate(config.get('inbounds', [])):
        if inbound.get('tag') in tags:
            results.append((i, inbound))
    return results


def add_client_to_inbounds(config, client_dict, tags=None):
    """
    Добавить клиента во все указанные inbound-ы.

    По умолчанию добавляет в оба TCP inbound-а (443 и 8443).
    Для gRPC inbound автоматически ставит flow="".
    """
    if tags is None:
        tags = TCP_TAGS
    for _, inbound in find_inbounds_by_tags(config, tags):
        client_copy = dict(client_dict)
        # gRPC несовместим с xtls-rprx-vision, flow должен быть пустым
        if inbound.get('tag') == VLESS_GRPC_TAG:
            client_copy['flow'] = ''
        inbound.setdefault('settings', {}).setdefault('clients', []).append(client_copy)


def remove_clients_by_email(config, emails_to_remove, tags=None):
    """
    Удалить клиентов по email из всех указанных inbound-ов.

    Возвращает количество удалённых записей.
    """
    if tags is None:
        tags = ALL_VLESS_TAGS
    removed = 0
    for _, inbound in find_inbounds_by_tags(config, tags):
        clients = inbound.get('settings', {}).get('clients', [])
        new_clients = [c for c in clients if c.get('email') not in emails_to_remove]
        removed += len(clients) - len(new_clients)
        inbound['settings']['clients'] = new_clients
    return removed


def restart_xray():
    """Перезапустить Xray через systemd."""
    subprocess.run(["systemctl", "restart", "xray"], check=True)
