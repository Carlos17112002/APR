from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db.models import Sum, Avg
from datetime import date
from decimal import Decimal
from django.core.exceptions import FieldError

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
    db_alias = f'db_{slug}'                     # Base de datos de la empresa
    empresa = get_object_or_404(Empresa, slug=slug)

    # Obtener sectores (método de Empresa)
    sectores = empresa.sectores()  # Asegúrate de que este método existe

    # Obtener clientes desde la BD de la empresa
    clientes = Cliente.objects.using(db_alias).all()

    # Filtros (aplicados en la BD de la empresa)
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

    # Período actual en formato YYYY-MM
    hoy = timezone.now()
    periodo_actual = f"{hoy.year}-{hoy.month:02d}"

    # Obtener boletas del mes en la BD de la empresa
    boletas_del_mes = Boleta.objects.using(db_alias).filter(
        empresa_slug=empresa.slug,
        periodo=periodo_actual
    ).values('cliente_id', 'id')   # Obtenemos tanto el ID del cliente como el de la boleta

    # Crear diccionarios para acceso rápido
    clientes_con_boleta = {b['cliente_id']: b['id'] for b in boletas_del_mes}

    # Asignar atributos a cada cliente
    for cliente in clientes:
        if cliente.id in clientes_con_boleta:
            cliente.boleta_mes = True
            cliente.boleta_id = clientes_con_boleta[cliente.id]
        else:
            cliente.boleta_mes = False
            cliente.boleta_id = None

    # Calcular cantidad de clientes con email (estadística opcional)
    clientes_con_email = clientes.exclude(email='').count()

    context = {
        'empresa': empresa,
        'slug': slug,
        'clientes': clientes,
        'sectores': sectores,
        'clientes_con_email': clientes_con_email,  # para la tarjeta de estadísticas
    }
    return render(request, 'listado_clientes.html', context)

from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

from empresas.models import Empresa
from clientes.models import Cliente
from lecturas.models import LecturaMovil

def detalle_cliente(request, alias, cliente_id):
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa, slug=alias)
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)

    # Obtener lecturas del cliente desde la base de datos por defecto
    lecturas = LecturaMovil.objects.filter(
        empresa_slug=alias,
        cliente=cliente_id
    ).order_by('-fecha_lectura')

    # Obtener pagos (si existen)
    try:
        from pagos.models import Pago
        pagos = Pago.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    except ImportError:
        pagos = []

    # Estadísticas básicas
    consumo_promedio = lecturas.aggregate(Avg('consumo'))['consumo__avg'] or 0
    total_pagado = pagos.aggregate(Sum('monto'))['monto__sum'] or 0 if pagos else 0
    deuda_actual = 0  # Calcular según tu lógica

    # --- Datos para el gráfico de consumo ---
    rango = request.GET.get('rango', '6m')  # 6m, 1y, all
    hoy = timezone.now()

    # Determinar fecha de inicio según el rango
    if rango == '6m':
        fecha_inicio = hoy - timedelta(days=180)
    elif rango == '1y':
        fecha_inicio = hoy - timedelta(days=365)
    else:  # 'all' o cualquier otro
        fecha_inicio = None  # sin límite

    # Consulta base para el consumo agrupado por mes
    lecturas_historico = LecturaMovil.objects.filter(
        empresa_slug=alias,
        cliente=cliente_id,
        consumo__isnull=False
    )
    if fecha_inicio:
        lecturas_historico = lecturas_historico.filter(fecha_lectura__gte=fecha_inicio)

    # Agrupar por mes
    consumo_por_mes = lecturas_historico.annotate(
        mes=TruncMonth('fecha_lectura')
    ).values('mes').annotate(
        total_consumo=Sum('consumo')
    ).order_by('mes')

    # Construir listas para el gráfico
    meses_espanol = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    fechas_grafico = []
    consumos_grafico = []

    # Crear un diccionario con los consumos por mes (clave: 'YYYY-MM')
    consumo_dict = {}
    for item in consumo_por_mes:
        if item['mes']:
            key = item['mes'].strftime('%Y-%m')
            consumo_dict[key] = float(item['total_consumo'] or 0)

    # Determinar el rango de meses a mostrar
    if rango == 'all':
        # Si es 'all', usar todos los meses disponibles en consumo_dict, ordenados
        claves_ordenadas = sorted(consumo_dict.keys())
        fechas_grafico = [f"{meses_espanol[int(k[5:7])-1]} '{k[2:4]}" for k in claves_ordenadas]
        consumos_grafico = [consumo_dict[k] for k in claves_ordenadas]
    else:
        # Para rango '6m' o '1y', generamos los últimos N meses
        num_meses = 6 if rango == '6m' else 12
        for i in range(num_meses - 1, -1, -1):
            fecha = hoy - timedelta(days=30 * i)
            mes_num = fecha.month
            anio_num = fecha.year
            mes_nombre = meses_espanol[mes_num - 1]
            anio_corto = str(anio_num)[2:]
            fechas_grafico.append(f"{mes_nombre} '{anio_corto}")
            key = f"{anio_num}-{mes_num:02d}"
            consumos_grafico.append(consumo_dict.get(key, 0.0))

    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'lecturas': lecturas,
        'pagos': pagos,
        'consumo_promedio': consumo_promedio,
        'total_pagado': total_pagado,
        'deuda_actual': deuda_actual,
        # Para el gráfico
        'fechas_grafico': json.dumps(fechas_grafico),
        'consumos_grafico': json.dumps(consumos_grafico),
        'rango_seleccionado': rango,
    }
    return render(request, 'clientes/detalle_cliente.html', context)


