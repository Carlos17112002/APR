from django.urls import path
from . import views

urlpatterns = [
    path('<slug:alias>/compras/', views.lista_compras, name='lista_compras'),
    path('<slug:alias>/ventas/', views.lista_ventas, name='lista_ventas'),
    path('<slug:alias>/libro/', views.panel_libro_sii, name='panel_libro_sii'),
    path('<slug:alias>/libro/exportar/', views.exportar_libro_sii, name='exportar_libro_sii'),
    path('<slug:alias>/libro/subir/', views.subir_libro_sii, name='subir_libro_sii'),
    path('<slug:alias>/libros/', views.lista_libros_sii, name='lista_libros_sii'),
    path('<slug:alias>/libro/<int:libro_id>/revisar/', views.revisar_libro_sii, name='revisar_libro_sii'),
    path('<slug:alias>/libro/<int:libro_id>/eliminar/', views.eliminar_libro_sii, name='eliminar_libro_sii'),
   
    

]
