from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction, DatabaseError
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.utils.timezone import make_aware
from django.views.decorators.http import require_http_methods
from django.core.exceptions import FieldError
from django.contrib.auth.decorators import login_required

from boletas.models import Boleta
from .models import LecturaMovil
from empresas.models import Empresa
from clientes.models import Cliente
import json
from decimal import Decimal, InvalidOperation
import uuid
from datetime import datetime, timedelta
import calendar
import logging
from django.db import connection

# Configurar logger
logger = logging.getLogger(__name__)

# ========== VISTAS PARA WEB ==========

@login_required
def listado_lecturas_app(request, alias):
    """
    Vista para listar lecturas de la app móvil
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Verificar que el usuario tiene acceso a esta empresa
    if not request.user.is_superuser and empresa not in request.user.empresas.all():
        return render(request, '403.html', status=403)
    
    # Obtener filtros
    filtros = {
        'mes': request.GET.get('mes', 'all'),
        'anio': request.GET.get('anio', 'all'),
        'estado': request.GET.get('estado', ''),
        'usuario': request.GET.get('usuario', ''),
    }
    
    # Construir query
    query = Q(empresa=empresa)
    
    if filtros['mes'] != 'all':
        try:
            mes = int(filtros['mes'])
            query &= Q(fecha_lectura__month=mes)
        except:
            pass
    
    if filtros['anio'] != 'all':
        try:
            anio = int(filtros['anio'])
            query &= Q(fecha_lectura__year=anio)
        except:
            pass
    
    if filtros['estado']:
        query &= Q(estado=filtros['estado'])
    
    if filtros['usuario']:
        query &= Q(usuario_app__icontains=filtros['usuario'])
    
    # Obtener lecturas
    lecturas = LecturaMovil.objects.filter(query).order_by('-fecha_lectura', '-fecha_sincronizacion')
    
    # Estadísticas
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)
    
    lecturas_hoy = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_sincronizacion__date=hoy
    ).count()
    
    lecturas_mes = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_sincronizacion__date__gte=inicio_mes
    ).count()
    
    # Obtener usuarios únicos
    usuarios = LecturaMovil.objects.filter(
        empresa=empresa
    ).values_list('usuario_app', flat=True).distinct()
    
    # Obtener estados únicos para filtro
    estados_filtro = LecturaMovil.objects.filter(
        empresa=empresa
    ).values_list('estado', flat=True).distinct()
    
    # Obtener información de clientes desde la BD específica
    cliente_info = {}
    try:
        alias_db = f'db_{alias}'
        
        if alias_db in connection.settings_dict['DATABASES']:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT id, nombre, rut, medidor
                    FROM clientes_cliente 
                    WHERE empresa_slug = %s
                """, [alias])
                
                for row in cursor.fetchall():
                    cliente_id, nombre, rut, medidor = row
                    cliente_info[str(cliente_id)] = {
                        'nombre': nombre or f"Cliente {cliente_id}",
                        'rut': rut or "No especificado",
                        'medidor': medidor or "No especificado"
                    }
    except Exception as e:
        print(f"Error obteniendo info de clientes: {e}")
        cliente_info = {}
    
    # Añadir información del cliente a cada lectura
    lecturas_con_info = []
    for lectura in lecturas:
        cliente_valor = str(lectura.cliente)
        
        if cliente_valor in cliente_info:
            info_cliente = cliente_info[cliente_valor]
        else:
            info_cliente = {
                'nombre': f"Cliente ID: {lectura.cliente}",
                'rut': "Información no disponible",
                'medidor': "No disponible"
            }
        
        lecturas_con_info.append({
            'lectura': lectura,
            'cliente_info': info_cliente
        })
    
    # Opciones para filtros - MESES
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    # Obtener años disponibles - FORMA CORREGIDA
    try:
        # Opción 1: Usar annotate y values
        anios = LecturaMovil.objects.filter(
            empresa=empresa
        ).annotate(
            year=ExtractYear('fecha_lectura')
        ).values_list('year', flat=True).distinct().order_by('-year')
        
        anios = list(anios)
        
        # Si no hay años, usar el año actual
        if not anios:
            anios = [timezone.now().year]
    except Exception as e:
        print(f"Error obteniendo años: {e}")
        # Fallback: últimos 5 años
        current_year = timezone.now().year
        anios = list(range(current_year - 4, current_year + 1))
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'lecturas_con_info': lecturas_con_info,
        'lecturas_hoy': lecturas_hoy,
        'lecturas_mes': lecturas_mes,
        'usuarios': list(usuarios),
        'estados_filtro': estados_filtro,
        'filtros': filtros,
        'meses': meses,
        'anios': anios,
        'page_title': 'Lecturas App Móvil',
    }
    
    return render(request, 'lecturas/listado_lecturas.html', context)

