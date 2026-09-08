"""
URL configuration for airsrv project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from telemetry.views import health, latest, query, index, statistics, devices, fan_status, fan_toggle, fan_auto, fan_manual




urlpatterns = [
    path('api/query', query),
    path('admin/', admin.site.urls),
    path('api/health', health, name='api-health'),
    path('api/latest', latest, name='api-latest'),
    path('api/query', query, name='api-query'),
    path('api/statistics', statistics, name='api-statistics'),
    path('api/devices', devices, name='api-devices'),
    path('api/fan', fan_status, name='api-fan'),
    path('api/fan/toggle', fan_toggle, name='api-fan-toggle'),
    path('api/fan/auto', fan_auto, name='api-fan-auto'), 
    path('api/fan/manual', fan_manual, name='api-fan-manual'),    
]

