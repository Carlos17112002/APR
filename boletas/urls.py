from django.urls import path
from .views import boletas_cliente_view, ver_boleta, pagar_boleta, descargar_boleta_pdf, confirmar_pago, ver_boleta_print

urlpatterns = [
    path('<slug:alias>/boletas/', boletas_cliente_view, name='panel_boletas'),
    path('<slug:alias>/boleta/<int:boleta_id>/ver/', ver_boleta, name='ver_boleta'),
    path('<slug:alias>/boleta/<int:boleta_id>/pagar/', pagar_boleta, name='pagar_boleta'),
    path('<slug:alias>/boleta/<int:boleta_id>/pdf/', descargar_boleta_pdf, name='descargar_boleta_pdf'),
    path('<slug:alias>/boleta/<int:boleta_id>/confirmar-pago/', confirmar_pago, name='confirmar_pago'),
    path('<slug:alias>/boleta/<int:boleta_id>/print/', ver_boleta_print, name='ver_boleta_print'),

]
