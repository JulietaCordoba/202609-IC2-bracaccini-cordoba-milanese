#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"   // WIFI_SSID, WIFI_PASS y MQTT_HOST viven acá (no se sube al repo)

// -------- PINES Y CONFIGURACIÓN --------
const int MQ135_A0 = 32;   

// LEDs
const int LED_VERDE    = 27;
const int LED_AMARILLO = 26;
const int LED_ROJO     = 25;

// Relay
const int RELAY_PIN = 23;   
const int RELAY_ON  = HIGH;  
const int RELAY_OFF = LOW; 

// MQTT
const int MQTT_PORT = 1883;

const char* TOPIC_MQ135     = "aq/aula-1/mq135";        // datos del sensor
const char* TOPIC_VENT_SET  = "aq/aula-1/vent/set";     // recibe ON/OFF/AUTO
const char* TOPIC_VENT_EST  = "aq/aula-1/vent/estado";  // publica estado (JSON)

WiFiClient espClient;
PubSubClient mqtt(espClient);

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 4000; // 4 segundos

// --- Modo de control del ventilador ---
bool manualMode = false;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Conectando a WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado!");
  Serial.println(WiFi.localIP());
}

void setFan(bool on) {
  digitalWrite(RELAY_PIN, on ? RELAY_ON : RELAY_OFF);
}

void publishVentStatus() {
  bool fanOn = (digitalRead(RELAY_PIN) == RELAY_ON);
  char msg[48];
  snprintf(msg, sizeof(msg), "{\"fan_on\":%s,\"manual\":%s}",
           fanOn ? "true" : "false",
           manualMode ? "true" : "false");
  mqtt.publish(TOPIC_VENT_EST, msg);
}

void callback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  if (String(topic) != TOPIC_VENT_SET) return;

  if (msg == "ON") {
    manualMode = true;
    setFan(true);
    Serial.println("[ESP32] Ventilador -> ON (manual)");
    publishVentStatus();
  }
  else if (msg == "OFF") {
    manualMode = true;
    setFan(false);
    Serial.println("[ESP32] Ventilador -> OFF (manual)");
    publishVentStatus();
  }
  else if (msg == "AUTO") {
    manualMode = false;
    Serial.println("[ESP32] Ventilador -> modo AUTOMATICO reactivado");
    publishVentStatus();
  }
  else if (msg == "MANUAL") {
    manualMode = true;
    Serial.println("[ESP32] Modo MANUAL activado (sin cambiar el estado actual)");
    publishVentStatus();
  }
}

void connectMQTT() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);

  while (!mqtt.connected()) {
    String clientId = "ESP32-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("Conectando a MQTT...");
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" conectado!");

      mqtt.subscribe(TOPIC_VENT_SET);  
    } else {
      Serial.print(" fallo rc=");
      Serial.print(mqtt.state());
      Serial.println(" reintento en 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  connectWiFi();
  mqtt.setCallback(callback);
  connectMQTT();

  // LEDs
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);

  // Relay
  pinMode(RELAY_PIN, OUTPUT);
  setFan(false);  

  publishVentStatus();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastSend > SEND_INTERVAL) {
    lastSend = now;

    int val = analogRead(MQ135_A0);  
    const char* estado;

    // --- Clasificación del aire 
    if (val <= 700) {
      digitalWrite(LED_VERDE, HIGH);
      digitalWrite(LED_AMARILLO, LOW);
      digitalWrite(LED_ROJO, LOW);
      estado = "ambiente limpio";
    }
    else if (val > 700 && val <= 1500) {
      digitalWrite(LED_VERDE, LOW);
      digitalWrite(LED_AMARILLO, HIGH);
      digitalWrite(LED_ROJO, LOW);
      estado = "ambiente regular";
    }
    else {
      digitalWrite(LED_VERDE, LOW);
      digitalWrite(LED_AMARILLO, LOW);
      digitalWrite(LED_ROJO, HIGH);
      estado = "ambiente peligroso";
    }

    // --- CONTROL AUTOMÁTICO DEL VENTILADOR ---
    if (!manualMode) {
      setFan(val > 1500);
      publishVentStatus();
    }

    // --- Publicar datos del sensor ---
    char msg[64];
    snprintf(msg, sizeof(msg), "{\"g\":%d,\"estado\":\"%s\"}", val, estado);

    bool ok = mqtt.publish(TOPIC_MQ135, msg);
    Serial.printf("MQ135=%d -> pub %s -> %s\n", val, msg, ok ? "OK" : "FAIL");
  }
}