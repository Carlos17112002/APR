from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Avg, Q
from django.core.paginator import Paginator
import json
from django.http import HttpResponse
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import io

# ========== VISTA BASE PARA TODOS LOS INFORMES ==========
def render_informe(request, alias, template_name):
    """Vista base para renderizar informes"""
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Verificar conexión a BD de la empresa
        from django.db import connections
        db_alias = f'db_{alias}'
        
        if db_alias not in connections:
            messages.error(request, 'Base de datos de la empresa no disponible')
            return redirect('panel_general')
        
        # Contexto base para todos los informes
        base_context = {
            'empresa': empresa,
            'slug': alias,
            'fecha_generacion': timezone.now(),
            'periodo': obtener_periodo_default(),
            'usuario': request.user,
        }
        
        # Agregar datos específicos según el tipo de informe
        datos_especificos = obtener_datos_informe(request, db_alias, template_name)
        base_context.update(datos_especificos)
        
        return render(request, f'informes/{template_name}.html', base_context)
        
    except Exception as e:
        messages.error(request, f'Error al generar informe: {str(e)}')
        return redirect('dashboard_admin_ssr')

def obtener_periodo_default():
    """Obtiene el período por defecto (últimos 30 días)"""
    hoy = timezone.now()
    inicio = (hoy - timedelta(days=30)).strftime('%d/%m/%Y')
    fin = hoy.strftime('%d/%m/%Y')
    return f"{inicio} al {fin}"

# ========== INFORMES ESPECÍFICOS ==========

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Avg, Q
from django.core.paginator import Paginator
from empresas.models import Empresa
from informes.models import LibroContable

# ========== VISTA BASE PARA TODOS LOS INFORMES ==========
def render_informe_base(request, alias, template_name, context_extra=None):
    """Vista base para renderizar informes"""
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        # Contexto base para todos los informes
        base_context = {
            'empresa': empresa,
            'slug': alias,
            'fecha_generacion': timezone.now(),
            'periodo': obtener_periodo_default(),
            'usuario': request.user,
        }
        
        if context_extra:
            base_context.update(context_extra)
        
        return render(request, f'informes/{template_name}.html', base_context)
        
    except Exception as e:
        messages.error(request, f'Error al generar informe: {str(e)}')
        return redirect('dashboard_admin_ssr')

def obtener_periodo_default():
    """Obtiene el período por defecto (últimos 30 días)"""
    hoy = timezone.now()
    inicio = (hoy - timedelta(days=30)).strftime('%d/%m/%Y')
    fin = hoy.strftime('%d/%m/%Y')
    return f"{inicio} al {fin}"

# ========== 1. INFORME CARGO Y DESCUENTO ==========
def informe_cargo_descuento(request, alias):
    """
    Análisis detallado de cargos y descuentos aplicados
    (Basado en LibroContable)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    tipo = request.GET.get('tipo', '')
    
    try:
        # Obtener libros contables del período
        libros = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            periodo__startswith=periodo[:4]  # Filtro por año
        )
        
        if tipo:
            libros = libros.filter(tipo=tipo)
        
        # Estadísticas
        total_neto = libros.aggregate(total=Sum('neto'))['total'] or 0
        total_iva = libros.aggregate(total=Sum('iva'))['total'] or 0
        total_general = libros.aggregate(total=Sum('total'))['total'] or 0
        
        # Por tipo de libro
        por_tipo = libros.values('tipo').annotate(
            cantidad=Count('id'),
            neto_total=Sum('neto'),
            iva_total=Sum('iva'),
            total_general=Sum('total')
        ).order_by('-total_general')
        
        # Estados de procesamiento
        por_estado = libros.values('estado').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('estado')
        
        # Meses disponibles
        meses_disponibles = LibroContable.objects.using(db_alias).filter(
            empresa=empresa
        ).values_list('periodo', flat=True).distinct().order_by('-periodo')
        
        context = {
            'titulo': 'Informe de Cargos y Descuentos',
            'libros': libros,
            'periodo': periodo,
            'estadisticas': {
                'total_neto': total_neto,
                'total_iva': total_iva,
                'total_general': total_general,
                'libros_procesados': libros.count(),
                'validados': libros.filter(estado='validado').count(),
                'con_errores': libros.filter(estado='error').count()
            },
            'por_tipo': por_tipo,
            'por_estado': por_estado,
            'meses_disponibles': meses_disponibles,
            'filtros': {
                'periodo': periodo,
                'tipo': tipo
            }
        }
        
        return render_informe_base(request, alias, 'informe_cargo_descuento', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'informe_cargo_descuento', {
            'error': str(e),
            'titulo': 'Informe de Cargos y Descuentos'
        })

# ========== 2. INFORME CIERRE DE CAJA ==========
def informe_cierre_caja(request, alias):
    """
    Resumen financiero diario basado en LibroContable
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    fecha = request.GET.get('fecha', timezone.now().strftime('%Y-%m-%d'))
    mes = fecha[:7] if fecha else timezone.now().strftime('%Y-%m')
    
    try:
        # Para el cierre de caja, usar ventas del día/mes
        libros = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            tipo='ventas',
            periodo=mes
        )
        
        # Calcular totales
        total_ventas = libros.aggregate(
            neto=Sum('neto'),
            iva=Sum('iva'),
            total=Sum('total')
        )
        
        # Por día (simulado)
        ventas_por_dia = []
        for i in range(1, 32):
            dia = f"{mes}-{i:02d}"
            # Simulación - en realidad deberías tener fecha específica
            ventas_dia = libros.filter(fecha_subida__day=i).aggregate(
                total=Sum('total')
            )
            if ventas_dia['total']:
                ventas_por_dia.append({
                    'dia': dia,
                    'total': ventas_dia['total']
                })
        
        context = {
            'titulo': 'Cierre de Caja',
            'fecha': fecha,
            'libros_ventas': libros,
            'estadisticas': {
                'total_neto': total_ventas['neto'] or 0,
                'total_iva': total_ventas['iva'] or 0,
                'total_ventas': total_ventas['total'] or 0,
                'ventas_diarias_promedio': (total_ventas['total'] or 0) / 30 if (total_ventas['total'] or 0) > 0 else 0
            },
            'ventas_por_dia': ventas_por_dia,
            'filtros': {
                'fecha': fecha
            }
        }
        
        return render_informe_base(request, alias, 'informe_cierre_caja', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'informe_cierre_caja', {
            'error': str(e),
            'titulo': 'Cierre de Caja'
        })

