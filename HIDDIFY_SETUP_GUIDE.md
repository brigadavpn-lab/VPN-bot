# Руководство по настройке Hiddify для VPN

## 📋 О Hiddify

Hiddify - универсальный VPN клиент для Windows, Android, iOS, macOS и Linux.
Поддерживает VLESS Reality, V2Ray, Xray, и другие протоколы.

**Версия:** v2.0.5 и выше
**Официальный сайт:** https://hiddify.com

---

## ✅ Проверка текущих настроек

### Ваши текущие параметры (правильные):

- **Реализация:** TUN mixed ✅
- **Смешанный порт:** 12334 ✅
- **Прозрачный прокси порт:** 12335 ✅
- **Локальный DNS порт:** 16450 ✅
- **Платформа:** Windows 10 (Build 26200) ✅

**Вывод:** Эти порты **НЕ конфликтуют** с сервером и **не требуют изменения**.

Локальные порты (12334, 12335, 16450) - это порты на вашем компьютере.
Сервер слушает на порту **443** (VLESS Reality).

---

## 🚀 Быстрая настройка

### Вариант 1: Импорт готовой конфигурации (рекомендуется)

1. **Скачайте файл конфигурации:**
   ```
   /home/user/VPN-bot/hiddify-optimized-config.json
   ```

2. **Замените UUID:**
   - Откройте файл в текстовом редакторе
   - Найдите строку: `"id": "REPLACE_WITH_YOUR_UUID"`
   - Замените на ваш UUID из Telegram бота
   - Сохраните файл

3. **Импорт в Hiddify:**
   - Откройте Hiddify
   - **Settings** → **Profiles** → **+ Add**
   - **Import from File**
   - Выберите `hiddify-optimized-config.json`

4. **Подключение:**
   - Выберите импортированный профиль
   - Нажмите **Connect**

---

### Вариант 2: Импорт через VLESS ссылку (быстрый способ)

1. **Получите VLESS ссылку от бота:**
   - Откройте Telegram бота
   - Нажмите "🚀 Получить VPN"
   - Скопируйте VLESS ссылку

2. **Импорт в Hiddify:**
   - Откройте Hiddify
   - **+ Add** → **Import from Clipboard**
   - Hiddify автоматически распознает VLESS ссылку

3. **Дополнительные настройки (опционально):**
   - После импорта нажмите на профиль → **Edit**
   - Добавьте оптимизации (см. раздел "Оптимизации" ниже)

---

## ⚙️ Рекомендуемые настройки в Hiddify

### Основные настройки (Settings)

#### 1. General Settings

```
✅ TUN Mode: Enabled
✅ Mixed Port: 12334 (оставить как есть)
✅ SOCKS Port: Auto
✅ HTTP Port: Auto
✅ Transparent Proxy Port: 12335 (оставить как есть)
```

#### 2. DNS Settings

```
✅ DNS Server: https://security.cloudflare-dns.com/dns-query
✅ FakeDNS: Enabled
✅ DNS Fallback: 1.1.1.2, 1.0.0.2, 8.8.8.8
```

**Почему важно:**
- DoH (DNS-over-HTTPS) шифрует DNS запросы
- FakeDNS критично для HTTP/3 и Gemini
- 1.1.1.2/1.0.0.2 - Cloudflare Malware Blocking

#### 3. Routing Settings

```
✅ Route Mode: Rule-based
✅ Domain Strategy: IPIfNonMatch
✅ Split-tunneling: Enabled (для .ru доменов)
```

**Правила маршрутизации:**
- `.ru, .su` домены → Direct (без VPN)
- `.org` домены → Direct
- Google/Gemini → Proxy (через VPN)
- Всё остальное → Proxy

#### 4. Advanced Settings

```
✅ QUIC Sniffing: Enabled
✅ HTTP/3 Support: Enabled
✅ TCP Fast Open: Enabled
✅ Connection Idle Timeout: 300s
✅ Handshake Timeout: 4s
```

