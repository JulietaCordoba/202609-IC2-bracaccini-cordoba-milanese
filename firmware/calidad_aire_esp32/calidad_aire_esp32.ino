#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"   // WIFI_SSID, WIFI_PASS y MQTT_HOST viven acá (no se sube al repo)

// -------- PINES Y CONFIGURACIÓN --------
const int MQ135_A0 = 32;   // ADC GPIO32 en ESP32

// LEDs
const int LED_VERDE    = 27;
const int LED_AMARILLO = 26;
const int LED_ROJO     = 25;

// Relay
const int RELAY_PIN = 23;   // pin del relay del ventilador

// MQTT
const int MQTT_PORT = 1883;

const char* TOPIC_MQ135     = "aq/aula-1/mq135";        // datos del sensor
const char* TOPIC_VENT_SET  = "aq/aula-1/vent/set";     // recibe ON/OFF/AUTO
const char* TOPIC_VENT_EST  = "aq/aula-1/vent/estado";  // publica ON/OFF

WiFiClient espClient;
PubSubClient mqtt(espClient);

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 4000; // 4 segundos

// --- Modo de control del ventilador ---
// Mientras manualMode == true, el bloque automático del loop() no toca el
// relé: solo lo hace el usuario desde la web (comandos ON/OFF). El sistema
// vuelve a decidir solo cuando llega el comando "AUTO".
bool manualMode = false;

// ======================================================
//  WIFI
// ======================================================
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

// ======================================================
//   MQTT CALLBACK
// ======================================================
void callback(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

  if (String(topic) != TOPIC_VENT_SET) return;

  if (msg == "ON") {
    manualMode = true;
    digitalWrite(RELAY_PIN, LOW);     // relay activo
    mqtt.publish(TOPIC_VENT_EST, "ON");
    Serial.println("[ESP32] Ventilador -> ON (manual)");
  }
  else if (msg == "OFF") {
    manualMode = true;
    digitalWrite(RELAY_PIN, HIGH);    // relay apagado
    mqtt.publish(TOPIC_VENT_EST, "OFF");
    Serial.println("[ESP32] Ventilador -> OFF (manual)");
  }
  else if (msg == "AUTO") {
    manualMode = false;
    Serial.println("[ESP32] Ventilador -> modo AUTOMATICO reactivado");
    // No tocamos el relé acá: el próximo ciclo del loop() lo va a
    // ajustar según la lectura actual del sensor.
  }
}

// ======================================================
//  MQTT CONNECT
// ======================================================
void connectMQTT() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);

  while (!mqtt.connected()) {
    String clientId = "ESP32-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    Serial.print("Conectando a MQTT...");
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" conectado!");

      mqtt.subscribe(TOPIC_VENT_SET);  // escuchar órdenes
    } else {
      Serial.print(" fallo rc=");
      Serial.print(mqtt.state());
      Serial.println(" reintento en 2s");
      delay(2000);
    }
  }
}

// ======================================================
//  SETUP
// ======================================================
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
  digitalWrite(RELAY_PIN, HIGH);  // apagado al inicio (HIGH = off)
}

// ======================================================
//  LOOP
// ======================================================
void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastSend > SEND_INTERVAL) {
    lastSend = now;

    int val = analogRead(MQ135_A0);  // lectura cruda
    const char* estado;

    // --- Clasificación del aire (esto SIEMPRE se calcula y se muestra
    // en los LEDs, independientemente del modo del ventilador) ---
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
    // Solo actúa si NO estamos en modo manual. Si el usuario apagó el
    // ventilador a mano, esto no lo va a volver a prender solo hasta
    // que llegue el comando "AUTO".
    if (!manualMode) {
      if (val <= 700) {
        digitalWrite(RELAY_PIN, HIGH);
        mqtt.publish(TOPIC_VENT_EST, "OFF");
      } else {
        // "ambiente regular" o "ambiente peligroso": ventilador ON
        digitalWrite(RELAY_PIN, LOW);
        mqtt.publish(TOPIC_VENT_EST, "ON");
      }
    }

    // --- Publicar datos del sensor ---
    char msg[64];
    snprintf(msg, sizeof(msg), "{\"g\":%d,\"estado\":\"%s\"}", val, estado);

    bool ok = mqtt.publish(TOPIC_MQ135, msg);
    Serial.printf("MQ135=%d -> pub %s -> %s\n", val, msg, ok ? "OK" : "FAIL");
  }
}