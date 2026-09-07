from django.urls import path
from .views import (
    index,
    api_health,
    api_latest,
    api_query,
    api_statistics,
    api_devices,
    api_fan_status,
    api_fan_toggle,
    api_fan_auto,
)

urlpatterns = [
    path('', index, name='index'),
    path('api/health', api_health),
    path('api/latest', api_latest),
    path('api/query', api_query),
    path('api/statistics', api_statistics),
    path('api/devices', api_devices),
    path('api/fan', api_fan_status),
    path('api/fan/toggle', api_fan_toggle),
    path('api/fan/auto', api_fan_auto),
]