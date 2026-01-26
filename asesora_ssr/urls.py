from django.contrib.auth import logout
from django.shortcuts import render, redirect
from empresas.models import Empresa
from clientes.models import Cliente
from django.urls import path, include
from django.contrib import admin
from .views import LoginView

def root_redirect(request):
    if not request.user.is_authenticated:
        return redirect('login_ssr')

    if request.user.is_superuser:
        return redirect('dashboard_admin_ssr')

    # 🏢 Si es admin de empresa
    empresa = Empresa.objects.filter(slug=request.user.username).first()
    if empresa:
        return redirect('panel_empresa', slug=empresa.slug)

    # 👤 Buscar al cliente en todas las bases multiempresa
    for empresa in Empresa.objects.all():
        alias_db = f'db_{empresa.slug}'
        try:
            cliente = Cliente.objects.using(alias_db).filter(usuario_id=request.user.id).first()
            if cliente:
                return redirect('perfil_cliente', alias=empresa.slug)
        except Exception:
            continue  # Si la base no existe o falla, seguimos

    # 🚫 Usuario válido pero sin rol asignado
    logout(request)
    return render(request, 'usuarios/sin_panel.html', {
        'mensaje': 'Tu cuenta no tiene acceso a ningún panel asignado.'
    })



urlpatterns = [
    path('admin/', admin.site.urls),
    path('empresas/', include('empresas.urls')),
    path('clientes/', include('clientes.urls')),
    path('login/', include('usuarios.urls')),
    path('', root_redirect),  # redirección inicial
    path('empresa/<slug:slug>/inventario/', include('inventario.urls')),  # ✅ conecta inventario con empresa
    path('empresa/<slug:slug>/avisos/', include('avisos.urls')),
    path('empresa/<slug:slug>/faq/', include('faq.urls')),
    path('empresa/<slug:slug>/cliente/', include('clientes.urls')),
    path('empresa/<slug:alias>/lecturas/', include('lecturas.urls')),
    path('boletas/', include('boletas.urls')),
    path('api/login/', LoginView.as_view(), name='login'),
    path('empresa/', include('clientes.urls')),
    path('contabilidad/', include('contabilidad.urls')),
    path('trabajadores/', include('trabajadores.urls')),
    path('informes/', include('informes.urls')),
    path('ssr-tools/', include('ssr_tools.urls')),  # 🔧 ssr_tools URLs
    path('', include('empresas.urls')),
    path('apps-moviles/', include('apps_moviles.urls')),






]
