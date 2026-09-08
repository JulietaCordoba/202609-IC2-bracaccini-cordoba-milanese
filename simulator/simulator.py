"""
Simulador del ESP32 para el sistema de monitoreo de calidad del aire.

Publica telemetría falsa por MQTT con el mismo contrato (tópicos, formato de
payload y comportamiento) que el firmware real (firmware/calidad_aire_esp32/
calidad_aire_esp32.ino), para poder probar el backend y el frontend sin tener
el hardware físico conectado.

Uso:
    python simulator.py
    (mientras corre, podés escribir un número 0-4095 + Enter para cambiar
    el valor simulado del sensor)
"""

import json
import os
import random
import threading
import time

import paho.mqtt.client as mqtt

# --- Debe coincidir exactamente con el .ino real ---
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

TOPIC_MQ135 = "aq/aula-1/mq135"
TOPIC_VENT_SET = "aq/aula-1/vent/set"      # el ESP32 se suscribe acá
TOPIC_VENT_EST = "aq/aula-1/vent/estado"   # el ESP32 publica acá

SEND_INTERVAL = 4  # segundos, igual a SEND_INTERVAL del .ino (4000 ms)

UMBRAL_REGULAR = 700
UMBRAL_PELIGRO = 1500

# Valor base del sensor simulado. Se puede cambiar en caliente escribiendo
# un número en la consola mientras el script corre.
valor_base = 500
lock = threading.Lock()

# Estado del ventilador simulado, replicando las variables del .ino real
manual_mode = False
fan_on = False


def clasificar(val):
    if val <= UMBRAL_REGULAR:
        return "ambiente limpio"
    elif val <= UMBRAL_PELIGRO:
        return "ambiente regular"
    else:
        return "ambiente peligroso"


def publish_vent_status(client):
    """Replica publishVentStatus() del .ino: siempre manda fan_on + manual
    juntos, en JSON, tanto al arrancar como en cada cambio de estado."""
    payload = json.dumps({"fan_on": fan_on, "manual": manual_mode})
    client.publish(TOPIC_VENT_EST, payload)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[SIM] Conectado a {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(TOPIC_VENT_SET)
        # El .ino real avisa su estado real apenas arranca (automático + apagado)
        publish_vent_status(client)
    else:
        print(f"[SIM] Fallo de conexion, rc={rc}")


def on_message(client, userdata, msg):
    global manual_mode, fan_on

    if msg.topic != TOPIC_VENT_SET:
        return

    payload = msg.payload.decode(errors="replace")

    if payload == "ON":
        manual_mode = True
        fan_on = True
        print("[SIM] Ventilador -> ON (manual)")
        publish_vent_status(client)
    elif payload == "OFF":
        manual_mode = True
        fan_on = False
        print("[SIM] Ventilador -> OFF (manual)")
        publish_vent_status(client)
    elif payload == "AUTO":
        manual_mode = False
        print("[SIM] Modo AUTOMATICO reactivado")
        publish_vent_status(client)
    elif payload == "MANUAL":
        manual_mode = True
        print("[SIM] Modo MANUAL activado (sin cambiar el estado actual)")
        publish_vent_status(client)
    else:
        print(f"[SIM] Payload no reconocido en {msg.topic}: {payload}")


def loop_publicacion(client):
    global fan_on

    while True:
        with lock:
            base = valor_base
        val = max(0, min(4095, base + random.randint(-20, 20)))

        estado = clasificar(val)

        # Replica el comportamiento REAL y ya corregido del .ino: el
        # automático solo actúa si NO estamos en modo manual, y solo
        # enciende el ventilador con "ambiente peligroso" (rojo). Si el
        # usuario puso el modo manual, este bloque no toca fan_on para nada.
        if not manual_mode:
            fan_on = val > UMBRAL_PELIGRO
            publish_vent_status(client)

        payload = json.dumps({"g": val, "estado": estado})
        client.publish(TOPIC_MQ135, payload)
        print(f"[SIM] MQ135={val} -> {payload} (modo={'manual' if manual_mode else 'auto'}, fan_on={fan_on})")

        time.sleep(SEND_INTERVAL)


def leer_consola():
    global valor_base
    print("Escribi un numero (0-4095) y Enter para cambiar el valor simulado del sensor.")
    while True:
        try:
            entrada = input()
            nuevo = int(entrada)
            with lock:
                valor_base = max(0, min(4095, nuevo))
            print(f"[SIM] Nuevo valor base: {valor_base}")
        except ValueError:
            print("Ingresa un numero entero.")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    threading.Thread(target=loop_publicacion, args=(client,), daemon=True).start()
    threading.Thread(target=leer_consola, daemon=True).start()

    client.loop_forever()


if __name__ == "__main__":
    main()