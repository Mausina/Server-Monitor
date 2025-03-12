import requests
import time
import psutil
import os
import sys
import signal
import subprocess
import socket
import zeroconf
import time

# We'll use mDNS to find the ESP32 automatically
ESP32_HOSTNAME = "esp32-controller.local"
ESP32_URL = f"http://{ESP32_HOSTNAME}/"

# Fallback to manual IP discovery if mDNS fails
def discover_esp32():
    """Try to discover ESP32 on the network"""
    print("[DEBUG] Attempting to discover ESP32 on the network...")
    
    # First try mDNS hostname
    try:
        print(f"[DEBUG] Trying to connect using mDNS hostname: {ESP32_HOSTNAME}")
        response = requests.get(f"http://{ESP32_HOSTNAME}/", timeout=2)
        if response.status_code == 200:
            print(f"[DEBUG] Successfully connected to ESP32 using mDNS!")
            return f"http://{ESP32_HOSTNAME}/"
    except:
        print("[DEBUG] Could not connect using mDNS, trying IP scan...")
    
    # If mDNS fails, try common subnet ranges for mobile hotspots
    possible_subnets = [
        "192.168.43.", # Common for Android hotspots
        "172.20.10.",  # Common for iPhone hotspots
        "192.168.1.",  # Common for home networks
        "192.168.0."   # Common for home networks
    ]
    
    for subnet in possible_subnets:
        print(f"[DEBUG] Scanning subnet {subnet}x...")
        for i in range(1, 255):
            ip = f"{subnet}{i}"
            try:
                response = requests.get(f"http://{ip}/", timeout=0.5)
                if response.status_code == 200 and "ESP32 Server is running" in response.text:
                    print(f"[DEBUG] Found ESP32 at IP: {ip}")
                    return f"http://{ip}/"
            except:
                pass
    
    print("[ERROR] Could not discover ESP32. Please check connections.")
    return ESP32_URL  # Return default as fallback

print("[DEBUG] Скрипт сервера запущен")
print(f"[DEBUG] PID скрипта: {os.getpid()}")

# Discover ESP32 address
ESP32_URL = discover_esp32()
print(f"[DEBUG] Using ESP32 URL: {ESP32_URL}")

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
        
        response = requests.post(ESP32_URL, headers={"Content-Type": "text/plain"}, data=data, timeout=5)
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
        # Reconnection logic - try to rediscover ESP32 on failure
        print("[DEBUG] Attempting to rediscover ESP32...")
        ESP32_URL = discover_esp32()
        print(f"[DEBUG] Reconnecting with ESP32 URL: {ESP32_URL}")
    
    time.sleep(5)  # Отправлять данные каждые 5 секунд
