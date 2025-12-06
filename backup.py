import asyncio
import os
import zipfile
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile

# --- НАСТРОЙКИ ---
# Вставь сюда данные, которые ты нашел в config.py / bot.py
BOT_TOKEN = "8220192914:AAGgPdmEjZhXUZrkIzk7VByUSRjSrvoGTZE" 
ADMIN_ID = 5984716315  # Вставь сюда свой цифровой ID (без кавычек)

# Файлы, которые нужно сохранить
# Проверь, что эти пути правильные для твоего сервера
FILES_TO_BACKUP = [
    "/root/vpn-bot/vpn_users.db",       # База данных пользователей
    "/usr/local/etc/xray/config.json",  # Конфиг сервера Xray
    "/root/vpn-bot/bot.py",             # Основной код бота
    "/root/vpn-bot/config.py"           # На всякий случай настройки
]

# Имя архива (с текущей датой)
BACKUP_NAME = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.zip"

async def send_backup():
    try:
        # 1. Создаем ZIP архив
        print(f"📦 Создаю архив {BACKUP_NAME}...")
        files_found = 0
        with zipfile.ZipFile(BACKUP_NAME, 'w') as zipf:
            for file in FILES_TO_BACKUP:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
                    files_found += 1
                else:
                    print(f"⚠️ Файл не найден (пропускаю): {file}")
        
        if files_found == 0:
            print("❌ Ни один файл не найден! Проверь пути.")
            return

        # 2. Отправляем в Telegram
        if "ВСТАВЬ" not in BOT_TOKEN:
            print("🚀 Отправляю в Telegram...")
            bot = Bot(token=BOT_TOKEN)
            archive = FSInputFile(BACKUP_NAME)
            
            await bot.send_document(
                chat_id=ADMIN_ID, 
                document=archive, 
                caption=f"🛡 Авто-бэкап сервера\n📅 Дата: {datetime.now()}"
            )
            print("✅ Бэкап успешно отправлен!")
            await bot.session.close()
        else:
            print("❌ Ошибка: Ты забыл вставить Токен в код!")

    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")

    # 3. Удаляем архив с диска (чистим за собой)
    finally:
        if os.path.exists(BACKUP_NAME):
            os.remove(BACKUP_NAME)
            print("🗑 Локальный файл удален.")

if __name__ == "__main__":
    asyncio.run(send_backup())