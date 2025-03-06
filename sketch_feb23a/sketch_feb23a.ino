#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "eir98854834";  
const char* password = "Pfc9JApskc";

WebServer server(80);
String lastMessage = "No data yet";  // Последнее сообщение от сервера

void handleRoot() {
  Serial.println("[DEBUG] HTTP GET / request received.");
  server.send(200, "text/plain", "ESP32 Server is running!");
}

void handlePost() {
  Serial.println("[DEBUG] HTTP POST / request received.");
  if (server.hasArg("plain")) {
    lastMessage = server.arg("plain");  // Сохраняем сообщение
    Serial.println("[DEBUG] Received from server: " + lastMessage);
    server.send(200, "text/plain", "Data received");
  } else {
    Serial.println("[DEBUG] No data received in POST request.");
    server.send(400, "text/plain", "No data received");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("[DEBUG] Starting up...");

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

  // Выводим последнее полученное сообщение каждые 5 секунд
  static unsigned long lastMillis = 0;
  if (millis() - lastMillis >= 5000) {
    lastMillis = millis();
    Serial.println("[INFO] Last received data: " + lastMessage);
  }
}

