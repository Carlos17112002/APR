from django.urls import path
from . import views

urlpatterns = [
    path('crear/', views.crear_cliente, name='crear_cliente'),
    path('listado/', views.listado_clientes, name='listado_clientes'),
    path('<int:cliente_id>/', views.detalle_cliente, name='detalle_cliente'),
    path('<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('<int:cliente_id>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),
    path('<int:cliente_id>/historial/', views.historial_cliente, name='historial_cliente'),
    path('<int:cliente_id>/boleta/', views.ver_boleta_cliente, name='ver_boleta_cliente'),
    path('exportar/', views.exportarclientes_excel, name='exportar_clientes'),
    path('importar/', views.importar_clientes, name='importar_clientes'),
    path('mapa-clientes/', views.mapa_clientes, name='mapa_clientes'),
    path('pdf-contrato/<int:cliente_id>/', views.generar_pdf_contrato, name='pdf_contrato_cliente'),
    path('informe-contratos/', views.informe_contratos, name='informe_contratos_socios'),
    path('exportar-contratos-excel/', views.exportar_contratos_excel, name='exportar_contratos_excel'),
    path('informe-socios/', views.informe_socios, name='informe_socios_nuevo'),
    path('exportar-socios-excel/', views.exportar_socios_excel, name='exportar_socios_excel'),
    path('clientes/<int:cliente_id>/cambio-medidor/ajax/',views.registrar_cambio_medidor_ajax, name='registrar_cambio_medidor_ajax'),
]