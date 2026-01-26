from django.urls import path
from . import views

app_name = 'apps_moviles'

urlpatterns = [
    # Panel principal
    path('', views.panel_apps_moviles, name='panel_apps_moviles'),
    
    # Detalle de empresa
    path('empresa/<str:empresa_slug>/', views.detalle_app_empresa, name='detalle_app_empresa'),
    
    # Generar app
    path('empresa/<str:empresa_slug>/generar/', views.generar_app_empresa, name='generar_app_empresa'),
    
    # Gestionar dispositivos
    path('empresa/<str:empresa_slug>/dispositivos/', views.gestionar_dispositivos, name='gestionar_dispositivos'),
    
    # QR
    path('empresa/<str:empresa_slug>/qr/', views.ver_qr_app, name='ver_qr_app'),
    path('empresa/<str:empresa_slug>/qr/manual/', views.generar_qr_manual, name='generar_qr_manual'),
    
    # ===================================================================
    # APIS PARA LA APP MÓVIL (endpoints que escaneará el QR)
    # ===================================================================
    
    # API para descargar configuración completa (para empresas medianas)
    path('descargar-config/<str:empresa_slug>/', views.api_descargar_config, name='api_descargar_config'),
    
    # API para descargar clientes completos (para empresas medianas)
    path('descargar-clientes/<str:empresa_slug>/', views.descargar_clientes_completo, name='descargar_clientes_completo'),
    
    # API para descargar segmentos (para empresas grandes)
    path('descargar-segmento/<str:empresa_slug>/', views.descargar_clientes_segmento, name='descargar_clientes_segmento'),
    
    # API para config grande (solo metadata, para empresas grandes)
    path('config-grande/<str:empresa_slug>/', views.descargar_config_grande, name='descargar_config_grande'),
    
    # ===================================================================
    # APIS PÚBLICAS (sin auth, para la app móvil)
    # ===================================================================
    
    # API pública para la app móvil (verifica token en sesión)
    path('api/config/<str:empresa_slug>/', views.api_descargar_config, name='api_publica_config'),
    
    # ===================================================================
    # DEBUG
    # ===================================================================
    
    path('debug-config/<str:empresa_slug>/', views.debug_config_json, name='debug_config'),
    path('ver-config/<str:empresa_slug>/', views.ver_config_app, name='ver_config_app'),
    
    # Preview de JSON generado
    path('preview/<str:empresa_slug>/', views.ver_config_app, name='preview_config'),
]