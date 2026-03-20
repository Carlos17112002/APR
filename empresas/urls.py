from django.urls import path
from empresas import views
from empresas.views import crear_admin_empresa, eliminar_empresa, generar_boletas_ssr, listado_empresas, agregar_pozo
from empresas.views import agregar_produccion, eliminar_pozo, editar_pozo
from .views import api_lecturas_mapa

urlpatterns = [
    path('admin_ssr/dashboard/', views.dashboard_admin_ssr, name='dashboard_admin_ssr'),
    path('admin_ssr/crear/', views.crear_empresa, name='crear_empresa'),
    path('<slug:slug>/panel_empresa/', views.panel_empresa, name='panel_empresa'),
    path('crear-admin/<slug:slug>/', crear_admin_empresa, name='crear_admin_empresa'),
    path('eliminar/<slug:slug>/', eliminar_empresa, name='eliminar_empresa'),
    path('empresas/<slug:slug>/generar-boletas/', generar_boletas_ssr, name='generar_boletas_ssr'),
    path('listado/', listado_empresas, name='listado_empresas'),
    path('api/lecturas-mapa/<slug:slug>/', api_lecturas_mapa, name='api_lecturas_mapa'),
    path('empresa/<str:empresa_slug>/api/sectores/', views.obtener_sectores_empresa, name='obtener_sectores_empresa'),
    path('agregar-pozo/<slug:empresa_slug>/', agregar_pozo, name='agregar_pozo'),
    path('agregar-produccion/<slug:slug>/', agregar_produccion, name='agregar_produccion'),
    path('api/datos-produccion-consumo/<slug:slug>/', views.datos_produccion_consumo_api, name='api_datos_produccion_consumo'),
    path('api/pozos/<slug:slug>/', views.api_pozos_empresa, name='api_pozos_empresa'),
    path('eliminar-pozo/<int:pozo_id>/', views.eliminar_pozo, name='eliminar_pozo'),
    path('api/pozo/<int:pozo_id>/', views.api_pozo_detalle, name='api_pozo_detalle'),
    path('editar-pozo/<int:pozo_id>/', views.editar_pozo_api, name='editar_pozo'),
    path('editar-pozo/<int:pozo_id>/', editar_pozo, name='editar_pozo'),
]