@login_required
def generar_boletas_lote(request, alias):
    """
    Vista para generar boletas en lote a partir de lecturas - CORREGIDO: acepta 'alias'
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        alias_db = f'db_{alias}'
        
        # Obtener parámetros
        mes = request.POST.get('mes', timezone.now().month)
        anio = request.POST.get('anio', timezone.now().year)
        sector = request.POST.get('sector', '')
        
        # Validar que no hay boletas ya generadas para este período
        boletas_existentes = Boleta.objects.using(alias_db).filter(
            mes=mes,
            anio=anio,
            empresa=empresa
        ).count()
        
        if boletas_existentes > 0:
            return JsonResponse({
                'success': False,
                'error': f'Ya existen {boletas_existentes} boletas generadas para {mes}/{anio}'
            })
        
        # Obtener lecturas completadas para el período
        query = Q(empresa=empresa, mes=mes, anio=anio, estado='completada')
        if sector and sector != 'all':
            query &= Q(cliente__sector__nombre=sector)
        
        lecturas = LecturaMovil.objects.using(alias_db).filter(query).select_related('cliente')
        
        if not lecturas:
            return JsonResponse({
                'success': False,
                'error': f'No hay lecturas completadas para {mes}/{anio}'
            })
        
        boletas_generadas = 0
        boletas_con_error = []
        
        with transaction.atomic(using=alias_db):
            for lectura in lecturas:
                try:
                    # Verificar si ya existe boleta para este cliente en el período
                    boleta_existente = Boleta.objects.using(alias_db).filter(
                        cliente=lectura.cliente,
                        mes=mes,
                        anio=anio
                    ).exists()
                    
                    if boleta_existente:
                        boletas_con_error.append({
                            'cliente': lectura.cliente.nombre,
                            'error': 'Ya existe boleta para este período'
                        })
                        continue
                    
                    # Calcular consumo (buscar lectura anterior)
                    lectura_anterior = LecturaMovil.objects.using(alias_db).filter(
                        cliente=lectura.cliente,
                        estado='completada'
                    ).exclude(id=lectura.id).order_by('-fecha_lectura').first()
                    
                    consumo = lectura.lectura - (lectura_anterior.lectura if lectura_anterior else Decimal('0'))
                    
                    if consumo < 0:
                        consumo = Decimal('0')
                    
                    # Calcular monto (esto es un ejemplo, ajusta según tu lógica)
                    tarifa_base = Decimal('1500')  # Ejemplo
                    valor_m3 = Decimal('850')  # Ejemplo
                    monto_total = tarifa_base + (consumo * valor_m3)
                    
                    # Crear boleta
                    boleta = Boleta.objects.using(alias_db).create(
                        empresa=empresa,
                        cliente=lectura.cliente,
                        lectura=lectura,
                        mes=mes,
                        anio=anio,
                        consumo=consumo,
                        monto_total=monto_total,
                        tarifa_base=tarifa_base,
                        valor_m3=valor_m3,
                        fecha_emision=timezone.now().date(),
                        fecha_vencimiento=timezone.now().date() + timedelta(days=15),
                        estado='pendiente',
                        numero_boleta=f"B{anio}{mes:02d}{lectura.cliente.id:06d}"
                    )
                    
                    boletas_generadas += 1
                    
                except Exception as e:
                    logger.error(f"Error generando boleta para cliente {lectura.cliente.id}: {str(e)}")
                    boletas_con_error.append({
                        'cliente': lectura.cliente.nombre,
                        'error': str(e)
                    })
        
        # Registrar en log de la empresa
        logger.info(f"Generadas {boletas_generadas} boletas para empresa {empresa.nombre} ({mes}/{anio})")
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'mes': mes,
            'anio': anio,
            'boletas_generadas': boletas_generadas,
            'boletas_con_error': len(boletas_con_error),
            'detalle_errores': boletas_con_error,
            'mensaje': f'Se generaron {boletas_generadas} boletas exitosamente'
        })
        
    except Exception as e:
        logger.error(f"Error en generar_boletas_lote: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def listado_boletas(request, alias):
    """
    Vista para listar boletas generadas - CORREGIDO: acepta 'alias'
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    alias_db = f'db_{alias}'
    
    # Obtener boletas
    boletas = Boleta.objects.using(alias_db).select_related(
        'cliente', 'lectura', 'cliente__sector'
    ).filter(empresa=empresa).order_by('-fecha_emision')
    
    # Aplicar filtros
    estado = request.GET.get('estado')
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')
    sector = request.GET.get('sector')
    cliente = request.GET.get('cliente', '').strip()
    
    if estado and estado != 'all':
        boletas = boletas.filter(estado=estado)
    if mes and mes != 'all':
        boletas = boletas.filter(mes=mes)
    if anio and anio != 'all':
        boletas = boletas.filter(anio=anio)
    if sector and sector != 'all':
        boletas = boletas.filter(cliente__sector__nombre=sector)
    if cliente:
        boletas = boletas.filter(Q(cliente__nombre__icontains=cliente) | Q(cliente__rut__icontains=cliente))
    
    # Paginación
    paginator = Paginator(boletas, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    hoy = timezone.now().date()
    boletas_mes = boletas.filter(
        fecha_emision__month=hoy.month,
        fecha_emision__year=hoy.year
    )
    
    estadisticas = {
        'total': boletas_mes.count(),
        'pagadas': boletas_mes.filter(estado='pagada').count(),
        'pendientes': boletas_mes.filter(estado='pendiente').count(),
        'vencidas': boletas_mes.filter(estado='vencida').count(),
        'monto_total': float(boletas_mes.aggregate(Sum('monto_total'))['monto_total__sum'] or 0),
        'monto_pagado': float(boletas_mes.filter(estado='pagada').aggregate(Sum('monto_total'))['monto_total__sum'] or 0),
    }
    
    # Obtener sectores disponibles
    sectores = Cliente.objects.using(alias_db).filter(
        empresa=empresa,
        activo=True
    ).values_list('sector__nombre', flat=True).distinct().order_by('sector__nombre')
    
    # Obtener años disponibles
    anios_disponibles = Boleta.objects.using(alias_db).filter(
        empresa=empresa
    ).values_list('anio', flat=True).distinct().order_by('-anio')
    
    context = {
        'empresa': empresa,
        'slug': alias,  # Cambiado de empresa_slug a alias
        'page_obj': page_obj,
        'boletas': page_obj.object_list,
        'estados': Boleta.ESTADOS_BOLETA,
        'sectores': sectores,
        'anios': anios_disponibles,
        'meses': [
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        'estadisticas': estadisticas,
        'filtros': {
            'estado': estado or 'all',
            'mes': mes or 'all',
            'anio': anio or 'all',
            'sector': sector or 'all',
            'cliente': cliente,
        },
        'hoy': hoy,
    }
    
    return render(request, 'lecturas/listado_boletas.html', context)

@login_required
def detalle_lectura(request, alias, lectura_id):
    """
    Vista para ver el detalle de una lectura específica - CORREGIDO: acepta 'alias'
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    alias_db = f'db_{alias}'
    
    # NOTA: El modelo LecturaMovil está en la BD principal, no en la específica
    lectura = get_object_or_404(LecturaMovil.objects.select_related(
        'empresa'
    ), id=lectura_id, empresa=empresa)
    
    # Obtener información del cliente desde la BD específica
    cliente_info = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT nombre, rut, direccion, medidor 
                FROM clientes_cliente 
                WHERE id = %s AND empresa_slug = %s
            """, [lectura.cliente, alias])
            
            row = cursor.fetchone()
            if row:
                cliente_info = {
                    'nombre': row[0] or f"Cliente {lectura.cliente}",
                    'rut': row[1] or "No especificado",
                    'direccion': row[2] or "No especificada",
                    'medidor': row[3] or "No especificado"
                }
    except Exception as e:
        print(f"Error obteniendo info del cliente: {e}")
    
    # Obtener lecturas anteriores del mismo cliente (desde BD principal)
    lecturas_anteriores = LecturaMovil.objects.filter(
        empresa=empresa,
        cliente=lectura.cliente
    ).exclude(id=lectura_id).order_by('-fecha_lectura')[:5]
    
    # Obtener boleta relacionada si existe
    boleta_relacionada = None
    try:
        boleta_relacionada = Boleta.objects.filter(
            lectura=lectura
        ).first()
    except:
        pass
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'lectura': lectura,
        'cliente_info': cliente_info,
        'lecturas_anteriores': lecturas_anteriores,
        'boleta_relacionada': boleta_relacionada,
    }
    
    return render(request, 'lecturas/detalle_lectura.html', context)