# ========== 3. INFORME CONTRATOS ==========
# informes/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
from django.db.models import Sum, Count, Avg, Q
from empresas.models import Empresa
from trabajadores.models import ContratoLaboral

def informe_contratos(request, alias):
    """
    Informe de contratos laborales con debugging
    """
    print(f"\n=== DEBUG INICIO INFORME CONTRATOS ===")
    print(f"Empresa slug: {alias}")
    print(f"Request user: {request.user}")
    
    try:
        # 1. Obtener la empresa primero
        empresa = get_object_or_404(Empresa, slug=alias)
        print(f"✓ Empresa encontrada: {empresa.nombre}")
        
        # 2. Definir el alias de la base de datos
        db_alias = f'db_{alias}'
        print(f"Alias DB: {db_alias}")
        
        # 3. Intentar usar la base de datos específica primero
        from django.db import connections
        
        # Opción A: Usar BD específica de la empresa (si existe y tiene datos)
        usar_bd_especifica = False
        
        if db_alias in connections.databases:
            try:
                conn = connections[db_alias]
                conn.ensure_connection()
                print(f"✓ Conexión a {db_alias} establecida")
                
                # Verificar si hay datos en esta BD
                contratos_en_bd_especifica = ContratoLaboral.objects.using(db_alias).filter(alias=alias).count()
                print(f"✓ Contratos en BD específica: {contratos_en_bd_especifica}")
                
                if contratos_en_bd_especifica > 0:
                    usar_bd_especifica = True
                    print(f"✓ Usando BD específica: {db_alias}")
                else:
                    print(f"✗ BD específica vacía, usando BD default")
            except Exception as e:
                print(f"✗ Error conectando a BD específica: {e}")
        else:
            print(f"✗ BD específica {db_alias} no configurada")
        
        # 4. Obtener contratos según la estrategia seleccionada
        cargo = request.GET.get('cargo', '')
        estado = request.GET.get('estado', '')
        tipo_contrato = request.GET.get('tipo_contrato', '')
        afp = request.GET.get('afp', '')
        
        print(f"✓ Filtros aplicados: cargo='{cargo}', estado='{estado}', tipo='{tipo_contrato}', afp='{afp}'")
        
        if usar_bd_especifica:
            # Usar base de datos específica de la empresa
            contratos = ContratoLaboral.objects.using(db_alias).filter(alias=alias)
        else:
            # Usar base de datos por defecto (donde listado_contratos busca)
            contratos = ContratoLaboral.objects.filter(alias=alias)
            print(f"✓ Buscando en BD default con alias='{alias}'")
            print(f"✓ Total contratos encontrados en BD default: {contratos.count()}")
            
            # Mostrar algunos contratos para debug
            if contratos.exists():
                print("✓ Primeros 3 contratos encontrados:")
                for i, c in enumerate(contratos[:3]):
                    print(f"  {i+1}. {c.nombre} - {c.cargo} - Alias: '{c.alias}'")
        
        # Ordenar por fecha de inicio
        contratos = contratos.order_by('-fecha_inicio')
        print(f"✓ Contratos después de filtrar por alias: {contratos.count()}")
        
        # 5. Aplicar filtros adicionales
        if cargo:
            contratos = contratos.filter(cargo__icontains=cargo)
            print(f"✓ Después de filtrar por cargo: {contratos.count()}")
        
        if estado:
            hoy = date.today()
            if estado == 'vigente':
                contratos = contratos.filter(
                    Q(fecha_termino__isnull=True) | Q(fecha_termino__gte=hoy)
                )
            elif estado == 'vencido':
                contratos = contratos.filter(fecha_termino__lt=hoy)
            print(f"✓ Después de filtrar por estado '{estado}': {contratos.count()}")
        
        if tipo_contrato:
            contratos = contratos.filter(tipo_contrato=tipo_contrato)
            print(f"✓ Después de filtrar por tipo: {contratos.count()}")
        
        if afp:
            contratos = contratos.filter(afp=afp)
            print(f"✓ Después de filtrar por AFP: {contratos.count()}")
        
        print(f"✓ Total contratos final: {contratos.count()}")
        
        # 6. Calcular estadísticas
        total_contratos = contratos.count()
        
        # Contratos vigentes vs vencidos
        hoy = date.today()
        contratos_vigentes = contratos.filter(
            Q(fecha_termino__isnull=True) | Q(fecha_termino__gte=hoy)
        ).count()
        
        contratos_vencidos = contratos.filter(
            fecha_termino__lt=hoy
        ).count()
        
        # Totales financieros
        total_sueldos = contratos.aggregate(
            total=Sum('sueldo_base')
        )['total'] or 0
        
        total_gratificaciones = contratos.aggregate(
            total=Sum('gratificacion')
        )['total'] or 0
        
        total_bonos = contratos.aggregate(
            total=Sum('bonos')
        )['total'] or 0
        
        total_remuneracion = total_sueldos + total_gratificaciones + total_bonos
        
        # 7. Datos para gráficos/distribución
        contratos_por_tipo = contratos.values('tipo_contrato').annotate(
            cantidad=Count('id'),
            sueldo_total=Sum('sueldo_base')
        ).order_by('-cantidad')
        
        contratos_por_afp = contratos.values('afp').annotate(
            cantidad=Count('id'),
            sueldo_total=Sum('sueldo_base')
        ).order_by('-cantidad')
        
        contratos_por_jornada = contratos.values('jornada').annotate(
            cantidad=Count('id'),
            sueldo_promedio=Avg('sueldo_base')
        ).order_by('-cantidad')
        
        contratos_por_gratificacion = contratos.values('sistema_gratificacion').annotate(
            cantidad=Count('id'),
            gratificacion_total=Sum('gratificacion')
        ).order_by('-cantidad')
        
        # Próximos a vencer (próximos 30 días)
        proximos_30_dias = hoy + timedelta(days=30)
        contratos_proximos_vencer = contratos.filter(
            fecha_termino__range=[hoy, proximos_30_dias]
        ).count()
        
        # 8. Obtener opciones para filtros
        if usar_bd_especifica:
            cargos_disponibles = ContratoLaboral.objects.using(db_alias).filter(
                alias=alias
            ).values_list('cargo', flat=True).distinct().order_by('cargo')
            
            tipos_contrato_disponibles = ContratoLaboral.objects.using(db_alias).filter(
                alias=alias
            ).values_list('tipo_contrato', flat=True).distinct().order_by('tipo_contrato')
            
            afps_disponibles = ContratoLaboral.objects.using(db_alias).filter(
                alias=alias
            ).values_list('afp', flat=True).distinct().order_by('afp')
        else:
            cargos_disponibles = ContratoLaboral.objects.filter(
                alias=alias
            ).values_list('cargo', flat=True).distinct().order_by('cargo')
            
            tipos_contrato_disponibles = ContratoLaboral.objects.filter(
                alias=alias
            ).values_list('tipo_contrato', flat=True).distinct().order_by('tipo_contrato')
            
            afps_disponibles = ContratoLaboral.objects.filter(
                alias=alias
            ).values_list('afp', flat=True).distinct().order_by('afp')
        
        print(f"✓ Cargos disponibles: {list(cargos_disponibles)}")
        print(f"✓ Tipos contrato disponibles: {list(tipos_contrato_disponibles)}")
        print(f"✓ AFPs disponibles: {list(afps_disponibles)}")
        
        # 9. Preparar contexto
        context = {
            'empresa': empresa,
            'slug': alias,
            'contratos': contratos,
            'cargos': cargos_disponibles,
            'tipos_contrato': tipos_contrato_disponibles,
            'afps': afps_disponibles,
            'estadisticas': {
                'total_contratos': total_contratos,
                'contratos_vigentes': contratos_vigentes,
                'contratos_vencidos': contratos_vencidos,
                'contratos_proximos_vencer': contratos_proximos_vencer,
                'total_sueldos': total_sueldos,
                'total_gratificaciones': total_gratificaciones,
                'total_bonos': total_bonos,
                'total_remuneracion': total_remuneracion,
                'sueldo_promedio': total_sueldos / total_contratos if total_contratos > 0 else 0,
                'gratificacion_promedio': total_gratificaciones / total_contratos if total_contratos > 0 else 0,
            },
            'contratos_por_tipo': contratos_por_tipo,
            'contratos_por_afp': contratos_por_afp,
            'contratos_por_jornada': contratos_por_jornada,
            'contratos_por_gratificacion': contratos_por_gratificacion,
            'filtros': {
                'cargo': cargo,
                'estado': estado,
                'tipo_contrato': tipo_contrato,
                'afp': afp,
            },
            'fecha_generacion': timezone.now(),
            'hoy': hoy,
        }
        
        print(f"✓ Contexto preparado con {len(contratos)} contratos")
        print(f"=== DEBUG FIN INFORME CONTRATOS ===\n")
        
        return render(request, 'informes/informe_contratos.html', context)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"\n✗ ERROR en informe_contratos:")
        print(f"  Empresa: {alias}")
        print(f"  Error: {str(e)}")
        print(f"  Traceback: {error_detail}")
        print(f"=== DEBUG ERROR ===\n")
        
        messages.error(request, f'Error al generar informe de contratos: {str(e)}')
        
        # Intentar obtener la empresa para el contexto de error
        try:
            empresa = Empresa.objects.get(slug=alias)
        except:
            empresa = None
        
        # Devolver contexto con información de depuración
        return render(request, 'informes/informe_contratos.html', {
            'empresa': empresa,
            'slug': alias,
            'contratos': [],
            'cargos': [],
            'tipos_contrato': [],
            'afps': [],
            'error': f"{str(e)} - Ver consola para detalles",
            'debug_info': {
                'alias_db': f'db_{alias}',
                'empresa_slug': alias,
                'error': str(e),
            },
            'estadisticas': {
                'total_contratos': 0,
                'contratos_vigentes': 0,
                'contratos_vencidos': 0,
                'contratos_proximos_vencer': 0,
                'total_sueldos': 0,
                'total_gratificaciones': 0,
                'total_bonos': 0,
                'total_remuneracion': 0,
                'sueldo_promedio': 0,
                'gratificacion_promedio': 0,
            },
            'fecha_generacion': timezone.now(),
            'hoy': date.today(),
        })

# ========== 4. INFORME CONVENIOS ==========
def informe_convenios(request, alias):
    """
    Informe de convenios (simplificado)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    
    try:
        # Para convenios, podemos usar retenciones
        retenciones = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            tipo='retenciones',
            periodo__startswith=periodo[:4]
        )
        
        # Estadísticas
        total_retenciones = retenciones.aggregate(
            cantidad=Count('id'),
            total=Sum('total')
        )
        
        # Por estado
        retenciones_por_estado = retenciones.values('estado').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('estado')
        
        context = {
            'titulo': 'Informe de Convenios (Retenciones)',
            'retenciones': retenciones,
            'periodo': periodo,
            'estadisticas': {
                'total_convenios': total_retenciones['cantidad'] or 0,
                'valor_total': total_retenciones['total'] or 0,
                'promedio_convenio': (total_retenciones['total'] or 0) / (total_retenciones['cantidad'] or 1),
                'activos': retenciones.filter(estado='validado').count()
            },
            'retenciones_por_estado': retenciones_por_estado,
            'filtros': {
                'periodo': periodo
            }
        }
        
        return render_informe_base(request, alias, 'informe_convenios', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'informe_convenios', {
            'error': str(e),
            'titulo': 'Informe de Convenios'
        })

# ========== 5. INFORME DAES ==========
def informe_DAES(request, alias):
    """
    Documentos electrónicos (basado en todos los libros)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    tipo_documento = request.GET.get('tipo_documento', '')
    
    try:
        # Todos los libros como documentos electrónicos
        documentos = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            periodo__startswith=periodo[:4]
        )
        
        if tipo_documento:
            documentos = documentos.filter(tipo=tipo_documento)
        
        # Estadísticas por tipo
        por_tipo = documentos.values('tipo').annotate(
            cantidad=Count('id'),
            neto_total=Sum('neto'),
            iva_total=Sum('iva'),
            total_general=Sum('total')
        ).order_by('-cantidad')
        
        # Por estado (validación SII)
        por_estado = documentos.values('estado').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('estado')
        
        # Totales generales
        totales = documentos.aggregate(
            total_documentos=Count('id'),
            total_neto=Sum('neto'),
            total_iva=Sum('iva'),
            total_general=Sum('total')
        )
        
        context = {
            'titulo': 'Informe de Documentos Electrónicos (DAES)',
            'documentos': documentos,
            'periodo': periodo,
            'por_tipo': por_tipo,
            'por_estado': por_estado,
            'estadisticas': {
                'total_documentos': totales['total_documentos'] or 0,
                'total_neto': totales['total_neto'] or 0,
                'total_iva': totales['total_iva'] or 0,
                'total_general': totales['total_general'] or 0,
                'validados': documentos.filter(estado='validado').count(),
                'en_proceso': documentos.filter(estado='procesando').count(),
                'con_errores': documentos.filter(estado='error').count()
            },
            'filtros': {
                'periodo': periodo,
                'tipo_documento': tipo_documento
            },
            'tipos_documento': ['compras', 'ventas', 'retenciones']
        }
        
        return render_informe_base(request, alias, 'informe_DAES', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'informe_DAES', {
            'error': str(e),
            'titulo': 'Informe de Documentos Electrónicos'
        })

# ========== 6. INFORME DEUDA ==========
def informe_deuda(request, alias):
    """
    Análisis de deuda (basado en ventas pendientes)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    
    try:
        # Considerar ventas en proceso como "deuda por cobrar"
        ventas_pendientes = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            tipo='ventas',
            estado='procesando'  # Pendientes de pago
        )
        
        # Ventas validadas (cobradas)
        ventas_cobradas = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            tipo='ventas',
            estado='validado'
        )
        
        # Estadísticas de deuda
        deuda_total = ventas_pendientes.aggregate(
            cantidad=Count('id'),
            total=Sum('total')
        )
        
        cobrado_total = ventas_cobradas.aggregate(
            cantidad=Count('id'),
            total=Sum('total')
        )
        
        # Por período
        deuda_por_periodo = ventas_pendientes.values('periodo').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('periodo')
        
        # Antigüedad de deuda (simplificado)
        antiguedad_deuda = {
            'menos_30_dias': 0,
            '31_60_dias': 0,
            '61_90_dias': 0,
            'mas_90_dias': 0
        }
        
        # Calcular porcentaje de morosidad
        porcentaje_morosidad = 0
        if (deuda_total['total'] or 0) + (cobrado_total['total'] or 0) > 0:
            porcentaje_morosidad = (deuda_total['total'] or 0) / ((deuda_total['total'] or 0) + (cobrado_total['total'] or 0)) * 100
        
        context = {
            'titulo': 'Informe de Deuda y Morosidad',
            'ventas_pendientes': ventas_pendientes,
            'ventas_cobradas': ventas_cobradas,
            'periodo': periodo,
            'estadisticas': {
                'deuda_total': deuda_total['total'] or 0,
                'cobrado_total': cobrado_total['total'] or 0,
                'facturas_pendientes': deuda_total['cantidad'] or 0,
                'facturas_cobradas': cobrado_total['cantidad'] or 0,
                'porcentaje_morosidad': porcentaje_morosidad,
                'deuda_promedio': (deuda_total['total'] or 0) / (deuda_total['cantidad'] or 1) if (deuda_total['cantidad'] or 0) > 0 else 0
            },
            'deuda_por_periodo': deuda_por_periodo,
            'antiguedad_deuda': antiguedad_deuda,
            'filtros': {
                'periodo': periodo
            }
        }
        
        return render_informe_base(request, alias, 'informe_deuda', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'informe_deuda', {
            'error': str(e),
            'titulo': 'Informe de Deuda'
        })

# ========== 7. INFORME LECTURAS ==========
# informes/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Sum, Count, Avg, Q, Min, Max
from empresas.models import Empresa
from lecturas.models import LecturaMovil

def informe_lecturas(request, alias):
    """
    Informe de lecturas usando el modelo LecturaMovil real
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        # Obtener filtros
        fecha_str = request.GET.get('fecha', '')
        mes_str = request.GET.get('mes', '')
        estado = request.GET.get('estado', '')
        cliente_id = request.GET.get('cliente', '')
        
        # Determinar período de búsqueda
        if fecha_str:
            # Filtro por fecha específica
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            fecha_inicio = fecha
            fecha_fin = fecha
        elif mes_str:
            # Filtro por mes (formato: YYYY-MM)
            year, month = map(int, mes_str.split('-'))
            fecha_inicio = date(year, month, 1)
            if month == 12:
                fecha_fin = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                fecha_fin = date(year, month + 1, 1) - timedelta(days=1)
        else:
            # Por defecto: último mes
            fecha_fin = date.today()
            fecha_inicio = fecha_fin - timedelta(days=30)
        
        # Obtener lecturas
        lecturas = LecturaMovil.objects.filter(
            empresa=empresa,
            fecha_lectura__range=[fecha_inicio, fecha_fin]
        ).order_by('-fecha_lectura', '-fecha_sincronizacion')
        
        # Aplicar filtros adicionales
        if estado:
            lecturas = lecturas.filter(estado=estado)
        
        if cliente_id:
            try:
                cliente_id_int = int(cliente_id)
                lecturas = lecturas.filter(cliente=cliente_id_int)
            except ValueError:
                pass
        
        # Estadísticas
        total_lecturas = lecturas.count()
        lecturas_pendientes = lecturas.filter(estado='pendiente').count()
        lecturas_cargadas = lecturas.filter(estado='cargada').count()
        lecturas_procesadas = lecturas.filter(estado='procesada').count()
        lecturas_usadas = lecturas.filter(usada_para_boleta=True).count()
        
        # Consumo total
        consumo_total = lecturas.filter(consumo__isnull=False).aggregate(
            total=Sum('consumo'),
            promedio=Avg('consumo'),
            maximo=Max('consumo'),
            minimo=Min('consumo')
        )
        
        # Por estado
        lecturas_por_estado = lecturas.values('estado').annotate(
            cantidad=Count('id'),
            consumo_total=Sum('consumo'),
            consumo_promedio=Avg('consumo')
        ).order_by('-cantidad')
        
        # Por fecha (últimos 7 días)
        hoy = date.today()
        ultimos_7_dias = [hoy - timedelta(days=i) for i in range(7)]
        
        lecturas_por_dia = []
        for dia in reversed(ultimos_7_dias):
            lecturas_dia = lecturas.filter(fecha_lectura=dia)
            lecturas_por_dia.append({
                'fecha': dia,
                'total': lecturas_dia.count(),
                'procesadas': lecturas_dia.filter(estado='procesada').count(),
                'consumo': lecturas_dia.filter(consumo__isnull=False).aggregate(
                    total=Sum('consumo')
                )['total'] or 0
            })
        
        # Top 10 clientes con más consumo
        top_consumo = lecturas.values('cliente').annotate(
            total_consumo=Sum('consumo'),
            lecturas=Count('id')
        ).order_by('-total_consumo')[:10]
        
        # Clientes sin lecturas en el período (simulado - necesitarías modelo Cliente)
        # Para esto necesitarías importar el modelo Cliente si existe
        
        # Meses disponibles para filtro
        if lecturas.exists():
            primera_lectura = lecturas.order_by('fecha_lectura').first()
            ultima_lectura = lecturas.order_by('-fecha_lectura').first()
            
            # Generar lista de meses entre primera y última lectura
            meses_disponibles = []
            current_date = primera_lectura.fecha_lectura.replace(day=1)
            end_date = ultima_lectura.fecha_lectura.replace(day=1)
            
            while current_date <= end_date:
                meses_disponibles.append(current_date.strftime('%Y-%m'))
                # Siguiente mes
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
        else:
            meses_disponibles = []
        
        # Estados disponibles para filtro
        estados_disponibles = LecturaMovil.ESTADOS_LECTURA
        
        # Clientes únicos (para filtro)
        clientes_unicos = lecturas.values('cliente').distinct().order_by('cliente')
        
        context = {
            'empresa': empresa,
            'slug': alias,
            'lecturas': lecturas,
            'estadisticas': {
                'total_lecturas': total_lecturas,
                'lecturas_pendientes': lecturas_pendientes,
                'lecturas_cargadas': lecturas_cargadas,
                'lecturas_procesadas': lecturas_procesadas,
                'lecturas_usadas_boleta': lecturas_usadas,
                'consumo_total': consumo_total['total'] or 0,
                'consumo_promedio': consumo_total['promedio'] or 0,
                'consumo_maximo': consumo_total['maximo'] or 0,
                'consumo_minimo': consumo_total['minimo'] or 0,
                'porcentaje_procesadas': (lecturas_procesadas / total_lecturas * 100) if total_lecturas > 0 else 0,
            },
            'lecturas_por_estado': lecturas_por_estado,
            'lecturas_por_dia': lecturas_por_dia,
            'top_consumo': top_consumo,
            'meses_disponibles': meses_disponibles,
            'estados_disponibles': estados_disponibles,
            'clientes_unicos': clientes_unicos,
            'filtros': {
                'fecha': fecha_str,
                'mes': mes_str,
                'estado': estado,
                'cliente': cliente_id,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
            },
            'fecha_generacion': timezone.now(),
            'hoy': date.today(),
        }
        
        return render(request, 'informes/informe_lecturas.html', context)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f'Error al generar informe de lecturas: {str(e)}')
        
        return render(request, 'informes/informe_lecturas.html', {
            'empresa': empresa,
            'slug': alias,
            'lecturas': [],
            'error': str(e),
            'estadisticas': {
                'total_lecturas': 0,
                'lecturas_pendientes': 0,
                'lecturas_cargadas': 0,
                'lecturas_procesadas': 0,
                'lecturas_usadas_boleta': 0,
                'consumo_total': 0,
                'consumo_promedio': 0,
                'consumo_maximo': 0,
                'consumo_minimo': 0,
                'porcentaje_procesadas': 0,
            },
            'filtros': {
                'fecha': '',
                'mes': '',
                'estado': '',
                'cliente': '',
            },
            'fecha_generacion': timezone.now(),
            'hoy': date.today(),
        })

