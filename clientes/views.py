from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db.models import Sum, Avg
from datetime import date
from decimal import Decimal

from clientes.models import Cliente
from empresas.models import Empresa

# ============================================================================
# VISTAS PARA GESTIÓN DE CLIENTES (sin autenticación)
# ============================================================================

def crear_cliente(request, alias):
    """
    Crea un nuevo cliente en la base de datos de la empresa.
    (Sin creación de usuario en auth_user)
    """
    slug = alias
    alias_db = f'db_{slug}'
    empresa = Empresa.objects.get(slug=slug)          # desde base default
    sectores = empresa.sectores()
    error = None

    if request.method == 'POST':
        rut = request.POST.get('rut')
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        direccion = request.POST.get('direccion')
        medidor = request.POST.get('medidor')
        telefono = request.POST.get('telefono')
        sector = request.POST.get('sector')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        # Verificar si ya existe un cliente con el mismo RUT en la BD de la empresa
        if Cliente.objects.using(alias_db).filter(rut=rut).exists():
            error = 'Ya existe un cliente con ese RUT.'
        else:
            try:
                Cliente.objects.using(alias_db).create(
                    usuario_id=None,                     # Sin usuario asociado
                    empresa_slug=slug,
                    nombre=nombre,
                    rut=rut,
                    direccion=direccion,
                    medidor=medidor,
                    email=email,
                    telefono=telefono,
                    sector=sector,
                    latitude=latitude,
                    longitude=longitude,
                )
                messages.success(request, 'Cliente creado exitosamente.')
                return redirect('listado_clientes', alias=slug)
            except Exception as e:
                error = f'Error al registrar el cliente: {str(e)}'

    return render(request, 'crear_cliente.html', {
        'empresa': empresa,
        'slug': slug,
        'sectores': sectores,
        'error': error,
    })


def listado_clientes(request, alias):
    """
    Lista todos los clientes de una empresa, con filtros opcionales.
    """
    slug = alias
    alias_db = f'db_{slug}'
    empresa = Empresa.objects.get(slug=slug)          # desde base default
    sectores = empresa.sectores()

    clientes = Cliente.objects.using(alias_db).all()

    sector = request.GET.get('sector')
    rut = request.GET.get('rut')
    nombre = request.GET.get('nombre')

    if sector:
        clientes = clientes.filter(sector=sector)
    if rut:
        clientes = clientes.filter(rut__icontains=rut)
    if nombre:
        clientes = clientes.filter(nombre__icontains=nombre)

    clientes = clientes.order_by('nombre')

    return render(request, 'listado_clientes.html', {
        'empresa': empresa,
        'slug': slug,
        'clientes': clientes,
        'sectores': sectores,
    })


def detalle_cliente(request, alias, cliente_id):
    """
    Muestra el detalle completo de un cliente, incluyendo contratos,
    lecturas y pagos (si existen los modelos).
    """
    db_alias = f'db_{alias}'
    empresa = Empresa.objects.get(slug=alias)          # desde base default
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)

    # Importaciones condicionales para evitar errores si las apps no están instaladas
    try:
        from contratos.models import Contrato
        contratos = Contrato.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_inicio')
    except ImportError:
        contratos = []

    try:
        from lecturas.models import Lectura
        lecturas = Lectura.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')[:10]
    except ImportError:
        lecturas = []

    try:
        from pagos.models import Pago
        pagos = Pago.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')[:10]
    except ImportError:
        pagos = []

    # Estadísticas básicas
    consumo_promedio = 0
    total_pagado = 0
    if lecturas:
        consumo_promedio = lecturas.aggregate(Avg('consumo'))['consumo__avg'] or 0
    if pagos:
        total_pagado = pagos.aggregate(Sum('monto'))['monto__sum'] or 0

    # Deuda actual (si existe)
    deuda_actual = Decimal('0.00')

    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'contratos': contratos,
        'lecturas': lecturas,
        'pagos': pagos,
        'consumo_promedio': consumo_promedio,
        'total_pagado': total_pagado,
        'deuda_actual': deuda_actual,
        'hoy': date.today(),
    }

    return render(request, 'clientes/detalle_cliente.html', context)


