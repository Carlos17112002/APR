# admin_ssr/decorators.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from empresas.models import PerfilAdmin


def permiso_requerido(permiso):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # Obtener el slug desde la URL (puede llamarse 'slug' o 'alias')
            slug = kwargs.get('slug') or kwargs.get('alias')
            if not slug:
                raise ValueError("El decorador requiere 'slug' o 'alias' en la URL")

            # ✅ Los superusuarios tienen acceso total sin restricciones
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Para usuarios normales, verificar el perfil y los permisos
            try:
                perfil = PerfilAdmin.objects.get(usuario=request.user)
            except PerfilAdmin.DoesNotExist:
                messages.error(request, "No tienes un perfil de administrador configurado.")
                return redirect('panel_empresa', slug=slug)

            if not perfil.tiene_permiso(slug, permiso):
                messages.error(request, f"No tienes permiso para acceder a '{permiso}'.")
                return redirect('panel_empresa', slug=slug)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator