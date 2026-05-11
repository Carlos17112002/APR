from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from empresas.models import Empresa
from clientes.models import Cliente
from .views import LoginView

def root_redirect(request):
    """Redirección inicial según el tipo de usuario"""
    if not request.user.is_authenticated:
        return redirect('login_ssr')

    if request.user.is_superuser:
        return redirect('dashboard_admin_ssr')

    # Admin de empresa
    empresa = Empresa.objects.filter(slug=request.user.username).first()
    if empresa:
        return redirect('panel_empresa', slug=empresa.slug)

    # Cliente en bases multiempresa
    for empresa in Empresa.objects.all():
        alias_db = f'db_{empresa.slug}'
        try:
            cliente = Cliente.objects.using(alias_db).filter(usuario_id=request.user.id).first()
            if cliente:
                return redirect('perfil_cliente', alias=empresa.slug)
        except Exception:
            continue

    # Usuario sin rol
    logout(request)
    return render(request, 'usuarios/sin_panel.html', {
        'mensaje': 'Tu cuenta no tiene acceso a ningún panel asignado.'
    })

urlpatterns = [
    # Administración
    path('admin/', admin.site.urls),

    # Autenticación
    path('login/', include('usuarios.urls')),
    path('api/login/', LoginView.as_view(), name='login'),

    # Redirección raíz
    path('', root_redirect, name='root'),

    # Módulos con slug de empresa (deben tener rutas internas sin slug)
    path('empresa/<slug:alias>/clientes/', include('clientes.urls')),
    path('empresa/<slug:slug>/inventario/', include('inventario.urls')),
    path('empresa/<slug:slug>/avisos/', include('avisos.urls')),
    path('empresa/<slug:slug>/faq/', include('faq.urls')),

    # Módulos que manejan su propio slug internamente (se incluyen sin prefijo)
    path('lecturas/', include('lecturas.urls')),
    path('apps_moviles/', include('apps_moviles.urls')),
    path('apps/api/', include('apps_moviles.api_urls')),

    # Otros módulos sin dependencia de empresa
    path('empresas/', include('empresas.urls')),
    path('boletas/', include('boletas.urls')),
    path('contabilidad/', include('contabilidad.urls')),
    path('trabajadores/', include('trabajadores.urls')),
    # path('informes/', include('informes.urls')),
    path('ssr-tools/', include('ssr_tools.urls')),
]

# Archivos multimedia y estáticos en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)