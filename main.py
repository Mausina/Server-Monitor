import requests
import time
import psutil
import os
import sys
import signal
import subprocess

ESP32_IP = "192.168.1.33"  # Замените на актуальный IP ESP32
ESP32_URL = f"http://{ESP32_IP}/"

print("[DEBUG] Скрипт сервера запущен")
print(f"[DEBUG] PID скрипта: {os.getpid()}")

def get_system_stats():
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

running = True
while running:
    try:
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
        print(f"[ERROR] Ошибка: {e}")
    
    time.sleep(5)  # Отправлять данные каждые 5 секунд
