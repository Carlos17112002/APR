from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from empresas.models import Empresa
from inventario.models import ItemInventario
from empresas.decorators import permiso_requerido   # ✅ 导入正确

@login_required
@permiso_requerido('inventario')
def inventario_view(request, slug):
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

    items = ItemInventario.objects.filter(empresa=empresa).order_by('-fecha_creacion')

    return render(request, 'inventario/inventario.html', {
        'empresa': empresa,
        'items': items,
        'slug': slug
    })

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

    return redirect('inventario', slug=slug)