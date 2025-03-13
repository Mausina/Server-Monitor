import requests
import time
import psutil
import os
import sys
import signal
import subprocess
import argparse

# Parameters for connecting to ESP32
ESP32_AP_IP = "192.168.4.1"  # ESP32 IP in access point mode
ESP32_STATION_IP = "192.168.1.33"  # ESP32 IP in WiFi client mode

# Command-line argument parser
parser = argparse.ArgumentParser(description='Script for interacting with ESP32')
parser.add_argument('--ap', action='store_true', help='Use IP for access point mode')
parser.add_argument('--ip', type=str, help='Specify a custom IP address for ESP32')
parser.add_argument('--simple', action='store_true', help='Start simple data sending without monitoring')
parser.add_argument('--message', type=str, default="Hello from Python!", help='Message to send in simple mode')
args = parser.parse_args()

# Determine ESP32 IP address and request URLs
if args.ip:
    ESP32_IP = args.ip
elif args.ap:
    ESP32_IP = ESP32_AP_IP
else:
    ESP32_IP = ESP32_STATION_IP

# URLs for requests
ESP32_URL = f"http://{ESP32_IP}/"
ESP32_SEND_URL = f"http://{ESP32_IP}/send"

print(f"[DEBUG] Script started, using IP: {ESP32_IP}")
print(f"[DEBUG] Script PID: {os.getpid()}")

def send_simple_message(message):
    """Sends a simple message to ESP32"""
    try:
        print(f"[DEBUG] Sending message: {message}")
        response = requests.post(ESP32_SEND_URL, data=message)
        print(f"[DEBUG] ESP32 response: {response.text}")
        return True
    except Exception as e:
        print(f"[ERROR] Error while sending message: {e}")
        return False

def get_system_stats():
    """Collects system statistics"""
    cpu_load = psutil.cpu_percent(interval=1)  # CPU load in percentage
    memory_info = psutil.virtual_memory()  # Memory information
    memory_usage = memory_info.percent  # Memory usage in percentage
    
    # Get top 3 processes by CPU usage
    top_cpu_processes = sorted(psutil.process_iter(['pid', 'name', 'cpu_percent']), 
                               key=lambda p: p.info['cpu_percent'], 
                               reverse=True)[:3]
    top_cpu = ", ".join([f"{p.info['name']}({p.info['cpu_percent']}%)" for p in top_cpu_processes])
    
    # Get top 3 processes by memory usage
    top_mem_processes = sorted(psutil.process_iter(['pid', 'name', 'memory_percent']), 
                               key=lambda p: p.info['memory_percent'], 
                               reverse=True)[:3]
    top_mem = ", ".join([f"{p.info['name']}({p.info['memory_percent']:.2f}%)" for p in top_mem_processes])
    
    return f"CPU: {cpu_load}%, RAM: {memory_usage}%, Top CPU: {top_cpu}, Top RAM: {top_mem}"

def kill_process(process_name):
    """Kills a process by name"""
    try:
        print(f"[DEBUG] Attempting to kill process: {process_name}")
        for proc in psutil.process_iter(['pid', 'name']):
            if process_name.lower() in proc.info['name'].lower():
                pid = proc.info['pid']
                print(f"[DEBUG] Found process {process_name} with PID {pid}, sending SIGTERM signal")
                try:
                    os.kill(pid, signal.SIGTERM)
                    print(f"[DEBUG] Process {process_name} (PID {pid}) successfully stopped")
                    return True
                except Exception as e:
                    print(f"[ERROR] Failed to stop process {process_name}: {e}")
        
        print(f"[ERROR] Process {process_name} not found")
        return False
    except Exception as e:
        print(f"[ERROR] Error while killing process {process_name}: {e}")
        return False

def restart_script():
    """Restarts the current script"""
    print("[DEBUG] Restarting script...")
    python = sys.executable
    os.execl(python, python, *sys.argv)

def run_monitoring_loop():
    """Main monitoring loop for system stats and interaction with ESP32"""
    print("[DEBUG] Starting monitoring loop")
    running = True
    
    while running:
        try:
            # Get and send system statistics
            data = get_system_stats()
            print(f"[DEBUG] Sending data: {data}")
            response = requests.post(ESP32_URL, headers={"Content-Type": "text/plain"}, data=data)
            print(f"[DEBUG] ESP32 response: {response.text}")
            
            # Check response for commands
            if "|RESET_SCRIPT" in response.text:
                print("[DEBUG] Received command to restart script")
                restart_script()
            
            if "|KILL_PROCESS|" in response.text:
                parts = response.text.split("|KILL_PROCESS|")
                if len(parts) > 1:
                    process_name = parts[1]
                    print(f"[DEBUG] Received command to kill process: {process_name}")
                    kill_process(process_name)
            
        except Exception as e:
            print(f"[ERROR] Error in monitoring loop: {e}")
        
        time.sleep(5)  # Send data every 5 seconds

# Main script logic
if __name__ == "__main__":
    try:
        if args.simple:
            # Simple message sending mode
            send_simple_message(args.message)
        else:
            # System monitoring mode
            run_monitoring_loop()
    except KeyboardInterrupt:
        print("[DEBUG] Script stopped by user")
    except Exception as e:
        print(f"[ERROR] Critical error: {e}")
