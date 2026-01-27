# Руководство по установке Cloudflare WARP для доступа к Gemini

## 🎯 Цель

Решение проблемы "Gemini пока не поддерживается в вашей стране" путем изменения геолокации VPN сервера через Cloudflare WARP.

---

## 📋 Что делает WARP?

- 🌐 Туннелирует весь исходящий трафик VPN сервера через сеть Cloudflare
- 🔄 Меняет геолокацию IP адреса на разрешенную страну
- 🚀 Работает как SOCKS5 proxy (127.0.0.1:40000)
- ✅ Не требует изменения клиентских настроек VPN

---

## 🚀 Быстрая установка

### Шаг 1: Установка WARP

На VPN сервере выполните:

```bash
cd /root/vpn-bot

# Сделайте скрипты исполняемыми
chmod +x install_warp.sh configure_xray_warp.sh

# Установите WARP
./install_warp.sh
```

**Что произойдет:**
1. ✅ Проверка текущей геолокации сервера
2. ✅ Установка Cloudflare WARP
3. ✅ Регистрация и подключение к WARP
4. ✅ Настройка SOCKS5 proxy на порту 40000
5. ✅ Проверка новой геолокации через WARP

**Ожидаемый результат:**
```
================================================================
   Сравнение геолокации
================================================================
                     | БЕЗ WARP                      | С WARP
----------------------------------------------------------------
IP адрес             | 123.45.67.89                  | 104.28.X.X
Страна               | Russia                        | United States
Город                | Moscow                        | San Francisco
================================================================
```

### Шаг 2: Настройка Xray для работы через WARP

```bash
./configure_xray_warp.sh
```

**Что произойдет:**
1. ✅ Проверка работы WARP
2. ✅ Создание резервной копии config.json
3. ✅ Добавление WARP outbound в конфигурацию
4. ✅ Изменение маршрутизации: весь трафик → через WARP
5. ✅ Перезапуск Xray

**Модификации config.json:**
- Добавлен outbound "warp" (SOCKS5 proxy)
- Изменено правило routing: `tcp,udp` → `outboundTag: "warp"`

---

## ✅ Проверка работы

### 1. Проверка статуса WARP

```bash
warp-cli status
```

Должно быть: `Status update: Connected`

### 2. Проверка IP через WARP

```bash
curl --socks5 127.0.0.1:40000 ifconfig.me
```

Должен показать IP Cloudflare (обычно начинается с 104.28.X.X или 172.64.X.X)

### 3. Проверка геолокации

```bash
curl --socks5 127.0.0.1:40000 "https://ipapi.co/$(curl -s --socks5 127.0.0.1:40000 ifconfig.me)/json/" | grep country_name
```

Должна быть страна, где Gemini разрешен (обычно United States)

### 4. Проверка Xray

```bash
systemctl status xray
journalctl -u xray -n 20
```

Xray должен быть `active (running)` без ошибок

### 5. Проверка VPN клиента

1. **Подключитесь к VPN** с телефона/компьютера
2. **Откройте:** https://whoer.net или https://browserleaks.com/ip
3. **Проверьте:**
   - IP должен быть Cloudflare (AS13335)
   - Страна должна быть США или другая разрешенная
   - DNS не должен утекать

4. **Откройте:** https://gemini.google.com
5. **Результат:** Gemini должен работать без сообщения о блокировке

---

## 🔧 Управление WARP

### Основные команды:

```bash
# Проверить статус
warp-cli status

# Подключиться
warp-cli connect

# Отключиться
warp-cli disconnect

# Информация об аккаунте
warp-cli account

# Переключить режим (proxy/warp)
warp-cli mode proxy

# Удалить регистрацию и перерегистрироваться
warp-cli registration delete
warp-cli register
```

### Автозапуск WARP при загрузке:

```bash
systemctl enable warp-svc
systemctl start warp-svc
```

---

## 🐛 Решение проблем

### Проблема: WARP не подключается

**Решение:**
```bash
warp-cli registration delete
warp-cli register
warp-cli mode proxy
warp-cli connect
```

### Проблема: VPN не работает после настройки WARP

**Решение:**
```bash
# Откатите конфигурацию
cp /usr/local/etc/xray/config.json.backup.* /usr/local/etc/xray/config.json
systemctl restart xray
```

### Проблема: Медленное соединение через WARP

**Решение:**
```bash
# Переключите на режим WARP+ (требует оплаты или бесплатные 1GB)
warp-cli registration new
warp-cli mode warp
```

### Проблема: Gemini все равно заблокирован

**Возможные причины:**
1. DNS leak - проверьте на https://dnsleaktest.com
2. WebRTC leak - отключите WebRTC в браузере
3. IPv6 leak - отключите IPv6 в настройках сети
4. WARP не подключен - проверьте `warp-cli status`

**Решение:**
```bash
# Проверьте IP через VPN
curl ifconfig.me  # На сервере
# Должен показать Cloudflare IP

# Проверьте в браузере через VPN
# Откройте https://browserleaks.com/ip
# Все тесты должны показывать Cloudflare IP
```

---

## 📊 Структура после установки

```
/root/vpn-bot/
├── config.json                    # Конфигурация с WARP outbound
├── install_warp.sh                # Скрипт установки WARP
├── configure_xray_warp.sh         # Скрипт настройки Xray
└── WARP_SETUP_GUIDE.md            # Это руководство

/usr/local/etc/xray/
└── config.json                    # Рабочая конфигурация Xray
    └── *.backup.*                 # Резервные копии

WARP работает как:
- Daemon: warp-svc (systemd service)
- SOCKS5 proxy: 127.0.0.1:40000
```

---

## 🔐 Безопасность

### Что происходит с трафиком:

```
Клиент VPN → Xray сервер → WARP SOCKS5 → Cloudflare сеть → Интернет
   (E2E шифрование)    (Локально)    (Cloudflare шифрование)
```

1. **Клиент → Xray:** Шифрование VLESS + Reality (E2E)
2. **Xray → WARP:** Локальное соединение на сервере
3. **WARP → Интернет:** Шифрование WireGuard от Cloudflare

### Что видит Cloudflare:

- ✅ Весь исходящий трафик от VPN сервера
- ✅ Домены, к которым вы обращаетесь
- ❌ Контент (защищен HTTPS)
- ❌ Связь клиента с вашим VPN сервером (Reality маскировка)

---

## 💡 Альтернативы WARP

Если WARP не подходит, рассмотрите:

1. **Переместить сервер** в другую страну (США, Германия, Нидерланды)
2. **Chain proxy** через другой сервер в разрешенной стране
3. **AWS/Google Cloud** VPN с IP в разрешенной стране

---

## 📞 Поддержка

Если что-то не работает:

1. Проверьте логи:
   ```bash
   journalctl -u warp-svc -n 50
   journalctl -u xray -n 50
   ```

2. Проверьте статус:
   ```bash
   warp-cli status
   systemctl status xray
   ```

3. Откатите изменения и попробуйте снова

---

## ✅ Ожидаемый результат

После успешной настройки:
- ✅ VPN работает нормально
- ✅ IP адрес через VPN показывает Cloudflare
- ✅ Gemini открывается без блокировки
- ✅ Геолокация определяется как разрешенная страна
- ✅ Все остальные сайты работают

**Тест:** https://gemini.google.com должен работать! 🎉
