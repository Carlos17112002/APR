# apps_moviles/api_urls.py
from django.urls import path
from . import api_views

urlpatterns = [
    # Endpoint principal de configuración
    path('config/<str:empresa_slug>/', api_views.api_config_app, name='api_config_app'),
    
    # Redireccionador de localhost a Render
    path('redirect/<str:empresa_slug>/', api_views.redirect_to_public, name='redirect_to_public'),
    
    # Endpoints de datos
    path('clientes/<str:empresa_slug>/', api_views.api_clientes, name='api_clientes'),
    path('segmentos/<str:empresa_slug>/', api_views.api_segmentos, name='api_segmentos'),
    
    # Endpoints de operaciones
    path('verificar/', api_views.verificar_conexion, name='api_verificar_conexion'),
    path('registrar-dispositivo/', api_views.registrar_dispositivo, name='api_registrar_dispositivo'),
    path('subir-lecturas/', api_views.subir_lecturas, name='api_subir_lecturas'),
    path('sincronizar/<str:empresa_slug>/', api_views.sincronizar_datos, name='api_sincronizar_datos'),
    
    # Endpoints de utilidad
    path('test/', api_views.api_test_simple, name='api_test_simple'),
    path('debug/', api_views.debug_info, name='api_debug'),
    path('diagnostic/', api_views.public_diagnostic, name='api_public_diagnostic'),
]