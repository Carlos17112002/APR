# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Informes principales
    path('<str:alias>/informes/cargo-descuento/', 
         views.informe_cargo_descuento, name='informe_cargo_descuento'),
    path('<str:alias>/informes/cierre-caja/', 
         views.informe_cierre_caja, name='informe_cierre_caja'),
    path('<str:alias>/informes/contabilidad/', 
         views.informe_contabilidad, name='informe_contabilidad'),
    path('<str:alias>/informes/contratos/', 
         views.informe_contratos, name='informe_contratos'),
    path('<str:alias>/informes/convenios/', 
         views.informe_convenios, name='informe_convenios'),
    path('<str:alias>/informes/DAES/', 
         views.informe_DAES, name='informe_DAES'),
    path('<str:alias>/informes/deuda/', 
         views.informe_deuda, name='informe_deuda'),
    path('<str:alias>/informes/lecturas/', 
         views.informe_lecturas, name='informe_lecturas'),
    path('<str:alias>/informes/socios/', 
         views.informe_socios, name='informe_socios'),
    path('<str:alias>/informes/subsidios/', 
         views.informe_subsidios, name='informe_subsidios'),
    path('<str:alias>/informes/macromedidor/', 
         views.registro_macromedidor, name='registro_macromedidor'),
    
    # Exportaciones
    path('<str:alias>/informes/<str:tipo_informe>/pdf/', 
         views.exportar_pdf, name='exportar_informe_pdf'),
    path('<str:alias>/informes/<str:tipo_informe>/excel/', 
         views.exportar_excel, name='exportar_informe_excel'),
    path('<str:alias>/informes/<str:tipo_informe>/csv/', 
         views.exportar_csv, name='exportar_informe_csv'),
]