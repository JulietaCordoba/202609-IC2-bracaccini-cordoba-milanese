from django.apps import AppConfig


class TelemetryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telemetry'
    def ready(self):
        from .mqtt_client import start_mqtt_thread
        start_mqtt_thread()
