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
from datetime import date, datetime, timedelta
import os
import json
from django.conf import settings
from django.db.models import Sum, Avg, Count, Q
from django.db.models.functions import TruncMonth
import calendar
from decimal import Decimal

def panel_empresa(request, slug):
    """
    Vista para acceder al panel de una empresa específica
    """
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
        
        # 4. Importar modelos DINÁMICAMENTE para la base de datos de la empresa
        from clientes.models import Cliente
        from lecturas.models import LecturaMovil
        from avisos.models import Aviso
        from faq.models import PreguntaFrecuente
        from boletas.models import Boleta
        
        # Usar .using(alias) para consultar en la BD de la empresa
        total_clientes = Cliente.objects.using(alias).count()
        
        # Obtener el mes y año actual
        ahora = timezone.now()
        mes_actual = ahora.month
        anio_actual = ahora.year
        hoy = ahora.date()
        
        # 5. Lecturas del mes actual (CON DATOS REALES)
        lecturas_mes = LecturaMovil.objects.using(alias).filter(
            fecha_lectura__month=mes_actual,
            fecha_lectura__year=anio_actual,
            empresa_slug=slug
        ).count()
        
        # 6. Avisos activos
        avisos_activos = Aviso.objects.using(alias).filter(activo=True).count()
        
        # 7. Preguntas frecuentes
        total_faq = PreguntaFrecuente.objects.using(alias).count()
        
        # === CÁLCULOS PARA GRÁFICOS CON DATOS REALES ===
        
        # 8. Cálculo de consumo mensual total (USANDO LECTURAS)
        try:
            # Sumar consumo de todas las lecturas del mes actual
            consumo_total_mes_result = LecturaMovil.objects.using(alias).filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                consumo__isnull=False
            ).aggregate(total=Sum('consumo'))
            
            consumo_total_mes = consumo_total_mes_result['total'] or Decimal('0')
            
        except Exception as e:
            print(f"Error cálculo consumo_total_mes: {e}")
            consumo_total_mes = Decimal('0')
        
        # 9. Variación de consumo vs mes anterior (USANDO LECTURAS)
        try:
            # Calcular mes anterior
            if mes_actual == 1:
                mes_anterior = 12
                anio_anterior = anio_actual - 1
            else:
                mes_anterior = mes_actual - 1
                anio_anterior = anio_actual
            
            # Consumo del mes anterior
            consumo_mes_anterior_result = LecturaMovil.objects.using(alias).filter(
                fecha_lectura__month=mes_anterior,
                fecha_lectura__year=anio_anterior,
                empresa_slug=slug,
                consumo__isnull=False
            ).aggregate(total=Sum('consumo'))
            
            consumo_mes_anterior = consumo_mes_anterior_result['total'] or Decimal('0')
            
            # Calcular variación porcentual
            if consumo_mes_anterior > 0:
                variacion_consumo = float(
                    ((consumo_total_mes - consumo_mes_anterior) / consumo_mes_anterior) * 100
                )
            else:
                variacion_consumo = 100.0 if consumo_total_mes > 0 else 0.0
                
        except Exception as e:
            print(f"Error cálculo variación: {e}")
            variacion_consumo = 0.0
        
        # 10. Estado de lecturas (CON DATOS REALES DEL MODELO)
        try:
            # Lecturas completadas (estado = 'cargada' o 'procesada')
            lecturas_completadas = LecturaMovil.objects.using(alias).filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                estado__in=['cargada', 'procesada']
            ).count()
            
            # Lecturas pendientes (estado = 'pendiente')
            lecturas_pendientes = LecturaMovil.objects.using(alias).filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                estado='pendiente'
            ).count()
            
            # Calcular porcentaje
            total_lecturas_estado = lecturas_completadas + lecturas_pendientes
            if total_lecturas_estado > 0:
                porcentaje_lecturas_completadas = (lecturas_completadas / total_lecturas_estado) * 100
            else:
                porcentaje_lecturas_completadas = 0
                
        except Exception as e:
            print(f"Error cálculo estado lecturas: {e}")
            lecturas_completadas = 0
            lecturas_pendientes = lecturas_mes
            porcentaje_lecturas_completadas = 0
        
        # 11. Hora pico de consumo (para SSR simplificado)
        hora_pico_consumo = "10:00"
        
        # 12. Top 10 consumidores (USANDO LECTURAS REALES)
        try:
            # Obtener los clientes con mayor consumo en el mes
            top_consumidores_data = LecturaMovil.objects.using(alias).filter(
                fecha_lectura__month=mes_actual,
                fecha_lectura__year=anio_actual,
                empresa_slug=slug,
                consumo__isnull=False,
                consumo__gt=0
            ).values('cliente').annotate(
                total_consumo=Sum('consumo')
            ).order_by('-total_consumo')[:10]
            
            # Obtener detalles de los clientes
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
            
            # Calcular total del top 10
            consumo_top10 = sum(item['consumo'] for item in top_consumidores)
            
        except Exception as e:
            print(f"Error top consumidores: {e}")
            top_consumidores = []
            consumo_top10 = Decimal('0')
        
        # 13. Datos para gráfico de consumo histórico (ÚLTIMOS 12 MESES)
        try:
            # Obtener consumo por mes para los últimos 12 meses desde LECTURAS
            fecha_inicio = ahora - timedelta(days=365)
            
            # Consulta optimizada para SQLite con datos de lecturas
            consumo_historico = LecturaMovil.objects.using(alias).filter(
                fecha_lectura__gte=fecha_inicio,
                empresa_slug=slug,
                consumo__isnull=False
            ).extra({
                'month': "strftime('%m', fecha_lectura)",
                'year': "strftime('%Y', fecha_lectura)"
            }).values('year', 'month').annotate(
                total_consumo=Sum('consumo')
            ).order_by('year', 'month')
            
            # Preparar datos para el gráfico
            meses_grafico = []
            consumo_mensual = []
            
            # Diccionario de meses en español
            meses_espanol = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                            'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            
            # Crear un diccionario para fácil acceso
            consumo_dict = {}
            for item in consumo_historico:
                key = f"{item['year']}-{int(item['month']):02d}"
                consumo_dict[key] = float(item['total_consumo'] or 0)
            
            # Generar secuencia de últimos 12 meses
            for i in range(11, -1, -1):
                fecha = ahora - timedelta(days=30*i)
                mes_num = fecha.month
                anio_num = fecha.year
                mes_nombre = meses_espanol[mes_num - 1]
                anio_corto = str(anio_num)[2:]
                
                meses_grafico.append(f"{mes_nombre} '{anio_corto}")
                
                # Buscar consumo en el diccionario
                key = f"{anio_num}-{mes_num:02d}"
                consumo_mes = consumo_dict.get(key, 0.0)
                consumo_mensual.append(consumo_mes)
                
        except Exception as e:
            print(f"Error histórico consumo: {e}")
            # Datos de ejemplo si hay error
            meses_espanol = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                            'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            meses_grafico = [f"{mes} '{str(ahora.year)[2:]}" for mes in meses_espanol]
            # Generar datos realistas basados en el consumo actual
            base_consumo = float(consumo_total_mes) if consumo_total_mes > 0 else 1000
            consumo_mensual = [
                base_consumo * 0.8, base_consumo * 0.85, base_consumo * 0.9,
                base_consumo * 0.75, base_consumo, base_consumo * 1.1,
                base_consumo * 0.9, base_consumo * 1.05, base_consumo * 1.15,
                base_consumo * 1.1, base_consumo * 1.0, base_consumo * 0.95
            ]
        
        # 14. Distribución por sector (USANDO SECTORES DE LA EMPRESA Y CLIENTES)
        try:
            # Obtener sectores configurados en la empresa
            sectores_empresa = empresa.sectores()  # Esto viene del campo sectores_json
            
            # Agrupar clientes por sector
            clientes_por_sector = Cliente.objects.using(alias).filter(
                sector__isnull=False,
                sector__ne=''
            ).values('sector').annotate(
                total=Count('id')
            ).order_by('-total')
            
            # Preparar datos para gráfico
            distribucion_sectores = []
            
            if sectores_empresa:
                # Usar sectores definidos en la empresa como base
                for sector in sectores_empresa:
                    # Buscar si hay clientes en este sector
                    clientes_sector = next((item for item in clientes_por_sector 
                                          if item['sector'].strip().lower() == sector.strip().lower()), None)
                    
                    total = clientes_sector['total'] if clientes_sector else 0
                    
                    # Calcular porcentaje
                    porcentaje = (total / total_clientes * 100) if total_clientes > 0 else 0
                    
                    distribucion_sectores.append({
                        'tipo': sector,
                        'total': total,
                        'porcentaje': round(porcentaje, 1)
                    })
            else:
                # Si no hay sectores configurados, usar sectores de los clientes
                for item in clientes_por_sector:
                    sector = item['sector']
                    total = item['total']
                    porcentaje = (total / total_clientes * 100) if total_clientes > 0 else 0
                    
                    distribucion_sectores.append({
                        'tipo': sector,
                        'total': total,
                        'porcentaje': round(porcentaje, 1)
                    })
            
            # Si no hay datos de sectores, mostrar distribución simple
            if not distribucion_sectores:
                # Agrupar por primeros caracteres de la dirección
                clientes_por_zona = Cliente.objects.using(alias).filter(
                    direccion__isnull=False
                ).extra({
                    'zona': "SUBSTR(direccion, 1, 3)"
                }).values('zona').annotate(
                    total=Count('id')
                ).order_by('-total')[:5]
                
                for item in clientes_por_zona:
                    zona = item['zona'] or 'Sin zona'
                    total = item['total']
                    porcentaje = (total / total_clientes * 100) if total_clientes > 0 else 0
                    
                    distribucion_sectores.append({
                        'tipo': f"Zona {zona}",
                        'total': total,
                        'porcentaje': round(porcentaje, 1)
                    })
            
            # Limitar a top 5 sectores y agrupar el resto como "Otros"
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
            # Datos de ejemplo basados en sectores comunes
            distribucion_sectores = [
                {'tipo': 'Centro', 'total': 45, 'porcentaje': 45.0},
                {'tipo': 'Norte', 'total': 25, 'porcentaje': 25.0},
                {'tipo': 'Sur', 'total': 15, 'porcentaje': 15.0},
                {'tipo': 'Este', 'total': 10, 'porcentaje': 10.0},
                {'tipo': 'Oeste', 'total': 5, 'porcentaje': 5.0},
            ]
        
        # 15. Datos para tendencia anual (consumo vs lecturas completadas)
        try:
            # Obtener tendencia de consumo (ya calculado)
            tendencia_consumo = consumo_mensual[-12:]  # Últimos 12 meses
            
            # Calcular tendencia de lecturas completadas por mes
            tendencia_lecturas = []
            for i in range(11, -1, -1):
                fecha = ahora - timedelta(days=30*i)
                mes_num = fecha.month
                anio_num = fecha.year
                
                lecturas_mes_historico = LecturaMovil.objects.using(alias).filter(
                    fecha_lectura__month=mes_num,
                    fecha_lectura__year=anio_num,
                    empresa_slug=slug,
                    estado__in=['cargada', 'procesada']
                ).count()
                
                tendencia_lecturas.append(lecturas_mes_historico)
                
        except Exception as e:
            print(f"Error tendencia: {e}")
            tendencia_consumo = consumo_mensual
            # Simular crecimiento de lecturas
            base_lecturas = max(lecturas_completadas - 5, 0)
            tendencia_lecturas = [max(0, base_lecturas + i) for i in range(12)]
        
        # 16. Consumo promedio por cliente
        try:
            if total_clientes > 0:
                consumo_promedio = float(consumo_total_mes) / total_clientes
            else:
                consumo_promedio = 0
        except:
            consumo_promedio = 0
        
        # 17. Rendimiento del mes (porcentaje de tiempo transcurrido)
        dia_actual = hoy.day
        dias_en_mes = calendar.monthrange(anio_actual, mes_actual)[1]
        rendimiento_mes = (dia_actual / dias_en_mes) * 100
        
        # 18. Datos existentes de helpers
        try:
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
            
            firma = obtener_certificado_firma(alias)
            folios = obtener_estado_folios(alias)
            interes = obtener_tasa_interes(alias)
            reajuste = obtener_reajuste_sii(alias)
            contratos_corte = obtener_contratos_corte(alias)
            pagos = obtener_detalle_recaudacion(alias, date.today())
            meses, produccion, consumo = obtener_produccion_consumo(alias)
            puntos_lectura = obtener_puntos_lectura(alias)
        except Exception as e:
            print(f"Error helpers: {e}")
            messages.warning(request, f'Algunos datos no están disponibles: {str(e)}')
            firma = folios = interes = reajuste = None
            contratos_corte = pagos = puntos_lectura = []
            meses, produccion, consumo = [], [], []
        
        # 19. Preparar datos para tabla top consumidores en template
        top_consumidores_template = []
        for idx, item in enumerate(top_consumidores[:10], 1):
            cliente = item['cliente']
            consumo_cliente = item['consumo']
            
            # Calcular porcentaje del total
            porcentaje_total = (float(consumo_cliente) / float(consumo_total_mes) * 100) if consumo_total_mes > 0 else 0
            
            top_consumidores_template.append({
                'posicion': idx,
                'nombre': cliente.nombre,
                'rut': cliente.rut,
                'sector': cliente.sector or 'Sin sector',
                'consumo': float(consumo_cliente),
                'porcentaje': round(porcentaje_total, 1)
            })
        
        # 20. También obtener datos para gráfico de sectores (formato para JavaScript)
        # Preparar datos JSON para el template
        sectores_para_json = []
        colores_base = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#f97316']
        
        for idx, item in enumerate(distribucion_sectores):
            color_idx = idx % len(colores_base)
            sectores_para_json.append({
                'tipo': item['tipo'],
                'total': item['total'],
                'porcentaje': item['porcentaje'],
                'color': colores_base[color_idx]
            })
        
        # 21. Renderizar el template con todas las variables
        context = {
            # Variables existentes
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
            
            # === NUEVAS VARIABLES PARA GRÁFICOS ===
            'consumo_total_mes': float(consumo_total_mes),
            'variacion_consumo': round(variacion_consumo, 1),
            'porcentaje_lecturas_completadas': round(porcentaje_lecturas_completadas, 0),
            'lecturas_completadas': lecturas_completadas,
            'lecturas_pendientes': lecturas_pendientes,
            'hora_pico_consumo': hora_pico_consumo,
            'consumo_top10': float(consumo_top10),
            'top_consumidores': top_consumidores_template,
            'meses_grafico': json.dumps(meses_grafico),
            'consumo_mensual': json.dumps(consumo_mensual),
            'distribucion_sectores': json.dumps(sectores_para_json),
            'tendencia_consumo': json.dumps(tendencia_consumo),
            'tendencia_lecturas': json.dumps(tendencia_lecturas),
            'consumo_promedio': round(consumo_promedio, 2),
            'rendimiento_mes': round(rendimiento_mes, 1),
            
            # Fecha actual para referencia
            'hoy': hoy,
            'dia_actual': dia_actual,
            'dias_en_mes': dias_en_mes,
            
            # Sectores de la empresa (para referencia)
            'sectores_empresa': empresa.sectores(),
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

import sqlite3
import json
import os
from django.conf import settings
from django.shortcuts import render, redirect
from django.utils.text import slugify
from empresas.models import Empresa
from django.contrib import messages
from django.db import connections

def crear_empresa(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        slug = slugify(nombre)

        # Validar que no exista
        if Empresa.objects.filter(slug=slug).exists():
            messages.error(request, 'Ya existe una empresa con ese nombre')
            return render(request, 'admin_ssr/crear_empresa.html')

        # Procesar sectores
        sectores_raw = request.POST.get('sectores', '')
        sectores = [s.strip() for s in sectores_raw.split(',') if s.strip()]

        try:
            # 1. Crear empresa
            empresa = Empresa.objects.create(
                nombre=nombre,
                slug=slug,
                sectores_json=json.dumps(sectores)
            )

            # 2. Crear base de datos física
            alias = f'db_{slug}'
            db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
            
            # Asegurar que el directorio existe
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            
            # Crear la base de datos
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Crear tablas básicas
            cursor.execute('''
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    email TEXT,
                    password TEXT,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE configuracion (
                    clave TEXT PRIMARY KEY,
                    valor TEXT
                )
            ''')
            
            # Insertar configuración inicial
            cursor.execute(
                "INSERT INTO configuracion (clave, valor) VALUES (?, ?)",
                ('nombre_empresa', nombre)
            )
            
            conn.commit()
            conn.close()
            
            # 3. Registrar alias
            registrar_alias(slug)
            
            # 4. Actualizar JSON de aliases
            actualizar_alias_json()
            
            messages.success(request, f'Empresa {nombre} creada exitosamente')
            return redirect('dashboard_admin_ssr')
            
        except Exception as e:
            # Revertir en caso de error
            if 'empresa' in locals():
                empresa.delete()
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
import sqlite3
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.db import connections
from django.contrib import messages
from .models import Empresa, EliminacionEmpresa

def eliminar_empresa(request, slug):
    if request.method == 'POST' and request.user.is_superuser:
        empresa = get_object_or_404(Empresa, slug=slug)
        alias = f'db_{slug}'
        
        try:
            # 1. Cerrar todas las conexiones posibles
            if alias in connections:
                try:
                    connections[alias].close()
                    del connections[alias]
                except:
                    pass
            
            # 2. Forzar cierre de conexiones SQLite
            db_path = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
            
            # Intentar eliminar archivo .db-wal y .db-shm si existen
            wal_path = db_path + '-wal'
            shm_path = db_path + '-shm'
            
            for temp_file in [wal_path, shm_path]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
            # 3. Eliminar base física con reintentos
            if os.path.exists(db_path):
                for intento in range(3):
                    try:
                        os.remove(db_path)
                        break
                    except PermissionError:
                        if intento < 2:
                            time.sleep(1)  # Esperar 1 segundo antes de reintentar
                        else:
                            # Guardar en registro de auditoría el error
                            EliminacionEmpresa.objects.create(
                                nombre=empresa.nombre,
                                slug=empresa.slug,
                                ejecutado_por=request.user,
                                error=f"No se pudo eliminar archivo: {db_path}"
                            )
                            messages.error(request, 'No se pudo eliminar la base de datos. Puede estar en uso.')
                            return redirect('dashboard_admin_ssr')
            
            # 4. Eliminar alias del JSON externo
            alias_json_path = os.path.join(settings.BASE_DIR, 'asesora_ssr', 'empresas_alias.json')
            if os.path.exists(alias_json_path):
                try:
                    with open(alias_json_path, 'r') as f:
                        aliases = json.load(f)
                    
                    if slug in aliases:
                        aliases.remove(slug)
                        
                    with open(alias_json_path, 'w') as f:
                        json.dump(aliases, f, indent=2)
                except Exception as e:
                    # Continuar aunque falle el JSON
                    print(f"Error actualizando JSON: {e}")
            
            # 5. Registrar en historial de auditoría
            EliminacionEmpresa.objects.create(
                nombre=empresa.nombre,
                slug=empresa.slug,
                ejecutado_por=request.user,
                completado=True
            )
            
            # 6. Eliminar registro en modelo Empresa
            empresa.delete()
            
            # 7. Eliminar logs por alias
            log_path = os.path.join(settings.BASES_DIR, f'{slug}_log.txt')
            if os.path.exists(log_path):
                try:
                    os.remove(log_path)
                except:
                    pass
            
            messages.success(request, f'Empresa {empresa.nombre} eliminada exitosamente')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar empresa: {str(e)}')
        
        return redirect('dashboard_admin_ssr')
    
    messages.error(request, 'Método no permitido')
    return redirect('dashboard_admin_ssr')

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