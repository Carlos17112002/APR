# apps_moviles/api_urls.py
from django.urls import path
from . import api_views  # Importaremos las vistas que crearemos

urlpatterns = [
    # Endpoint principal de configuración
    path('config/<str:empresa_slug>/', api_views.api_config_app, name='api_config_app'),
    
    # Endpoint para verificar conexión
    path('verificar/', api_views.verificar_conexion, name='api_verificar_conexion'),

    path('redirect/<str:empresa_slug>/', api_views.redirect_to_public, name='redirect_to_public'),

    path('verificar/', api_views.verificar_conexion, name='api_verificar_conexion'),
]