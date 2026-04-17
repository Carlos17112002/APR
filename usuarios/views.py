from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from clientes.models import Cliente
from empresas.models import Empresa
from empresas.models import PerfilAdmin  # Asegúrate de importar el modelo

def login_ssr(request):
    error = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            if remember_me:
                request.session.set_expiry(1209600)
            else:
                request.session.set_expiry(0)

            # Superusuario → Panel general SSR
            if user.is_superuser:
                return redirect('dashboard_admin_ssr')

            # Admin de empresa cuyo username coincide con el slug (compatibilidad)
            empresa = Empresa.objects.filter(slug=user.username).first()
            if empresa:
                return redirect('panel_empresa', slug=empresa.slug)

            # NUEVO: Admin con PerfilAdmin → redirige al primer panel donde tenga permisos
            try:
                perfil = PerfilAdmin.objects.get(usuario=user)
                # Iterar sobre las empresas para las que tiene permisos
                for slug_empresa, permisos in perfil.permisos.items():
                    if permisos:  # Si tiene al menos un permiso
                        empresa = Empresa.objects.filter(slug=slug_empresa).first()
                        if empresa:
                            return redirect('panel_empresa', slug=empresa.slug)
            except PerfilAdmin.DoesNotExist:
                pass  # No tiene perfil, continuar con la búsqueda de cliente

            # Cliente → Buscar en todas las bases multiempresa
            for empresa in Empresa.objects.all():
                alias_db = f'db_{empresa.slug}'
                try:
                    cliente = Cliente.objects.using(alias_db).filter(usuario_id=user.id).first()
                    if cliente:
                        return redirect('perfil_cliente', alias=empresa.slug)
                except Exception:
                    continue

            # Sin rol asignado
            error = 'Tu cuenta no tiene acceso a ningún panel asignado.'
        else:
            error = 'Credenciales inválidas. Intenta nuevamente.'

    return render(request, 'login.html', {'error': error})


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_ssr(request):
    logout(request)
    return redirect('login_ssr')

