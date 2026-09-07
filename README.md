# Sistema de Monitoreo de Calidad del Aire Basado en IoT

## 1. Identificación
* **Integrantes:** 
  * Agostina Bracaccini
  * Julieta Córdoba
  * Luisina Milanese
* **Institución:** Universidad Nacional de Rafaela (UNRaf)
* **Carrera:** Ingeniería en Computación
* **Materia:** Ingeniería en Computación II (IC2)
* **Año / Período:** Agosto / Septiembre 2026

---

## 2. Descripción del Proyecto
El sistema tiene como objetivo el monitoreo continuo de la calidad del aire en espacios académicos cerrados (Aula 1) y la actuación sobre el ambiente mediante un sistema de ventilación. 
El dispositivo captura la concentración de gases contaminantes, transmite los registros a través de la red local, almacena el histórico en una base de datos de series temporales y visualiza los datos en tiempo real mediante un tablero web.

### Componentes Físicos
* **Microcontrolador:** ESP32 (con conectividad WiFi integrada).
* **Sensor de gas:** MQ-135 (sensible a amoníaco, óxidos de nitrógeno, humo y CO2, conectado a entrada analógica ADC).
* **Actuador simulado:** LED testigo / Relay conectado a pin GPIO para simular el encendido y apagado del extractor/ventilador.
* **Carcasa física:** Gabinete diseñado en Onshape e impreso en 3D para la sujeción y protección de la electrónica.

---

## 3. Arquitectura del Sistema
El sistema se organiza en cuatro capas desacopladas:

| Capa | Componente | Ejecución / Entorno | Responsabilidad |
| :--- | :--- | :--- | :--- |
| **1. Adquisición** | Firmware ESP32 / `simulator.py` | Microcontrolador ESP32 o Host local | Lee el sensor MQ-135, evalúa umbrales, conmuta el ventilador y publica telemetría por MQTT. |
| **2. Transporte** | Broker MQTT (Eclipse Mosquitto) | Servidor / Raspberry Pi / Docker | Broker de mensajería para distribución de telemetría y comandos de control. |
| **3. Procesamiento y Persistencia** | Backend Django (`airsrv` / `telemetry`) e InfluxDB | Servidor / Raspberry Pi / Docker | Suscriptor MQTT, procesa e ingesta mediciones en InfluxDB v1 y expone API REST. |
| **4. Presentación** | Frontend Django (`airdash` / `dashboard`) | Navegador del cliente | Visualización de mediciones en tiempo real, histórico con gráficos y control manual de ventilación. |

---

## 4. Stack Tecnológico y Dependencias

* **Firmware:** C++ / Arduino Core para ESP32.
  * `WiFi.h` (v2.0.0+)
  * `PubSubClient` (v2.8.0)
  * `ArduinoJson` (v6.21.0+)
* **Broker MQTT:** Eclipse Mosquitto `v2.0.18` (puerto 1883).
* **Base de Datos:** InfluxDB `v1.8.10` (puerto 8086, base: `calidadaire`).
* **Backend:** Python `3.10+`, Django `4.2 LTS`, Django REST Framework `3.14.0`, `influxdb==5.3.1`, `paho-mqtt==1.6.1`.
* **Frontend:** Django Templates, HTML5, CSS3, JavaScript (Fetch API, Chart.js).
* **Simulador:** Python `3.10+`, `paho-mqtt==1.6.1`.

---

## 5. Estructura del Repositorio

```text
├── backend/                  # Backend Django (airsrv): ingesta MQTT, InfluxDB y API REST
├── docs/                     # Informe técnico formal en PDF (informe-ic2.pdf)
├── firmware/                 # Código fuente para el microcontrolador ESP32
│   └── calidad_aire_esp32/
│       ├── calidad_aire_esp32.ino   # Firmware Arduino/ESP32
│       └── config.h.example         # Plantilla de credenciales WiFi y Broker
├── frontend/                 # Aplicación web Django para visualización (airdash)
│   ├── airdash/              # Configuración del proyecto Django web
│   ├── dashboard/            # App frontend (vistas, templates y estáticos JS/CSS)
│   ├── manage.py
│   └── requirements.txt      # Dependencias fijas del frontend
├── simulator/                # Simulador de hardware para pruebas sin ESP32 físico
│   ├── simulator.py          # Emulador MQTT del ESP32 y del sensor MQ-135
│   └── requirements.txt      # Dependencias del simulador (paho-mqtt)
├── .gitignore                # Reglas de exclusión de Git (entornos virtuales, secretos, .env)
└── README.md                 # Documentación técnica principal del proyecto