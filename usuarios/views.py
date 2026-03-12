from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from clientes.models import Cliente
from empresas.models import Empresa

def login_ssr(request):
    error = None

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')  # Captura el checkbox (será 'on' si está marcado)
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            # ⏱️ Aplicar recordar sesión
            if remember_me:
                # Si marcó "Recordar sesión", la sesión dura 2 semanas (en segundos)
                request.session.set_expiry(1209600)
            else:
                # Si no marcó, la sesión expira al cerrar el navegador
                request.session.set_expiry(0)

            # 🔐 Superusuario → Panel general SSR
            if user.is_superuser:
                return redirect('dashboard_admin_ssr')

            # 🏢 Admin de empresa → Panel por slug
            empresa = Empresa.objects.filter(slug=user.username).first()
            if empresa:
                return redirect('panel_empresa', slug=empresa.slug)

            # 👤 Cliente → Buscar en todas las bases multiempresa
            for empresa in Empresa.objects.all():
                alias_db = f'db_{empresa.slug}'
                try:
                    cliente = Cliente.objects.using(alias_db).filter(usuario_id=user.id).first()
                    if cliente:
                        return redirect('perfil_cliente', alias=empresa.slug)
                except Exception:
                    continue

            # 🚫 Usuario válido pero sin rol asignado
            error = 'Tu cuenta no tiene acceso a ningún panel asignado.'
            # Opcional: hacer logout automático si no tiene acceso
            # logout(request)
        else:
            error = 'Credenciales inválidas. Intenta nuevamente.'

    return render(request, 'login.html', {'error': error})


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_ssr(request):
    logout(request)
    return redirect('login_ssr')