# ========== 8. INFORME SOCIOS ==========
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import date
from django.db.models import Count, Q
from empresas.models import Empresa
from clientes.models import Cliente

def informe_socios(request, alias):
    """
    Informe de socios usando el modelo Cliente
    (Consideramos clientes como socios en este contexto)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        # Obtener filtros
        sector = request.GET.get('sector', '')
        busqueda = request.GET.get('busqueda', '')
        
        # IMPORTANTE: Usar la base de datos correcta
        alias_db = f'db_{alias}'  # ← AGREGAR ESTA LÍNEA
        clientes = Cliente.objects.using(alias_db).all().order_by('nombre')  # ← AGREGAR .using()
        
        # Aplicar filtros
        if sector:
            clientes = clientes.filter(sector__icontains=sector)
        
        if busqueda:
            clientes = clientes.filter(
                Q(nombre__icontains=busqueda) |
                Q(rut__icontains=busqueda) |
                Q(direccion__icontains=busqueda) |
                Q(telefono__icontains=busqueda) |
                Q(email__icontains=busqueda)
            )
        
        # Estadísticas
        total_socios = clientes.count()
        
        # Por sector - usar la misma base de datos
        socios_por_sector = clientes.values('sector').annotate(
            cantidad=Count('id')
        ).order_by('-cantidad')
        
        # Socios con y sin email
        socios_con_email = clientes.exclude(email='').count()
        socios_con_telefono = clientes.exclude(telefono='').count()
        socios_con_coordenadas = clientes.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).count()
        
        # Obtener sectores únicos para filtro - usando la misma base de datos
        sectores_disponibles = clientes.exclude(sector='').values_list(
            'sector', flat=True
        ).distinct().order_by('sector')
        
        # Preparar datos para el template
        socios_data = []
        for cliente in clientes:
            socios_data.append({
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'direccion': cliente.direccion,
                'telefono': cliente.telefono,
                'email': cliente.email,
                'medidor': cliente.medidor,
                'sector': cliente.sector,
                'activo': True,
                'tiene_email': bool(cliente.email),
                'tiene_telefono': bool(cliente.telefono),
                'tiene_coordenadas': cliente.latitude is not None and cliente.longitude is not None,
            })
        
        context = {
            'empresa': empresa,
            'slug': alias,
            'socios': socios_data,
            'sectores': sectores_disponibles,
            'estadisticas': {
                'total_socios': total_socios,
                'socios_con_email': socios_con_email,
                'socios_con_telefono': socios_con_telefono,
                'socios_con_coordenadas': socios_con_coordenadas,
                'porcentaje_con_email': (socios_con_email / total_socios * 100) if total_socios > 0 else 0,
                'porcentaje_con_telefono': (socios_con_telefono / total_socios * 100) if total_socios > 0 else 0,
                'socios_por_sector': list(socios_por_sector),  # ← Convertir a lista
            },
            'filtros': {
                'sector': sector,
                'busqueda': busqueda,
            },
            'fecha_generacion': timezone.now(),
        }
        
        return render(request, 'informes/informe_socios.html', context)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f'Error al generar informe de socios: {str(e)}')
        
        return render(request, 'informes/informe_socios.html', {
            'empresa': empresa,
            'slug': alias,
            'socios': [],
            'sectores': [],
            'error': str(e),
            'estadisticas': {
                'total_socios': 0,
                'socios_con_email': 0,
                'socios_con_telefono': 0,
                'socios_con_coordenadas': 0,
                'porcentaje_con_email': 0,
                'porcentaje_con_telefono': 0,
                'socios_por_sector': [],
            },
            'fecha_generacion': timezone.now(),
        })
# ========== 9. INFORME SUBSIDIOS ==========
def informe_subsidios(request, alias):
    """
    Informe de subsidios (simplificado - basado en retenciones)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    
    try:
        # Usar retenciones como proxy para subsidios
        subsidios = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            tipo='retenciones',  # Retenciones como subsidios
            periodo__startswith=periodo[:4]
        )
        
        # Estadísticas
        total_subsidios = subsidios.aggregate(
            cantidad=Count('id'),
            neto=Sum('neto'),
            iva=Sum('iva'),
            total=Sum('total')
        )
        
        # Por estado
        subsidios_por_estado = subsidios.values('estado').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('estado')
        
        # Por período
        subsidios_por_periodo = subsidios.values('periodo').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('periodo')
        
        context = {
            'titulo': 'Informe de Subsidios (Retenciones)',
            'subsidios': subsidios,
            'periodo': periodo,
            'estadisticas': {
                'total_subsidios': total_subsidios['cantidad'] or 0,
                'valor_total': total_subsidios['total'] or 0,
                'beneficio_promedio': (total_subsidios['total'] or 0) / (total_subsidios['cantidad'] or 1),
                'subsidios_activos': subsidios.filter(estado='validado').count(),
                'subsidios_pendientes': subsidios.filter(estado='procesando').count()
            },
            'subsidios_por_estado': subsidios_por_estado,
            'subsidios_por_periodo': subsidios_por_periodo,
            'filtros': {
                'periodo': periodo
            }
        }
        
        return render_informe_base(request, alias, 'informe_subsidios', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'informe_subsidios', {
            'error': str(e),
            'titulo': 'Informe de Subsidios'
        })

