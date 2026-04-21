from django.urls import path
from .views import inventario_view, agregar_item, reporte_inventario_excel

urlpatterns = [
    path('', inventario_view, name='inventario'),
    path('agregar/', agregar_item, name='agregar_item'),  # ✅ sin slug adicional
    path('reporte/', reporte_inventario_excel, name='reporte_inventario_excel'),
]
