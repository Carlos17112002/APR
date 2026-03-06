from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from .models import Aviso
from empresas.models import Empresa

def avisos_view(request, slug):
    alias = f'db_{slug}'
    empresa = get_object_or_404(Empresa.objects.using(alias), alias=slug)

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        mensaje = request.POST.get('mensaje')
        activo = request.POST.get('activo') == 'on'

        if titulo and mensaje:
            Aviso.objects.using(alias).create(
                empresa=empresa,
                titulo=titulo,
                mensaje=mensaje,
                activo=activo
            )
        return redirect('avisos', slug=slug)

    avisos = Aviso.objects.using(alias).filter(empresa=empresa).order_by('-fecha_creacion')

    return render(request, 'avisos/avisos.html', {
        'empresa': empresa,
        'avisos': avisos,
        'slug': slug
    })


from django.shortcuts import render, get_object_or_404
from .models import Aviso
from empresas.models import Empresa

def avisos_activos_view(request, slug):
    alias = f'db_{slug}'
    empresa = get_object_or_404(Empresa.objects.using(alias), slug=slug)
    avisos = Aviso.objects.using(alias).filter(empresa=empresa, activo=True).order_by('-fecha_creacion')

    return render(request, 'avisos/avisos_activos.html', {
        'empresa': empresa,
        'avisos': avisos,
        'slug': slug
    })


from django.shortcuts import render, redirect, get_object_or_404
from .models import Aviso
from empresas.models import Empresa

def editar_aviso(request, slug, aviso_id):
    alias = f'db_{slug}'
    empresa = get_object_or_404(Empresa.objects.using(alias), slug=slug)
    aviso = get_object_or_404(Aviso.objects.using(alias), id=aviso_id, empresa=empresa)

    if request.method == 'POST':
        aviso.titulo = request.POST.get('titulo')
        aviso.mensaje = request.POST.get('mensaje')
        aviso.activo = request.POST.get('activo') == 'on'
        aviso.save(using=alias)
        return redirect('avisos_activos', slug=slug)

    return render(request, 'avisos/editar_aviso.html', {
        'empresa': empresa,
        'aviso': aviso,
        'slug': slug
    })

def eliminar_aviso(request, slug, aviso_id):
    alias = f'db_{slug}'
    empresa = get_object_or_404(Empresa.objects.using(alias), slug=slug)
    aviso = get_object_or_404(Aviso.objects.using(alias), id=aviso_id, empresa=empresa)

    if request.method == 'POST':
        aviso.delete(using=alias)
        return redirect('avisos_activos', slug=slug)

    return render(request, 'avisos/eliminar_aviso.html', {
        'empresa': empresa,
        'aviso': aviso,
        'slug': slug
    })