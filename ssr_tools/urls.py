from django.urls import path
from . import views

urlpatterns = [
    path('<slug:alias>/reparar-entorno/', views.reparar_entorno, name='reparar_entorno'),
    path('<slug:alias>/ver-logs/', views.ver_logs_alias, name='ver_logs_alias'),
    path('<slug:alias>/validar-migraciones/', views.validar_migraciones, name='validar_migraciones'),
    path('<slug:alias>/exportar-datos/', views.exportar_datos, name='exportar_datos'),
]
