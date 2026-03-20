from django.shortcuts import render

# Create your views here.
# empresas/views.py

from django.shortcuts import render
from empresas.models import Empresa
from empresas.multiempresa import registrar_alias
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_superuser)
def dashboard_admin_ssr(request):
    empresas = Empresa.objects.all().order_by('-fecha_creacion')
    empresas_con_estado = []

    for empresa in empresas:
        slug = empresa.slug
        registrar_alias(slug)  # registra alias si falta

        estado = {
            'base_creada': True,
            'alias_registrado': slug in [k.replace('db_', '') for k in settings.DATABASES.keys()],
            'tablas': {},  # podés agregar validaciones reales
            'columnas': {},
        }

        empresas_con_estado.append((empresa, estado))

    return render(request, 'admin_ssr/dashboard.html', {
        'empresas_con_estado': empresas_con_estado
    })
    
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from empresas.models import Empresa
from django.utils import timezone
from datetime import date, timedelta
import os
import json
from django.conf import settings
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth
import calendar
from decimal import Decimal

# Importar modelos de pozos y producción
from empresas.models import Pozo, Produccion

def panel_empresa(request, slug):
    try:
        # 1. Obtener la empresa desde la base de datos DEFAULT
        empresa = Empresa.objects.get(slug=slug)

        # 2. Verificar que la base de datos de la empresa existe
        alias = f'db_{slug}'
        db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')

        if not os.path.exists(db_path):
            messages.error(request, 'La base de datos de la empresa no existe')
            return redirect('dashboard_admin_ssr')

        # 3. Verificar que podemos conectarnos a la BD de la empresa
        try:
            from django.db import connections
            connections[alias].ensure_connection()
        except Exception as e:
            messages.error(request, f'No se puede conectar a la base de datos: {str(e)}')
            return redirect('dashboard_admin_ssr')

        # 4. Importar modelos de la BD de la empresa (clientes, lecturas, etc.)
        from clientes.models import Cliente
        from lecturas.models import LecturaMovil
        from avisos.models import Aviso
        from faq.models import PreguntaFrecuente
        from boletas.models import Boleta

        # ========== DATOS BÁSICOS ==========
        total_clientes = Cliente.objects.using(alias).count()

        ahora = timezone.now()
        mes_actual = ahora.month
        anio_actual = ahora.year
        hoy = ahora.date()

        # Lecturas del mes actual (BD principal)
        lecturas_mes = LecturaMovil.objects.filter(
            fecha_lectura__month=mes_actual,
            fecha_lectura__year=anio_actual,
            empresa_slug=slug
        ).count()

        # Avisos activos
        avisos_activos = Aviso.objects.using(alias).filter(activo=True).count()

        # Preguntas frecuentes
        total_faq = PreguntaFrecuente.objects.using(alias).count()

        # ========== CONSUMO TOTAL MES ==========
        try:
            consumo_total_mes_result = LecturaMovil.objects.filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                consumo__isnull=False
            ).aggregate(total=Sum('consumo'))
            consumo_total_mes = consumo_total_mes_result['total'] or Decimal('0')
        except Exception as e:
            print(f"Error cálculo consumo_total_mes: {e}")
            consumo_total_mes = Decimal('0')

        # ========== VARIACIÓN VS MES ANTERIOR ==========
        try:
            if mes_actual == 1:
                mes_anterior = 12
                anio_anterior = anio_actual - 1
            else:
                mes_anterior = mes_actual - 1
                anio_anterior = anio_actual

            consumo_mes_anterior_result = LecturaMovil.objects.filter(
                fecha_lectura__month=mes_anterior,
                fecha_lectura__year=anio_anterior,
                empresa_slug=slug,
                consumo__isnull=False
            ).aggregate(total=Sum('consumo'))
            consumo_mes_anterior = consumo_mes_anterior_result['total'] or Decimal('0')

            if consumo_mes_anterior > 0:
                variacion_consumo = float(((consumo_total_mes - consumo_mes_anterior) / consumo_mes_anterior) * 100)
            else:
                variacion_consumo = 100.0 if consumo_total_mes > 0 else 0.0
        except Exception as e:
            print(f"Error cálculo variación: {e}")
            variacion_consumo = 0.0

        # ========== ESTADO DE LECTURAS ==========
        try:
            lecturas_completadas = LecturaMovil.objects.filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                estado__in=['cargada', 'procesada']
            ).count()

            lecturas_pendientes = LecturaMovil.objects.filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                estado='pendiente'
            ).count()

            total_lecturas_estado = lecturas_completadas + lecturas_pendientes
            if total_lecturas_estado > 0:
                porcentaje_lecturas_completadas = (lecturas_completadas / total_lecturas_estado) * 100
            else:
                porcentaje_lecturas_completadas = 0
        except Exception as e:
            print(f"Error cálculo estado lecturas: {e}")
            lecturas_completadas = 0
            lecturas_pendientes = 0
            porcentaje_lecturas_completadas = 0

        # ========== TOP 10 CONSUMIDORES ==========
        try:
            top_consumidores_data = LecturaMovil.objects.filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                consumo__isnull=False,
                consumo__gt=0
            ).values('cliente').annotate(
                total_consumo=Sum('consumo')
            ).order_by('-total_consumo')[:10]

            top_consumidores = []
            for item in top_consumidores_data:
                try:
                    cliente = Cliente.objects.using(alias).get(id=item['cliente'])
                    top_consumidores.append({
                        'cliente': cliente,
                        'consumo': item['total_consumo']
                    })
                except Cliente.DoesNotExist:
                    continue

            consumo_top10 = sum(item['consumo'] for item in top_consumidores)
        except Exception as e:
            print(f"Error top consumidores: {e}")
            top_consumidores = []
            consumo_top10 = Decimal('0')

        # ========== CONSUMO HISTÓRICO (últimos 12 meses) ==========
        try:
            fecha_inicio = ahora - timedelta(days=365)
            consumo_por_mes = LecturaMovil.objects.filter(
                fecha_lectura__gte=fecha_inicio,
                empresa_slug=slug,
                consumo__isnull=False
            ).annotate(
                mes=TruncMonth('fecha_lectura')
            ).values('mes').annotate(
                total_consumo=Sum('consumo')
            ).order_by('mes')

            consumo_dict = {}
            for item in consumo_por_mes:
                key = item['mes'].strftime('%Y-%m')
                consumo_dict[key] = float(item['total_consumo'] or 0)

            meses_espanol = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            meses_grafico = []
            consumo_mensual = []

            for i in range(11, -1, -1):
                fecha = ahora - timedelta(days=30 * i)
                mes_num = fecha.month
                anio_num = fecha.year
                mes_nombre = meses_espanol[mes_num - 1]
                anio_corto = str(anio_num)[2:]
                meses_grafico.append(f"{mes_nombre} '{anio_corto}")
                key = f"{anio_num}-{mes_num:02d}"
                consumo_mensual.append(consumo_dict.get(key, 0.0))
        except Exception as e:
            print(f"Error histórico consumo: {e}")
            meses_grafico = []
            consumo_mensual = []

        # ========== DISTRIBUCIÓN POR SECTOR ==========
        try:
            sectores_empresa = empresa.sectores()
            clientes_por_sector = Cliente.objects.using(alias).filter(
                sector__isnull=False
            ).exclude(sector='').values('sector').annotate(
                total=Count('id')
            ).order_by('-total')

            distribucion_sectores = []
            if sectores_empresa:
                for sector in sectores_empresa:
                    encontrado = next((item for item in clientes_por_sector
                                       if item['sector'].strip().lower() == sector.strip().lower()), None)
                    total = encontrado['total'] if encontrado else 0
                    porcentaje = (total / total_clientes * 100) if total_clientes > 0 else 0
                    distribucion_sectores.append({
                        'tipo': sector,
                        'total': total,
                        'porcentaje': round(porcentaje, 1)
                    })
            else:
                for item in clientes_por_sector:
                    sector = item['sector']
                    total = item['total']
                    porcentaje = (total / total_clientes * 100) if total_clientes > 0 else 0
                    distribucion_sectores.append({
                        'tipo': sector,
                        'total': total,
                        'porcentaje': round(porcentaje, 1)
                    })

            if len(distribucion_sectores) > 5:
                top_5 = distribucion_sectores[:5]
                otros_total = sum(item['total'] for item in distribucion_sectores[5:])
                otros_porcentaje = sum(item['porcentaje'] for item in distribucion_sectores[5:])
                distribucion_sectores = top_5 + [{
                    'tipo': 'Otros',
                    'total': otros_total,
                    'porcentaje': round(otros_porcentaje, 1)
                }]
        except Exception as e:
            print(f"Error distribución sectores: {e}")
            distribucion_sectores = []

        # ========== TENDENCIA ANUAL ==========
        try:
            tendencia_consumo = consumo_mensual[-12:] if consumo_mensual else []
            tendencia_lecturas = []
            for i in range(11, -1, -1):
                fecha = ahora - timedelta(days=30 * i)
                mes_num = fecha.month
                anio_num = fecha.year
                lecturas_mes_historico = LecturaMovil.objects.filter(
                    fecha_lectura__month=mes_num,
                    fecha_lectura__year=anio_num,
                    empresa_slug=slug,
                    estado__in=['cargada', 'procesada']
                ).count()
                tendencia_lecturas.append(lecturas_mes_historico)
        except Exception as e:
            print(f"Error tendencia: {e}")
            tendencia_consumo = []
            tendencia_lecturas = []

        # ========== CONSUMO PROMEDIO POR CLIENTE ==========
        try:
            if total_clientes > 0:
                consumo_promedio = float(consumo_total_mes) / total_clientes
            else:
                consumo_promedio = 0
        except:
            consumo_promedio = 0

        # ========== RENDIMIENTO DEL MES ==========
        dia_actual = hoy.day
        dias_en_mes = calendar.monthrange(anio_actual, mes_actual)[1]
        rendimiento_mes = (dia_actual / dias_en_mes) * 100

        # ========== CLIENTES CON COORDENADAS PARA EL MAPA ==========
        puntos_clientes = []
        try:
            clientes_con_ubicacion = Cliente.objects.using(alias).filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).exclude(latitude=0, longitude=0)
            for c in clientes_con_ubicacion:
                puntos_clientes.append({
                    'id': c.id,
                    'nombre': c.nombre,
                    'lat': float(c.latitude),
                    'lng': float(c.longitude),
                    'medidor': c.medidor,
                    'direccion': c.direccion,
                })
        except Exception as e:
            print(f"Error obteniendo clientes con coordenadas: {e}")
            puntos_clientes = []

        # ========== POZOS Y PRODUCCIÓN ==========
        total_pozos = Pozo.objects.filter(empresa=empresa, activo=True).count()
        pozos = Pozo.objects.filter(empresa=empresa, activo=True).order_by('nombre')

        # Producción mensual últimos 12 meses (total)
        try:
            fecha_inicio_prod = ahora - timedelta(days=365)
            produccion_por_mes = Produccion.objects.filter(
                empresa=empresa,
                fecha__gte=fecha_inicio_prod
            ).annotate(
                mes=TruncMonth('fecha')
            ).values('mes').annotate(
                total_produccion=Sum('volumen')
            ).order_by('mes')

            prod_dict = {}
            for item in produccion_por_mes:
                key = item['mes'].strftime('%Y-%m')
                prod_dict[key] = float(item['total_produccion'] or 0)

            meses_produccion = []
            produccion_mensual = []
            for i in range(11, -1, -1):
                fecha = ahora - timedelta(days=30 * i)
                mes_num = fecha.month
                anio_num = fecha.year
                mes_nombre = calendar.month_abbr[mes_num]
                anio_corto = str(anio_num)[2:]
                meses_produccion.append(f"{mes_nombre} '{anio_corto}")
                key = f"{anio_num}-{mes_num:02d}"
                produccion_mensual.append(prod_dict.get(key, 0.0))

            # Producción por pozo individual (para el filtro)
            produccion_por_pozo = {}
            for pozo in pozos:
                try:
                    prod_pozo = Produccion.objects.filter(
                        empresa=empresa,
                        pozo=pozo,
                        fecha__gte=fecha_inicio_prod
                    ).annotate(
                        mes=TruncMonth('fecha')
                    ).values('mes').annotate(
                        total=Sum('volumen')
                    ).order_by('mes')

                    prod_dict_pozo = {}
                    for item in prod_pozo:
                        key = item['mes'].strftime('%Y-%m')
                        prod_dict_pozo[key] = float(item['total'] or 0)

                    serie = []
                    for i in range(11, -1, -1):
                        fecha = ahora - timedelta(days=30*i)
                        key = f"{fecha.year}-{fecha.month:02d}"
                        serie.append(prod_dict_pozo.get(key, 0.0))
                    produccion_por_pozo[str(pozo.id)] = serie
                except Exception as e:
                    produccion_por_pozo[str(pozo.id)] = [0.0]*12
        except Exception as e:
            print(f"Error obteniendo producción mensual: {e}")
            meses_produccion = []
            produccion_mensual = []
            produccion_por_pozo = {}

        # ========== HELPERS (AJUSTADOS PARA USAR BD PRINCIPAL EN LECTURAS) ==========
        from .helpers import (
            obtener_certificado_firma,
            obtener_estado_folios,
            obtener_tasa_interes,
            obtener_reajuste_sii,
            obtener_contratos_corte,
            obtener_detalle_recaudacion,
            obtener_produccion_consumo,
            obtener_puntos_lectura
        )

        try:
            firma = obtener_certificado_firma()
        except Exception as e:
            print(f"Error helper firma: {e}")
            firma = None

        try:
            folios = obtener_estado_folios()
        except Exception as e:
            print(f"Error helper folios: {e}")
            folios = []

        try:
            interes = obtener_tasa_interes()
        except Exception as e:
            print(f"Error helper interés: {e}")
            interes = None

        try:
            reajuste = obtener_reajuste_sii()
        except Exception as e:
            print(f"Error helper reajuste: {e}")
            reajuste = None

        try:
            contratos_corte = obtener_contratos_corte(alias)
        except Exception as e:
            print(f"Error helper contratos corte: {e}")
            contratos_corte = []

        try:
            pagos = obtener_detalle_recaudacion(alias, date.today())
        except Exception as e:
            print(f"Error helper recaudación: {e}")
            pagos = []

        try:
            meses, produccion, consumo = obtener_produccion_consumo(alias)
        except Exception as e:
            print(f"Error helper producción/consumo: {e}")
            meses, produccion, consumo = [], [], []

        try:
            puntos_lectura = obtener_puntos_lectura(alias)
        except Exception as e:
            print(f"Error helper puntos lectura: {e}")
            puntos_lectura = []

        # ========== PREPARAR TOP CONSUMIDORES ==========
        top_consumidores_template = []
        for idx, item in enumerate(top_consumidores[:10], 1):
            cliente = item['cliente']
            consumo_cliente = item['consumo']
            porcentaje_total = (float(consumo_cliente) / float(consumo_total_mes) * 100) if consumo_total_mes > 0 else 0
            top_consumidores_template.append({
                'posicion': idx,
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'sector': cliente.sector or 'Sin sector',
                'consumo': float(consumo_cliente),
                'porcentaje': round(porcentaje_total, 1)
            })

        # ========== PREPARAR SECTORES PARA JSON ==========
        colores_base = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#f97316']
        sectores_para_json = []
        for idx, item in enumerate(distribucion_sectores):
            color_idx = idx % len(colores_base)
            sectores_para_json.append({
                'tipo': item['tipo'],
                'total': item['total'],
                'porcentaje': item['porcentaje'],
                'color': colores_base[color_idx]
            })

        # ========== CONTEXTO FINAL ==========
        context = {
            'empresa': empresa,
            'slug': slug,
            'total_clientes': total_clientes,
            'lecturas_mes': lecturas_mes,
            'avisos_activos': avisos_activos,
            'total_faq': total_faq,
            'firma': firma,
            'folios': folios,
            'interes': interes,
            'reajuste': reajuste,
            'contratos_corte': contratos_corte,
            'pagos': pagos,
            'mes_actual': date.today().strftime("%B %Y").capitalize(),
            'meses': meses,
            'produccion': produccion,
            'consumo': consumo,
            'puntos_lectura': puntos_lectura,
            'db_existe': os.path.exists(db_path),
            'pozos': pozos,
            'consumo_total_mes': float(consumo_total_mes),
            'variacion_consumo': round(variacion_consumo, 1),
            'porcentaje_lecturas_completadas': round(porcentaje_lecturas_completadas, 0),
            'lecturas_completadas': lecturas_completadas,
            'lecturas_pendientes': lecturas_pendientes,
            'hora_pico_consumo': "10:00",
            'consumo_top10': float(consumo_top10),
            'top_consumidores': top_consumidores_template,
            'meses_grafico': json.dumps(meses_grafico),
            'consumo_mensual': json.dumps(consumo_mensual),
            'distribucion_sectores': json.dumps(sectores_para_json),
            'tendencia_consumo': json.dumps(tendencia_consumo),
            'tendencia_lecturas': json.dumps(tendencia_lecturas),
            'consumo_promedio': round(consumo_promedio, 2),
            'rendimiento_mes': round(rendimiento_mes, 1),

            'hoy': hoy,
            'dia_actual': dia_actual,
            'dias_en_mes': dias_en_mes,
            'sectores_empresa': empresa.sectores(),

            'puntos_clientes': json.dumps(puntos_clientes),
            'total_clientes_mapa': len(puntos_clientes),

            # Nuevas variables para pozos y producción
            'total_pozos': total_pozos,
            'meses_produccion': json.dumps(meses_produccion),
            'produccion_mensual': json.dumps(produccion_mensual),
            'consumo_produccion': json.dumps(consumo_mensual),
            'produccion_por_pozo_json': json.dumps(produccion_por_pozo),
        }

        return render(request, 'admin_ssr/panel_empresa.html', context)

    except Empresa.DoesNotExist:
        messages.error(request, f'La empresa "{slug}" no existe')
        return redirect('dashboard_admin_ssr')
    except Exception as e:
        messages.error(request, f'Error al acceder al panel: {str(e)}')
        import traceback
        print(f"Error completo: {traceback.format_exc()}")
        return redirect('dashboard_admin_ssr')


