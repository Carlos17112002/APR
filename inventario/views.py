from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from .models import ItemInventario
from empresas.models import Empresa  # ✅ Correcto


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from empresas.models import Empresa
from inventario.models import ItemInventario
from empresas.models import PerfilAdmin  # Ajusta la ruta según tu proyecto
 # Ajusta la ruta según tu proyecto

@login_required
def inventario_view(request, slug):
    empresa = get_object_or_404(Empresa, slug=slug)

    # Verificar permiso de inventario para esta empresa
    try:
        perfil = PerfilAdmin.objects.get(usuario=request.user)
    except PerfilAdmin.DoesNotExist:
        return HttpResponseForbidden("No tienes un perfil de administrador configurado.")

    if not perfil.tiene_permiso(empresa.slug, 'inventario'):
        return HttpResponseForbidden("No tienes permiso para acceder al inventario de esta empresa.")

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        cantidad = request.POST.get('cantidad')
        categoria = request.POST.get('categoria')

        if nombre and cantidad:
            ItemInventario.objects.create(
                empresa=empresa,
                nombre=nombre,
                cantidad=int(cantidad),
                categoria=categoria
            )
            return redirect('inventario', slug=slug)

    items = ItemInventario.objects.filter(empresa=empresa).order_by('-fecha_creacion')

    return render(request, 'inventario/inventario.html', {
        'empresa': empresa,
        'items': items,
        'slug': slug
    })
    
from django.shortcuts import render, redirect, get_object_or_404
from empresas.models import Empresa  # Ajustá si tu modelo está en otra app
from .models import ItemInventario

def agregar_item(request, slug):
    empresa = get_object_or_404(Empresa, slug=slug)

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        cantidad = request.POST.get('cantidad')
        categoria = request.POST.get('categoria')

        if nombre and cantidad:
            ItemInventario.objects.create(
                empresa=empresa,
                nombre=nombre,
                cantidad=int(cantidad),
                categoria=categoria
            )
        return redirect('inventario', slug=slug)

    # Si alguien accede por GET, redirigimos al inventario
    return redirect('inventario', slug=slug)
    
