# admin_ssr/decorators.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from empresas.models import PerfilAdmin

def permiso_requerido(permiso):
    """
    Decorador para verificar que el usuario tenga un permiso específico
    para la empresa indicada por 'slug' o 'alias' en la URL.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # Obtener el slug/alias de los parámetros de la URL
            slug = kwargs.get('slug') or kwargs.get('alias')
            if not slug:
                raise ValueError("El decorador requiere un parámetro 'slug' o 'alias' en la URL")

            # Superuser tiene todos los permisos
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Verificar que el usuario tenga un perfil y el permiso
            try:
                perfil = PerfilAdmin.objects.get(usuario=request.user)
            except PerfilAdmin.DoesNotExist:
                messages.error(request, "No tienes un perfil de administrador configurado.")
                return redirect('dashboard_admin_ssr')  # o donde corresponda

            if not perfil.tiene_permiso(slug, permiso):
                messages.error(request, f"No tienes permiso para acceder a '{permiso}' en esta empresa.")
                return redirect('panel_empresa', slug=slug)  # redirigir al panel de la empresa

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator