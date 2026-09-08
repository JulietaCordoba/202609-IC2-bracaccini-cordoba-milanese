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

## 3. Arquitectura del Sistema

El sistema se organiza en cuatro capas desacopladas.

La **capa de adquisición** está compuesta por el firmware del ESP32 (o, alternativamente, por `simulator.py` cuando no se dispone del hardware físico), y se ejecuta directamente sobre el microcontrolador o sobre un host local. Es responsable de leer el sensor MQ-135, evaluar los umbrales de calidad del aire, conmutar el ventilador y publicar la telemetría por MQTT.

La **capa de transporte** está implementada mediante el broker MQTT Eclipse Mosquitto, desplegado en un contenedor Docker. Su responsabilidad es la de broker de mensajería, distribuyendo tanto la telemetría como los comandos de control entre los distintos componentes.

La **capa de procesamiento y persistencia** está formada por el backend Django (`airsrv`/`telemetry`) junto con InfluxDB, y puede ejecutarse en cualquier servidor (en este proyecto, una Raspberry Pi, aunque también puede correr en la misma máquina que el resto de los componentes). Se encarga de actuar como suscriptor MQTT, procesar e ingestar las mediciones en InfluxDB v1, y exponer una API REST.

La **capa de presentación** corresponde al frontend Django (`airdash`/`dashboard`), que se ejecuta en el navegador del cliente. Su responsabilidad es la visualización de las mediciones en tiempo real, la consulta del histórico mediante gráficos, y el control manual/automático del sistema de ventilación.

## 4. Contrato de Tópicos MQTT

Todos los tópicos usan QoS 0 (sin garantía de entrega adicional; suficiente para telemetría periódica y comandos idempotentes).

El tópico `aq/aula-1/mq135` es publicado por el ESP32 (o por `simulator.py`) y consumido por el backend (`airsrv`). Su payload es un JSON con la estructura `{"g": <int>, "estado": "<string>"}`, donde `g` es el valor analógico crudo del sensor (0-4095) y `estado` es uno de los siguientes valores: `"ambiente limpio"`, `"ambiente regular"` o `"ambiente peligroso"`. Este mensaje se publica cada 4 segundos y corresponde a la telemetría del sensor.

El tópico `aq/aula-1/vent/set` es publicado por el backend (`airsrv`) y consumido por el ESP32 (o por `simulator.py`). Su payload es texto plano, con alguno de los valores `"ON"`, `"OFF"`, `"AUTO"` o `"MANUAL"`, y representa el comando de control del ventilador enviado desde la web. Los comandos `ON`/`OFF` fuerzan el estado del relé y activan el modo manual; `AUTO` devuelve el control al umbral automático del sensor; `MANUAL` cambia a modo manual sin alterar el estado actual del relé.

El tópico `aq/aula-1/vent/estado` es publicado por el ESP32 (o por `simulator.py`) y consumido por el backend (`airsrv`). Su payload es un JSON con la estructura `{"fan_on": <bool>, "manual": <bool>}`, que confirma el estado real del ventilador y el modo activo. Se publica en cada cambio de estado y una vez al arrancar, para que el backend y la web nunca queden con un dato desactualizado tras un reinicio.

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

```
├── backend/                       # Backend Django (airsrv): ingesta MQTT, InfluxDB y API REST
│   ├── airsrv/                    # Configuración del proyecto Django (settings, urls)
│   │   └── .env.example           # Plantilla de configuración MQTT/InfluxDB
│   ├── telemetry/                 # App: cliente MQTT, endpoints REST, lógica de ventilación
│   ├── manage.py
│   └── requirements.txt
├── docs/                          # Informe técnico formal en PDF
├── firmware/                      # Código fuente para el microcontrolador ESP32
│   └── calidad_aire_esp32/
│       ├── calidad_aire_esp32.ino # Firmware Arduino/ESP32
│       └── config.h.example       # Plantilla de credenciales WiFi y Broker
├── frontend/                      # Aplicación web Django para visualización (airdash)
│   ├── airdash/                   # Configuración del proyecto Django web
│   │   └── .env.example           # Plantilla de configuración (URL del backend)
│   ├── dashboard/                 # App frontend (vistas, templates y estáticos JS/CSS)
│   ├── manage.py
│   └── requirements.txt
├── mosquitto/
│   └── config/
│       └── mosquitto.conf         # Configuración del broker para el contenedor Docker
├── simulator/                     # Simulador de hardware para pruebas sin ESP32 físico
│   ├── simulator.py               # Emulador MQTT del ESP32 y del sensor MQ-135
│   └── requirements.txt
├── docker-compose.yml             # Levanta Mosquitto e InfluxDB con versiones fijas
├── .gitignore
└── README.md
```

## 7. Puesta en Marcha

*No hace falta hardware físico para probar el sistema.* Los pasos 7.1 a 7.4 levantan todo el stack (broker, base de datos, backend, frontend y un simulador de sensor) en una sola máquina, sin necesidad de una Raspberry Pi, un ESP32 ni un sensor real. El paso 7.5 (firmware físico) es opcional, solo para quien tenga el hardware armado.

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

Ningún archivo con credenciales reales (`.env`, `config.h`) se sube al repositorio — están excluidos vía `.gitignore`. En su lugar, cada componente incluye una plantilla.

Para el **backend**, la plantilla es `backend/airsrv/.env.example`, a partir de la cual debe crearse el archivo real `backend/airsrv/.env`. Para el **frontend**, la plantilla es `frontend/airdash/.env.example`, a partir de la cual debe crearse `frontend/airdash/.env`. Para el **firmware**, la plantilla es `firmware/calidad_aire_esp32/config.h.example`, a partir de la cual debe crearse `firmware/calidad_aire_esp32/config.h`.

## 9. Limitaciones Conocidas

- **Sin TLS en MQTT:** las comunicaciones con el broker no están cifradas (aceptable para una red local de laboratorio, no para producción).
- **Redes con aislamiento de clientes:** el sistema requiere que el ESP32, el broker y el backend puedan verse entre sí en la misma red local. Redes institucionales con aislamiento de clientes (común en WiFi de campus) pueden bloquear esta comunicación aunque todos los dispositivos estén conectados a la misma red. Se recomienda usar un hotspot dedicado para demostraciones fuera del entorno habitual.
- **Reloj del servidor sin batería de respaldo (RTC):** la Raspberry Pi utilizada no tiene reloj de hardware con batería. Sin acceso a internet para sincronizar por NTP, el reloj del sistema puede desviarse entre reinicios, afectando el cálculo de "última señal" del dispositivo en el dashboard. Se recomienda verificar la sincronización horaria (`timedatectl`) antes de cada demostración.
- **Polaridad del relé dependiente del módulo físico:** el nivel lógico que activa el relé (`RELAY_ON`/`RELAY_OFF` en el firmware) depende del módulo de relé específico utilizado. Si el ventilador queda invertido respecto a lo que indica la interfaz, hay que ajustar esas dos constantes en el `.ino`.
- **Calibración del sensor MQ-135:** los umbrales de clasificación (limpio/regular/peligroso) están definidos sobre el valor analógico crudo (ADC), no sobre una concentración calibrada en ppm. Sirven como referencia relativa, no como medición certificada de un gas específico.