def editar_cliente(request, alias, cliente_id):
    """
    Edita los datos de un cliente existente.
    (Requiere un formulario, aquí se muestra la estructura básica)
    """
    db_alias = f'db_{alias}'
    empresa = Empresa.objects.get(slug=alias)          # desde base default
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)

    # Si tienes un formulario definido (ej. ClienteForm), úsalo así:
    from django import forms
    class ClienteForm(forms.ModelForm):
        class Meta:
            model = Cliente
            fields = ['nombre', 'rut', 'direccion', 'telefono', 'email',
                      'medidor', 'sector', 'latitude', 'longitude']

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save(using=db_alias)
            messages.success(request, f'Cliente {cliente.nombre} actualizado.')
            return redirect('detalle_cliente', alias=alias, cliente_id=cliente.id)
    else:
        form = ClienteForm(instance=cliente)

    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'form': form,
    }

    return render(request, 'clientes/editar_cliente.html', context)


def historial_cliente(request, alias, cliente_id):
    """
    Muestra el historial completo del cliente: todas las lecturas,
    pagos, contratos y avisos.
    """
    db_alias = f'db_{alias}'
    empresa = Empresa.objects.get(slug=alias)          # desde base default
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)

    # Importaciones condicionales
    try:
        from lecturas.models import Lectura
        lecturas_completas = Lectura.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    except ImportError:
        lecturas_completas = []

    try:
        from pagos.models import Pago
        pagos_completos = Pago.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    except ImportError:
        pagos_completos = []

    try:
        from contratos.models import Contrato
        contratos_completos = Contrato.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_inicio')
    except ImportError:
        contratos_completos = []

    try:
        from avisos.models import Aviso
        avisos = Aviso.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_creacion')
    except ImportError:
        avisos = []

    # Estadísticas
    consumo_total = lecturas_completas.aggregate(Sum('consumo'))['consumo__sum'] or 0
    pago_total = pagos_completos.aggregate(Sum('monto'))['monto__sum'] or 0
    consumo_promedio = lecturas_completas.aggregate(Avg('consumo'))['consumo__avg'] or 0

    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'lecturas': lecturas_completas,
        'pagos': pagos_completos,
        'contratos': contratos_completos,
        'avisos': avisos,
        'consumo_total': consumo_total,
        'pago_total': pago_total,
        'consumo_promedio': consumo_promedio,
        'total_registros': len(lecturas_completas) + len(pagos_completos) + len(contratos_completos),
    }

    return render(request, 'clientes/historial_cliente.html', context)


@require_POST
@csrf_protect
def eliminar_cliente(request, alias, cliente_id):
    """
    Elimina un cliente de la base de datos de la empresa.
    Soporta peticiones AJAX y normales.
    """
    db_alias = f'db_{alias}'
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)
        cliente.delete()

        if is_ajax:
            return JsonResponse({'success': True, 'message': 'Cliente eliminado exitosamente.'})
        else:
            messages.success(request, f'Cliente {cliente.nombre} eliminado.')
            return redirect('listado_clientes', alias=alias)

    except Exception as e:
        if is_ajax:
            return JsonResponse({'success': False, 'error': str(e)})
        else:
            messages.error(request, f'Error al eliminar: {str(e)}')
            return redirect('listado_clientes', alias=alias)


def clientes_por_alias(request, alias):
    """
    API que devuelve los clientes con coordenadas (para mapas).
    """
    try:
        clientes = Cliente.objects.using(f'db_{alias}').exclude(latitude=None).exclude(longitude=None)
        data = list(clientes.values('id', 'nombre', 'direccion', 'latitude', 'longitude'))
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)