def editar_cliente(request, alias, cliente_id):
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa, slug=alias)
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)

    # Obtener sectores disponibles (método que ya tienes en Empresa)
    sectores = empresa.sectores()  # Devuelve lista de strings

    # Definir el formulario dentro de la vista para poder pasarle los sectores
    from django import forms

    class ClienteForm(forms.ModelForm):
        # Convertir sector en un campo de selección
        sector = forms.ChoiceField(
            choices=[('', 'Seleccione un sector')] + [(s, s) for s in sectores],
            required=False,
            widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus'})
        )

        class Meta:
            model = Cliente
            fields = ['nombre', 'rut', 'direccion', 'telefono', 'email',
                      'medidor', 'sector', 'latitude', 'longitude']
            widgets = {
                'nombre': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus', 'placeholder': 'Nombre completo'}),
                'rut': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus', 'placeholder': '12.345.678-9'}),
                'direccion': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus'}),
                'telefono': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus'}),
                'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus'}),
                'medidor': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus'}),
                'latitude': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus', 'step': 'any'}),
                'longitude': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg input-focus', 'step': 'any'}),
            }

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            cliente_actualizado = form.save(commit=False)  # No guarda aún
            # Si quieres asegurar el slug de la empresa (opcional)
            cliente_actualizado.empresa_slug = alias
            cliente_actualizado.save(using=db_alias)       # Guarda en la BD correcta
            messages.success(request, f'Cliente {cliente.nombre} actualizado correctamente.')
            return redirect('detalle_cliente', alias=alias, cliente_id=cliente.id)
        else:
            # Si hay errores, mostrar mensaje
            messages.error(request, 'Por favor corrige los errores del formulario.')
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
    pagos, contratos y avisos (avisos generales de la empresa).
    """
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa, slug=alias)          # desde base default
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)

    # Importaciones condicionales con manejo de errores
    lecturas_completas = []
    pagos_completos = []
    contratos_completos = []
    avisos = []

    try:
        from lecturas.models import Lectura
        lecturas_completas = Lectura.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    except (ImportError, FieldError, Exception) as e:
        # Si no existe el modelo o el campo, dejar lista vacía
        logger.warning(f"Error al obtener lecturas: {e}")

    try:
        from pagos.models import Pago
        pagos_completos = Pago.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    except (ImportError, FieldError, Exception) as e:
        logger.warning(f"Error al obtener pagos: {e}")

    try:
        from contratos.models import Contrato
        contratos_completos = Contrato.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_inicio')
    except (ImportError, FieldError, Exception) as e:
        logger.warning(f"Error al obtener contratos: {e}")

    try:
        from avisos.models import Aviso
        # Suponiendo que Aviso tiene un campo 'empresa' (ForeignKey a Empresa)
        # y queremos mostrar avisos de la empresa (no específicos del cliente)
        avisos = Aviso.objects.using(db_alias).filter(empresa=empresa).order_by('-fecha_creacion')
    except (ImportError, FieldError, Exception) as e:
        logger.warning(f"Error al obtener avisos: {e}")
        # Si el campo es otro, intentar con 'empresa_id' o similar
        try:
            avisos = Aviso.objects.using(db_alias).filter(empresa_id=empresa.id).order_by('-fecha_creacion')
        except:
            avisos = []

    # Estadísticas (calcular solo si hay datos)
    consumo_total = 0
    pago_total = 0
    consumo_promedio = 0
    if lecturas_completas:
        consumo_total = lecturas_completas.aggregate(Sum('consumo'))['consumo__sum'] or 0
        consumo_promedio = lecturas_completas.aggregate(Avg('consumo'))['consumo__avg'] or 0
    if pagos_completos:
        pago_total = pagos_completos.aggregate(Sum('monto'))['monto__sum'] or 0

    total_registros = len(lecturas_completas) + len(pagos_completos) + len(contratos_completos) + len(avisos)

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
        'total_registros': total_registros,
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
    # Obtener empresa desde la base por defecto (Empresa está en BD principal)
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Determinar el alias de la base de datos de la empresa
    db_alias = f'db_{alias}'
    
    # Obtener el período actual (YYYY-MM)
    hoy = timezone.now()
    periodo_actual = f"{hoy.year}-{hoy.month:02d}"
    
    # Buscar la boleta en la base de datos de la empresa
    boleta = get_object_or_404(
        Boleta.objects.using(db_alias),
        empresa_slug=empresa.slug,
        cliente_id=cliente_id,
        periodo=periodo_actual
    )
    
    return render(request, 'boletas/detalle_boleta.html', {
        'boleta': boleta,
        'empresa': empresa,
        'slug': alias,  # opcional, para usar en templates
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

import csv
import logging
from datetime import date
from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import get_object_or_404
from empresas.models import Empresa
from clientes.models import Cliente

logger = logging.getLogger(__name__)

def exportar_clientes_csv(request, alias):
    try:
        db_alias = f'db_{alias}'
        empresa = get_object_or_404(Empresa, slug=alias)

        # Obtener clientes con los mismos filtros que en el listado
        clientes = Cliente.objects.using(db_alias).all()

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

        # Crear respuesta CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="clientes_{alias}_{date.today()}.csv"'

        writer = csv.writer(response)
        # Encabezados (sin fecha_creacion)
        writer.writerow(['ID', 'RUT', 'Nombre', 'Email', 'Teléfono', 'Dirección', 'Medidor', 'Sector', 'Latitud', 'Longitud'])

        for cliente in clientes:
            writer.writerow([
                cliente.id,
                cliente.rut or '',
                cliente.nombre or '',
                cliente.email or '',
                cliente.telefono or '',
                cliente.direccion or '',
                cliente.medidor or '',
                cliente.sector or '',
                cliente.latitude or '',
                cliente.longitude or '',
            ])

        return response
    except Exception as e:
        logger.error(f"Error exportando clientes para {alias}: {e}", exc_info=True)
        return HttpResponseServerError(f"Error interno: {e}")


def importar_clientes(request, alias):
    """
    Permite subir un archivo CSV para crear o actualizar clientes.
    """
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa, slug=alias)

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'Debe seleccionar un archivo CSV.')
            return redirect('importar_clientes', alias=alias)

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'El archivo debe ser CSV.')
            return redirect('importar_clientes', alias=alias)

        try:
            # Leer y decodificar el archivo
            data = csv_file.read().decode('utf-8')
            import io
            io_string = io.StringIO(data)
            reader = csv.reader(io_string, delimiter=',')
            next(reader)  # Saltar la fila de encabezados

            creados = 0
            actualizados = 0
            errores = []

            for fila_num, row in enumerate(reader, start=2):  # empezamos en línea 2 (después del header)
                # Esperamos el orden: RUT, Nombre, Email, Teléfono, Dirección, Medidor, Sector, Latitud, Longitud
                if len(row) < 3:  # Mínimo: RUT y Nombre
                    errores.append(f"Fila {fila_num}: datos insuficientes")
                    continue

                rut = row[0].strip()
                nombre = row[1].strip()
                email = row[2].strip() if len(row) > 2 else ''
                telefono = row[3].strip() if len(row) > 3 else ''
                direccion = row[4].strip() if len(row) > 4 else ''
                medidor = row[5].strip() if len(row) > 5 else ''
                sector = row[6].strip() if len(row) > 6 else ''
                latitud = row[7].strip() if len(row) > 7 else None
                longitud = row[8].strip() if len(row) > 8 else None

                if not rut:
                    errores.append(f"Fila {fila_num}: RUT vacío")
                    continue

                # Buscar o crear cliente
                cliente, created = Cliente.objects.using(db_alias).update_or_create(
                    rut=rut,
                    defaults={
                        'nombre': nombre,
                        'email': email,
                        'telefono': telefono,
                        'direccion': direccion,
                        'medidor': medidor,
                        'sector': sector,
                        'latitude': latitud if latitud else None,
                        'longitude': longitud if longitud else None,
                        'empresa_slug': alias,  # Importante para multiempresa
                    }
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

            # Mensajes de resultado
            messages.success(request, f'Importación completada: {creados} creados, {actualizados} actualizados.')
            if errores:
                messages.warning(request, f'Se encontraron {len(errores)} errores. Los primeros: {", ".join(errores[:3])}')

            return redirect('listado_clientes', alias=alias)

        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            return redirect('importar_clientes', alias=alias)

    # GET: mostrar formulario
    return render(request, 'importar_clientes.html', {
        'empresa': empresa,
        'slug': alias,
    })

from django.db import connections
from django.contrib.auth.decorators import login_required
import json

@login_required
def mapa_clientes(request, alias):
    """
    Muestra un mapa con la ubicación de todos los clientes de la empresa.
    """
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener clientes con coordenadas válidas
    clientes = Cliente.objects.using(db_alias).filter(
        latitude__isnull=False,
        longitude__isnull=False
    ).exclude(latitude=0, longitude=0)
    
    # Preparar datos para el mapa
    puntos = []
    for c in clientes:
        puntos.append({
            'id': c.id,
            'nombre': c.nombre,
            'rut': c.rut,
            'medidor': c.medidor,
            'direccion': c.direccion,
            'lat': float(c.latitude),
            'lng': float(c.longitude),
        })
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'puntos': json.dumps(puntos),
        'total_clientes': len(puntos),
    }
    return render(request, 'clientes/mapa_clientes.html', context)