@login_required
def estadisticas_lecturas(request, alias):
    """
    Vista para mostrar estadísticas de lecturas - CORREGIDO: acepta 'alias'
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Parámetros de tiempo
    mes = request.GET.get('mes', timezone.now().month)
    anio = request.GET.get('anio', timezone.now().year)
    periodo = request.GET.get('periodo', 'mensual')  # mensual, trimestral, anual
    
    # Obtener datos según período
    hoy = timezone.now().date()
    
    if periodo == 'mensual':
        fecha_inicio = datetime(int(anio), int(mes), 1).date()
        if int(mes) == 12:
            fecha_fin = datetime(int(anio) + 1, 1, 1).date() - timedelta(days=1)
        else:
            fecha_fin = datetime(int(anio), int(mes) + 1, 1).date() - timedelta(days=1)
    elif periodo == 'trimestral':
        trimestre = (int(mes) - 1) // 3 + 1
        mes_inicio = (trimestre - 1) * 3 + 1
        fecha_inicio = datetime(int(anio), mes_inicio, 1).date()
        fecha_fin = datetime(int(anio), mes_inicio + 3, 1).date() - timedelta(days=1)
    else:  # anual
        fecha_inicio = datetime(int(anio), 1, 1).date()
        fecha_fin = datetime(int(anio), 12, 31).date()
    
    # Consultar datos (desde BD principal)
    lecturas_periodo = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_lectura__date__range=[fecha_inicio, fecha_fin],
        estado='cargada'  # NOTA: Cambiado de 'completada' a 'cargada'
    )
    
    # Estadísticas generales
    total_lecturas = lecturas_periodo.count()
    lecturas_por_usuario = lecturas_periodo.values('usuario_app').annotate(
        total=Count('id')
    ).order_by('-total')
    
    # Obtener información de clientes por sector
    lecturas_por_sector = []
    try:
        alias_db = f'db_{alias}'
        if alias_db in connection.settings_dict['DATABASES']:
            with connection.cursor() as cursor:
                # Obtener clientes con lecturas en el período
                cursor.execute(f"""
                    SELECT cc.sector, COUNT(lm.id) as total
                    FROM lecturas_lecturamovil lm
                    INNER JOIN clientes_cliente cc ON lm.cliente = cc.id
                    WHERE lm.empresa_slug = %s 
                    AND lm.fecha_lectura BETWEEN %s AND %s
                    AND lm.estado = 'cargada'
                    GROUP BY cc.sector
                    ORDER BY total DESC
                """, [alias, fecha_inicio, fecha_fin])
                
                for row in cursor.fetchall():
                    lecturas_por_sector.append({
                        'sector': row[0] or 'Sin sector',
                        'total': row[1],
                        'porcentaje': (row[1] * 100.0 / total_lecturas) if total_lecturas > 0 else 0
                    })
    except Exception as e:
        print(f"Error obteniendo lecturas por sector: {e}")
    
    lecturas_por_dia = lecturas_periodo.values('fecha_lectura__date').annotate(
        total=Count('id')
    ).order_by('fecha_lectura__date')
    
    # Promedios
    promedio_diario = total_lecturas / ((fecha_fin - fecha_inicio).days + 1) if (fecha_fin - fecha_inicio).days > 0 else 0
    promedio_por_usuario = total_lecturas / lecturas_por_usuario.count() if lecturas_por_usuario.count() > 0 else 0
    
    # Obtener datos para gráficos
    dias = []
    lecturas_por_dia_list = []
    for item in lecturas_por_dia:
        dias.append(item['fecha_lectura__date'].strftime('%d/%m'))
        lecturas_por_dia_list.append(item['total'])
    
    sectores = []
    lecturas_por_sector_list = []
    for item in lecturas_por_sector:
        sectores.append(item['sector'])
        lecturas_por_sector_list.append(item['total'])
    
    usuarios = []
    lecturas_por_usuario_list = []
    for item in lecturas_por_usuario:
        if item['usuario_app']:
            usuarios.append(item['usuario_app'])
            lecturas_por_usuario_list.append(item['total'])
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'periodo': periodo,
        'mes': int(mes) if mes else hoy.month,
        'anio': int(anio) if anio else hoy.year,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'estadisticas': {
            'total_lecturas': total_lecturas,
            'promedio_diario': round(promedio_diario, 1),
            'promedio_por_usuario': round(promedio_por_usuario, 1),
            'usuarios_activos': lecturas_por_usuario.count(),
            'sectores_cubiertos': len(lecturas_por_sector),
        },
        'lecturas_por_usuario': list(lecturas_por_usuario),
        'lecturas_por_sector': lecturas_por_sector,
        'lecturas_por_dia': list(lecturas_por_dia),
        'datos_graficos': {
            'dias': json.dumps(dias),
            'lecturas_por_dia': json.dumps(lecturas_por_dia_list),
            'sectores': json.dumps(sectores),
            'lecturas_por_sector': json.dumps(lecturas_por_sector_list),
            'usuarios': json.dumps(usuarios),
            'lecturas_por_usuario': json.dumps(lecturas_por_usuario_list),
        },
        'meses': [
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        'anios': range(hoy.year - 5, hoy.year + 1),
        'periodos': [('mensual', 'Mensual'), ('trimestral', 'Trimestral'), ('anual', 'Anual')],
    }
    
    return render(request, 'lecturas/estadisticas_lecturas.html', context)

@login_required
def mapa_lecturas(request, alias):
    """
    Vista para mostrar lecturas en un mapa - CORREGIDO: acepta 'alias'
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener parámetros
    mes = request.GET.get('mes', timezone.now().month)
    anio = request.GET.get('anio', timezone.now().year)
    estado = request.GET.get('estado', 'cargada')
    
    # Obtener lecturas con coordenadas (desde BD principal)
    lecturas = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_lectura__month=mes,
        fecha_lectura__year=anio,
        estado=estado,
        latitud__isnull=False,
        longitud__isnull=False
    )
    
    # Preparar datos para el mapa
    puntos_mapa = []
    for lectura in lecturas:
        if lectura.latitud and lectura.longitud:
            puntos_mapa.append({
                'id': lectura.id,
                'nombre': f"Cliente {lectura.cliente}",
                'lat': float(lectura.latitud),
                'lng': float(lectura.longitud),
                'lectura': float(lectura.lectura_actual),
                'fecha': lectura.fecha_lectura.strftime('%d/%m/%Y'),
                'usuario': lectura.usuario_app,
                'estado': lectura.estado,
                'color': {
                    'cargada': 'green',
                    'pendiente': 'orange',
                    'procesada': 'blue'
                }.get(lectura.estado, 'gray')
            })
    
    # Obtener información de sectores
    lecturas_por_sector = []
    try:
        alias_db = f'db_{alias}'
        if alias_db in connection.settings_dict['DATABASES']:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT cc.sector, COUNT(lm.id) as total
                    FROM lecturas_lecturamovil lm
                    INNER JOIN clientes_cliente cc ON lm.cliente = cc.id
                    WHERE lm.empresa_slug = %s 
                    AND MONTH(lm.fecha_lectura) = %s 
                    AND YEAR(lm.fecha_lectura) = %s
                    AND lm.estado = %s
                    GROUP BY cc.sector
                    ORDER BY total DESC
                """, [alias, mes, anio, estado])
                
                for row in cursor.fetchall():
                    lecturas_por_sector.append({
                        'sector': row[0] or 'Sin sector',
                        'total': row[1]
                    })
    except Exception as e:
        print(f"Error obteniendo lecturas por sector: {e}")
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'puntos_mapa': json.dumps(puntos_mapa),
        'total_puntos': len(puntos_mapa),
        'lecturas_por_sector': lecturas_por_sector,
        'filtros': {
            'mes': mes,
            'anio': anio,
            'estado': estado,
        },
        'meses': [
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        'anios': range(timezone.now().year - 5, timezone.now().year + 1),
        'estados': ['cargada', 'pendiente', 'procesada'],
        'center_lat': -33.4489 if not puntos_mapa else puntos_mapa[0]['lat'] if puntos_mapa else -33.4489,
        'center_lng': -70.6693 if not puntos_mapa else puntos_mapa[0]['lng'] if puntos_mapa else -70.6693,
    }
    
    return render(request, 'lecturas/mapa_lecturas.html', context)

# ========== API PARA APP MÓVIL ==========

@csrf_exempt
@require_http_methods(["POST"])
def api_sincronizar_lecturas(request, alias):
    """
    API para sincronizar lecturas desde la app móvil - CORREGIDO: acepta 'alias'
    """
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Parsear datos
        try:
            data = json.loads(request.body)
            lecturas_data = data.get('lecturas', [])
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato JSON inválido'
            }, status=400)
        
        if not lecturas_data:
            return JsonResponse({
                'success': False,
                'error': 'No hay lecturas para sincronizar'
            }, status=400)
        
        lecturas_procesadas = []
        lecturas_con_error = []
        
        for lectura_data in lecturas_data:
            try:
                # Validar datos básicos
                cliente_id = lectura_data.get('cliente_id')
                lectura_valor = lectura_data.get('lectura_actual')
                
                if not cliente_id or not lectura_valor:
                    lecturas_con_error.append({
                        'cliente_id': cliente_id,
                        'error': 'Datos incompletos'
                    })
                    continue
                
                # Convertir lectura a Decimal
                try:
                    lectura_decimal = Decimal(str(lectura_valor))
                except (InvalidOperation, ValueError):
                    lecturas_con_error.append({
                        'cliente_id': cliente_id,
                        'error': 'Valor de lectura inválido'
                    })
                    continue
                
                # Crear nueva lectura en BD principal
                lectura_uuid = uuid.uuid4().hex
                
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO lecturas_lecturamovil 
                        (id, empresa_id, cliente, fecha_lectura, lectura_actual, 
                         latitud, longitud, estado, observaciones_app, usuario_app, 
                         empresa_slug, usada_para_boleta, fecha_sincronizacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, [
                        lectura_uuid,
                        empresa.id,
                        int(cliente_id),
                        timezone.now().date(),
                        str(lectura_decimal),
                        lectura_data.get('latitud'),
                        lectura_data.get('longitud'),
                        'cargada',
                        lectura_data.get('observaciones', ''),
                        lectura_data.get('usuario', 'App Móvil'),
                        alias,
                        0,
                        timezone.now()
                    ])
                
                lecturas_procesadas.append({
                    'cliente_id': cliente_id,
                    'lectura_id': lectura_uuid,
                    'estado': 'creada',
                    'fecha': timezone.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error procesando lectura para cliente {lectura_data.get('cliente_id')}: {str(e)}")
                lecturas_con_error.append({
                    'cliente_id': lectura_data.get('cliente_id'),
                    'error': str(e)
                })
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'lecturas_procesadas': len(lecturas_procesadas),
            'lecturas_con_error': len(lecturas_con_error),
            'detalle_procesadas': lecturas_procesadas,
            'detalle_errores': lecturas_con_error,
            'fecha_sincronizacion': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_sincronizar_lecturas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def api_obtener_clientes_pendientes(request, alias):
    """
    API para obtener clientes con lecturas pendientes - CORREGIDO: acepta 'alias'
    """
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Parámetros de filtro
        limite = int(request.GET.get('limite', 100))
        
        # Obtener clientes desde la BD específica
        clientes_data = []
        try:
            alias_db = f'db_{alias}'
            if alias_db in connection.settings_dict['DATABASES']:
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT id, nombre, rut, direccion, medidor, sector
                        FROM clientes_cliente 
                        WHERE empresa_slug = %s AND activo = 1
                        LIMIT %s
                    """, [alias, limite])
                    
                    for row in cursor.fetchall():
                        clientes_data.append({
                            'id': row[0],
                            'nombre': row[1],
                            'rut': row[2],
                            'direccion': row[3],
                            'medidor': row[4],
                            'sector': row[5]
                        })
        except Exception as e:
            print(f"Error obteniendo clientes: {e}")
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'total_clientes': len(clientes_data),
            'clientes': clientes_data,
            'fecha_consulta': timezone.now().date().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_obtener_clientes_pendientes: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