---

## 🎯 Оптимизации для производительности

### 1. Для максимальной скорости

В настройках профиля:

```json
"policy": {
  "levels": {
    "0": {
      "handshake": 4,
      "connIdle": 300,
      "uplinkOnly": 2,
      "downlinkOnly": 5,
      "bufferSize": 512
    }
  }
}
```

### 2. Для Gemini и Google сервисов

Убедитесь, что включены:

```json
"dns": {
  "servers": [
    {
      "address": "fakedns",
      "domains": [
        "geosite:google",
        "domain:gemini.google.com"
      ]
    }
  ]
},
"fakedns": [{
  "ipPool": "198.18.0.0/15",
  "poolSize": 10000
}]
```

### 3. Для безопасности и приватности

```json
"dns": {
  "servers": [
    "https://security.cloudflare-dns.com/dns-query",
    "1.1.1.2",
    "1.0.0.2"
  ]
}
```

---

## 🧪 Проверка работы

### 1. Проверка подключения

Откройте: https://whoer.net

**Должно быть:**
- IP: Не ваш реальный IP (IP сервера или Cloudflare)
- DNS: 1.1.1.2 или Cloudflare
- WebRTC: Нет утечки IP
- Уровень анонимности: Высокий

### 2. Проверка DNS утечек

Откройте: https://dnsleaktest.com

**Нажмите:** "Extended test"

**Результат:**
- DNS серверы: Cloudflare (1.1.1.2, 1.0.0.2)
- Страна: НЕ Россия
- Нет DNS вашего провайдера

### 3. Проверка Gemini

Откройте: https://gemini.google.com

**Результат:**
- ✅ Интерфейс Gemini открывается
- ✅ Можно задавать вопросы
- ❌ НЕТ сообщения "не поддерживается в вашей стране"

### 4. Проверка split-tunneling

Откройте: https://yandex.ru (или любой .ru сайт)

**Результат:**
- ✅ Сайт открывается быстро
- ✅ Не проходит через VPN (direct connection)

**Как проверить:**
- В Hiddify смотрите статистику трафика
- При открытии .ru сайтов трафик НЕ должен расти

---

## 🐛 Решение проблем

### Проблема 1: VPN не подключается

**Симптомы:**
- Ошибка подключения
- Красный индикатор
- Таймаут соединения

**Решение:**

1. Проверьте UUID в конфигурации
2. Проверьте доступность сервера:
   ```cmd
   ping 141.105.143.224
   ```
3. Проверьте порт 443:
   ```cmd
   telnet 141.105.143.224 443
   ```
4. Попробуйте переимпортировать VLESS ссылку

---

### Проблема 2: Gemini не открывается

**Решение:**

1. **Очистите кеш браузера:**
   - Chrome: `Ctrl+Shift+Delete`
   - Выберите "Весь период"
   - Очистите кеш

2. **Очистите DNS кеш Windows:**
   ```cmd
   ipconfig /flushdns
   ```

3. **Откройте в режиме инкогнито:**
   - `Ctrl+Shift+N` в Chrome

4. **Проверьте, что FakeDNS включен в Hiddify**

**Если всё равно не работает:**
- Проблема может быть на сервере (см. GEMINI_STABILITY_FIX.md)

---

### Проблема 3: Медленная скорость

**Решение:**

1. **Попробуйте другой режим маршрутизации:**
   - Settings → Routing → Route Mode
   - Попробуйте "Global" вместо "Rule-based"

2. **Отключите Split-tunneling:**
   - Если не нужен доступ к .ru сайтам напрямую

3. **Проверьте нагрузку на сервер:**
   - Много пользователей могут замедлить VPN

4. **Используйте TCP Fast Open:**
   - Settings → Advanced → TCP Fast Open: Enabled

---

### Проблема 4: .ru сайты не открываются

