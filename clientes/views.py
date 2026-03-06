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


from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from empresas.models import Empresa
from clientes.models import Cliente
from boletas.models import Boleta

def listado_clientes(request, alias):
    slug = alias
    alias_db = f'db_{slug}'
    empresa = get_object_or_404(Empresa, slug=slug)

    # Obtener sectores (suponiendo que empresa.sectores() es un método que devuelve lista)
    sectores = empresa.sectores()  # Asegúrate de que este método existe

    # Obtener clientes desde la base de datos de la empresa
    clientes = Cliente.objects.using(alias_db).all()

    # Filtros
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

    # Obtener mes y año actual
    hoy = timezone.now()
    mes_actual = hoy.month
    año_actual = hoy.year

    # Obtener IDs de clientes que tienen boleta en el mes actual (en la base por defecto)
    boletas_del_mes = Boleta.objects.filter(
        empresa_slug=empresa.slug,
        fecha_emision__year=año_actual,
        fecha_emision__month=mes_actual
    ).values_list('cliente_id', flat=True)

    # Convertir a set para búsqueda eficiente
    clientes_con_boleta = set(boletas_del_mes)

    # Añadir atributo a cada cliente
    for cliente in clientes:
        cliente.boleta_mes = cliente.id in clientes_con_boleta

    context = {
        'empresa': empresa,
        'slug': slug,
        'clientes': clientes,
        'sectores': sectores,
    }
    return render(request, 'listado_clientes.html', context)


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

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from boletas.models import Boleta
from empresas.models import Empresa

def ver_boleta_cliente(request, alias, cliente_id):
    empresa = get_object_or_404(Empresa, slug=alias)
    hoy = timezone.now()
    boleta = get_object_or_404(
        Boleta,
        empresa_slug=empresa.slug,
        cliente_id=cliente_id,
        fecha_emision__year=hoy.year,
        fecha_emision__month=hoy.month
    )
    # Aquí renderizas el template de la boleta (debes crearlo)
    return render(request, 'boletas/detalle_boleta.html', {
        'boleta': boleta,
        'empresa': empresa
    })

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from boletas.models import Boleta
from clientes.models import Cliente
from lecturas.models import LecturaMovil
from empresas.models import Empresa
from boletas.helpers import generar_boletas_por_alias  # si quieres usar la función masiva

def generar_boleta_individual(request, empresa_slug, cliente_id, lectura_id=None):
    """
    Genera una boleta para un cliente específico.
    Si se proporciona lectura_id, la asocia; si no, calcula con la última lectura.
    """
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    
    # Obtener cliente desde la base de datos de la empresa
    alias_db = f'db_{empresa_slug}'
    cliente = Cliente.objects.using(alias_db).get(id=cliente_id)
    
    # Si se proporciona lectura_id, verificar que exista
    lectura = None
    if lectura_id:
        lectura = LecturaMovil.objects.using(alias_db).get(id=lectura_id, cliente_id=cliente_id)
    
    # Verificar si ya existe una boleta para este período (mes actual)
    hoy = timezone.now()
    mes_actual = hoy.month
    año_actual = hoy.year
    periodo_str = f"{año_actual}-{mes_actual:02d}"
    
    # Buscar boleta existente (usando la base de datos default donde están las boletas)
    boleta_existente = Boleta.objects.filter(
        empresa_slug=empresa_slug,
        cliente_id=cliente_id,
        periodo=periodo_str
    ).first()
    
    if boleta_existente:
        messages.warning(request, f"Ya existe una boleta para {cliente.nombre} en el período {periodo_str}.")
        return redirect('ver_boleta', boleta_id=boleta_existente.id)
    
    # Calcular consumo
    # Si no hay lectura, usar la última lectura registrada
    if not lectura:
        # Obtener la última lectura (podrías tener un método en el modelo)
        lectura = LecturaMovil.objects.using(alias_db).filter(
            cliente_id=cliente_id
        ).order_by('-fecha_lectura').first()
        if not lectura:
            messages.error(request, "No hay lecturas para este cliente.")
            return redirect('listado_clientes', alias=empresa_slug)
    
    # Obtener lectura anterior (la penúltima)
    lectura_anterior = LecturaMovil.objects.using(alias_db).filter(
        cliente_id=cliente_id
    ).exclude(id=lectura.id).order_by('-fecha_lectura').first()
    
    valor_anterior = lectura_anterior.valor if lectura_anterior else 0
    valor_actual = lectura.valor
    consumo = valor_actual - valor_anterior
    if consumo < 0:
        consumo = 0  # o manejar reinicio de medidor
    
    # Calcular montos (esto debería estar en una función de negocio)
    tarifa_m3 = Decimal('500')  # ejemplo, debería venir de configuración
    cargo_fijo = Decimal('2000')
    monto_consumo = consumo * tarifa_m3
    total = monto_consumo + cargo_fijo
    
    # Crear boleta
    boleta = Boleta.objects.create(
        cliente_id=cliente_id,
        empresa_slug=empresa_slug,
        lectura_id=lectura.id,
        periodo=periodo_str,
        fecha_vencimiento=hoy.replace(day=10) + timezone.timedelta(days=30),  # ejemplo
        lectura_anterior=valor_anterior,
        lectura_actual=valor_actual,
        consumo=consumo,
        monto_consumo=monto_consumo,
        cargo_fijo=cargo_fijo,
        otros_cargos=0,
        total=total,
        estado='generada',
        codigo_barras='',  # generar si es necesario
    )
    
    messages.success(request, f"Boleta generada para {cliente.nombre} por ${total}.")
    return redirect('ver_boleta', boleta_id=boleta.id)