def agregar_produccion(request, slug):
    """
    Vista para registrar una nueva producción desde el modal del panel.
    """
    if request.method == 'POST':
        try:
            empresa = Empresa.objects.get(slug=slug)
            pozo_id = request.POST.get('pozo')
            fecha = request.POST.get('fecha')
            volumen = request.POST.get('volumen')
            observacion = request.POST.get('observacion', '')

            if not all([pozo_id, fecha, volumen]):
                messages.error(request, 'Todos los campos son obligatorios')
                return redirect('panel_empresa', slug=slug)

            pozo = Pozo.objects.get(id=pozo_id, empresa=empresa)

            Produccion.objects.create(
                empresa=empresa,
                pozo=pozo,
                fecha=fecha,
                volumen=volumen,
                observacion=observacion
            )
            messages.success(request, 'Producción registrada correctamente')
        except Pozo.DoesNotExist:
            messages.error(request, 'El pozo seleccionado no existe')
        except Exception as e:
            messages.error(request, f'Error al registrar producción: {str(e)}')

        return redirect('panel_empresa', slug=slug)
    else:
        return redirect('panel_empresa', slug=slug)

from lecturas.models import LecturaMovil

def obtener_puntos_lectura(alias):
    """
    CORRECCIÓN: Usar LecturaMovil en lugar de Lectura
    """
    from lecturas.models import LecturaMovil
    from clientes.models import Cliente
    from django.utils import timezone
    
    # Obtener clientes con coordenadas
    clientes = Cliente.objects.using(alias).filter(
        latitude__isnull=False,
        longitude__isnull=False
    )
    
    puntos = []
    hoy = timezone.now()
    
    for cliente in clientes:
        # Buscar la lectura más reciente de este cliente
        lectura = LecturaMovil.objects.using(alias).filter(
            cliente=cliente
        ).order_by('-fecha_lectura').first()
        
        # Determinar estado por lógica
        if lectura:
            if lectura.fecha_lectura.month == hoy.month:
                estado = "Normal"
            else:
                estado = "Término medio"
        else:
            estado = "Faltante"
        
        puntos.append({
            "id": cliente.id,
            "nombre": cliente.nombre,
            "lat": cliente.latitude,
            "lng": cliente.longitude,
            "estado": estado,
            "medidor": cliente.medidor or "",
            "ultima_lectura": lectura.fecha_lectura if lectura else "Nunca"
        })
    
    return puntos


