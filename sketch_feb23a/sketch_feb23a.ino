#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "&&";  
const char* password = "&&";

// Пины для кнопок
const int BUTTON_RESET_ESP = 14;     // Кнопка для перезагрузки ESP32
const int BUTTON_RESET_SCRIPT = 12;  // Кнопка для перезагрузки скрипта на сервере
const int BUTTON_KILL_PROCESS = 13;  // Кнопка для убийства процесса

WebServer server(80);
String lastMessage = "No data yet";  // Последнее сообщение от сервера
bool resetScriptRequest = false;     // Флаг запроса перезагрузки скрипта
bool killProcessRequest = false;     // Флаг запроса убийства процесса
String processToKill = "";           // Имя процесса для убийства

void handleRoot() {
  Serial.println("[DEBUG] HTTP GET / request received.");
  server.send(200, "text/plain", "ESP32 Server is running!");
}

void handlePost() {
  Serial.println("[DEBUG] HTTP POST / request received.");
  if (server.hasArg("plain")) {
    lastMessage = server.arg("plain");  // Сохраняем сообщение
    Serial.println("[DEBUG] Received from server: " + lastMessage);
    
    // Отправляем текущие флаги управления в ответе
    String response = "Data received";
    if (resetScriptRequest) {
      response += "|RESET_SCRIPT";
      resetScriptRequest = false;  // Сбрасываем флаг после отправки
      Serial.println("[DEBUG] Отправлен запрос на перезагрузку скрипта");
    }
    if (killProcessRequest) {
      response += "|KILL_PROCESS|" + processToKill;
      killProcessRequest = false;  // Сбрасываем флаг после отправки
      Serial.println("[DEBUG] Отправлен запрос на убийство процесса: " + processToKill);
      processToKill = "";
    }
    
    server.send(200, "text/plain", response);
  } else {
    Serial.println("[DEBUG] No data received in POST request.");
    server.send(400, "text/plain", "No data received");
  }
}

// Функция для получения списка процессов и выбора первого для убийства
void handleKillProcess() {
  // Используем информацию о топовых процессах из lastMessage
  if (lastMessage.indexOf("Top CPU:") >= 0) {
    int start = lastMessage.indexOf("Top CPU:") + 9;
    int end = lastMessage.indexOf(",", start);
    if (end < 0) end = lastMessage.length();
    
    String topProcess = lastMessage.substring(start, end);
    // Извлекаем имя процесса (без процентов)
    int bracketPos = topProcess.indexOf("(");
    if (bracketPos > 0) {
      processToKill = topProcess.substring(0, bracketPos);
      killProcessRequest = true;
      Serial.println("[DEBUG] Выбран процесс для убийства: " + processToKill);
    } else {
      Serial.println("[ERROR] Не удалось извлечь имя процесса из данных");
    }
  } else {
    Serial.println("[ERROR] Нет данных о процессах");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("[DEBUG] Starting up...");

  // Настраиваем пины кнопок как входы с подтяжкой к питанию
  pinMode(BUTTON_RESET_ESP, INPUT_PULLUP);
  pinMode(BUTTON_RESET_SCRIPT, INPUT_PULLUP);
  pinMode(BUTTON_KILL_PROCESS, INPUT_PULLUP);
  
  Serial.println("[DEBUG] Buttons initialized.");

  WiFi.begin(ssid, password);
  Serial.print("[DEBUG] Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n[DEBUG] Connected to Wi-Fi!");
  Serial.println("[DEBUG] ESP32 IP: " + WiFi.localIP().toString());
  
  server.on("/", HTTP_GET, handleRoot);
  server.on("/", HTTP_POST, handlePost);
  server.begin();
  Serial.println("[DEBUG] HTTP server started.");
}

void loop() {
  server.handleClient();

  // Проверяем кнопку перезагрузки ESP32
  if (digitalRead(BUTTON_RESET_ESP) == LOW) {
    Serial.println("[DEBUG] Кнопка перезагрузки ESP32 нажата. Перезагрузка...");
    delay(500);  // Дебаунс
    ESP.restart();  // Перезагрузка ESP32
  }
  
  // Проверяем кнопку перезагрузки скрипта
  if (digitalRead(BUTTON_RESET_SCRIPT) == LOW) {
    Serial.println("[DEBUG] Кнопка перезагрузки скрипта нажата.");
    delay(500);  // Дебаунс
    resetScriptRequest = true;  // Устанавливаем флаг для следующего ответа на POST запрос
    Serial.println("[DEBUG] Запрос на перезапуск скрипта установлен.");
  }
  
  // Проверяем кнопку убийства процесса
  if (digitalRead(BUTTON_KILL_PROCESS) == LOW) {
    Serial.println("[DEBUG] Кнопка убийства процесса нажата.");
    delay(500);  // Дебаунс
    handleKillProcess();  // Обрабатываем запрос на убийство процесса
  }

  // Выводим последнее полученное сообщение каждые 5 секунд
  static unsigned long lastMillis = 0;
  if (millis() - lastMillis >= 5000) {
    lastMillis = millis();
    Serial.println("[INFO] Last received data: " + lastMessage);
  }
}
