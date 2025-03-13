import requests
import time
import psutil
import os
import sys
import signal
import subprocess
import argparse

# Параметры для подключения к ESP32
ESP32_AP_IP = "192.168.4.1"  # IP ESP32 в режиме точки доступа
ESP32_STATION_IP = "192.168.1.33"  # IP ESP32 в режиме клиента WiFi

# Парсер аргументов командной строки
parser = argparse.ArgumentParser(description='Скрипт для взаимодействия с ESP32')
parser.add_argument('--ap', action='store_true', help='Использовать IP для режима точки доступа')
parser.add_argument('--ip', type=str, help='Указать произвольный IP адрес ESP32')
parser.add_argument('--simple', action='store_true', help='Запустить простую отправку данных без мониторинга')
parser.add_argument('--message', type=str, default="Hello from Python!", help='Сообщение для отправки в простом режиме')
args = parser.parse_args()

# Определяем IP адрес ESP32 и URL для запросов
if args.ip:
    ESP32_IP = args.ip
elif args.ap:
    ESP32_IP = ESP32_AP_IP
else:
    ESP32_IP = ESP32_STATION_IP

# URL для запросов
ESP32_URL = f"http://{ESP32_IP}/"
ESP32_SEND_URL = f"http://{ESP32_IP}/send"

print(f"[DEBUG] Скрипт запущен, используется IP: {ESP32_IP}")
print(f"[DEBUG] PID скрипта: {os.getpid()}")

def send_simple_message(message):
    """Отправляет простое сообщение на ESP32"""
    try:
        print(f"[DEBUG] Отправка сообщения: {message}")
        response = requests.post(ESP32_SEND_URL, data=message)
        print(f"[DEBUG] Ответ ESP32: {response.text}")
        return True
    except Exception as e:
        print(f"[ERROR] Ошибка при отправке сообщения: {e}")
        return False

def get_system_stats():
    """Собирает статистику о системе"""
    cpu_load = psutil.cpu_percent(interval=1)  # Загруженность CPU в процентах
    memory_info = psutil.virtual_memory()  # Информация о памяти
    memory_usage = memory_info.percent  # Использование памяти в процентах
    
    # Получаем топ-3 процесса по загрузке CPU
    top_cpu_processes = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), 
                               key=lambda p: p.info['cpu_percent'], 
                               reverse=True)[:3]
    top_cpu = ", ".join([f"{p.info['name']}({p.info['cpu_percent']}%)" for p in top_cpu_processes])
    
    # Получаем топ-3 процесса по использованию памяти
    top_mem_processes = sorted(psutil.process_iter(['pid', 'name', 'memory_percent']), 
                               key=lambda p: p.info['memory_percent'], 
                               reverse=True)[:3]
    top_mem = ", ".join([f"{p.info['name']}({p.info['memory_percent']:.2f}%)" for p in top_mem_processes])
    
    return f"CPU: {cpu_load}%, RAM: {memory_usage}%, Top CPU: {top_cpu}, Top RAM: {top_mem}"

def kill_process(process_name):
    """Убивает процесс по имени"""
    try:
        print(f"[DEBUG] Попытка убить процесс: {process_name}")
        for proc in psutil.process_iter(['pid', 'name']):
            if process_name.lower() in proc.info['name'].lower():
                pid = proc.info['pid']
                print(f"[DEBUG] Найден процесс {process_name} с PID {pid}, отправка сигнала SIGTERM")
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"[DEBUG] Процесс {process_name} (PID {pid}) успешно остановлен")
                    return True
                except Exception as e:
                    print(f"[ERROR] Не удалось остановить процесс {process_name}: {e}")
        
        print(f"[ERROR] Процесс {process_name} не найден")
        return False
    except Exception as e:
        print(f"[ERROR] Ошибка при убийстве процесса {process_name}: {e}")
        return False

def restart_script():
    """Перезапускает текущий скрипт"""
    print("[DEBUG] Перезапуск скрипта...")
    python = sys.executable
    os.execl(python, python, *sys.argv)

def run_monitoring_loop():
    """Основной цикл мониторинга системы и взаимодействия с ESP32"""
    print("[DEBUG] Запуск цикла мониторинга")
    running = True
    
    while running:
        try:
            # Получаем и отправляем статистику системы
            data = get_system_stats()
            print(f"[DEBUG] Отправка данных: {data}")
            response = requests.post(ESP32_URL, headers={"Content-Type": "text/plain"}, data=data)
            print(f"[DEBUG] Ответ ESP32: {response.text}")
            
            # Проверяем ответ на наличие команд
            if "|RESET_SCRIPT" in response.text:
                print("[DEBUG] Получена команда перезапуска скрипта")
                restart_script()
            
            if "|KILL_PROCESS|" in response.text:
                parts = response.text.split("|KILL_PROCESS|")
                if len(parts) > 1:
                    process_name = parts[1]
                    print(f"[DEBUG] Получена команда убийства процесса: {process_name}")
                    kill_process(process_name)
            
        except Exception as e:
            print(f"[ERROR] Ошибка в цикле мониторинга: {e}")
        
        time.sleep(5)  # Отправлять данные каждые 5 секунд

# Главная логика скрипта
if __name__ == "__main__":
    try:
        if args.simple:
            # Режим простой отправки сообщения
            send_simple_message(args.message)
        else:
            # Режим мониторинга системы
            run_monitoring_loop()
    except KeyboardInterrupt:
        print("[DEBUG] Скрипт остановлен пользователем")
    except Exception as e:
        print(f"[ERROR] Критическая ошибка: {e}")
