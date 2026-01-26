from django.urls import path
from . import views, views_api



urlpatterns = [
    path('lecturas-app/', views.listado_lecturas_app, name='listado_lecturas_app'),
    path('generar-boletas/', views.generar_boletas_lote, name='generar_boletas_lote'),
    path('boletas/', views.listado_boletas, name='listado_boletas'),
    path('mapa-lecturas/', views.mapa_lecturas, name='mapa_lecturas'),
    path('lecturas/<uuid:lectura_id>/', views.detalle_lectura, name='detalle_lectura'),
    path('api/sincronizar/', views.api_sincronizar_lecturas, name='api_sincronizar_lecturas'),
    path('api/pendientes/', views.api_obtener_clientes_pendientes, name='api_clientes_pendientes'),
    path('api/movil/autenticar/', views_api.api_autenticar_dispositivo, name='api_autenticar_dispositivo'),
    path('api/movil/clientes/<uuid:token>/', views_api.api_obtener_clientes, name='api_obtener_clientes'),
    path('api/movil/enviar-lecturas/<uuid:token>/', views_api.api_enviar_lecturas, name='api_enviar_lecturas'),
    path('api/movil/lecturas-pendientes/<uuid:token>/', views_api.api_obtener_lecturas_pendientes, name='api_obtener_lecturas_pendientes'),
    path('clientes/<uuid:cliente_uuid>/', views_api.api_obtener_cliente_por_uuid, name='obtener-cliente-uuid'),
    path('cliente/<uuid:cliente_uuid>/', views_api.api_obtener_cliente_por_uuid, name='obtener-cliente-uuid'),
    path('<uuid:lectura_id>/', views.detalle_lectura, name='detalle_lectura'),
    path('<uuid:lectura_id>/calcular/', views.calcular_consumo, name='calcular_consumo'),
     path('api/<slug:alias>/dispositivos/login/', views.api_dispositivo_login, name='api_dispositivo_login'),
    path('api/<slug:alias>/descargar-app/', views.api_descargar_config_app, name='api_descargar_config_app'),
    
    # Datos
    path('api/<slug:alias>/sectores/', views.api_obtener_sectores, name='api_obtener_sectores'),
    path('api/<slug:alias>/sectores/<str:sector>/clientes/', views.api_obtener_clientes_por_sector, name='api_obtener_clientes_por_sector'),
    
    # Lecturas
    path('api/<slug:alias>/lecturas/guardar/', views.api_guardar_lectura, name='api_guardar_lectura'),
    path('api/<slug:alias>/lecturas/pendientes/', views.api_obtener_lecturas_pendientes, name='api_obtener_lecturas_pendientes'),
    path('api/<slug:alias>/lecturas/sincronizar/', views.api_sincronizar_lecturas_batch, name='api_sincronizar_lecturas_batch'),
    
    # Validación
    path('api/<slug:alias>/validar-gps/', views.api_validar_gps, name='api_validar_gps'),
    
    # Endpoints existentes (mantener compatibilidad)
    path('api/<slug:alias>/sincronizar/', views.api_sincronizar_lecturas, name='api_sincronizar_lecturas'),
    path('api/<slug:alias>/clientes-pendientes/', views.api_obtener_clientes_pendientes, name='api_obtener_clientes_pendientes'),

]