@login_required
def calcular_consumo(request, alias, lectura_id):
    """Vista para calcular consumo de una lectura"""
    db_alias = f'db_{alias}'
    lectura = get_object_or_404(LecturaMovil.objects.using(db_alias), id=lectura_id)
    
    if request.method == 'POST':
        # Calcular consumo si hay lectura anterior
        if lectura.lectura_anterior:
            lectura.calcular_consumo()
            # Mensaje de éxito
            # Redirigir al detalle
    
    return redirect('detalle_lectura', alias=alias, lectura_id=lectura_id)

# ========== API ESPECÍFICA PARA APP MÓVIL ==========

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.db import connection
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import DispositivoMovil, ConfigAppMovil
from empresas.models import Empresa
import hashlib
import secrets

@csrf_exempt
def api_dispositivo_login(request, alias):
    """
    API para autenticar dispositivo móvil
    URL: /api/<alias>/dispositivos/login/
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Parsear datos
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato JSON inválido'
            }, status=400)
        
        dispositivo_id = data.get('dispositivo_id')
        token = data.get('token')
        
        if not dispositivo_id or not token:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo ID y token requeridos'
            }, status=400)
        
        # Buscar dispositivo
        try:
            dispositivo = DispositivoMovil.objects.get(
                identificador=dispositivo_id,
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no encontrado o inactivo'
            }, status=401)
        
        # Actualizar última conexión
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.save()
        
        # Obtener configuración de la app
        config_app, _ = ConfigAppMovil.objects.get_or_create(empresa=empresa)
        
        return JsonResponse({
            'success': True,
            'token': dispositivo.token_acceso,
            'dispositivo_nombre': dispositivo.nombre_dispositivo,
            'dispositivo_id': dispositivo.identificador,
            'empresa': {
                'nombre': empresa.nombre,
                'slug': empresa.slug,
                'version_app': empresa.version_app,
                'color_primario': empresa.color_app_primario,
                'color_secundario': empresa.color_app_secundario,
                'url_servidor': empresa.url_servidor,
            },
            'configuracion': {
                'habilitar_mapa': config_app.habilitar_mapa,
                'habilitar_offline': config_app.habilitar_offline,
                'validar_gps': config_app.validar_gps,
                'sincronizacion_auto': config_app.sincronizacion_auto,
                'mostrar_logo': config_app.mostrar_logo,
                'intervalo_sincronizacion': config_app.intervalo_sincronizacion,
                'mensaje_bienvenida': config_app.mensaje_bienvenida,
                'max_lecturas_pendientes': config_app.max_lecturas_pendientes,
            },
            'fecha_sincronizacion': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_dispositivo_login: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_obtener_sectores(request, alias):
    """
    API para obtener sectores de la empresa
    URL: /api/<alias>/sectores/
    """
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar autenticación del dispositivo
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            dispositivo = DispositivoMovil.objects.get(
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no autenticado'
            }, status=401)
        
        # Obtener sectores desde la BD específica
        sectores = []
        alias_db = f'db_{alias}'
        
        if alias_db in connection.settings_dict['DATABASES']:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT DISTINCT sector 
                    FROM clientes_cliente 
                    WHERE empresa_slug = %s AND activo = 1
                    ORDER BY sector
                """, [alias])
                
                for row in cursor.fetchall():
                    if row[0]:  # Solo agregar si no es None o vacío
                        sectores.append(row[0])
        
        # Si no hay sectores en clientes, usar los de la empresa
        if not sectores:
            sectores = empresa.sectores() or []
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'total_sectores': len(sectores),
            'sectores': sectores,
            'fecha_consulta': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_obtener_sectores: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_obtener_clientes_por_sector(request, alias, sector):
    """
    API para obtener clientes de un sector específico
    URL: /api/<alias>/sectores/<sector>/clientes/
    """
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar autenticación
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            dispositivo = DispositivoMovil.objects.get(
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no autenticado'
            }, status=401)
        
        # Obtener clientes del sector
        clientes = []
        alias_db = f'db_{alias}'
        
        if alias_db in connection.settings_dict['DATABASES']:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT id, nombre, rut, direccion, medidor, sector
                    FROM clientes_cliente 
                    WHERE empresa_slug = %s AND activo = 1 AND sector = %s
                    ORDER BY nombre
                """, [alias, sector])
                
                for row in cursor.fetchall():
                    # Obtener última lectura si existe
                    cursor.execute(f"""
                        SELECT lectura_actual, fecha_lectura 
                        FROM lecturas_lecturamovil 
                        WHERE empresa_slug = %s AND cliente = %s
                        ORDER BY fecha_lectura DESC 
                        LIMIT 1
                    """, [alias, row[0]])
                    
                    ultima_lectura = cursor.fetchone()
                    
                    clientes.append({
                        'id': row[0],
                        'nombre': row[1] or f"Cliente {row[0]}",
                        'rut': row[2] or "No especificado",
                        'direccion': row[3] or "No especificada",
                        'medidor': row[4] or "No especificado",
                        'sector': row[5] or "Sin sector",
                        'ultima_lectura': {
                            'valor': float(ultima_lectura[0]) if ultima_lectura and ultima_lectura[0] else 0,
                            'fecha': ultima_lectura[1].isoformat() if ultima_lectura and ultima_lectura[1] else None
                        } if ultima_lectura else None,
                        'pendiente': not bool(ultima_lectura)  # Pendiente si no tiene lecturas
                    })
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'sector': sector,
            'total_clientes': len(clientes),
            'clientes': clientes,
            'fecha_consulta': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_obtener_clientes_por_sector: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_guardar_lectura(request, alias):
    """
    API para guardar una lectura desde la app móvil
    URL: /api/<alias>/lecturas/guardar/
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar autenticación
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            dispositivo = DispositivoMovil.objects.get(
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no autenticado'
            }, status=401)
        
        # Parsear datos
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato JSON inválido'
            }, status=400)
        
        # Validar datos requeridos
        cliente_id = data.get('cliente_id')
        lectura_valor = data.get('lectura')
        latitud = data.get('latitud')
        longitud = data.get('longitud')
        
        if not cliente_id or not lectura_valor:
            return JsonResponse({
                'success': False,
                'error': 'Cliente ID y lectura requeridos'
            }, status=400)
        
        # Verificar que el cliente existe
        alias_db = f'db_{alias}'
        cliente_existe = False
        if alias_db in connection.settings_dict['DATABASES']:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT COUNT(*) 
                    FROM clientes_cliente 
                    WHERE id = %s AND empresa_slug = %s AND activo = 1
                """, [cliente_id, alias])
                
                cliente_existe = cursor.fetchone()[0] > 0
        
        if not cliente_existe:
            return JsonResponse({
                'success': False,
                'error': f'Cliente {cliente_id} no encontrado o inactivo'
            }, status=404)
        
        # Configuración de la app para validaciones
        config_app, _ = ConfigAppMovil.objects.get_or_create(empresa=empresa)
        
        # Validar GPS si está habilitado
        if config_app.validar_gps and (not latitud or not longitud):
            return JsonResponse({
                'success': False,
                'error': 'Ubicación GPS requerida'
            }, status=400)
        
        # Crear lectura en BD principal
        from decimal import Decimal, InvalidOperation
        
        try:
            lectura_decimal = Decimal(str(lectura_valor))
        except (InvalidOperation, ValueError):
            return JsonResponse({
                'success': False,
                'error': 'Valor de lectura inválido'
            }, status=400)
        
        import uuid
        from datetime import datetime
        
        lectura_uuid = str(uuid.uuid4())
        
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO lecturas_lecturamovil 
                (id, empresa_id, cliente, fecha_lectura, lectura_actual, 
                 latitud, longitud, estado, observaciones_app, usuario_app, 
                 empresa_slug, dispositivo_id, fecha_sincronizacion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                lectura_uuid,
                empresa.id,
                int(cliente_id),
                datetime.now().date(),
                str(lectura_decimal),
                latitud,
                longitud,
                'pendiente',
                data.get('observaciones', ''),
                dispositivo.nombre_dispositivo,
                alias,
                dispositivo.identificador,
                timezone.now()
            ])
        
        # Actualizar última conexión del dispositivo
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.save()
        
        return JsonResponse({
            'success': True,
            'lectura_id': lectura_uuid,
            'cliente_id': cliente_id,
            'lectura': float(lectura_decimal),
            'fecha': datetime.now().isoformat(),
            'dispositivo': dispositivo.nombre_dispositivo,
            'estado': 'pendiente',
            'mensaje': 'Lectura guardada exitosamente'
        })
        
    except Exception as e:
        logger.error(f"Error en api_guardar_lectura: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_obtener_lecturas_pendientes(request, alias):
    """
    API para obtener lecturas pendientes del dispositivo
    URL: /api/<alias>/lecturas/pendientes/
    """
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar autenticación
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            dispositivo = DispositivoMovil.objects.get(
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no autenticado'
            }, status=401)
        
        # Obtener lecturas pendientes del dispositivo
        lecturas_pendientes = []
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, cliente, lectura_actual, latitud, longitud, 
                       observaciones_app, fecha_lectura, estado
                FROM lecturas_lecturamovil 
                WHERE empresa_slug = %s AND dispositivo_id = %s AND estado = 'pendiente'
                ORDER BY fecha_lectura DESC
            """, [alias, dispositivo.identificador])
            
            for row in cursor.fetchall():
                lecturas_pendientes.append({
                    'id': row[0],
                    'cliente_id': row[1],
                    'lectura': float(row[2]) if row[2] else 0,
                    'latitud': float(row[3]) if row[3] else None,
                    'longitud': float(row[4]) if row[4] else None,
                    'observaciones': row[5] or '',
                    'fecha': row[6].isoformat() if row[6] else None,
                    'estado': row[7]
                })
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'dispositivo': dispositivo.nombre_dispositivo,
            'total_pendientes': len(lecturas_pendientes),
            'lecturas': lecturas_pendientes,
            'fecha_consulta': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_obtener_lecturas_pendientes: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_sincronizar_lecturas_batch(request, alias):
    """
    API para sincronizar múltiples lecturas en lote
    URL: /api/<alias>/lecturas/sincronizar/
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar autenticación
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            dispositivo = DispositivoMovil.objects.get(
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no autenticado'
            }, status=401)
        
        # Parsear datos
        try:
            data = json.loads(request.body)
            lecturas_data = data.get('lecturas', [])
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato JSON inválido'
            }, status=400)
        
        if not lecturas_data:
            return JsonResponse({
                'success': False,
                'error': 'No hay lecturas para sincronizar'
            }, status=400)
        
        lecturas_procesadas = []
        lecturas_con_error = []
        
        for lectura_data in lecturas_data:
            try:
                # Validar datos mínimos
                if not all(k in lectura_data for k in ['cliente_id', 'lectura']):
                    lecturas_con_error.append({
                        'cliente_id': lectura_data.get('cliente_id'),
                        'error': 'Datos incompletos'
                    })
                    continue
                
                cliente_id = lectura_data['cliente_id']
                
                # Verificar que el cliente existe
                alias_db = f'db_{alias}'
                cliente_existe = False
                if alias_db in connection.settings_dict['DATABASES']:
                    with connection.cursor() as cursor:
                        cursor.execute(f"""
                            SELECT COUNT(*) 
                            FROM clientes_cliente 
                            WHERE id = %s AND empresa_slug = %s AND activo = 1
                        """, [cliente_id, alias])
                        
                        cliente_existe = cursor.fetchone()[0] > 0
                
                if not cliente_existe:
                    lecturas_con_error.append({
                        'cliente_id': cliente_id,
                        'error': 'Cliente no encontrado'
                    })
                    continue
                
                # Convertir lectura a Decimal
                from decimal import Decimal, InvalidOperation
                
                try:
                    lectura_decimal = Decimal(str(lectura_data['lectura']))
                except (InvalidOperation, ValueError):
                    lecturas_con_error.append({
                        'cliente_id': cliente_id,
                        'error': 'Valor de lectura inválido'
                    })
                    continue
                
                # Crear o actualizar lectura
                import uuid
                from datetime import datetime
                
                # Intentar encontrar lectura existente
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT id FROM lecturas_lecturamovil 
                        WHERE empresa_slug = %s AND cliente = %s AND dispositivo_id = %s
                        AND estado = 'pendiente'
                        LIMIT 1
                    """, [alias, cliente_id, dispositivo.identificador])
                    
                    existing = cursor.fetchone()
                    
                    if existing:
                        # Actualizar lectura existente
                        cursor.execute("""
                            UPDATE lecturas_lecturamovil 
                            SET lectura_actual = %s, latitud = %s, longitud = %s,
                                observaciones_app = %s, fecha_sincronizacion = %s,
                                estado = 'cargada'
                            WHERE id = %s
                        """, [
                            str(lectura_decimal),
                            lectura_data.get('latitud'),
                            lectura_data.get('longitud'),
                            lectura_data.get('observaciones', ''),
                            timezone.now(),
                            existing[0]
                        ])
                        
                        lectura_id = existing[0]
                    else:
                        # Crear nueva lectura
                        lectura_id = str(uuid.uuid4())
                        
                        cursor.execute("""
                            INSERT INTO lecturas_lecturamovil 
                            (id, empresa_id, cliente, fecha_lectura, lectura_actual, 
                             latitud, longitud, estado, observaciones_app, usuario_app, 
                             empresa_slug, dispositivo_id, fecha_sincronizacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, [
                            lectura_id,
                            empresa.id,
                            int(cliente_id),
                            datetime.now().date(),
                            str(lectura_decimal),
                            lectura_data.get('latitud'),
                            lectura_data.get('longitud'),
                            'cargada',
                            lectura_data.get('observaciones', ''),
                            dispositivo.nombre_dispositivo,
                            alias,
                            dispositivo.identificador,
                            timezone.now()
                        ])
                
                lecturas_procesadas.append({
                    'cliente_id': cliente_id,
                    'lectura_id': lectura_id,
                    'estado': 'sincronizada',
                    'fecha': timezone.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error procesando lectura para cliente {lectura_data.get('cliente_id')}: {str(e)}")
                lecturas_con_error.append({
                    'cliente_id': lectura_data.get('cliente_id'),
                    'error': str(e)
                })
        
        # Actualizar última conexión del dispositivo
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.save()
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'dispositivo': dispositivo.nombre_dispositivo,
            'lecturas_procesadas': len(lecturas_procesadas),
            'lecturas_con_error': len(lecturas_con_error),
            'detalle_procesadas': lecturas_procesadas,
            'detalle_errores': lecturas_con_error,
            'fecha_sincronizacion': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_sincronizar_lecturas_batch: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_validar_gps(request, alias):
    """
    API para validar coordenadas GPS
    URL: /api/<alias>/validar-gps/
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar autenticación
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Token '):
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=401)
        
        token = auth_header.split(' ')[1]
        
        try:
            dispositivo = DispositivoMovil.objects.get(
                token_acceso=token,
                empresa=empresa,
                activo=True
            )
        except DispositivoMovil.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Dispositivo no autenticado'
            }, status=401)
        
        # Parsear datos
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Formato JSON inválido'
            }, status=400)
        
        latitud = data.get('latitud')
        longitud = data.get('longitud')
        cliente_id = data.get('cliente_id')
        
        if not latitud or not longitud:
            return JsonResponse({
                'success': False,
                'error': 'Coordenadas GPS requeridas'
            }, status=400)
        
        # Validar que las coordenadas sean números válidos
        try:
            lat = float(latitud)
            lng = float(longitud)
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Coordenadas inválidas'
            }, status=400)
        
        # Validar rangos de coordenadas (Chile aproximadamente)
        # Latitud: -56 a -17, Longitud: -76 a -66
        if not (-56 <= lat <= -17) or not (-76 <= lng <= -66):
            return JsonResponse({
                'success': False,
                'error': 'Ubicación fuera de rango válido',
                'detalle': 'Las coordenadas deben estar dentro de Chile'
            })
        
        # Si se proporciona cliente_id, validar que esté cerca del cliente
        if cliente_id:
            alias_db = f'db_{alias}'
            if alias_db in connection.settings_dict['DATABASES']:
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT direccion, coordenadas 
                        FROM clientes_cliente 
                        WHERE id = %s AND empresa_slug = %s
                    """, [cliente_id, alias])
                    
                    row = cursor.fetchone()
                    if row and row[1]:  # Si tiene coordenadas guardadas
                        # Aquí podrías implementar validación de proximidad
                        # Por ahora solo registramos la validación
                        pass
        
        return JsonResponse({
            'success': True,
            'validado': True,
            'latitud': lat,
            'longitud': lng,
            'cliente_id': cliente_id,
            'mensaje': 'Ubicación GPS válida',
            'fecha_validacion': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error en api_validar_gps: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
def api_descargar_config_app(request, alias):
    """
    API para descargar configuración de la app móvil
    URL: /api/<alias>/descargar-app/
    """
    if request.method != 'GET':
        return JsonResponse({
            'success': False,
            'error': 'Método no permitido'
        }, status=405)
    
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        config_app, _ = ConfigAppMovil.objects.get_or_create(empresa=empresa)
        
        # Construir configuración completa
        config_completa = {
            'app_name': f'SSR {empresa.nombre}',
            'empresa_slug': empresa.slug,
            'version': empresa.version_app,
            'primary_color': empresa.color_app_primario or '#1E40AF',
            'secondary_color': empresa.color_app_secundario or '#DC2626',
            'base_url': f'{empresa.url_servidor}/api/{empresa.slug}/',
            'sectores': empresa.sectores(),
            'habilitar_mapa': config_app.habilitar_mapa,
            'habilitar_offline': config_app.habilitar_offline,
            'validar_gps': config_app.validar_gps,
            'sincronizacion_auto': config_app.sincronizacion_auto,
            'mostrar_logo': config_app.mostrar_logo,
            'intervalo_sincronizacion': config_app.intervalo_sincronizacion,
            'mensaje_bienvenida': config_app.mensaje_bienvenida,
            'max_lecturas_pendientes': config_app.max_lecturas_pendientes,
            'fecha_generacion': timezone.now().isoformat(),
            'empresa_info': {
                'nombre': empresa.nombre,
                'descripcion': f'Aplicación móvil para lecturas de {empresa.nombre}',
                'contacto': empresa.contacto or 'Contacto no especificado',
                'telefono': empresa.telefono or 'Teléfono no especificado',
            }
        }
        
        response = JsonResponse(config_completa)
        response['Content-Disposition'] = f'attachment; filename="{empresa.slug}_config.json"'
        return response
        
    except Exception as e:
        logger.error(f"Error en api_descargar_config_app: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)