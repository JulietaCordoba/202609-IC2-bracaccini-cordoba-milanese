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

const char* TOPIC_MQ135    = "aq/aula-1/mq135";
const char* TOPIC_VENT_SET = "aq/aula-1/vent/set";
const char* TOPIC_VENT_EST = "aq/aula-1/vent/estado";

// -------- VALIDACIÓN DE SENSOR --------
const int ADC_MIN_VALIDO = 5;      // rail bajo -> sensor probablemente desconectado
const int ADC_MAX_VALIDO = 4090;   // rail alto -> circuito probablemente abierto

// -------- RECONEXIÓN NO BLOQUEANTE (backoff exponencial) --------
const unsigned long WIFI_RETRY_MIN_MS = 2000;
const unsigned long WIFI_RETRY_MAX_MS = 30000;
const unsigned long MQTT_RETRY_MIN_MS = 2000;
const unsigned long MQTT_RETRY_MAX_MS = 30000;

unsigned long wifiRetryDelay = WIFI_RETRY_MIN_MS;
unsigned long wifiLastAttempt = 0;
unsigned long mqttRetryDelay = MQTT_RETRY_MIN_MS;
unsigned long mqttLastAttempt = 0;

WiFiClient espClient;
PubSubClient mqtt(espClient);

unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 4000; // 4 segundos

bool manualMode = false;
int lecturasInvalidasSeguidas = 0;

// ======================================================
//  WIFI NO BLOQUEANTE
// ======================================================
void wifiTick() {
  if (WiFi.status() == WL_CONNECTED) {
    wifiRetryDelay = WIFI_RETRY_MIN_MS;
    return;
  }
  unsigned long now = millis();
  if (now - wifiLastAttempt < wifiRetryDelay) return;

  wifiLastAttempt = now;
  Serial.println("[WiFi] Intentando conectar...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  wifiRetryDelay = min(wifiRetryDelay * 2, WIFI_RETRY_MAX_MS);
}

// ======================================================
//  RELAY / ESTADO DEL VENTILADOR
// ======================================================
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

// ======================================================
//  MQTT CALLBACK (sin String, avisa payload inesperado)
// ======================================================
void callback(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, TOPIC_VENT_SET) != 0) return;
  if (length == 0 || length > 8) {
    Serial.println("[MQTT] Payload de longitud inesperada en vent/set, se ignora");
    return;
  }

  char msg[9];
  memcpy(msg, payload, length);
  msg[length] = '\0';

  if (strcmp(msg, "ON") == 0) {
    manualMode = true;
    setFan(true);
    Serial.println("[ESP32] Ventilador -> ON (manual)");
  }
  else if (strcmp(msg, "OFF") == 0) {
    manualMode = true;
    setFan(false);
    Serial.println("[ESP32] Ventilador -> OFF (manual)");
  }
  else if (strcmp(msg, "AUTO") == 0) {
    manualMode = false;
    Serial.println("[ESP32] Ventilador -> modo AUTOMATICO reactivado");
  }
  else if (strcmp(msg, "MANUAL") == 0) {
    manualMode = true;
    Serial.println("[ESP32] Modo MANUAL activado (sin cambiar el estado actual)");
  }
  else {
    Serial.printf("[MQTT] Comando no reconocido en vent/set: %s\n", msg);
    return; // no publicamos estado si el comando no era válido
  }
  publishVentStatus();
}

// ======================================================
//  MQTT NO BLOQUEANTE
// ======================================================
void mqttTick() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqtt.connected()) {
    mqttRetryDelay = MQTT_RETRY_MIN_MS;
    mqtt.loop();
    return;
  }
  unsigned long now = millis();
  if (now - mqttLastAttempt < mqttRetryDelay) return;
  mqttLastAttempt = now;

  char clientId[24];
  snprintf(clientId, sizeof(clientId), "ESP32-%06X", (unsigned int)(ESP.getEfuseMac() & 0xFFFFFF));

  Serial.print("[MQTT] Conectando...");
  if (mqtt.connect(clientId)) {
    Serial.println(" conectado!");
    mqtt.subscribe(TOPIC_VENT_SET);
    publishVentStatus();
  } else {
    Serial.printf(" fallo rc=%d, reintento en %lums\n", mqtt.state(), mqttRetryDelay);
    mqttRetryDelay = min(mqttRetryDelay * 2, MQTT_RETRY_MAX_MS);
  }
}

// ======================================================
//  LECTURA Y VALIDACIÓN DEL SENSOR
// ======================================================
bool leerSensorValido(int &valor) {
  valor = analogRead(MQ135_A0);
  if (valor <= ADC_MIN_VALIDO || valor >= ADC_MAX_VALIDO) {
    lecturasInvalidasSeguidas++;
    return false;
  }
  lecturasInvalidasSeguidas = 0;
  return true;
}

// ======================================================
//  SETUP
// ======================================================
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARILLO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  setFan(false);

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(callback);

  WiFi.mode(WIFI_STA);
  wifiTick();
}

// ======================================================
//  LOOP
// ======================================================
void loop() {
  wifiTick();
  mqttTick();

  unsigned long now = millis();
  if (now - lastSend < SEND_INTERVAL) return;
  lastSend = now;

  int val;
  bool valido = leerSensorValido(val);

  if (!valido) {
    Serial.printf("[Sensor] Lectura fuera de rango (%d). Invalidas seguidas: %d\n",
                  val, lecturasInvalidasSeguidas);
    char msgFalla[64];
    snprintf(msgFalla, sizeof(msgFalla),
             "{\"fault\":true,\"raw\":%d,\"consecutivas\":%d}", val, lecturasInvalidasSeguidas);
    mqtt.publish(TOPIC_MQ135, msgFalla);
    return;
  }

  const char* estado;
  if (val <= 700) {
    digitalWrite(LED_VERDE, HIGH); digitalWrite(LED_AMARILLO, LOW); digitalWrite(LED_ROJO, LOW);
    estado = "ambiente limpio";
  } else if (val <= 1500) {
    digitalWrite(LED_VERDE, LOW); digitalWrite(LED_AMARILLO, HIGH); digitalWrite(LED_ROJO, LOW);
    estado = "ambiente regular";
  } else {
    digitalWrite(LED_VERDE, LOW); digitalWrite(LED_AMARILLO, LOW); digitalWrite(LED_ROJO, HIGH);
    estado = "ambiente peligroso";
  }

  if (!manualMode) {
    setFan(val > 1500);
    publishVentStatus();
  }

  char msg[64];
  snprintf(msg, sizeof(msg), "{\"g\":%d,\"estado\":\"%s\"}", val, estado);
  bool ok = mqtt.publish(TOPIC_MQ135, msg);
  Serial.printf("MQ135=%d -> pub %s -> %s\n", val, msg, ok ? "OK" : "FAIL");
}