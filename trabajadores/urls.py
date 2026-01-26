# urls.py (app trabajadores)
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('<str:alias>/dashboard/', views.dashboard_trabajadores, name='dashboard_trabajadores'),
    
    # Contratos
    path('<str:alias>/contratos/', views.listado_contratos, name='listado_contratos'),
    path('<str:alias>/contratos/crear/', views.crear_contrato, name='crear_contrato'),
    path('<str:alias>/contratos/crear/<int:trabajador_id>/', views.crear_contrato, name='crear_contrato_con_trabajador'),
    path('<str:alias>/contrato/<int:id>/', views.ver_contrato_pdf, name='ver_contrato_pdf'),
    path('<str:alias>/contrato/<int:id>/editar/', views.editar_contrato, name='editar_contrato'),
    path('<str:alias>/contrato/<int:id>/eliminar/', views.eliminar_contrato, name='eliminar_contrato'),
    
    # Exportaciones y reportes
    path('<str:alias>/contratos/exportar/', views.exportar_contratos_excel, name='exportar_contratos'),
    path('<str:alias>/contratos/recordatorios/', views.recordatorios_vencimiento, name='recordatorios'),
    path('<str:alias>/contratos/reporte/', views.reporte_contratos, name='reporte_contratos'),
    
    # Finiquitos
    path('<str:alias>/finiquitos/', views.listado_finiquitos, name='listado_finiquitos'),
    path('<str:alias>/finiquitos/crear/', views.crear_finiquito, name='crear_finiquito'),
    path('<str:alias>/finiquito/<int:id>/', views.ver_finiquito_pdf, name='ver_finiquito_pdf'),
    
    # Liquidaciones
    path('<str:alias>/liquidaciones/', views.listado_liquidaciones, name='listado_liquidaciones'),
    path('<str:alias>/liquidaciones/crear/', views.crear_liquidacion, name='crear_liquidacion'),
    path('<str:alias>/liquidacion/<int:id>/', views.ver_liquidacion_pdf, name='ver_liquidacion_pdf'),
]