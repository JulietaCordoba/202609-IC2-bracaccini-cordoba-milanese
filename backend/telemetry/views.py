from django.shortcuts import render
# Create your views here.
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from influxdb import InfluxDBClient
from . import mqtt_client
import os, time, datetime as dt
import os
# --- Influx config desde .env ---
INFLUX_URL = os.getenv("INFLUX_URL", "http://127.0.0.1:8086")
INFLUX_HOST = INFLUX_URL.split("://")[-1].split(":")[0]
INFLUX_PORT = int(INFLUX_URL.split(":")[-1])
INFLUX_DB   = os.getenv("INFLUX_DB", "calidadaire")
INFLUX_USER = os.getenv("INFLUX_USER") or None
INFLUX_PASS = os.getenv("INFLUX_PASS") or None
def _cli():
    return InfluxDBClient(
        host=INFLUX_HOST, port=INFLUX_PORT,
        username=INFLUX_USER, password=INFLUX_PASS,
        database=INFLUX_DB
    )
def health(request):
    return JsonResponse({"status": "ok"})
def statistics(request):
    limit = int(request.GET.get("limit","5000"))
    limit = max(100, min(5000, limit))
    cli = _cli()
    res = cli.query(f"SELECT * FROM mq135 ORDER BY time DESC LIMIT {limit}", epoch='ns')
    pts = list(res.get_points()) if res else []
    if not pts:
        return JsonResponse({"status":"ok","statistics":None,"hourly_average":[]})
    vals = [p["gas"] for p in pts if "gas" in p]
    avg = sum(vals)/len(vals)
    mx = max(vals); mn = min(vals)
    buckets = {}
    for p in pts:
        ts = int(p["time"])
        t  = dt.datetime.fromtimestamp(ts/1e9)
        k  = t.strftime("%H:00")
        buckets.setdefault(k,[]).append(p["gas"])
    hourly = [{"hour":k, "avg":(sum(v)/len(v) if v else 0)} for k,v in sorted(buckets.items())]
    status_counts = {}
    for p in pts:
        s = p.get("status") or "desconocido"
        status_counts[s] = status_counts.get(s, 0) + 1
    return JsonResponse({
        "status": "ok",
        "statistics": {
            "average": avg,
            "maximum": mx,
            "minimum": mn,
            "status_counts": status_counts
        },
        "hourly_average": hourly
    })
def devices(request):
    cli = _cli()
    res = cli.query("SELECT * FROM mq135 ORDER BY time DESC LIMIT 1", epoch='ns')
    pts = list(res.get_points()) if res else []
    if not pts:
        return JsonResponse({"status":"ok","devices":[]})
    p = pts[0]
    now_ns = int(time.time()*1e9)
    age = int(max(0, (now_ns - int(p["time"])) / 1e9))
    return JsonResponse({"status":"ok","devices":[{"id":"esp32-aula1","sensor":"MQ135","seconds_ago":age}]})
def latest(request):
    cli = _cli()
    # epoch='ns' => 'time' llega como entero en nanosegundos
    res = cli.query("SELECT * FROM mq135 ORDER BY time DESC LIMIT 1", epoch='ns')
    pts = list(res.get_points()) if res else []
    if not pts:
        return JsonResponse({"ts": None, "gas": None, "status": None})
    p = pts[0]
    return JsonResponse({
        "ts": int(p["time"]),
        "gas": p.get("gas"),
        "status": p.get("status")  
    })
def query(request):
    try:
        limit = int(request.GET.get("limit", "200"))
        limit = max(1, min(limit, 5000))
    except:
        limit = 200
    cli = _cli()
    res = cli.query(f"SELECT * FROM mq135 ORDER BY time DESC LIMIT {limit}", epoch='ns')
    pts = list(res.get_points()) if res else []
    data = [{
    "ts": int(p["time"]),
    "gas": p.get("gas"),
    "status": p.get("status")
    } for p in pts]
    return JsonResponse(list(reversed(data)), safe=False)
def index(request):
    return render(request, "telemetry/index.html")


def fan_status(request):
    return JsonResponse({
        "fan_on": mqtt_client.fan_state["fan_on"],
        "updated_at": mqtt_client.fan_state["updated_at"],
        "manual_mode": mqtt_client.fan_state["manual_mode"],
        "simulated": False,
    })


@csrf_exempt
@require_POST
def fan_toggle(request):
    # Si nunca se conoció el estado, arrancamos asumiendo que estaba apagado
    current = mqtt_client.fan_state["fan_on"]
    turn_on = not current if current is not None else True
    mqtt_client.publish_fan_command(turn_on)
    return JsonResponse({
        "fan_on": turn_on,
        "updated_at": None,   # se va a confirmar cuando el ESP32 responda por MQTT
        "manual_mode": True,
        "simulated": False,
        "pending_confirmation": True,
    })


@csrf_exempt
@require_POST
def fan_auto(request):
    mqtt_client.publish_fan_auto()
    return JsonResponse({
        "fan_on": None,   # el ESP32 decide solo; se va a confirmar por MQTT
        "updated_at": None,
        "manual_mode": False,
        "simulated": False,
        "pending_confirmation": True,
    })


@csrf_exempt
@require_POST
def fan_manual(request):
    mqtt_client.publish_fan_manual()
    return JsonResponse({
        "fan_on": mqtt_client.fan_state["fan_on"],  # no cambia, solo el modo
        "updated_at": None,
        "manual_mode": True,
        "simulated": False,
        "pending_confirmation": True,
    })