# ========== 10. INFORME CONTABILIDAD ==========
def informe_contabilidad(request, alias):
    """
    Estado financiero completo basado en LibroContable
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    tipo = request.GET.get('tipo', '')
    
    try:
        # Obtener libros contables
        libros = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            periodo__startswith=periodo[:4]  # Filtro por año
        )
        
        if tipo:
            libros = libros.filter(tipo=tipo)
        
        # Calcular balances
        ingresos = libros.filter(tipo='ventas').aggregate(
            neto=Sum('neto'),
            iva=Sum('iva'),
            total=Sum('total')
        )
        
        egresos = libros.filter(tipo='compras').aggregate(
            neto=Sum('neto'),
            iva=Sum('iva'),
            total=Sum('total')
        )
        
        retenciones = libros.filter(tipo='retenciones').aggregate(
            total=Sum('total')
        )
        
        balance = (ingresos['total'] or 0) - (egresos['total'] or 0)
        
        # Por tipo de libro
        por_tipo = libros.values('tipo').annotate(
            cantidad=Count('id'),
            neto_total=Sum('neto'),
            iva_total=Sum('iva'),
            total_general=Sum('total')
        ).order_by('-total_general')
        
        # Por período (mensual)
        por_periodo = libros.values('periodo').annotate(
            ingresos=Sum('total', filter=Q(tipo='ventas')),
            egresos=Sum('total', filter=Q(tipo='compras')),
            balance=Sum('total', filter=Q(tipo='ventas')) - Sum('total', filter=Q(tipo='compras'))
        ).order_by('periodo')
        
        # Estados de procesamiento
        por_estado = libros.values('estado').annotate(
            cantidad=Count('id'),
            total=Sum('total')
        ).order_by('estado')
        
        # Meses disponibles
        meses_disponibles = LibroContable.objects.using(db_alias).filter(
            empresa=empresa
        ).values_list('periodo', flat=True).distinct().order_by('-periodo')
        
        context = {
            'empresa': empresa,
            'slug': alias,
            'libros': libros,
            'meses': ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'],
            'titulo': 'Informe Contable',
            'estadisticas': {
                'total_ingresos': ingresos['total'] or 0,
                'total_egresos': egresos['total'] or 0,
                'total_retenciones': retenciones['total'] or 0,
                'balance': balance,
                'iva_recaudado': ingresos['iva'] or 0,
                'iva_pagado': egresos['iva'] or 0,
                'iva_neto': (ingresos['iva'] or 0) - (egresos['iva'] or 0),
                'libros_procesados': libros.count(),
                'validados': libros.filter(estado='validado').count(),
                'con_errores': libros.filter(estado='error').count()
            },
            'por_tipo': por_tipo,
            'por_periodo': por_periodo,
            'por_estado': por_estado,
            'meses_disponibles': meses_disponibles,
            'filtros': {
                'periodo': periodo,
                'tipo': tipo
            }
        }
        
        return render(request, 'informes/informe_contabilidad.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al generar informe contable: {str(e)}')
        return redirect('dashboard_admin_ssr')

# ========== 11. REGISTRO MACROMEDIDOR ==========
def registro_macromedidor(request, alias):
    """
    Registro de macromedidor (simplificado - métricas financieras)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    db_alias = f'db_{alias}'
    
    # Obtener filtros
    periodo = request.GET.get('periodo', timezone.now().strftime('%Y-%m'))
    
    try:
        # Usar ventas como proxy para consumo de macromedidor
        ventas = LibroContable.objects.using(db_alias).filter(
            empresa=empresa,
            tipo='ventas',
            periodo__startswith=periodo[:4]
        )
        
        # Calcular métricas de "consumo"
        consumo_por_mes = []
        for i in range(1, 13):
            mes = f"{periodo[:4]}-{i:02d}"
            ventas_mes = ventas.filter(periodo=mes).aggregate(
                total=Sum('total'),
                cantidad=Count('id')
            )
            consumo_por_mes.append({
                'mes': mes,
                'consumo': ventas_mes['total'] or 0,
                'lecturas': ventas_mes['cantidad'] or 0
            })
        
        # Totales
        total_consumo = sum(item['consumo'] for item in consumo_por_mes)
        total_lecturas = sum(item['lecturas'] for item in consumo_por_mes)
        
        # Alertas (consumo atípico)
        consumos = [item['consumo'] for item in consumo_por_mes if item['consumo'] > 0]
        promedio_consumo = sum(consumos) / len(consumos) if consumos else 0
        
        alertas = []
        for item in consumo_por_mes:
            if item['consumo'] > promedio_consumo * 1.5 and promedio_consumo > 0:
                alertas.append({
                    'mes': item['mes'],
                    'consumo': item['consumo'],
                    'promedio': promedio_consumo,
                    'variacion': ((item['consumo'] / promedio_consumo) - 1) * 100
                })
        
        context = {
            'titulo': 'Registro de Macromedidor (Métricas Financieras)',
            'consumo_por_mes': consumo_por_mes,
            'periodo': periodo,
            'estadisticas': {
                'total_consumo': total_consumo,
                'total_lecturas': total_lecturas,
                'consumo_promedio_mensual': total_consumo / 12 if total_consumo > 0 else 0,
                'consumo_promedio_lectura': total_consumo / total_lecturas if total_lecturas > 0 else 0,
                'mes_max_consumo': max(consumo_por_mes, key=lambda x: x['consumo']) if consumo_por_mes else None,
                'mes_min_consumo': min(consumo_por_mes, key=lambda x: x['consumo']) if consumo_por_mes else None,
                'alertas_detectadas': len(alertas)
            },
            'alertas': alertas,
            'filtros': {
                'periodo': periodo
            }
        }
        
        return render_informe_base(request, alias, 'registro_macromedidor', context)
        
    except Exception as e:
        return render_informe_base(request, alias, 'registro_macromedidor', {
            'error': str(e),
            'titulo': 'Registro de Macromedidor'
        })

# ========== FUNCIONES AUXILIARES ==========

def render_informe_base(request, alias, template_name, context_extra=None):
    """Renderiza informe con contexto base"""
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
        
        context = {
            'empresa': empresa,
            'slug': alias,
            'fecha_generacion': timezone.now(),
            'periodo': obtener_periodo_default(),
            'usuario': request.user,
        }
        
        if context_extra:
            context.update(context_extra)
        
        return render(request, f'informes/{template_name}.html', context)
        
    except Exception as e:
        messages.error(request, f'Error al cargar informe: {str(e)}')
        return redirect('dashboard_admin_ssr')

def obtener_datos_informe(request, db_alias, tipo_informe):
    """Obtiene datos específicos para cada informe"""
    # Esta función sería llamada desde render_informe para obtener datos
    # específicos según el tipo de informe
    return {}

def exportar_pdf(request, alias, tipo_informe):
    """Exporta informe a PDF"""
    # Implementar generación de PDF
    pass

def exportar_excel(request, alias, tipo_informe):
    """Exporta informe a Excel"""
    # Implementar generación de Excel
    pass

def exportar_csv(request, alias, tipo_informe):
    """Exporta informe a CSV"""
    # Implementar generación de CSV
    pass