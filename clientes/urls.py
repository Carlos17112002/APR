from django.urls import path
from clientes import views

urlpatterns = [
    # Crear cliente (sin usuario asociado)
    path('<slug:alias>/crear/', views.crear_cliente, name='crear_cliente'),

    # Listado de clientes
    path('listado/<slug:alias>/', views.listado_clientes, name='listado_clientes'),

    # Detalle de un cliente
    path('<slug:alias>/clientes/<int:cliente_id>/', views.detalle_cliente, name='detalle_cliente'),

    # Editar cliente
    path('<slug:alias>/clientes/<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),

    # Eliminar cliente
    path('<slug:alias>/clientes/<int:cliente_id>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),

    # Historial completo del cliente
    path('<slug:alias>/clientes/<int:cliente_id>/historial/', views.historial_cliente, name='historial_cliente'),

    # API para obtener clientes con coordenadas (para mapas)
    path('<slug:alias>/lecturas/ruta/', views.clientes_por_alias, name='lecturas_ruta'),

    
]