from django.http import JsonResponse
from lecturas.models import LecturaMovil

def api_lecturas_mapa(request, slug):
    alias = f'db_{slug}'
    lecturas = Lectura.objects.using(alias).filter(
        cliente__latitude__isnull=False,
        cliente__longitude__isnull=False
    ).select_related("cliente")

    puntos = []
    for l in lecturas:
        if l.valor:
            estado = "Normal"
        else:
            estado = "Faltante"

        puntos.append({
            "id": l.cliente.id,
            "nombre": l.cliente.nombre,
            "lat": float(l.cliente.latitude),
            "lng": float(l.cliente.longitude),
            "estado": estado
        })

    return JsonResponse(puntos, safe=False)


from django.shortcuts import render, redirect
from empresas.models import Empresa
from django.utils.text import slugify
from empresas.multiempresa import registrar_alias
from django.conf import settings
import os, json

def actualizar_alias_json():
    slugs = list(Empresa.objects.values_list('slug', flat=True))
    ruta_json = os.path.join(os.path.dirname(settings.__file__), 'empresas_alias.json')
    with open(ruta_json, 'w') as f:
        json.dump(slugs, f, indent=2)

import json
import os
from django.conf import settings
from django.shortcuts import render, redirect
from django.utils.text import slugify
from empresas.models import Empresa
from django.contrib import messages

