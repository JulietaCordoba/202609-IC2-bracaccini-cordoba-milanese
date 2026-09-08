README
# Sistema de Monitoreo de Calidad del Aire Basado en IoT

## 1. Identificación

**Integrantes:**
- Agostina Bracaccini
- Julieta Córdoba
- Luisina Milanese

**Institución:** Universidad Nacional de Rafaela (UNRaf)
**Carrera:** Ingeniería en Computación
**Materia:** Ingeniería en Computación II (IC2)
**Año / Período:** Septiembre 2026

## 2. Descripción del Proyecto

El sistema tiene como objetivo el monitoreo continuo de la calidad del aire en espacios académicos cerrados (Aula 1) y la actuación sobre el ambiente mediante un sistema de ventilación. El dispositivo captura la concentración de gases contaminantes, transmite los registros a través de la red local, almacena el histórico en una base de datos de series temporales y visualiza los datos en tiempo real mediante un tablero web.

### Componentes Físicos

- **Microcontrolador:** ESP32 (con conectividad WiFi integrada).
- **Sensor de gas:** MQ-135 (sensible a amoníaco, óxidos de nitrógeno, humo y CO2, conectado a entrada analógica ADC).
- **Actuador:** Relay conectado a pin GPIO para accionar el ventilador (control manual y automático); LED indicador de calidad del aire (verde/amarillo/rojo).
- **Carcasa física:** Gabinete diseñado en Onshape e impreso en 3D para la sujeción y protección de la electrónica.

## 3. Arquitectura del Sistema

El sistema se organiza en cuatro capas desacopladas:

| Capa | Componente | Ejecución / Entorno | Responsabilidad |
|---|---|---|---|
| 1. Adquisición | Firmware ESP32 / `simulator.py` | Microcontrolador ESP32 o host local | Lee el sensor MQ-135, evalúa umbrales, conmuta el ventilador y publica telemetría por MQTT. |
| 2. Transporte | Broker MQTT (Eclipse Mosquitto) | Contenedor Docker | Broker de mensajería para distribución de telemetría y comandos de control. |
| 3. Procesamiento y Persistencia | Backend Django (`airsrv`/`telemetry`) e InfluxDB | Servidor / Raspberry Pi + Contenedor Docker | Suscriptor MQTT, procesa e ingesta mediciones en InfluxDB v1 y expone API REST. |
| 4. Presentación | Frontend Django (`airdash`/`dashboard`) | Navegador del cliente | Visualización de mediciones en tiempo real, histórico con gráficos y control manual/automático de ventilación. |

## 4. Contrato de Tópicos MQTT

Todos los tópicos usan QoS 0 (sin garantía de entrega adicional; suficiente para telemetría periódica y comandos idempotentes).

| Tópico | Publica | Se suscribe | Formato del payload | Descripción |
|---|---|---|---|---|
| `aq/aula-1/mq135` | ESP32 / `simulator.py` | Backend (`airsrv`) | JSON: `{"g": <int>, "estado": "<string>"}` | Telemetría del sensor. `g` es el valor analógico crudo (0-4095). `estado` es uno de: `"ambiente limpio"`, `"ambiente regular"`, `"ambiente peligroso"`. Se publica cada 4 segundos. |
| `aq/aula-1/vent/set` | Backend (`airsrv`) | ESP32 / `simulator.py` | Texto plano: `"ON"` \| `"OFF"` \| `"AUTO"` \| `"MANUAL"` | Comando de control del ventilador enviado desde la web. `ON`/`OFF` fuerzan el estado y activan el modo manual. `AUTO` devuelve el control al umbral automático del sensor. `MANUAL` cambia a modo manual sin alterar el estado actual del relé. |
| `aq/aula-1/vent/estado` | ESP32 / `simulator.py` | Backend (`airsrv`) | JSON: `{"fan_on": <bool>, "manual": <bool>}` | Confirmación del estado real del ventilador y del modo activo. Se publica en cada cambio de estado y una vez al arrancar, para que el backend/la web nunca queden con un dato desactualizado tras un reinicio. |

### Lógica de control del ventilador

- **Modo automático** (`manual: false`): el ESP32 enciende el ventilador únicamente cuando el sensor indica `"ambiente peligroso"` (umbral > 1500 en la escala 0-4095). Con `"ambiente limpio"` o `"ambiente regular"` el ventilador permanece apagado.
- **Modo manual** (`manual: true`): el usuario controla el ventilador directamente desde la web (`ON`/`OFF`); el bloque automático no interviene mientras este modo esté activo.
- Si el aire está en `"ambiente peligroso"` y el ventilador está apagado en modo manual, la interfaz web muestra una alerta visual — el sistema no fuerza el encendido automáticamente para respetar la decisión manual del usuario.

## 5. Stack Tecnológico y Dependencias

- **Firmware:** C++ / Arduino Core para ESP32.
  - `WiFi.h` (incluida en el core de ESP32)
  - `PubSubClient` (v2.8)
- **Broker MQTT:** Eclipse Mosquitto 2.0.18 (contenedor Docker, puerto 1883).
- **Base de Datos:** InfluxDB 1.11 (contenedor Docker, puerto 8086, base: `calidadaire`).
- **Backend** (`backend/`): Python 3.11, Django 5.2.7, paho-mqtt 2.1.0, influxdb 5.3.2, python-dotenv 1.1.1.
- **Frontend** (`frontend/`): Python 3.11, Django 5.2.7, requests 2.32.3, python-dotenv 1.0.1, Django Templates, HTML5, CSS3, JavaScript (Fetch API, Chart.js).
- **Simulador** (`simulator/`): Python 3.11, paho-mqtt 2.1.0.

## 6. Estructura del Repositorio

├── backend/ # Backend Django (airsrv): ingesta MQTT, InfluxDB y API REST
│ ├── airsrv/ # Configuración del proyecto Django (settings, urls)
│ │ └── .env.example # Plantilla de configuración MQTT/InfluxDB
│ ├── telemetry/ # App: cliente MQTT, endpoints REST, lógica de ventilación
│ ├── manage.py
│ └── requirements.txt
├── docs/ # Informe técnico formal en PDF
├── firmware/ # Código fuente para el microcontrolador ESP32
│ └── calidad_aire_esp32/
│ ├── calidad_aire_esp32.ino # Firmware Arduino/ESP32
│ └── config.h.example # Plantilla de credenciales WiFi y Broker
├── frontend/ # Aplicación web Django para visualización (airdash)
│ ├── airdash/ # Configuración del proyecto Django web
│ │ └── .env.example # Plantilla de configuración (URL del backend)
│ ├── dashboard/ # App frontend (vistas, templates y estáticos JS/CSS)
│ ├── manage.py
│ └── requirements.txt
├── mosquitto/
│ └── config/
│ └── mosquitto.conf # Configuración del broker para el contenedor Docker
├── simulator/ # Simulador de hardware para pruebas sin ESP32 físico
│ ├── simulator.py # Emulador MQTT del ESP32 y del sensor MQ-135
│ └── requirements.txt
├── docker-compose.yml # Levanta Mosquitto e InfluxDB con versiones fijas
├── .gitignore
└── README.md


## 7. Puesta en Marcha

### 7.1 Infraestructura (Mosquitto + InfluxDB)

Desde la raíz del repositorio:
```bash
docker compose up -d
```
Esto levanta Mosquitto (puerto 1883) e InfluxDB (puerto 8086) con las versiones fijadas en `docker-compose.yml`, ya configurados para aceptar conexiones desde la red local. La base de datos `calidadaire` se crea automáticamente al iniciar el contenedor.

Verificar que ambos estén corriendo:
```bash
docker compose ps
```

### 7.2 Backend (`backend/`)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp airsrv/.env.example airsrv/.env
# Editar airsrv/.env con la IP real del broker/InfluxDB si no es 127.0.0.1
python manage.py runserver 0.0.0.0:8000 --noreload
```
> El flag `--noreload` es necesario: sin él, el autorecargador de Django duplica el hilo de conexión MQTT.

### 7.3 Frontend (`frontend/`)

```bash
cd frontend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp airdash/.env.example airdash/.env
# Editar airdash/.env con la IP real del backend (RASPBERRY_API_BASE)
python manage.py runserver
```
Abrir `http://127.0.0.1:8000` en el navegador.

### 7.4 Simulador (sin hardware físico)

```bash
cd simulator
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python simulator.py
```
Mientras corre, se puede escribir un número (0-4095) + Enter en la consola para simular distintas lecturas del sensor y ver reaccionar el dashboard en tiempo real.

### 7.5 Firmware físico (ESP32, opcional)

1. Copiar `firmware/calidad_aire_esp32/config.h.example` como `config.h` en la misma carpeta.
2. Completar `WIFI_SSID`, `WIFI_PASS` y `MQTT_HOST` con los datos reales de la red.
3. Abrir `calidad_aire_esp32.ino` en el IDE de Arduino, seleccionar la placa ESP32 correcta y subir.

## 8. Placeholders de Credenciales

Ningún archivo con credenciales reales (`.env`, `config.h`) se sube al repositorio — están excluidos vía `.gitignore`. En su lugar, cada componente incluye una plantilla:

| Componente | Plantilla | Archivo real a crear |
|---|---|---|
| Backend | `backend/airsrv/.env.example` | `backend/airsrv/.env` |
| Frontend | `frontend/airdash/.env.example` | `frontend/airdash/.env` |
| Firmware | `firmware/calidad_aire_esp32/config.h.example` | `firmware/calidad_aire_esp32/config.h` |

## 9. Limitaciones Conocidas

- **Sin TLS en MQTT:** las comunicaciones con el broker no están cifradas (aceptable para una red local de laboratorio, no para producción).
- **Redes con aislamiento de clientes:** el sistema requiere que el ESP32, el broker y el backend puedan verse entre sí en la misma red local. Redes institucionales con aislamiento de clientes (común en WiFi de campus) pueden bloquear esta comunicación aunque todos los dispositivos estén conectados a la misma red. Se recomienda usar un hotspot dedicado para demostraciones fuera del entorno habitual.
- **Reloj del servidor sin batería de respaldo (RTC):** la Raspberry Pi utilizada no tiene reloj de hardware con batería. Sin acceso a internet para sincronizar por NTP, el reloj del sistema puede desviarse entre reinicios, afectando el cálculo de "última señal" del dispositivo en el dashboard. Se recomienda verificar la sincronización horaria (`timedatectl`) antes de cada demostración.
- **Polaridad del relé dependiente del módulo físico:** el nivel lógico que activa el relé (`RELAY_ON`/`RELAY_OFF` en el firmware) depende del módulo de relé específico utilizado. Si el ventilador queda invertido respecto a lo que indica la interfaz, hay que ajustar esas dos constantes en el `.ino`.
- **Calibración del sensor MQ-135:** los umbrales de clasificación (limpio/regular/peligroso) están definidos sobre el valor analógico crudo (ADC), no sobre una concentración calibrada en ppm. Sirven como referencia relativa, no como medición certificada de un gas específico.