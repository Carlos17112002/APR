from django.urls import path
from clientes import views
from clientes.views import perfil_cliente_view, listado_clientes, crear_cliente, login_cliente, logout_view, clientes_por_alias

urlpatterns = [
    path('<slug:alias>/crear/', crear_cliente, name='crear_cliente'),
    path('<slug:alias>/perfil/', perfil_cliente_view, name='perfil_cliente'),
    path('listado/<slug:alias>/', listado_clientes, name='listado_clientes'),
    path('login/', login_cliente, name='login_cliente'),
    path('logout/', logout_view, name='logout'),
    path('<slug:alias>/lecturas/ruta/', clientes_por_alias, name='lecturas_ruta'),
    path('<slug:alias>/clientes/<int:cliente_id>/', views.detalle_cliente, name='detalle_cliente'),
    path('<slug:alias>/clientes/<int:cliente_id>/editar/', views.editar_cliente, name='editar_cliente'),
    path('<slug:alias>/clientes/<int:cliente_id>/eliminar/', views.eliminar_cliente, name='eliminar_cliente'),
    path('<slug:alias>/clientes/<int:cliente_id>/historial/', views.historial_cliente, name='historial_cliente'),
    
]