# Importar funciones de multiempresa
try:
    from .multiempresa import (
        registrar_alias,
        verificar_migraciones_aplicadas,
        crear_tabla_lecturas_manual
    )
except ImportError:
    # Fallback si no encuentra en el mismo directorio
    from admin_ssr.multiempresa import (
        registrar_alias,
        verificar_migraciones_aplicadas,
        crear_tabla_lecturas_manual
    )

def crear_empresa(request):
    if request.method == 'POST':
        # === CAMPOS EXISTENTES ===
        nombre = request.POST.get('nombre')
        slug = slugify(nombre)
        
        # === NUEVOS CAMPOS ===
        rut = request.POST.get('rut', '')
        direccion = request.POST.get('direccion', '')
        telefono = request.POST.get('telefono', '')
        celular = request.POST.get('celular', '')
        logo = request.FILES.get('logo')
        
        # Centros de costo (NUEVO)
        centros_costo_raw = request.POST.get('centros_costo', '')
        centros_costo = [c.strip() for c in centros_costo_raw.split(',') if c.strip()]
        
        # Sectores (existente)
        sectores_raw = request.POST.get('sectores', '')
        sectores = [s.strip() for s in sectores_raw.split(',') if s.strip()]
        
        # Colores personalizados
        color_app_primario = request.POST.get('color_app_primario', '#1E40AF')
        color_app_secundario = request.POST.get('color_app_secundario', '#DC2626')
        url_servidor = request.POST.get('url_servidor', 'http://localhost:8000')
        color_dashboard = request.POST.get('color_dashboard', '#008000')
        
        # Logo
        logo_app = request.FILES.get('logo_app')

        # Validar que no exista
        if Empresa.objects.filter(slug=slug).exists():
            messages.error(request, 'Ya existe una empresa con ese nombre')
            return render(request, 'admin_ssr/crear_empresa.html')

        try:
            # ============================================
            # PASO 1: Crear empresa en base general
            # ============================================
            # IMPORTANTE: Comenta estos campos si aún no los agregas al modelo
            empresa = Empresa.objects.create(
                nombre=nombre,
                slug=slug,
                # Comentar hasta agregar campos al modelo
                rut=rut,
                direccion=direccion,
                telefono=telefono,
                celular=celular,
                logo=logo,
                sectores_json=json.dumps(sectores),
                color_app_primario=color_app_primario,
                color_app_secundario=color_app_secundario,
                url_servidor=url_servidor,
                color_dashboard=color_dashboard,
                logo_app=logo_app if logo_app else None,
            )

            # ============================================
            # PASO 2: Registrar alias usando multiempresa
            # ============================================
            alias = registrar_alias(slug, ejecutar_migraciones=True)
            
            print(f"[SSR] Empresa creada: {nombre}")
            print(f"[SSR] Slug: {slug}")
            print(f"[SSR] Alias BD: {alias}")
            print(f"[SSR] Centros de costo: {centros_costo}")
            print(f"[SSR] Sectores: {sectores}")

            # ============================================
            # PASO 3: Insertar configuración inicial en BD de la empresa
            # ============================================
            from django.db import connections
            
            try:
                # Conectar a la base de datos de la empresa
                connection = connections[alias]
                
                with connection.cursor() as cursor:
                    # Verificar que existe la tabla configuracion
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='configuracion'
                    """)
                    
                    if not cursor.fetchone():
                        # Crear tabla configuracion si no existe
                        cursor.execute("""
                            CREATE TABLE configuracion (
                                clave TEXT PRIMARY KEY,
                                valor TEXT
                            )
                        """)
                    
                    # Insertar configuración inicial - CORREGIDO: pasar parámetros como tupla
                    config_inicial = [
                        ('nombre_empresa', nombre),
                        ('logo', logo),
                        ('rut_empresa', rut),
                        ('direccion_empresa', direccion),
                        ('telefono_empresa', telefono),
                        ('celular_empresa', celular),
                        ('centros_costo', json.dumps(centros_costo, ensure_ascii=False)),
                        ('sectores', json.dumps(sectores, ensure_ascii=False)),
                        ('color_primario', color_app_primario),
                        ('color_secundario', color_app_secundario),
                        ('url_servidor', url_servidor),
                    ]
                    
                    for clave, valor in config_inicial:
                        # CORREGIDO: Pasar como tupla (?, ?) con dos elementos
                        cursor.execute(
                            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
                            (clave, valor)  # ¡Esto es una tupla de 2 elementos!
                        )
                    
                    # Si hay centros de costo, también crear una tabla específica
                    if centros_costo:
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS centros_costo (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                codigo TEXT UNIQUE,
                                nombre TEXT,
                                activo BOOLEAN DEFAULT 1,
                                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        
                        # Insertar centros de costo
                        for centro in centros_costo:
                            codigo = centro.replace(' ', '_').replace('-', '_').upper()
                            # CORREGIDO: Pasar como tupla (?, ?)
                            cursor.execute(
                                "INSERT OR IGNORE INTO centros_costo (codigo, nombre) VALUES (?, ?)",
                                (codigo, centro)  # Tupla de 2 elementos
                            )
                    
                    # Guardar cambios
                    connection.commit()
                
                connection.close()
                print(f"[SSR] Configuración insertada correctamente en {alias}")
                
            except Exception as e:
                print(f"[SSR] Error insertando configuración: {e}")
                import traceback
                traceback.print_exc()

            # ============================================
            # PASO 4: Verificar migraciones
            # ============================================
            try:
                verificar_migraciones_aplicadas(alias)
            except Exception as e:
                print(f"[SSR] Error verificando migraciones: {e}")
                
                # Si la app 'lecturas' falla, crear tabla manualmente
                try:
                    from django.db import connections
                    crear_tabla_lecturas_manual(alias)
                except Exception as e2:
                    print(f"[SSR] Error creando tabla manual: {e2}")

            # ============================================
            # PASO 5: Actualizar archivo de aliases JSON
            # ============================================
            aliases_file = getattr(settings, 'ALIASES_FILE', 
                                  os.path.join(settings.BASE_DIR, 'config', 'database_aliases.json'))
            
            os.makedirs(os.path.dirname(aliases_file), exist_ok=True)
            
            aliases = {}
            if os.path.exists(aliases_file):
                with open(aliases_file, 'r', encoding='utf-8') as f:
                    aliases = json.load(f)
            
            aliases[slug] = {
                'alias': alias,
                'nombre': nombre,
                'rut': rut,
                'direccion': direccion,
                'telefono': telefono,
                'celular': celular,
                'centros_costo': centros_costo,
                'sectores': sectores,
                'db_path': os.path.join(settings.BASES_DIR, f'{alias}.sqlite3'),
                'fecha_creacion': empresa.fecha_creacion.isoformat() if empresa.fecha_creacion else None
            }
            
            with open(aliases_file, 'w', encoding='utf-8') as f:
                json.dump(aliases, f, indent=2, ensure_ascii=False)
            
            messages.success(request, f'Empresa {nombre} creada exitosamente con {len(centros_costo)} centro(s) de costo')
            return redirect('dashboard_admin_ssr')
            
        except Exception as e:
            # Revertir en caso de error
            if 'empresa' in locals():
                try:
                    empresa.delete()
                except:
                    pass
            
            import traceback
            error_detallado = traceback.format_exc()
            print(f"[SSR] ERROR CRÍTICO: {error_detallado}")
            
            messages.error(request, f'Error al crear empresa: {str(e)}')
            return render(request, 'admin_ssr/crear_empresa.html')

    return render(request, 'admin_ssr/crear_empresa.html')

def verificar_empresa_activa(slug):
    """Verifica si una empresa tiene todos sus recursos creados"""
    empresa = Empresa.objects.filter(slug=slug).first()
    if not empresa:
        return False
    
    # Verificar base de datos física
    alias = f'db_{slug}'
    db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
    
    if not os.path.exists(db_path):
        return False
    
    # Verificar alias en JSON
    alias_json_path = os.path.join(settings.BASE_DIR, 'asesora_ssr', 'empresas_alias.json')
    if os.path.exists(alias_json_path):
        with open(alias_json_path, 'r') as f:
            aliases = json.load(f)
        if slug not in aliases:
            return False
    
    return True

import json
import os
from django.conf import settings

def actualizar_alias_json():
    from empresas.models import Empresa
    slugs = list(Empresa.objects.values_list('slug', flat=True))
    ruta_json = os.path.join(settings.BASE_DIR, 'asesora_ssr', 'empresas_alias.json')

    with open(ruta_json, 'w') as f:
        json.dump(slugs, f, indent=2)


from django.contrib.auth.models import User

def crear_admin_empresa(request, slug):
    if request.method == 'POST' and request.user.is_superuser:
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        password = User.objects.make_random_password()

        usuario = User.objects.create_user(username=slug, email=email, password=password)
        usuario.first_name = nombre
        usuario.save()

        # (Opcional) mostrar credenciales o enviarlas por email
        return redirect('dashboard_admin_ssr')

    return render(request, 'admin_ssr/crear_admin.html', {'slug': slug})



import os
import json
import time
import shutil
import traceback
from datetime import datetime
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Empresa, EliminacionEmpresa

def cerrar_conexiones_archivo(ruta_archivo, max_intentos=3):
    """
    Intenta cerrar y eliminar un archivo que está siendo usado.
    """
    for intento in range(max_intentos):
        try:
            if os.path.exists(ruta_archivo):
                os.remove(ruta_archivo)
                return True, f"Archivo eliminado en intento {intento + 1}"
            else:
                return True, "Archivo no existe"
        except PermissionError:
            if intento < max_intentos - 1:
                print(f"[SSR] Intento {intento + 1} fallado, esperando...")
                time.sleep(1)  # Esperar 1 segundo
            else:
                # Último intento: renombrar el archivo
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nuevo_nombre = f"{ruta_archivo}.eliminado_{timestamp}"
                    os.rename(ruta_archivo, nuevo_nombre)
                    return True, f"Archivo renombrado a {nuevo_nombre}"
                except Exception as e:
                    return False, f"No se pudo eliminar ni renombrar: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    return False, "Máximo de intentos alcanzado"

def obtener_info_empresa_segura(empresa):
    """
    Obtiene información de la empresa de forma segura, usando getattr.
    """
    info = {
        'nombre': empresa.nombre,
        'slug': empresa.slug,
    }
    
    # Campos que podrían no existir en el modelo
    campos_opcionales = ['ruc', 'direccion', 'telefono', 'email', 'fecha_creacion']
    
    for campo in campos_opcionales:
        if hasattr(empresa, campo):
            valor = getattr(empresa, campo)
            if campo == 'fecha_creacion' and valor:
                info[campo] = valor.isoformat()
            else:
                info[campo] = valor
        else:
            info[campo] = None
    
    return info

@login_required
def eliminar_empresa(request, slug):
    """
    Elimina una empresa y todos sus datos asociados.
    """
    # ===== VERIFICAR PERMISOS =====
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para eliminar empresas.')
        return redirect('dashboard_admin_ssr')
    
    empresa = get_object_or_404(Empresa, slug=slug)
    
    # ===== SI ES GET, MOSTRAR CONFIRMACIÓN =====
    if request.method != 'POST':
        # Preparar información básica para mostrar
        alias = f'db_{slug}'
        db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
        
        context = {
            'empresa': empresa,
            'bd_existe': os.path.exists(db_path),
            'bd_tamano': f"{os.path.getsize(db_path) / 1024:.1f} KB" if os.path.exists(db_path) else 'No existe',
        }
        return render(request, 'empresas/confirmar_eliminacion.html', context)
    
    # ===== INICIO PROCESO DE ELIMINACIÓN =====
    alias = f'db_{slug}'
    nombre_empresa = empresa.nombre
    logs = []
    
    try:
        logs.append(f"=== ELIMINACIÓN EMPRESA: {nombre_empresa} ({slug}) ===")
        logs.append(f"Iniciada por: {request.user.username}")
        logs.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logs.append("=" * 50)
        
        # ===== PASO 1: REMOVER DE CONFIGURACIÓN =====
        logs.append("\n[1] Removiendo configuración...")
        
        # Remover de settings.DATABASES si existe
        if alias in settings.DATABASES:
            del settings.DATABASES[alias]
            logs.append("  ✓ Removido de settings.DATABASES")
        else:
            logs.append("  ℹ️  No estaba en settings.DATABASES")
        
        # Remover de empresas_alias.json si existe
        alias_json_path = os.path.join(settings.BASE_DIR, 'asesora_ssr', 'empresas_alias.json')
        if os.path.exists(alias_json_path):
            try:
                with open(alias_json_path, 'r') as f:
                    aliases = json.load(f)
                
                if slug in aliases:
                    aliases.remove(slug)
                    
                with open(alias_json_path, 'w') as f:
                    json.dump(aliases, f, indent=2)
                logs.append("  ✓ Removido de empresas_alias.json")
            except Exception as e:
                logs.append(f"  ⚠️  Error actualizando JSON: {str(e)}")
        
        # ===== PASO 2: ELIMINAR BASE DE DATOS =====
        logs.append("\n[2] Eliminando base de datos...")
        
        db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
        archivos_bd = [
            db_path,
            db_path + '-wal',
            db_path + '-shm',
            db_path.replace('.sqlite3', '.db'),
        ]
        
        eliminados = 0
        for archivo in archivos_bd:
            if os.path.exists(archivo):
                success, mensaje = cerrar_conexiones_archivo(archivo)
                if success:
                    eliminados += 1
                    logs.append(f"  ✓ {os.path.basename(archivo)}: {mensaje}")
                else:
                    logs.append(f"  ✗ {os.path.basename(archivo)}: {mensaje}")
            else:
                logs.append(f"  ℹ️  {os.path.basename(archivo)} no existe")
        
        logs.append(f"  Resumen: {eliminados}/{len(archivos_bd)} archivos eliminados")
        
        # ===== PASO 3: ELIMINAR DIRECTORIOS =====
        logs.append("\n[3] Eliminando directorios...")
        
        directorios = {
            'app_movil': os.path.join(settings.BASE_DIR, 'apps_moviles', 'apps_generadas', slug),
            'media': os.path.join(settings.MEDIA_ROOT, 'empresas', slug),
            'logos': os.path.join(settings.MEDIA_ROOT, 'logos', slug),
        }
        
        directorios_eliminados = 0
        for nombre, ruta in directorios.items():
            if os.path.exists(ruta):
                try:
                    # Contar archivos antes de eliminar
                    archivos = 0
                    for root, dirs, files in os.walk(ruta):
                        archivos += len(files)
                    
                    shutil.rmtree(ruta)
                    directorios_eliminados += 1
                    logs.append(f"  ✓ {nombre}: {archivos} archivos eliminados")
                except Exception as e:
                    logs.append(f"  ✗ {nombre}: Error {str(e)}")
            else:
                logs.append(f"  ℹ️  {nombre}: No existe")
        
        logs.append(f"  Resumen: {directorios_eliminados}/{len(directorios)} directorios eliminados")
        
        # ===== PASO 4: ELIMINAR ARCHIVOS DE LOG =====
        logs.append("\n[4] Eliminando archivos de log...")
        
        archivos_log = [
            os.path.join(settings.BASES_DIR, f'{slug}_log.txt'),
            os.path.join(settings.BASE_DIR, 'logs', f'{slug}.log'),
        ]
        
        logs_eliminados = 0
        for log_file in archivos_log:
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                    logs_eliminados += 1
                    logs.append(f"  ✓ {os.path.basename(log_file)} eliminado")
                except Exception as e:
                    logs.append(f"  ✗ {os.path.basename(log_file)}: Error {str(e)}")
            else:
                logs.append(f"  ℹ️  {os.path.basename(log_file)} no existe")
        
        # ===== PASO 5: REGISTRAR AUDITORÍA (ANTES de eliminar empresa) =====
        logs.append("\n[5] Registrando auditoría...")
        
        try:
            # Obtener información de la empresa de forma segura
            empresa_info = obtener_info_empresa_segura(empresa)
            
            eliminacion_registro = EliminacionEmpresa.objects.create(
                nombre=nombre_empresa,
                slug=slug,
                ejecutado_por=request.user.username,
                completado=True,
                detalles=json.dumps({
                    'empresa_info': empresa_info,
                    'archivos_bd_eliminados': eliminados,
                    'directorios_eliminados': directorios_eliminados,
                    'logs_eliminados': logs_eliminados,
                    'fecha_eliminacion': datetime.now().isoformat(),
                    'logs': logs
                }, ensure_ascii=False, indent=2)
            )
            logs.append(f"  ✓ Registro creado (ID: {eliminacion_registro.id})")
        except Exception as e:
            logs.append(f"  ⚠️  Error creando auditoría: {str(e)}")
            # Continuar aunque falle la auditoría
        
        # ===== PASO 6: ELIMINAR REGISTRO DE EMPRESA =====
        logs.append("\n[6] Eliminando registro de empresa...")
        
        try:
            with transaction.atomic():
                # Guardar información antes de eliminar (para logs)
                empresa_info_final = obtener_info_empresa_segura(empresa)
                
                # Eliminar empresa
                empresa.delete()
                logs.append(f"  ✓ Empresa eliminada de la base de datos")
                logs.append(f"  Información eliminada: {json.dumps(empresa_info_final, ensure_ascii=False)}")
        except Exception as e:
            logs.append(f"  ❌ Error eliminando empresa: {str(e)}")
            raise
        
        # ===== FINALIZAR =====
        logs.append("\n" + "=" * 50)
        logs.append("✅ ELIMINACIÓN COMPLETADA EXITOSAMENTE")
        logs.append(f"Resumen final:")
        logs.append(f"  • Archivos BD: {eliminados}/{len(archivos_bd)}")
        logs.append(f"  • Directorios: {directorios_eliminados}/{len(directorios)}")
        logs.append(f"  • Logs: {logs_eliminados}/{len(archivos_log)}")
        logs.append(f"  • Empresa: {nombre_empresa}")
        logs.append("=" * 50)
        
        # Guardar logs en archivo
        try:
            log_dir = os.path.join(settings.BASE_DIR, 'logs', 'eliminaciones')
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, f'eliminacion_{slug}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(logs))
            
            print(f"[SSR] Log guardado en: {log_file}")
        except Exception as e:
            print(f"[SSR] Error guardando log: {e}")
        
        # Mostrar logs en consola
        print("\n".join(logs))
        
        # Mensaje de éxito para el usuario
        messages.success(request, f'Empresa "{nombre_empresa}" eliminada exitosamente.')
        
    except Exception as e:
        # ===== MANEJO DE ERRORES =====
        error_traceback = traceback.format_exc()
        
        logs.append("\n" + "=" * 50)
        logs.append("❌ ERROR EN ELIMINACIÓN")
        logs.append(f"Tipo: {type(e).__name__}")
        logs.append(f"Mensaje: {str(e)}")
        logs.append("\nTraceback completo:")
        logs.append(error_traceback)
        logs.append("=" * 50)
        
        # Registrar error en auditoría
        try:
            empresa_info = obtener_info_empresa_segura(empresa)
            
            EliminacionEmpresa.objects.create(
                nombre=nombre_empresa,
                slug=slug,
                ejecutado_por=request.user.username,
                completado=False,
                error=f"{type(e).__name__}: {str(e)[:200]}",
                detalles=json.dumps({
                    'empresa_info': empresa_info,
                    'error_traceback': error_traceback,
                    'fecha_error': datetime.now().isoformat(),
                    'logs': logs
                }, ensure_ascii=False, indent=2)
            )
        except:
            pass
        
        # Guardar log de error
        try:
            log_dir = os.path.join(settings.BASE_DIR, 'logs', 'eliminaciones')
            os.makedirs(log_dir, exist_ok=True)
            
            log_file = os.path.join(log_dir, f'error_{slug}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(logs))
        except:
            pass
        
        # Mostrar error al usuario
        messages.error(request, f'Error al eliminar empresa "{nombre_empresa}": {type(e).__name__}: {str(e)}')
        
        # Mostrar logs en consola
        print("\n".join(logs))
    
    return redirect('dashboard_admin_ssr')

# ===== FUNCIONES AUXILIARES =====

def obtener_datos_empresa(empresa):
    """
    Obtiene información para mostrar en la confirmación.
    """
    datos = {
        'nombre': empresa.nombre,
        'slug': empresa.slug,
    }
    
    # Campos opcionales
    campos = ['ruc', 'direccion', 'telefono', 'email', 'fecha_creacion']
    for campo in campos:
        if hasattr(empresa, campo):
            valor = getattr(empresa, campo)
            if campo == 'fecha_creacion' and valor:
                datos[campo] = valor.strftime('%d/%m/%Y')
            else:
                datos[campo] = valor or 'No especificado'
        else:
            datos[campo] = 'No disponible'
    
    # Verificar base de datos
    alias = f'db_{empresa.slug}'
    db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
    
    if os.path.exists(db_path):
        try:
            tamano = os.path.getsize(db_path)
            datos['bd_existe'] = True
            datos['bd_tamano'] = f"{tamano / 1024:.1f} KB"
            
            # Intentar conectar para ver tablas
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            datos['bd_tablas'] = cursor.fetchone()[0]
            conn.close()
        except:
            datos['bd_existe'] = True
            datos['bd_tamano'] = 'Error al leer'
            datos['bd_tablas'] = 'Error'
    else:
        datos['bd_existe'] = False
        datos['bd_tamano'] = 'No existe'
        datos['bd_tablas'] = 0
    
    return datos

def obtener_datos_empresa(empresa):
    """Obtiene información detallada de la empresa."""
    try:
        datos = {
            'nombre': empresa.nombre,
            'slug': empresa.slug,
            'ruc': empresa.ruc,
            'direccion': empresa.direccion,
            'telefono': empresa.telefono,
            'email': empresa.email,
            'fecha_creacion': empresa.fecha_creacion.strftime('%d/%m/%Y') if empresa.fecha_creacion else 'N/A',
        }
        
        # Verificar base de datos
        alias = f'db_{empresa.slug}'
        db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
        
        if os.path.exists(db_path):
            tamano = os.path.getsize(db_path)
            datos['bd_existe'] = True
            datos['bd_tamano'] = f"{tamano / 1024:.1f} KB"
        else:
            datos['bd_existe'] = False
            datos['bd_tamano'] = 'No existe'
        
        # Verificar usuarios
        try:
            num_usuarios = Usuario.objects.filter(empresa_slug=empresa.slug).count()
            datos['num_usuarios'] = num_usuarios
        except:
            datos['num_usuarios'] = 'Error'
        
        return datos
        
    except Exception as e:
        return {
            'error': f"Error obteniendo datos: {str(e)}",
            'nombre': empresa.nombre,
            'slug': empresa.slug
        }

def obtener_datos_empresa(empresa):
    """
    Obtiene información detallada de la empresa para mostrar en confirmación.
    """
    try:
        datos = {
            'nombre': empresa.nombre,
            'slug': empresa.slug,
            'ruc': empresa.ruc,
            'direccion': empresa.direccion,
            'telefono': empresa.telefono,
            'email': empresa.email,
            'fecha_creacion': empresa.fecha_creacion.strftime('%d/%m/%Y') if empresa.fecha_creacion else 'N/A',
        }
        
        # Verificar base de datos
        alias = f'db_{empresa.slug}'
        db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
        
        if os.path.exists(db_path):
            tamano = os.path.getsize(db_path)
            datos['bd_existe'] = True
            datos['bd_tamano'] = f"{tamano / 1024:.1f} KB"
            
            # Intentar conectar para obtener stats
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Obtener número de tablas
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                datos['bd_tablas'] = cursor.fetchone()[0]
                
                # Obtener tabla django_migrations para ver migraciones
                cursor.execute("SELECT COUNT(*) FROM django_migrations")
                datos['bd_migraciones'] = cursor.fetchone()[0]
                
                conn.close()
            except:
                datos['bd_tablas'] = 'Error'
                datos['bd_migraciones'] = 'Error'
        else:
            datos['bd_existe'] = False
            datos['bd_tamano'] = 'No existe'
        
        # Verificar usuarios
        try:
            num_usuarios = Usuario.objects.filter(empresa_slug=empresa.slug).count()
            datos['num_usuarios'] = num_usuarios
        except:
            datos['num_usuarios'] = 'Error'
        
        # Verificar directorios
        directorios = {
            'app_movil': os.path.join(settings.BASE_DIR, 'apps_moviles', 'apps_generadas', empresa.slug),
            'media': os.path.join(settings.MEDIA_ROOT, 'empresas', empresa.slug),
        }
        
        datos['directorios'] = {}
        for nombre, path in directorios.items():
            if os.path.exists(path):
                try:
                    num_archivos = sum([len(files) for r, d, files in os.walk(path)])
                    datos['directorios'][nombre] = {
                        'existe': True,
                        'archivos': num_archivos,
                        'ruta': path
                    }
                except:
                    datos['directorios'][nombre] = {'existe': True, 'archivos': 'Error'}
            else:
                datos['directorios'][nombre] = {'existe': False}
        
        return datos
        
    except Exception as e:
        return {
            'error': f"Error obteniendo datos: {str(e)}",
            'nombre': empresa.nombre,
            'slug': empresa.slug
        }

from boletas.helpers import generar_boletas_por_alias
from empresas.models import Empresa
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404

def generar_boletas_ssr(request, slug):
    if not request.user.is_authenticated:
        return redirect('login_ssr')

    empresa = get_object_or_404(Empresa, slug=slug)
    boletas = generar_boletas_por_alias(empresa.slug)
    total = len(boletas)

    messages.success(request, f"✅ Se generaron {total} boletas para {empresa.nombre}.")
    return redirect(request.META.get('HTTP_REFERER') or 'panel_ssr')



# empresas/views.py
from django.http import JsonResponse
from empresas.models import Empresa

def listado_empresas(request):
    empresas = Empresa.objects.values('slug', 'nombre')
    return JsonResponse(list(empresas), safe=False)


# En tu archivo views.py de Django
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def obtener_sectores_empresa(request, empresa_slug):
    """
    Endpoint para obtener los sectores de una empresa específica.
    URL: /empresa/{slug}/api/sectores/
    Método: GET
    """
    try:
        # Buscar la empresa por slug
        empresa = get_object_or_404(Empresa, slug=empresa_slug)
        
        # Obtener sectores del campo JSON
        sectores_data = empresa.sectores()
        
        # Formatear la respuesta
        response_data = {
            'success': True,
            'empresa': {
                'id': empresa.id,
                'nombre': empresa.nombre,
                'slug': empresa.slug,
            },
            'sectores': sectores_data,
            'total': len(sectores_data)
        }
        
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from .models import Empresa, Pozo

@staff_member_required
def agregar_pozo(request, empresa_slug):
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        ubicacion = request.POST.get('ubicacion', '')
        caudal_estimado = request.POST.get('caudal_estimado')
        activo = request.POST.get('activo') == 'on'
        
        if not nombre:
            messages.error(request, 'El nombre del pozo es obligatorio.')
            return redirect('dashboard_admin_ssr')
        
        pozo = Pozo(
            empresa=empresa,
            nombre=nombre,
            ubicacion=ubicacion,
            caudal_estimado=caudal_estimado if caudal_estimado else None,
            activo=activo
        )
        pozo.save()
        
        messages.success(request, f'Pozo "{nombre}" agregado correctamente.')
        return redirect('dashboard_admin_ssr')
    
    # Si no es POST, redirigir al dashboard
    return redirect('dashboard_admin_ssr')


from django.http import JsonResponse
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from .models import Empresa, Produccion
from lecturas.models import LecturaMovil

def datos_produccion_consumo_api(request, slug):
    """API para obtener datos de producción y consumo según período y pozo."""
    periodo = request.GET.get('periodo', 'mes')
    pozo_id = request.GET.get('pozo', 'todos')
    
    try:
        empresa = Empresa.objects.get(slug=slug)
    except Empresa.DoesNotExist:
        return JsonResponse({'error': 'Empresa no encontrada'}, status=404)
    
    # Definir truncador según período
    trunc_map = {
        'dia': TruncDay,
        'semana': TruncWeek,
        'mes': TruncMonth,
        'año': TruncYear,
    }
    trunc_func = trunc_map.get(periodo, TruncMonth)
    
    # Rango de fechas según período
    hoy = timezone.now().date()
    if periodo == 'dia':
        fecha_inicio = hoy - timedelta(days=30)
    elif periodo == 'semana':
        fecha_inicio = hoy - timedelta(weeks=12)
    elif periodo == 'mes':
        fecha_inicio = hoy - timedelta(days=365)
    elif periodo == 'año':
        fecha_inicio = hoy - timedelta(days=5*365)
    else:
        fecha_inicio = hoy - timedelta(days=365)
    
    # Consulta de producción
    prod_qs = Produccion.objects.filter(empresa=empresa, fecha__gte=fecha_inicio)
    if pozo_id != 'todos':
        prod_qs = prod_qs.filter(pozo_id=pozo_id)
    
    prod_por_periodo = prod_qs.annotate(
        periodo=trunc_func('fecha')
    ).values('periodo').annotate(
        total=Sum('volumen')
    ).order_by('periodo')
    
    # Consulta de consumo
    consumo_qs = LecturaMovil.objects.filter(
        empresa_slug=slug,
        fecha_lectura__gte=fecha_inicio,
        consumo__isnull=False
    )
    consumo_por_periodo = consumo_qs.annotate(
        periodo=trunc_func('fecha_lectura')
    ).values('periodo').annotate(
        total=Sum('consumo')
    ).order_by('periodo')
    
    # Diccionarios para combinar
    prod_dict = {item['periodo']: float(item['total']) for item in prod_por_periodo}
    consumo_dict = {item['periodo']: float(item['total']) for item in consumo_por_periodo}
    
    # Períodos únicos ordenados
    periodos = sorted(set(list(prod_dict.keys()) + list(consumo_dict.keys())))
    
    # Meses en español
    meses_espanol = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                     'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    labels = []
    prod_data = []
    consumo_data = []
    for p in periodos:
        if periodo == 'mes':
            mes = meses_espanol[p.month - 1]
            anio = str(p.year)[2:]
            label = f"{mes} '{anio}"
        elif periodo == 'dia':
            label = p.strftime('%d/%m')
        elif periodo == 'semana':
            label = f"Semana {p.strftime('%W')}"
        elif periodo == 'año':
            label = p.strftime('%Y')
        else:
            label = p.strftime('%d/%m/%Y')
        
        labels.append(label)
        prod_data.append(prod_dict.get(p, 0))
        consumo_data.append(consumo_dict.get(p, 0))
    
    return JsonResponse({
        'labels': labels,
        'produccion': prod_data,
        'consumo': consumo_data,
    })

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from .models import Pozo

@require_GET
def api_pozos_empresa(request, slug):
    """Retorna lista de pozos de una empresa en formato JSON."""
    try:
        empresa = Empresa.objects.get(slug=slug)
        pozos = Pozo.objects.filter(empresa=empresa).order_by('nombre')
        data = []
        for p in pozos:
            data.append({
                'id': p.id,
                'nombre': p.nombre,
                'ubicacion': p.ubicacion or '',
                'caudal_estimado': float(p.caudal_estimado) if p.caudal_estimado else None,
                'activo': p.activo,
            })
        return JsonResponse(data, safe=False)
    except Empresa.DoesNotExist:
        return JsonResponse({'error': 'Empresa no encontrada'}, status=404)

@require_POST
@csrf_exempt  # O usar @csrf_protect con token incluido en el fetch
def eliminar_pozo(request, pozo_id):
    """Elimina un pozo (solo superusuario)."""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    try:
        pozo = Pozo.objects.get(id=pozo_id)
        pozo.delete()
        return JsonResponse({'mensaje': 'Pozo eliminado'})
    except Pozo.DoesNotExist:
        return JsonResponse({'error': 'Pozo no encontrado'}, status=404)

from django.http import JsonResponse
from .models import Pozo

def api_pozo_detalle(request, pozo_id):
    try:
        pozo = Pozo.objects.get(id=pozo_id)
        data = {
            'id': pozo.id,
            'nombre': pozo.nombre,
            'ubicacion': pozo.ubicacion or '',
            'caudal_estimado': float(pozo.caudal_estimado) if pozo.caudal_estimado else '',
            'activo': pozo.activo,
        }
        return JsonResponse(data)
    except Pozo.DoesNotExist:
        return JsonResponse({'error': 'Pozo no encontrado'}, status=404)

from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def editar_pozo_api(request, pozo_id):
    if request.method == 'POST':
        pozo = get_object_or_404(Pozo, id=pozo_id)
        try:
            data = json.loads(request.body)  # Si envías JSON
            pozo.nombre = data.get('nombre', pozo.nombre)
            pozo.ubicacion = data.get('ubicacion', pozo.ubicacion)
            pozo.caudal_estimado = data.get('caudal_estimado') if data.get('caudal_estimado') else None
            pozo.activo = data.get('activo', pozo.activo)
            pozo.save()
            return JsonResponse({'mensaje': 'Pozo actualizado correctamente'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@require_POST
@csrf_exempt
def editar_pozo(request, pozo_id):
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        pozo = Pozo.objects.get(id=pozo_id)
        pozo.nombre = request.POST.get('nombre')
        pozo.ubicacion = request.POST.get('ubicacion', '')
        pozo.caudal_estimado = request.POST.get('caudal_estimado') or None
        pozo.activo = request.POST.get('activo') == 'on'
        pozo.save()
        
        # Si la petición es AJAX (desde el modal), devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'mensaje': 'Pozo actualizado correctamente'})
        
        # Si es POST normal, redirigir
        messages.success(request, f'Pozo "{pozo.nombre}" actualizado.')
        return redirect('dashboard_admin_ssr')
        
    except Pozo.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Pozo no encontrado'}, status=404)
        messages.error(request, 'Pozo no encontrado')
        return redirect('dashboard_admin_ssr')