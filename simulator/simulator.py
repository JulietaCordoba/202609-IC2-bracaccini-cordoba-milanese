import json
import random
import threading
import time

import paho.mqtt.client as mqtt

# --- Debe coincidir exactamente con el .ino real ---
MQTT_HOST = "192.168.1.62"
MQTT_PORT = 1883

TOPIC_MQ135 = "aq/aula-1/mq135"
TOPIC_VENT_SET = "aq/aula-1/vent/set"      # el ESP32 se suscribe aca
TOPIC_VENT_EST = "aq/aula-1/vent/estado"   # el ESP32 publica aca

SEND_INTERVAL = 10  # segundos, igual a SEND_INTERVAL del .ino

UMBRAL_REGULAR = 700
UMBRAL_PELIGRO = 1500

# Valor base del sensor simulado. Se puede cambiar en caliente escribiendo
# un numero en la consola mientras el script corre.
valor_base = 500
lock = threading.Lock()


def clasificar(val):
    if val <= UMBRAL_REGULAR:
        return "ambiente limpio", False
    elif val <= UMBRAL_PELIGRO:
        return "ambiente regular", True
    else:
        return "ambiente peligroso", True


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[SIM] Conectado a {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(TOPIC_VENT_SET)
    else:
        print(f"[SIM] Fallo de conexion, rc={rc}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="replace")
    if msg.topic != TOPIC_VENT_SET:
        return
    if payload == "ON":
        client.publish(TOPIC_VENT_EST, "ON")
        print("[SIM] Ventilador -> ON (manual)")
    elif payload == "OFF":
        client.publish(TOPIC_VENT_EST, "OFF")
        print("[SIM] Ventilador -> OFF (manual)")
    else:
        print(f"[SIM] Payload no reconocido en {msg.topic}: {payload}")


def loop_publicacion(client):
    while True:
        with lock:
            base = valor_base
        val = max(0, min(4095, base + random.randint(-20, 20)))

        estado, quiere_ventilador_on = clasificar(val)

        # Replica el comportamiento REAL del .ino: cada ciclo automatico
        # vuelve a escribir el relay segun el sensor, aunque haya habido
        # una orden manual reciente (bug conocido, documentado en el informe).
        client.publish(TOPIC_VENT_EST, "ON" if quiere_ventilador_on else "OFF")

        payload = json.dumps({"g": val, "estado": estado})
        client.publish(TOPIC_MQ135, payload)
        print(f"[SIM] MQ135={val} -> {payload}")

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
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    threading.Thread(target=loop_publicacion, args=(client,), daemon=True).start()
    threading.Thread(target=leer_consola, daemon=True).start()

    client.loop_forever()


if __name__ == "__main__":
    main()