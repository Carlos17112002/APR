from django.urls import path
from . import views

urlpatterns = [
    # URLs principales de módulos
    path('<slug:alias>/libro/', views.panel_libro_sii, name='panel_libro_sii'),
    path('<slug:alias>/panel/', views.panel_remuneraciones, name='panel_remuneraciones'),
    path('<slug:alias>/afp/', views.panel_afp, name='panel_afp'),
    path('<slug:alias>/isapre/', views.panel_isapre, name='panel_isapre'),
    path('<slug:alias>/periodo/', views.panel_periodos, name='panel_periodos'),
    path('<slug:alias>/trabajadores/', views.panel_trabajadores, name='lista_trabajadores'),
    
    # URLs de Liquidaciones (corregidas y completas)
    path('<slug:alias>/liquidaciones/', views.panel_liquidaciones, name='panel_liquidaciones'),
    path('<slug:alias>/liquidacion/', views.lista_liquidaciones, name='lista_liquidacion'),  # Corregido
    
    
    # URLs de AFP
    path('<slug:alias>/afp/actualizar/', views.actualizar_cotizaciones, name='actualizar_cotizaciones'),
    path('<slug:alias>/afp/guardar/', views.guardar_cambios_afp, name='guardar_cambios_afp'),

    path('<slug:alias>/afp/datos/', views.obtener_datos_afp, name='obtener_datos_afp'),
    path('<slug:alias>/afp/actualizar/', views.actualizar_cotizacion, name='actualizar_cotizacion'),
    path('<slug:alias>/afp/agregar/', views.agregar_afp, name='agregar_afp'),
    path('<slug:alias>/afp/buscar/', views.buscar_afp, name='buscar_afp'),
    path('<slug:alias>/afp/eliminar/', views.eliminar_afp, name='eliminar_afp'),
    
    # URLs de Isapre
    path('<slug:alias>/isapres/actualizar/', views.actualizar_cotizacion_isapre, name='actualizar_cotizacion_isapre'),
    path('<slug:alias>/isapres/agregar/', views.agregar_isapre, name='agregar_isapre'),
    path('<slug:alias>/isapres/buscar/', views.buscar_isapre, name='buscar_isapre'),
    path('<slug:alias>/isapres/eliminar/', views.eliminar_isapre, name='eliminar_isapre'),
    path('<slug:alias>/isapres/actualizar-sii/', views.actualizar_desde_sii_isapre, name='actualizar_desde_sii_isapre'),
    
    # URLs de Períodos
    path('<slug:alias>/periodos/agregar/', views.agregar_periodo, name='agregar_periodo'),
    path('<slug:alias>/periodos/<int:periodo_id>/editar/', views.editar_periodo, name='editar_periodo'),
    path('<slug:alias>/periodos/<int:periodo_id>/eliminar/', views.eliminar_periodo, name='eliminar_periodo'),
    path('<slug:alias>/periodos/buscar/', views.buscar_periodos, name='buscar_periodos'),
    
    # URLs de Trabajadores
    path('<str:alias>/remuneraciones/trabajadores/buscar/', views.buscar_trabajadores_api, name='buscar_trabajadores_api'),
    path('<str:alias>/remuneraciones/trabajadores/agregar/', views.agregar_trabajador, name='agregar_trabajador'),
    path('<slug:alias>/liquidaciones/panel/', views.panel_liquidaciones, name='panel_liquidaciones_ajax'),  # Para AJAX
    path('<slug:alias>/liquidaciones/seleccionar-periodo/', views.seleccionar_periodo, name='seleccionar_periodo'),
    path('<slug:alias>/liquidaciones/cambiar-estado/', views.cambiar_estado_periodo, name='cambiar_estado_periodo'),
    path('<str:alias>/liquidaciones/generar/<int:periodo_id>/<int:trabajador_id>/', views.generar_liquidacion_individual, name='generar_liquidacion'),
    path('<slug:alias>/liquidaciones/guardar/', views.guardar_liquidacion, name='guardar_liquidacion'),
    path('<str:alias>/formatos/basico/', views.render_formato_basico, name='formato_basico'),
    path('<str:alias>/formatos/profesional/', views.render_formato_profesional, name='formato_profesional'),
    path('<str:alias>/formatos/detallado/', views.render_formato_detallado, name='formato_detallado'),
    path('<str:alias>/formatos/compacto/', views.render_formato_compacto, name='formato_compacto'),
    path('<str:alias>/trabajadores/editar/<int:trabajador_id>/', views.editar_trabajador, name='editar_trabajador'),

    path('<slug:alias>/centros-costo/', views.CentroCostoListView.as_view(), name='centro_costo_list'),
    path('<slug:alias>/centros-costo/nuevo/', views.CentroCostoCreateView.as_view(), name='centro_costo_create'),
    path('<slug:alias>/centros-costo/<int:pk>/editar/', views.CentroCostoUpdateView.as_view(), name='centro_costo_update'),
    path('<slug:alias>/centros-costo/<int:pk>/eliminar/', views.CentroCostoDeleteView.as_view(), name='centro_costo_delete'),
    path('<slug:alias>/liquidaciones/ver-pdf/<int:periodo_id>/<int:trabajador_id>/',views.ver_liquidacion_pdf,name='ver_liquidacion_pdf'),



]