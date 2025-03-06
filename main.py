import requests
import time
import psutil  # Нужно установить: pip install psutil

ESP32_IP = "192.168.1.33"  # Замените на актуальный IP ESP32
ESP32_URL = f"http://{ESP32_IP}/"

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

while True:
    try:
        data = get_system_stats()
        print(f"Sending: {data}")
        response = requests.post(ESP32_URL, headers={"Content-Type": "text/plain"}, data=data)
        print(f"ESP32 Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    time.sleep(5)  # Отправлять данные каждые 5 секунд