**Если вам НУЖЕН доступ к .ru через VPN:**

1. **Отредактируйте профиль:**
   - Нажмите на профиль → Edit
   - Найдите routing rules
   - Удалите правило:
     ```json
     {
       "type": "field",
       "outboundTag": "direct",
       "domain": ["regexp:.*\\.ru$", "regexp:.*\\.su$"]
     }
     ```

2. **Сохраните и переподключитесь**

---

## 📊 Сравнение настроек

| Параметр | По умолчанию | Оптимизированная |
|----------|--------------|------------------|
| Mixed port | Auto (7890) | 12334 (ваш выбор) ✅ |
| FakeDNS | ❌ Выключен | ✅ Включен |
| DoH | ❌ Нет | ✅ Cloudflare DoH |
| Split-tunneling | ❌ Нет | ✅ .ru/.org direct |
| QUIC sniffing | ❌ Нет | ✅ Включен |
| TCP Fast Open | ❌ Нет | ✅ Включен |
| DNS Malware Block | ❌ Нет | ✅ 1.1.1.2/1.0.0.2 |

---

## 🔐 Безопасность и приватность

### Что защищено:

✅ **DNS запросы** - шифруются через DoH
✅ **IP адрес** - скрывается за VPN сервером
✅ **Трафик** - шифруется VLESS + Reality
✅ **Блокировка malware** - Cloudflare Malware Blocking DNS
✅ **Анти-DPI** - Reality protocol маскирует VPN как HTTPS

### Что НЕ защищено:

❌ **Активность внутри сайтов** - зависит от HTTPS на самих сайтах
❌ **WebRTC утечки** - используйте расширение "WebRTC Leak Shield"
❌ **IPv6 утечки** - рекомендуется отключить IPv6 в Windows

### Рекомендации:

1. **Отключить IPv6:**
   - Панель управления → Сеть и Интернет → Сетевые подключения
   - Правой кнопкой на адаптере → Свойства
   - Снять галочку с "IP версии 6 (TCP/IPv6)"

2. **Установить WebRTC Leak Shield:**
   - Chrome Web Store → WebRTC Leak Shield
   - Включить расширение

3. **Проверять утечки регулярно:**
   - https://browserleaks.com/ip
   - https://ipleak.net

---

## 📞 Полезные ссылки

- **Официальный сайт Hiddify:** https://hiddify.com
- **Документация:** https://github.com/hiddify/hiddify-next/wiki
- **Telegram канал:** @hiddify
- **GitHub:** https://github.com/hiddify/hiddify-next

---

## ✨ Ожидаемый результат

После правильной настройки Hiddify:

✅ **VPN подключается** стабильно
✅ **Gemini работает** без блокировок
✅ **DNS не утекает** (проверено на dnsleaktest.com)
✅ **Split-tunneling работает** - .ru сайты без VPN
✅ **Высокая скорость** - оптимизированные настройки
✅ **Безопасность** - DoH + Malware blocking
✅ **Приватность** - IP скрыт, Reality маскировка

---

## 🎯 Краткая шпаргалка

### Быстрая настройка (3 шага):

1. **Импорт:**
   - Hiddify → + Add → Import from Clipboard
   - Вставить VLESS ссылку от бота

2. **DNS:**
   - Settings → DNS → FakeDNS: Enabled
   - DNS Server: https://security.cloudflare-dns.com/dns-query

3. **Connect:**
   - Нажать Connect
   - Проверить на https://whoer.net

### Проверка (3 теста):

1. **IP:** https://whoer.net → IP НЕ ваш
2. **DNS:** https://dnsleaktest.com → Cloudflare
3. **Gemini:** https://gemini.google.com → Работает

### Если проблемы:

1. Очистить кеш браузера
2. Переподключить VPN
3. Проверить сервер (см. GEMINI_STABILITY_FIX.md)

---

**Готово! Hiddify настроен оптимально для вашего VPN.** 🎉
