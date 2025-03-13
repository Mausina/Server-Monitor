import requests
import time
import psutil
import os
import sys
import signal
import subprocess
import socket
import platform
import json
import ipaddress
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

print("\n==================================================")
print("ESP32 Monitor Client - Enhanced Discovery Version")
print("==================================================\n")

print("[DEBUG] Скрипт сервера запущен")
print(f"[DEBUG] PID скрипта: {os.getpid()}")
print(f"[DEBUG] Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Глобальные параметры
ESP32_HOSTNAME = "esp32monitor.local"  # Имя mDNS
ESP32_IP = None  # Будет установлен после обнаружения
ESP32_URL = None  # Будет установлен после обнаружения
DISCOVERY_TIMEOUT = 1  # Таймаут для каждого запроса обнаружения (секунды)
MAX_DISCOVERY_WORKERS = 50  # Максимальное количество потоков для сканирования
CONFIG_FILE = "esp32_monitor_config.json"  # Файл для сохранения настроек

# Сохранение и загрузка конфигурации для запоминания IP адреса
def save_config(ip):
    """Сохраняет IP адрес в конфигурационный файл"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"esp32_ip": ip, "last_update": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        print(f"[DEBUG] IP {ip} сохранен в конфигурационном файле")
    except Exception as e:
        print(f"[WARNING] Не удалось сохранить конфигурацию: {e}")

def load_config():
    """Загружает IP адрес из конфигурационного файла"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                ip = config.get("esp32_ip")
                last_update = config.get("last_update", "неизвестно")
                print(f"[DEBUG] Загружен сохраненный IP {ip} (последнее обновление: {last_update})")
                return ip
        return None
    except Exception as e:
        print(f"[WARNING] Не удалось загрузить конфигурацию: {e}")
        return None

# Определение локальных интерфейсов для более точного сканирования
def get_local_interfaces():
    """Получает список локальных IP интерфейсов с их подсетями"""
    interfaces = []
    try:
        # Для Linux/Mac
        if platform.system() != "Windows":
            import netifaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if ip != '127.0.0.1':
                            netmask = addr.get('netmask', '255.255.255.0')
                            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                            interfaces.append({
                                'ip': ip, 
                                'network': str(network.network_address), 
                                'prefix': network.prefixlen
                            })
        else:
            # Для Windows используем упрощенный метод
            hostname = socket.gethostname()
            for ip in socket.gethostbyname_ex(hostname)[2]:
                if ip != '127.0.0.1':
                    interfaces.append({
                        'ip': ip, 
                        'network': ip.rsplit('.', 1)[0] + '.0', 
                        'prefix': 24
                    })
    except Exception as e:
        print(f"[WARNING] Ошибка при получении сетевых интерфейсов: {e}")
        # Добавляем стандартные сети для мобильных точек доступа
        interfaces.append({'ip': '192.168.43.1', 'network': '192.168.43.0', 'prefix': 24})  # Android
        interfaces.append({'ip': '172.20.10.1', 'network': '172.20.10.0', 'prefix': 24})   # iPhone
    
    if not interfaces:
        # Добавляем стандартные сети если не найдено ни одного интерфейса
        interfaces.append({'ip': '192.168.0.1', 'network': '192.168.0.0', 'prefix': 24})    # Обычные роутеры
        interfaces.append({'ip': '192.168.1.1', 'network': '192.168.1.0', 'prefix': 24})    # Обычные роутеры
        interfaces.append({'ip': '192.168.43.1', 'network': '192.168.43.0', 'prefix': 24})  # Android
        interfaces.append({'ip': '172.20.10.1', 'network': '172.20.10.0', 'prefix': 24})   # iPhone
    
    return interfaces

# Функция для проверки одного IP адреса
def check_ip(ip, port=80):
    """Проверяет, является ли указанный IP адрес ESP32 устройством"""
    try:
        url = f"http://{ip}:{port}/discovery"
        response = requests.get(url, timeout=DISCOVERY_TIMEOUT)
        if response.status_code == 200 and "ESP32_MONITOR_DEVICE" in response.text:
            print(f"[SUCCESS] Найдено ESP32 устройство на IP: {ip}")
            return ip
        
        # Проверяем корневой маршрут, если /discovery не отвечает
        url = f"http://{ip}:{port}/"
        response = requests.get(url, timeout=DISCOVERY_TIMEOUT)
        if response.status_code == 200 and "ESP32_MONITOR_DEVICE" in response.text:
            print(f"[SUCCESS] Найдено ESP32 устройство на IP: {ip}")
            return ip
    except:
        pass
    return None

# Функция сканирования диапазона IP-адресов в отдельном потоке
def scan_ip_range(network, prefix):
    """Сканирует диапазон IP адресов для поиска ESP32"""
    try:
        network = ipaddress.IPv4Network(f"{network}/{prefix}", strict=False)
        found_ip = None
        
        # Создаем список всех IP в сети для сканирования
        # Ограничиваем до 254 адресов для больших сетей
        hosts = list(network.hosts())
        if len(hosts) > 254:
            hosts = hosts[:254]
        
        print(f"[DEBUG] Сканирование сети {network} ({len(hosts)} адресов)...")
        
        # Используем пул потоков для параллельного сканирования
        with ThreadPoolExecutor(max_workers=MAX_DISCOVERY_WORKERS) as executor:
            results = list(executor.map(check_ip, [str(ip) for ip in hosts]))
            
        # Фильтруем None результаты
        found_ips = [ip for ip in results if ip]
        if found_ips:
            return found_ips[0]  # Возвращаем первый найденный IP
        
        return None
    except Exception as e:
        print(f"[ERROR] Ошибка при сканировании сети {network}/{prefix}: {e}")
        return None

# Функция для попытки подключения по mDNS
def try_mdns_connection():
    """Пытается подключиться к ESP32 по mDNS имени"""
    try:
        print(f"[DEBUG] Попытка подключения по mDNS: {ESP32_HOSTNAME}")
        response = requests.get(f"http://{ESP32_HOSTNAME}/", timeout=3)
        if response.status_code == 200:
            print(f"[SUCCESS] Успешное подключение по mDNS!")
            return ESP32_HOSTNAME
    except Exception as e:
        print(f"[DEBUG] Не удалось подключиться по mDNS: {e}")
    return None

# Основная функция обнаружения ESP32
def discover_esp32():
    """Обнаруживает ESP32 в сети используя несколько методов"""
    global ESP32_IP, ESP32_URL
    
    print("\n[DEBUG] Запуск процесса обнаружения ESP32...")
    
    # Шаг 1: Пробуем загрузить сохраненный IP
    saved_ip = load_config()
    if saved_ip:
        print(f"[DEBUG] Проверка сохраненного IP: {saved_ip}")
        if check_ip(saved_ip):
            ESP32_IP = saved_ip
            ESP32_URL = f"http://{ESP32_IP}/"
            print(f"[SUCCESS] Подключение установлено с сохраненным IP: {ESP32_IP}")
            return ESP32_URL
    
    # Шаг 2: Пробуем mDNS
    mdns_result = try_mdns_connection()
    if mdns_result:
        ESP32_IP = mdns_result
        ESP32_URL = f"http://{ESP32_IP}/"
        return ESP32_URL
    
    # Шаг 3: Сканируем локальные сети
    interfaces = get_local_interfaces()
    print(f"[DEBUG] Обнаружено {len(interfaces)} сетевых интерфейсов для сканирования")
    
    for interface in interfaces:
        print(f"[DEBUG] Сканирование сети: {interface['network']}/{interface['prefix']} (интерфейс: {interface['ip']})")
        found_ip = scan_ip_range(interface['network'], interface['prefix'])
        if found_ip:
            ESP32_IP = found_ip
            ESP32_URL = f"http://{ESP32_IP}/"
            # Сохраняем найденный IP
            save_config(ESP32_IP)
            return ESP32_URL
    
    # Шаг 4: Проверяем общие диапазоны IP для мобильных точек доступа
    common_networks = [
        "192.168.43.0/24",  # Android
        "172.20.10.0/24",   # iPhone
        "192.168.1.0/24",   # Обычные роутеры
        "192.168.0.0/24",   # Обычные роутеры
        "10.0.0.0/24"       # Некоторые офисные сети
    ]
    
    for network in common_networks:
        net, prefix = network.split('/')
        if not any(net == interface['network'] and int(prefix) == interface['prefix'] for interface in interfaces):
            print(f"[DEBUG] Сканирование дополнительной сети: {network}")
            found_ip = scan_ip_range(net, int(prefix))
            if found_ip:
                ESP32_IP = found_ip
                ESP32_URL = f"http://{ESP32_IP}/"
                # Сохраняем найденный IP
                save_config(ESP32_IP)
                return ESP32_URL
    
    print("[ERROR] ESP32 не обнаружен в сети. Проверьте подключение.")
    # Возвращаем запасной вариант
    return "http://esp32monitor.local/"

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

# Основная функция
def main():
    global ESP32_URL
    
    # Обнаружение ESP32
    ESP32_URL = discover_esp32()
    print(f"[INFO] Используем URL для подключения к ESP32: {ESP32_URL}")
    
    connection_failures = 0
    max_failures = 5
    
    while True:
        try:
            data = get_system_stats()
            print(f"[DEBUG] Отправка данных: {data}")
            
            response = requests.post(ESP32_URL, headers={"Content-Type": "text/plain"}, data=data, timeout=5)
            print(f"[DEBUG] Ответ ESP32: {response.text}")
            
            # Сброс счетчика ошибок при успешном подключении
            connection_failures = 0
            
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
            print(f"[ERROR] Ошибка соединения: {e}")
            connection_failures += 1
            
            if connection_failures >= max_failures:
                print(f"[WARNING] {connection_failures} неудачных попыток подряд. Запуск переобнаружения ESP32...")
                ESP32_URL = discover_esp32()
                connection_failures = 0
            
            print(f"[DEBUG] Пауза перед следующей попыткой ({connection_failures}/{max_failures})...")
            time.sleep(5)  # Пауза между попытками переподключения
        
        time.sleep(5)  # Отправлять данные каждые 5 секунд

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Скрипт остановлен пользователем")
    except Exception as e:
        print(f"[FATAL] Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
