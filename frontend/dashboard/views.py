from django.shortcuts import render

# Create your views here.
import os
import time
from urllib.parse import urlencode
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import requests

API_BASE = os.getenv("RASPBERRY_API_BASE", "http://192.168.1.62:8000").rstrip("/")

# --------- Página ----------
def index(request):
    return render(request, "dashboard/index.html")


# --------- Proxies GET a la Raspberry ----------
def _proxy_get(path, params=None):
    url = f"{API_BASE}{path}"
    try:
        r = requests.get(url, params=params, timeout=10)
        return HttpResponse(
            content=r.content,
            status=r.status_code,
            content_type=r.headers.get("Content-Type", "application/json"),
        )
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)

def api_health(request):
    return _proxy_get("/api/health")

def api_latest(request):
    return _proxy_get("/api/latest")

def api_query(request):
    # pasa los parámetros (p.ej. ?limit=50)
    return _proxy_get("/api/query", params=request.GET)

def api_statistics(request):
    return _proxy_get("/api/statistics")

def api_devices(request):
    return _proxy_get("/api/devices")


# --------- Control de ventilación (modalidad manual) ----------
#
# El estado real del relé lo administra el servicio de telemetría (airsrv)
# corriendo en la Raspberry Pi, que publica el comando en el broker MQTT
# para que el ESP32 accione el ventilador (ver sección 4.10 del informe).
#
# Como durante el desarrollo/demo no siempre hay un ESP32 y un relé físico
# conectados, este proxy intenta primero reenviar el comando al backend
# real; si ese backend no responde (por ejemplo, la Raspberry está
# apagada o el módulo de ventilación todavía no fue desplegado), cae a un
# estado simulado en memoria para que el botón siga siendo funcional
# durante la presentación.
_simulated_fan_state = {"fan_on": False, "updated_at": None, "manual_mode": True, "simulated": True}


def _proxy_post(path, json_body=None):
    url = f"{API_BASE}{path}"
    r = requests.post(url, json=json_body, timeout=10)
    return HttpResponse(
        content=r.content,
        status=r.status_code,
        content_type=r.headers.get("Content-Type", "application/json"),
    )


def api_fan_status(request):
    """Devuelve el estado actual del ventilador (real si la Raspberry responde,
    simulado en caso contrario)."""
    try:
        return _proxy_get("/api/fan")
    except requests.RequestException:
        pass
    return JsonResponse(_simulated_fan_state)


@csrf_exempt
@require_POST
def api_fan_toggle(request):
    """Activa/desactiva el ventilador desde la interfaz web (modo manual).

    Intenta primero reenviar la orden al servicio de telemetría de la
    Raspberry (que es quien realmente publica el comando MQTT hacia el
    ESP32). Si ese servicio no está disponible, actualiza el estado
    simulado para que la demo siga funcionando sin hardware conectado.
    """
    try:
        return _proxy_post("/api/fan/toggle")
    except requests.RequestException:
        pass

    _simulated_fan_state["fan_on"] = not _simulated_fan_state["fan_on"]
    _simulated_fan_state["updated_at"] = time.time()
    _simulated_fan_state["simulated"] = True
    return JsonResponse(_simulated_fan_state)


@csrf_exempt
@require_POST
def api_fan_auto(request):
    """Devuelve el control del ventilador al modo automático del ESP32."""
    try:
        return _proxy_post("/api/fan/auto")
    except requests.RequestException:
        pass

    _simulated_fan_state["fan_on"] = None
    _simulated_fan_state["manual_mode"] = False
    _simulated_fan_state["updated_at"] = time.time()
    _simulated_fan_state["simulated"] = True
    return JsonResponse(_simulated_fan_state)