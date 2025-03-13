#include <WiFi.h>
#include <WebServer.h>

// Parameters for access point mode
const char *apSSID = "ESP32_NETWORK";  // Network name in access point mode
const char *apPassword = "12345678";   // Network password in access point mode

// Parameters for connecting to an existing Wi-Fi network
const char* ssid = "&&";  
const char* password = "&&";

// Operating mode: true - access point, false - Wi-Fi connection
const bool ACCESS_POINT_MODE = true;

// Pins for buttons
const int BUTTON_RESET_ESP = 14;     // Button for rebooting ESP32
const int BUTTON_RESET_SCRIPT = 12;  // Button for restarting the script on the server
const int BUTTON_KILL_PROCESS = 13;  // Button for killing a process

WebServer server(80);
String lastMessage = "No data yet";  // Last message from the server
bool resetScriptRequest = false;     // Flag for script restart request
bool killProcessRequest = false;     // Flag for process kill request
String processToKill = "";           // Name of the process to be killed

void handleRoot() {
  Serial.println("[DEBUG] HTTP GET / request received.");
  server.send(200, "text/plain", "ESP32 Server is running!");
}

void handlePost() {
  Serial.println("[DEBUG] HTTP POST / request received.");
  if (server.hasArg("plain")) {
    lastMessage = server.arg("plain");  // Store the received message
    Serial.println("[DEBUG] Received from server: " + lastMessage);
    
    // Send the current control flags in response
    String response = "Data received";
    if (resetScriptRequest) {
      response += "|RESET_SCRIPT";
      resetScriptRequest = false;  // Reset the flag after sending
      Serial.println("[DEBUG] Script restart request sent");
    }
    if (killProcessRequest) {
      response += "|KILL_PROCESS|" + processToKill;
      killProcessRequest = false;  // Reset the flag after sending
      Serial.println("[DEBUG] Process kill request sent: " + processToKill);
      processToKill = "";
    }
    
    server.send(200, "text/plain", response);
  } else {
    Serial.println("[DEBUG] No data received in POST request.");
    server.send(400, "text/plain", "No data received");
  }
}

// Function for handling incoming data at the /send endpoint
void handleData() {
  if (server.hasArg("plain")) {
    String data = server.arg("plain");
    Serial.println("[DEBUG] Received Data at /send: " + data);
    server.send(200, "text/plain", "Data received!");
  } else {
    server.send(400, "text/plain", "No data received");
  }
}

// Function to get a list of processes and select the first one to kill
void handleKillProcess() {
  // Use information about top processes from lastMessage
  if (lastMessage.indexOf("Top CPU:") >= 0) {
    int start = lastMessage.indexOf("Top CPU:") + 9;
    int end = lastMessage.indexOf(",", start);
    if (end < 0) end = lastMessage.length();
    
    String topProcess = lastMessage.substring(start, end);
    // Extract process name (without percentages)
    int bracketPos = topProcess.indexOf("(");
    if (bracketPos > 0) {
      processToKill = topProcess.substring(0, bracketPos);
      killProcessRequest = true;
      Serial.println("[DEBUG] Selected process to kill: " + processToKill);
    } else {
      Serial.println("[ERROR] Failed to extract process name from data");
    }
  } else {
    Serial.println("[ERROR] No process data available");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("[DEBUG] Starting up...");

  // Configure button pins as inputs with pull-up resistors
  pinMode(BUTTON_RESET_ESP, INPUT_PULLUP);
  pinMode(BUTTON_RESET_SCRIPT, INPUT_PULLUP);
  pinMode(BUTTON_KILL_PROCESS, INPUT_PULLUP);
  
  Serial.println("[DEBUG] Buttons initialized.");

  // Start WiFi based on selected mode
  if (ACCESS_POINT_MODE) {
    // Access Point (AP) mode
    WiFi.softAP(apSSID, apPassword);
    Serial.println("[DEBUG] WiFi AP started!");
    Serial.print("[DEBUG] ESP32 AP IP: ");
    Serial.println(WiFi.softAPIP());
  } else {
    // Client mode (connecting to an existing network)
    WiFi.begin(ssid, password);
    Serial.print("[DEBUG] Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    
    Serial.println("\n[DEBUG] Connected to Wi-Fi!");
    Serial.println("[DEBUG] ESP32 IP: " + WiFi.localIP().toString());
  }
  
  // Set up HTTP request handlers
  server.on("/", HTTP_GET, handleRoot);
  server.on("/", HTTP_POST, handlePost);
  server.on("/send", HTTP_POST, handleData);
  
  server.begin();
  Serial.println("[DEBUG] HTTP server started.");
}

void loop() {
  server.handleClient();

  // Check ESP32 reset button
  if (digitalRead(BUTTON_RESET_ESP) == LOW) {
    Serial.println("[DEBUG] ESP32 reset button pressed. Restarting...");
    delay(500);  // Debounce
    ESP.restart();  // Restart ESP32
  }
  
  // Check script restart button
  if (digitalRead(BUTTON_RESET_SCRIPT) == LOW) {
    Serial.println("[DEBUG] Script restart button pressed.");
    delay(500);  // Debounce
    resetScriptRequest = true;  // Set flag for next POST request response
    Serial.println("[DEBUG] Script restart request set.");
  }
  
  // Check process kill button
  if (digitalRead(BUTTON_KILL_PROCESS) == LOW) {
    Serial.println("[DEBUG] Process kill button pressed.");
    delay(500);  // Debounce
    handleKillProcess();  // Handle process kill request
  }

  // Print the last received message every 5 seconds
  static unsigned long lastMillis = 0;  
  if (millis() - lastMillis >= 5000) {
    lastMillis = millis();
    Serial.println("[INFO] Last received data: " + lastMessage);
  }
}
