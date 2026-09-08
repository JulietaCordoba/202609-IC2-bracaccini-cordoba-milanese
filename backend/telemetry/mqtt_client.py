import os, threading, time
import paho.mqtt.client as mqtt
import json, time
from influxdb import InfluxDBClient

INFLUX_URL = os.getenv("INFLUX_URL","http://127.0.0.1:8086")
INFLUX_HOST = INFLUX_URL.split("://")[-1].split(":")[0]
INFLUX_PORT = int(INFLUX_URL.split(":")[-1])
INFLUX_DB   = os.getenv("INFLUX_DB","calidadaire")
INFLUX_USER = os.getenv("INFLUX_USER") or None
INFLUX_PASS = os.getenv("INFLUX_PASS") or None

influx = InfluxDBClient(host=INFLUX_HOST, port=INFLUX_PORT,
                        username=INFLUX_USER, password=INFLUX_PASS,
                        database=INFLUX_DB, timeout=5, retries=1)

def _to_value(payload: bytes):
    s = payload.decode("utf-8","ignore").strip()
    try:
        if s.startswith("{"):
            o = json.loads(s)
            for k in ("gas", "g", "raw"):
                if k in o: return float(o[k])
            return None
        return float(s)
    except:
        return None

MQTT_HOST = os.getenv("MQTT_HOST","127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT","1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC","aq/aula-1/mq135")
MQTT_USERNAME = os.getenv("MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD") or None
MQTT_TLS = os.getenv("MQTT_TLS","0") == "1"

# --- Ventilación (control manual desde la web) ---
TOPIC_VENT_SET = os.getenv("TOPIC_VENT_SET", "aq/aula-1/vent/set")
TOPIC_VENT_ESTADO = os.getenv("TOPIC_VENT_ESTADO", "aq/aula-1/vent/estado")

# Último estado conocido del ventilador (se actualiza cuando el ESP32
# confirma por MQTT en TOPIC_VENT_ESTADO). "manual_mode" es optimista:
# se actualiza cuando el backend publica un comando, no cuando el ESP32
# lo confirma (el ESP32 no publica confirmación del modo, solo del ON/OFF).
fan_state = {"fan_on": None, "updated_at": None, "manual_mode": None}


def _on_connect(c, u, f, rc):
    print("MQTT conectado rc=", rc)
    c.subscribe(MQTT_TOPIC, qos=0)
    c.subscribe(TOPIC_VENT_ESTADO, qos=0)


def _on_message(c, u, msg):
    txt = msg.payload.decode("utf-8", "ignore")
    print(f"[MQTT] {msg.topic} -> {txt}")

    # Mensaje de confirmación de estado del ventilador
    if msg.topic == TOPIC_VENT_ESTADO:
        try:
            # Formato nuevo: {"fan_on": true/false, "manual": true/false}
            data = json.loads(txt)
            fan_state["fan_on"] = bool(data.get("fan_on"))
            fan_state["manual_mode"] = bool(data.get("manual"))
        except (json.JSONDecodeError, TypeError):
            # Compatibilidad con el formato viejo (solo "ON"/"OFF" en texto plano)
            fan_state["fan_on"] = (txt.strip().upper() == "ON")
        fan_state["updated_at"] = time.time()
        return

    # Mensaje de telemetría del sensor (comportamiento original)
    try:
        data = json.loads(txt)
    except Exception:
        print("[MQTT] payload no es JSON valido")
        return
    gas = data.get("g")
    # El firmware manda la clave "estado" (no "status"); soportamos ambas
    # por compatibilidad con versiones previas del backend.
    status = (data.get("status") or data.get("estado") or "").strip()
    try:
        gas = float(gas)
    except (TypeError, ValueError):
        print("[MQTT] valor gas invalido:", gas)
        return
    mapping = {
        "ambiente limpio": "ambiente_limpio",
        "ambiente_limpio": "ambiente_limpio",
        "ambiente regular": "ambiente_regular",
        "ambiente_regular": "ambiente_regular",
        "ambiente peligroso": "aire_peligroso",
        "aire peligroso": "aire_peligroso",
        "aire_peligroso": "aire_peligroso",
    }
    status = mapping.get(status, "desconocido")
    now_ns = int(time.time() * 1e9)
    point = [{
        "measurement": "mq135",
        "tags": {
            "device": "esp32-aula1",
            "status": status,
        },
        "time": now_ns,
        "fields": {
            "gas": gas
        }
    }]
    try:
        influx.write_points(point, time_precision='n')
    except Exception as e:
        print("Error Influx:", e)


def start_mqtt_thread():
    def run():
        while True:
            try:
                c = mqtt.Client()
                if MQTT_USERNAME:
                    c.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
                if MQTT_TLS:
                    c.tls_set()  # usa CAs del sistema si TLS=1
                c.on_connect = _on_connect
                c.on_message = _on_message
                c.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
                c.loop_forever()
            except Exception as e:
                print("MQTT error:", e)
                time.sleep(2)
    threading.Thread(target=run, daemon=True).start()


def _publish_vent_command(payload: str):
    """Publica un comando crudo (ON / OFF / AUTO) en el tópico de control
    del ventilador. Usa un cliente MQTT efímero (se conecta, publica, se
    desconecta)."""
    client = mqtt.Client()
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    if MQTT_TLS:
        client.tls_set()
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.publish(TOPIC_VENT_SET, payload)
    client.disconnect()
    return payload


def publish_fan_command(turn_on: bool):
    """Publica ON u OFF (modo manual)."""
    payload = "ON" if turn_on else "OFF"
    _publish_vent_command(payload)
    fan_state["manual_mode"] = True
    return payload


def publish_fan_auto():
    """Publica AUTO: le devuelve al ESP32 el control automático del
    ventilador según la lectura del sensor."""
    _publish_vent_command("AUTO")
    fan_state["manual_mode"] = False
    return "AUTO"


def publish_fan_manual():
    """Publica MANUAL: cambia a modo manual sin tocar el estado actual
    del relé (ni prende ni apaga, solo bloquea al automático)."""
    _publish_vent_command("MANUAL")
    fan_state["manual_mode"] = True
    return "MANUAL"

