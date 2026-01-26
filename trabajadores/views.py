# views.py (app trabajadores)
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, FileResponse, Http404
from django.db.models import Count, Q, Sum, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
import csv
import json
from django.db.models.functions import TruncMonth
from django.db import models

from .models import ContratoLaboral, Trabajador, FiniquitoLaboral, LiquidacionLaboral
from .forms import ContratoForm, FiniquitoForm, LiquidacionForm
from .helpers import (
    generar_contrato_pdf, 
    generar_finiquito_pdf, 
    generar_liquidacion_pdf,
    calcular_gratificacion,
    calcular_afp,
    calcular_salud,
    calcular_seguro_cesantia
)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ContratoLaboral
from empresas.models import Empresa   
import json
from datetime import datetime

@login_required
def crear_contrato(request, alias):
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Verificar si viene de un trabajador específico
    trabajador_id = request.GET.get('trabajador_id')
    trabajador = None
    if trabajador_id:
        try:
            from .models import Trabajador
            trabajador = Trabajador.objects.get(id=trabajador_id, empresa=empresa)
        except (Trabajador.DoesNotExist, ValueError):
            pass
    
    if request.method == 'POST':
        try:
            # Recoger todos los datos del formulario manualmente
            datos = {
                'alias': alias,  # Usamos el alias de la empresa
                'rut_trabajador': request.POST.get('rut_trabajador', '').strip(),
                'nombre': request.POST.get('nombre', '').strip(),
                'cargo': request.POST.get('cargo', '').strip(),
                'jornada': request.POST.get('jornada', 'completa'),
                'tipo_contrato': request.POST.get('tipo_contrato', 'indefinido'),
                'fecha_inicio': request.POST.get('fecha_inicio', ''),
                'fecha_termino': request.POST.get('fecha_termino', '') or None,
                'afp': request.POST.get('afp', 'modelo'),
                'salud': request.POST.get('salud', 'fonasa'),
                'sistema_gratificacion': request.POST.get('sistema_gratificacion', 'art_50'),
                'tipo_gratificacion': request.POST.get('tipo_gratificacion', 'fija'),
                'sueldo_base': int(float(request.POST.get('sueldo_base', 0) or 0)),
                'gratificacion': int(float(request.POST.get('gratificacion', 0) or 0)),
                'bonos': 0,  # Lo calcularemos con los bonos dinámicos
            }
            
            # Validaciones básicas
            errores = []
            if not datos['rut_trabajador']:
                errores.append("El RUT del trabajador es requerido")
            if not datos['nombre']:
                errores.append("El nombre es requerido")
            if not datos['cargo']:
                errores.append("El cargo es requerido")
            if not datos['fecha_inicio']:
                errores.append("La fecha de inicio es requerida")
            if datos['sueldo_base'] <= 0:
                errores.append("El sueldo base debe ser mayor a 0")
            
            if errores:
                for error in errores:
                    messages.error(request, error)
                return render(request, 'trabajadores/crear_contrato.html', {
                    'empresa': empresa,
                    'alias': alias,
                    'trabajador': trabajador,
                    'datos': datos,  # Para mantener los datos ingresados
                })
            
            # Procesar los bonos dinámicos
            bono_conceptos = request.POST.getlist('bono_concepto[]')
            bono_montos = request.POST.getlist('bono_monto[]')
            
            bonos_lista = []
            total_bonos = 0
            
            for concepto, monto in zip(bono_conceptos, bono_montos):
                concepto_limpio = concepto.strip()
                if concepto_limpio and monto:
                    try:
                        monto_int = int(float(monto))
                        if monto_int > 0:
                            bonos_lista.append({
                                'concepto': concepto_limpio,
                                'monto': monto_int
                            })
                            total_bonos += monto_int
                    except (ValueError, TypeError):
                        pass
            
            # Actualizar el total de bonos
            datos['bonos'] = total_bonos
            
            # Calcular gratificación automáticamente si es necesario
            if datos['sistema_gratificacion'] == 'art_50' and datos['sueldo_base'] > 0:
                datos['gratificacion'] = int(datos['sueldo_base'] * 0.25)  # 25% del sueldo base
            
            # Convertir fecha_termino a None si está vacía
            if datos['fecha_termino'] == '':
                datos['fecha_termino'] = None
            
            # Crear el contrato directamente - SIN los campos que no existen
            contrato = ContratoLaboral.objects.create(
                # Campos que SÍ existen en tu modelo
                alias=datos['alias'],
                rut_trabajador=datos['rut_trabajador'],
                nombre=datos['nombre'],
                cargo=datos['cargo'],
                jornada=datos['jornada'],
                tipo_contrato=datos['tipo_contrato'],
                fecha_inicio=datos['fecha_inicio'],
                fecha_termino=datos['fecha_termino'],
                afp=datos['afp'],
                salud=datos['salud'],
                sistema_gratificacion=datos['sistema_gratificacion'],
                tipo_gratificacion=datos['tipo_gratificacion'],
                sueldo_base=datos['sueldo_base'],
                gratificacion=datos['gratificacion'],
                bonos=datos['bonos'],
                # NO incluir 'empresa' ni 'remuneracion_total' porque no existen
            )
            
            # Si necesitas guardar bonos detallados, necesitarías agregar un campo al modelo
            # Por ahora, puedes guardarlos en otro lugar o simplemente usar el total
            
            # Si venía de un trabajador específico, asociar el contrato
            # (Esto depende de cómo tengas la relación en tu modelo Trabajador)
            
            messages.success(request, f'✅ Contrato creado exitosamente para {contrato.nombre}.')
            
            # Redirigir al PDF del contrato
            return redirect('ver_contrato_pdf', alias=alias, id=contrato.id)
            
        except Exception as e:
            messages.error(request, f'❌ Error al crear el contrato: {str(e)}')
            print(f"Error en crear_contrato: {str(e)}")
            # Para debugging, imprime los datos que estás intentando guardar
            print(f"Datos intentados: {datos}")
            return render(request, 'trabajadores/crear_contrato.html', {
                'empresa': empresa,
                'alias': alias,
                'trabajador': trabajador,
                'datos': request.POST.dict() if request.method == 'POST' else {},
            })
    
    else:
        # GET request - mostrar formulario vacío o pre-llenado
        datos_iniciales = {}
        if trabajador:
            datos_iniciales = {
                'rut_trabajador': trabajador.rut,
                'nombre': trabajador.nombre,
                'cargo': trabajador.cargo,
            }
        
        context = {
            'empresa': empresa,
            'alias': alias,
            'trabajador': trabajador,
            'datos': datos_iniciales,
        }
        return render(request, 'trabajadores/crear_contrato.html', context)


@login_required
def agregar_bono_contrato(request, alias, contrato_id):
    """Agregar bono personalizado a un contrato existente"""
    contrato = get_object_or_404(ContratoLaboral, id=contrato_id, alias=alias)
    
    if request.method == 'POST':
        nombre_bono = request.POST.get('nombre_bono')
        monto = request.POST.get('monto')
        descripcion = request.POST.get('descripcion', '')
        
        try:
            contrato.agregar_bono(
                nombre_bono=nombre_bono,
                monto=int(monto),
                descripcion=descripcion,
                es_fijo=request.POST.get('es_fijo', 'true') == 'true'
            )
            
            messages.success(request, f"✅ Bono '{nombre_bono}' agregado por ${monto:,}")
            return redirect('detalle_contrato', alias=alias, contrato_id=contrato.id)
            
        except Exception as e:
            messages.error(request, f"❌ Error al agregar bono: {str(e)}")
    
    context = {
        'alias': alias,
        'contrato': contrato
    }
    
    return render(request, 'trabajadores/agregar_bono.html', context)

def listado_contratos(request, alias):
    """
    Vista principal para listar contratos con estadísticas.
    """
    # Obtener todos los contratos de esta empresa (alias)
    contratos = ContratoLaboral.objects.filter(alias=alias).order_by('-creado')
    
    # Calcular estadísticas
    hoy = timezone.now().date()
    
    # Estadísticas básicas
    total_contratos = contratos.count()
    contratos_activos = contratos.filter(
        Q(fecha_termino__isnull=True) | 
        Q(fecha_termino__gte=hoy)
    ).count()
    
    # Próximos a vencer (30 días)
    fecha_limite = hoy + timedelta(days=30)
    por_vencer = contratos.filter(
        fecha_termino__isnull=False,
        fecha_termino__gte=hoy,
        fecha_termino__lte=fecha_limite
    ).count()
    
    # Con PDF
    con_pdf = contratos.exclude(documento_pdf='').count()
    
    # Porcentajes
    porcentaje_activos = round((contratos_activos / total_contratos * 100), 1) if total_contratos > 0 else 0
    porcentaje_pdf = round((con_pdf / total_contratos * 100), 1) if total_contratos > 0 else 0
    
    # Distribución por tipo
    tipos = contratos.values('tipo_contrato').annotate(total=Count('id'))
    distribucion = {tipo['tipo_contrato']: tipo['total'] for tipo in tipos}
    
    # Ajustar según tus tipos de contrato
    indefinidos = distribucion.get('indefinido', 0)
    plazo_fijo = distribucion.get('plazo_fijo', 0)
    por_obra = distribucion.get('faena', 0)  # En tu modelo es 'faena'
    
    # Variación mensual
    mes_actual = hoy.replace(day=1)
    if mes_actual.month == 1:
        mes_anterior = mes_actual.replace(year=mes_actual.year-1, month=12)
    else:
        mes_anterior = mes_actual.replace(month=mes_actual.month-1)
    
    contratos_mes_actual = contratos.filter(creado__month=mes_actual.month, creado__year=mes_actual.year).count()
    contratos_mes_anterior = contratos.filter(creado__month=mes_anterior.month, creado__year=mes_anterior.year).count()
    
    if contratos_mes_anterior > 0:
        variacion_mensual = round(((contratos_mes_actual - contratos_mes_anterior) / contratos_mes_anterior * 100), 1)
    else:
        variacion_mensual = 100.0 if contratos_mes_actual > 0 else 0.0
    
    # Enriquecer contratos para template
    for contrato in contratos:
        contrato.esta_activo = (contrato.fecha_termino is None or contrato.fecha_termino >= hoy)
        if contrato.fecha_termino:
            dias_restantes = (contrato.fecha_termino - hoy).days
            contrato.por_vencer_soon = 0 < dias_restantes <= 30
            contrato.dias_para_vencer = dias_restantes
        else:
            contrato.por_vencer_soon = False
    
    context = {
        'empresa': {
            'nombre': alias.replace('-', ' ').title(),
            'alias': alias
        },
        'alias': alias,
        'contratos': contratos,
        'total_contratos': total_contratos,
        'contratos_activos': contratos_activos,
        'por_vencer': por_vencer,
        'con_pdf': con_pdf,
        'porcentaje_activos': porcentaje_activos,
        'porcentaje_pdf': porcentaje_pdf,
        'variacion_mensual': variacion_mensual,
        'indefinidos': indefinidos,
        'plazo_fijo': plazo_fijo,
        'por_obra': por_obra,
        'hoy': hoy,
    }
    
    return render(request, 'trabajadores/listado_contratos.html', context)
import pandas as pd
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime

def exportar_contratos_excel(request, alias):
    """
    Exporta contratos a un archivo Excel real (.xlsx) usando Pandas.
    """
    # Obtener contratos
    contratos = ContratoLaboral.objects.filter(alias=alias).values(
        'id', 'nombre', 'rut_trabajador', 'cargo', 
        'tipo_contrato', 'jornada', 'fecha_inicio', 'fecha_termino',
        'sueldo_base', 'gratificacion', 'bonos', 'afp', 'salud',
        'tipo_gratificacion', 'creado', 'documento_pdf'
    )
    
    # Convertir a DataFrame de Pandas
    df = pd.DataFrame(list(contratos))
    
    if df.empty:
        # Si no hay datos, crear un DataFrame vacío con las columnas correctas
        df = pd.DataFrame(columns=[
            'id', 'nombre', 'rut_trabajador', 'cargo', 
            'tipo_contrato', 'jornada', 'fecha_inicio', 'fecha_termino',
            'sueldo_base', 'gratificacion', 'bonos', 'afp', 'salud',
            'tipo_gratificacion', 'creado', 'documento_pdf'
        ])
    
    # Procesar datos
    hoy = datetime.now().date()
    
    # Agregar columnas calculadas
    df['Total Remuneración'] = df['sueldo_base'] + df['gratificacion'] + df['bonos']
    
    # Determinar estado
    def determinar_estado(fecha_termino):
        if pd.isna(fecha_termino):
            return "INDEFINIDO"
        
        fecha_termino = pd.to_datetime(fecha_termino).date()
        if fecha_termino < hoy:
            return "VENCIDO"
        elif (fecha_termino - hoy).days <= 30:
            return "PRÓXIMO A VENCER"
        else:
            return "ACTIVO"
    
    df['Estado'] = df['fecha_termino'].apply(determinar_estado)
    
    # Días para vencer
    def calcular_dias_vencer(fecha_termino):
        if pd.isna(fecha_termino):
            return "N/A"
        
        fecha_termino = pd.to_datetime(fecha_termino).date()
        if fecha_termino < hoy:
            return 0
        return (fecha_termino - hoy).days
    
    df['Días para Vencer'] = df['fecha_termino'].apply(calcular_dias_vencer)
    
    # PDF generado
    df['PDF Generado'] = df['documento_pdf'].apply(lambda x: "SI" if x else "NO")
    
    # Formatear fechas
    df['fecha_inicio'] = pd.to_datetime(df['fecha_inicio']).dt.strftime('%d/%m/%Y')
    df['fecha_termino'] = pd.to_datetime(df['fecha_termino']).dt.strftime('%d/%m/%Y')
    df['creado'] = pd.to_datetime(df['creado']).dt.strftime('%d/%m/%Y %H:%M')
    
    # Traducir valores de choices
    tipo_contrato_dict = dict(ContratoLaboral._meta.get_field('tipo_contrato').choices)
    jornada_dict = dict(ContratoLaboral._meta.get_field('jornada').choices)
    afp_dict = dict(ContratoLaboral._meta.get_field('afp').choices)
    salud_dict = dict(ContratoLaboral._meta.get_field('salud').choices)
    gratificacion_dict = dict(ContratoLaboral._meta.get_field('tipo_gratificacion').choices)
    
    df['tipo_contrato'] = df['tipo_contrato'].map(tipo_contrato_dict).fillna(df['tipo_contrato'])
    df['jornada'] = df['jornada'].map(jornada_dict).fillna(df['jornada'])
    df['afp'] = df['afp'].map(afp_dict).fillna(df['afp'])
    df['salud'] = df['salud'].map(salud_dict).fillna(df['salud'])
    df['tipo_gratificacion'] = df['tipo_gratificacion'].map(gratificacion_dict).fillna(df['tipo_gratificacion'])
    
    # Renombrar columnas en español
    df = df.rename(columns={
        'id': 'ID',
        'nombre': 'Nombre Completo',
        'rut_trabajador': 'RUT',
        'cargo': 'Cargo',
        'tipo_contrato': 'Tipo Contrato',
        'jornada': 'Jornada',
        'fecha_inicio': 'Fecha Inicio',
        'fecha_termino': 'Fecha Término',
        'sueldo_base': 'Sueldo Base',
        'gratificacion': 'Gratificación',
        'bonos': 'Bonos',
        'afp': 'AFP',
        'salud': 'Sistema Salud',
        'tipo_gratificacion': 'Tipo Gratificación',
        'creado': 'Fecha Creación',
    })
    
    # Reordenar columnas
    column_order = [
        'ID', 'Nombre Completo', 'RUT', 'Cargo', 'Tipo Contrato', 'Jornada',
        'Fecha Inicio', 'Fecha Término', 'Sueldo Base', 'Gratificación',
        'Bonos', 'Total Remuneración', 'AFP', 'Sistema Salud',
        'Tipo Gratificación', 'Fecha Creación', 'Estado', 'PDF Generado',
        'Días para Vencer'
    ]
    
    df = df[column_order]
    
    # Crear archivo Excel en memoria
    output = BytesIO()
    
    # Usar ExcelWriter con openpyxl
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Hoja de datos
        df.to_excel(writer, sheet_name='Contratos', index=False)
        
        # Ajustar ancho de columnas
        worksheet = writer.sheets['Contratos']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # Hoja de resumen
        summary_data = {
            'Métrica': [
                'Total Contratos',
                'Contratos Activos',
                'Próximos a Vencer (30 días)',
                'Con PDF Generado',
                'Exportado el',
                'Empresa'
            ],
            'Valor': [
                len(df),
                len(df[df['Estado'] == 'ACTIVO']),
                len(df[df['Estado'] == 'PRÓXIMO A VENCER']),
                len(df[df['PDF Generado'] == 'SI']),
                datetime.now().strftime('%d/%m/%Y %H:%M'),
                alias
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Resumen', index=False)
        
        # Ajustar ancho en resumen
        worksheet_summary = writer.sheets['Resumen']
        worksheet_summary.column_dimensions['A'].width = 30
        worksheet_summary.column_dimensions['B'].width = 30
    
    # Preparar respuesta
    output.seek(0)
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="contratos_{alias}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx"'
    
    return response

def recordatorios_vencimiento(request, alias):
    """
    Muestra contratos próximos a vencer.
    """
    hoy = timezone.now().date()
    fecha_limite = hoy + timedelta(days=30)
    
    contratos_por_vencer = ContratoLaboral.objects.filter(
        alias=alias,
        fecha_termino__isnull=False,
        fecha_termino__gte=hoy,
        fecha_termino__lte=fecha_limite
    ).order_by('fecha_termino')
    
    # Calcular días restantes
    for contrato in contratos_por_vencer:
        contrato.dias_restantes = (contrato.fecha_termino - hoy).days
    
    total_recordatorios = contratos_por_vencer.count()
    
    context = {
        'alias': alias,
        'empresa': {
            'nombre': alias.replace('-', ' ').title(),
            'alias': alias
        },
        'contratos_por_vencer': contratos_por_vencer,
        'total_recordatorios': total_recordatorios,
        'hoy': hoy,
        'fecha_limite': fecha_limite,
    }
    
    return render(request, 'trabajadores/recordatorios.html', context)

def reporte_contratos(request, alias):
    """
    Vista para el reporte de contratos.
    """
    # Obtener contratos
    contratos = ContratoLaboral.objects.filter(alias=alias)
    
    # Fecha actual (datetime para usar con hora)
    ahora = timezone.now()
    hoy = ahora.date()
    
    # Estadísticas básicas
    total = contratos.count()
    
    # Contratos activos
    activos = contratos.filter(
        Q(fecha_termino__isnull=True) | 
        Q(fecha_termino__gte=hoy)
    ).count()
    
    # Próximos a vencer (30 días)
    fecha_limite = hoy + timedelta(days=30)
    por_vencer_30_dias = contratos.filter(
        fecha_termino__isnull=False,
        fecha_termino__gte=hoy,
        fecha_termino__lte=fecha_limite
    ).count()
    
    # Con PDF
    con_pdf = contratos.exclude(documento_pdf='').count()
    
    # Distribuciones - CONVERTIR A LISTAS para usar en template
    por_tipo_raw = dict(contratos.values('tipo_contrato').annotate(total=Count('id')).values_list('tipo_contrato', 'total'))
    por_tipo = list(por_tipo_raw.items())  # Convertir a lista
    
    por_jornada_raw = dict(contratos.values('jornada').annotate(total=Count('id')).values_list('jornada', 'total'))
    por_jornada = list(por_jornada_raw.items())  # Convertir a lista
    
    por_afp_raw = dict(contratos.values('afp').annotate(total=Count('id')).values_list('afp', 'total'))
    por_afp = list(por_afp_raw.items())  # Convertir a lista
    
    por_salud_raw = dict(contratos.values('salud').annotate(total=Count('id')).values_list('salud', 'total'))
    por_salud = list(por_salud_raw.items())  # Convertir a lista
    
    # Estadísticas de sueldos
    from django.db.models import Avg, Max, Min, Sum
    sueldos = contratos.aggregate(
        promedio=Avg('sueldo_base'),
        maximo=Max('sueldo_base'),
        minimo=Min('sueldo_base'),
        total_gratificacion=Sum('gratificacion'),
        total_bonos=Sum('bonos')
    )
    
    # Contratos por mes (últimos 6 meses)
    seis_meses_atras = hoy - timedelta(days=180)
    contratos_por_mes = []
    
    # Crear datos dummy para el gráfico
    for i in range(5, -1, -1):
        mes = hoy - timedelta(days=30*i)
        # Contar contratos de este mes
        mes_inicio = mes.replace(day=1)
        if i == 0:
            mes_fin = hoy
        else:
            mes_fin = mes_inicio + timedelta(days=31)
            mes_fin = mes_fin.replace(day=1) - timedelta(days=1)
        
        count = contratos.filter(
            creado__date__gte=mes_inicio,
            creado__date__lte=mes_fin
        ).count()
        
        contratos_por_mes.append({
            'mes': mes.strftime('%b'),  # Nombre abreviado del mes
            'total': count
        })
    
    # Top 5 contratos por sueldo
    top_contratos = contratos.order_by('-sueldo_base')[:5]
    for contrato in top_contratos:
        contrato.esta_activo = (
            contrato.fecha_termino is None or 
            contrato.fecha_termino >= hoy
        )
        # Calcular total remuneración
        contrato.total_remuneracion = contrato.sueldo_base + contrato.gratificacion + contrato.bonos
    
    # Calcular porcentajes
    porcentaje_activos = (activos / total * 100) if total > 0 else 0
    porcentaje_por_vencer = (por_vencer_30_dias / total * 100) if total > 0 else 0
    
    # Preparar contexto
    context = {
        'empresa': {
            'nombre': alias.replace('-', ' ').title(),
            'alias': alias
        },
        'alias': alias,
        'hoy': ahora,
        'total_contratos': total,
        'contratos_activos': activos,
        'por_vencer': por_vencer_30_dias,
        'con_pdf': con_pdf,
        'porcentaje_activos': porcentaje_activos,
        'porcentaje_por_vencer': porcentaje_por_vencer,
        'stats': {
            'total': total,
            'activos': activos,
            'por_vencer_30_dias': por_vencer_30_dias,
            'con_pdf': con_pdf,
            'por_tipo': por_tipo,  # Ahora es lista
            'por_jornada': por_jornada,  # Ahora es lista
            'por_afp': por_afp,  # Ahora es lista
            'por_salud': por_salud,  # Ahora es lista
            'sueldos': sueldos,
            'contratos_por_mes': contratos_por_mes,
        },
        'top_contratos': top_contratos,
    }
    
    return render(request, 'trabajadores/reporte.html', context)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404
from .models import ContratoLaboral
import json

@login_required
def ver_contrato(request, alias, contrato_id):
    """
    Vista para ver el detalle de un contrato específico
    """
    try:
        # Obtener la empresa por alias
        empresa = get_object_or_404(Empresa, alias=alias)
        
        # Obtener el contrato
        contrato = get_object_or_404(ContratoLaboral, id=contrato_id, empresa=empresa)
        
        # Procesar bonos dinámicos si están almacenados como JSON
        bonos_detalle = []
        if hasattr(contrato, 'bonos_detalle') and contrato.bonos_detalle:
            try:
                bonos_detalle = json.loads(contrato.bonos_detalle)
            except (json.JSONDecodeError, TypeError):
                bonos_detalle = []
        
        # Calcular total de remuneraciones
        total_remuneracion = 0
        if hasattr(contrato, 'sueldo_base'):
            total_remuneracion += contrato.sueldo_base or 0
        if hasattr(contrato, 'gratificacion'):
            total_remuneracion += contrato.gratificacion or 0
        if hasattr(contrato, 'bonos'):
            total_remuneracion += contrato.bonos or 0
        
        # Determinar duración del contrato
        duracion_contrato = "Indefinido"
        if contrato.fecha_inicio and contrato.fecha_termino:
            try:
                from datetime import datetime
                inicio = contrato.fecha_inicio
                termino = contrato.fecha_termino
                
                if isinstance(inicio, str):
                    inicio = datetime.strptime(inicio, '%Y-%m-%d')
                if isinstance(termino, str):
                    termino = datetime.strptime(termino, '%Y-%m-%d')
                
                diferencia = termino - inicio
                dias = diferencia.days
                
                if dias >= 365:
                    anos = dias // 365
                    meses = (dias % 365) // 30
                    if meses > 0:
                        duracion_contrato = f"{anos} año{'s' if anos > 1 else ''} y {meses} mes{'es' if meses > 1 else ''}"
                    else:
                        duracion_contrato = f"{anos} año{'s' if anos > 1 else ''}"
                elif dias >= 30:
                    meses = dias // 30
                    dias_restantes = dias % 30
                    if dias_restantes > 0:
                        duracion_contrato = f"{meses} mes{'es' if meses > 1 else ''} y {dias_restantes} día{'s' if dias_restantes > 1 else ''}"
                    else:
                        duracion_contrato = f"{meses} mes{'es' if meses > 1 else ''}"
                else:
                    duracion_contrato = f"{dias} día{'s' if dias > 1 else ''}"
            except (ValueError, TypeError, AttributeError):
                duracion_contrato = "Período específico"
        
        # Determinar estado del contrato
        estado_contrato = "Activo"
        if contrato.fecha_termino:
            try:
                from datetime import date
                hoy = date.today()
                
                if isinstance(contrato.fecha_termino, str):
                    fecha_termino = datetime.strptime(contrato.fecha_termino, '%Y-%m-%d').date()
                else:
                    fecha_termino = contrato.fecha_termino
                
                if fecha_termino < hoy:
                    estado_contrato = "Finalizado"
                elif fecha_termino == hoy:
                    estado_contrato = "Finaliza hoy"
                else:
                    dias_restantes = (fecha_termino - hoy).days
                    if dias_restantes <= 30:
                        estado_contrato = f"Finaliza en {dias_restantes} día{'s' if dias_restantes > 1 else ''}"
            except (ValueError, TypeError, AttributeError):
                pass
        
        # Contexto para el template
        context = {
            'empresa': empresa,
            'alias': alias,
            'contrato': contrato,
            'bonos_detalle': bonos_detalle,
            'total_remuneracion': total_remuneracion,
            'duracion_contrato': duracion_contrato,
            'estado_contrato': estado_contrato,
            # Métodos get_display para campos con choices
            'tipo_contrato_display': contrato.get_tipo_contrato_display() if hasattr(contrato, 'get_tipo_contrato_display') else contrato.tipo_contrato,
            'jornada_display': contrato.get_jornada_display() if hasattr(contrato, 'get_jornada_display') else contrato.jornada,
            'afp_display': contrato.get_afp_display() if hasattr(contrato, 'get_afp_display') else (contrato.afp or "No especificado"),
            'salud_display': contrato.get_salud_display() if hasattr(contrato, 'get_salud_display') else (contrato.salud or "No especificado"),
            'sistema_gratificacion_display': contrato.get_sistema_gratificacion_display() if hasattr(contrato, 'get_sistema_gratificacion_display') else (contrato.sistema_gratificacion or ""),
            'tipo_gratificacion_display': contrato.get_tipo_gratificacion_display() if hasattr(contrato, 'get_tipo_gratificacion_display') else (contrato.tipo_gratificacion or ""),
        }
        
        # Verificar si la solicitud es para PDF
        if request.GET.get('pdf') == '1':
            return render(request, 'trabajadores/contrato_pdf.html', context)
        
        # Renderizar template normal
        return render(request, 'trabajadores/ver_contrato.html', context)
        
    except Http404:
        messages.error(request, 'El contrato solicitado no existe o no tiene permisos para acceder.')
        return redirect('lista_contratos', alias=alias)
    except Exception as e:
        messages.error(request, f'Error al cargar el contrato: {str(e)}')
        print(f"Error en ver_contrato: {str(e)}")  # Para debugging
        return redirect('lista_contratos', alias=alias)

def ver_contrato_pdf(request, alias, id):
    """Ver PDF del contrato."""
    try:
        contrato = ContratoLaboral.objects.get(id=id, alias=alias)
        if contrato.documento_pdf:
            return FileResponse(contrato.documento_pdf.open(), content_type='application/pdf')
        else:
            # Generar PDF si no existe
            contrato.documento_pdf = generar_contrato_pdf(contrato)
            contrato.save()
            return FileResponse(contrato.documento_pdf.open(), content_type='application/pdf')
    except ContratoLaboral.DoesNotExist:
        raise Http404("Contrato no encontrado.")

def editar_contrato(request, alias, id):
    """Editar contrato existente."""
    contrato = get_object_or_404(ContratoLaboral, id=id, alias=alias)
    
    if request.method == 'POST':
        form = ContratoForm(request.POST, instance=contrato)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Contrato actualizado correctamente.")
            return redirect(f'/trabajadores/{alias}/contratos/')
    else:
        form = ContratoForm(instance=contrato)
    
    return render(request, 'trabajadores/editar_contrato.html', {
        'form': form,
        'alias': alias,
        'contrato': contrato,
        'empresa': {'alias': alias, 'nombre': alias.replace('-', ' ').title()}
    })

def eliminar_contrato(request, alias, id):
    """Eliminar contrato."""
    if request.method == 'POST':
        contrato = get_object_or_404(ContratoLaboral, id=id, alias=alias)
        contrato.delete()
        messages.success(request, "✅ Contrato eliminado correctamente.")
    return redirect(f'/trabajadores/{alias}/contratos/')

# ================ VISTAS DE FINIQUITOS ================

def crear_finiquito(request, alias):
    if request.method == 'POST':
        form = FiniquitoForm(request.POST)
        if form.is_valid():
            finiquito = form.save(commit=False)
            finiquito.alias = alias
            finiquito.save()
            finiquito.documento_pdf = generar_finiquito_pdf(finiquito)
            finiquito.save()
            messages.success(request, "✅ Finiquito creado correctamente.")
            return redirect(f'/trabajadores/{alias}/finiquitos/')
    else:
        form = FiniquitoForm()
    
    return render(request, 'trabajadores/crear_finiquito.html', {
        'form': form,
        'alias': alias,
        'empresa': {'alias': alias, 'nombre': alias.replace('-', ' ').title()}
    })

def listado_finiquitos(request, alias):
    finiquitos = FiniquitoLaboral.objects.filter(alias=alias).order_by('-fecha_finiquito')
    
    return render(request, 'trabajadores/listado_finiquitos.html', {
        'finiquitos': finiquitos,
        'alias': alias,
        'empresa': {'alias': alias, 'nombre': alias.replace('-', ' ').title()}
    })

def ver_finiquito_pdf(request, alias, id):
    try:
        finiquito = FiniquitoLaboral.objects.get(id=id, alias=alias)
        if finiquito.documento_pdf:
            return FileResponse(finiquito.documento_pdf.open(), content_type='application/pdf')
        else:
            raise Http404("Finiquito sin PDF generado.")
    except FiniquitoLaboral.DoesNotExist:
        raise Http404("Finiquito no encontrado.")

# ================ VISTAS DE LIQUIDACIONES ================

COMISIONES_AFP = {
    'uno': 0.0049,
    'modelo': 0.0058,
    'planvital': 0.0116,
    'habitat': 0.0127,
    'capital': 0.0144,
    'cuprum': 0.0144,
    'provida': 0.0145,
}

def crear_liquidacion(request, alias):
    modo = request.POST.get('modo', '')
    form_carga = LiquidacionForm()
    form_liquidacion = None
    contrato = None
    afp_nombre = 'planvital'

    if request.method == 'POST':
        if modo == 'cargar':
            trabajador_id = request.POST.get('trabajador')
            contrato = ContratoLaboral.objects.filter(
                id=trabajador_id,
                alias=alias
            ).filter(
                Q(fecha_termino__isnull=True) | Q(fecha_termino__gt=timezone.now())
            ).first()

            if contrato:
                sueldo_base = contrato.sueldo_base or 0
                gratificacion = calcular_gratificacion(contrato)
                bonos = contrato.bonos or 0
                afp_nombre = contrato.afp.lower()
                
                initial = {
                    'trabajador': contrato.id,
                    'sueldo_base': sueldo_base,
                    'gratificacion': gratificacion,
                    'bonos': bonos,
                    'afp': calcular_afp(afp_nombre, sueldo_base, gratificacion, bonos),
                    'salud': calcular_salud(contrato.salud, sueldo_base, 30, 0),
                    'seguro_cesantia': calcular_seguro_cesantia(contrato.tipo_contrato, sueldo_base, 30),
                    'otros_descuentos': 0,
                    'dias_trabajados': 30,
                    'dias_licencia': 0,
                    'dias_vacaciones': 0,
                    'dias_ausente': 0,
                    'horas_extra_50': 0,
                    'horas_extra_100': 0,
                }
                form_liquidacion = LiquidacionForm(initial=initial)
            else:
                messages.error(request, "❌ El trabajador no tiene contrato vigente o indefinido.")

        elif modo == 'guardar':
            form_liquidacion = LiquidacionForm(request.POST)
            if form_liquidacion.is_valid():
                liquidacion = form_liquidacion.save(commit=False)
                liquidacion.alias = alias
                liquidacion.documento_pdf = generar_liquidacion_pdf(liquidacion)
                liquidacion.save()
                messages.success(request, "✅ Liquidación generada correctamente.")
                return redirect(f'/trabajadores/{alias}/liquidaciones/')
            else:
                messages.error(request, "❌ Hay errores en el formulario de liquidación.")

    if form_liquidacion is None:
        form_liquidacion = LiquidacionForm()

    return render(request, 'trabajadores/crear_liquidacion.html', {
        'form_carga': form_carga,
        'form_liquidacion': form_liquidacion,
        'alias': alias,
        'afp_nombre': afp_nombre,
        'contrato': contrato,
        'empresa': {'alias': alias, 'nombre': alias.replace('-', ' ').title()}
    })

def listado_liquidaciones(request, alias):
    mes = request.GET.get('mes')
    trabajador_id = request.GET.get('trabajador')

    liquidaciones = LiquidacionLaboral.objects.filter(alias=alias)
    if mes:
        liquidaciones = liquidaciones.filter(mes=mes)
    if trabajador_id:
        liquidaciones = liquidaciones.filter(trabajador_id=trabajador_id)

    trabajadores = ContratoLaboral.objects.filter(alias=alias)

    return render(request, 'trabajadores/listado_liquidaciones.html', {
        'liquidaciones': liquidaciones.order_by('-mes'),
        'trabajadores': trabajadores,
        'filtro_mes': mes,
        'filtro_trabajador': trabajador_id,
        'alias': alias,
        'empresa': {'alias': alias, 'nombre': alias.replace('-', ' ').title()}
    })

def ver_liquidacion_pdf(request, alias, id):
    liquidacion = get_object_or_404(LiquidacionLaboral, id=id, alias=alias)
    if liquidacion.documento_pdf:
        return FileResponse(liquidacion.documento_pdf.open(), content_type='application/pdf')
    raise Http404("Liquidación sin PDF generado.")

# ================ VISTAS ADICIONALES ================

def dashboard_trabajadores(request, alias):
    """
    Dashboard general de trabajadores.
    """
    # Estadísticas rápidas
    total_contratos = ContratoLaboral.objects.filter(alias=alias).count()
    total_trabajadores = Trabajador.objects.filter(alias=alias).count()
    total_finiquitos = FiniquitoLaboral.objects.filter(alias=alias).count()
    total_liquidaciones = LiquidacionLaboral.objects.filter(alias=alias).count()
    
    # Contratos por vencer (próximos 30 días)
    hoy = timezone.now().date()
    fecha_limite = hoy + timedelta(days=30)
    contratos_por_vencer = ContratoLaboral.objects.filter(
        alias=alias,
        fecha_termino__isnull=False,
        fecha_termino__gte=hoy,
        fecha_termino__lte=fecha_limite
    ).count()
    
    context = {
        'alias': alias,
        'empresa': {
            'nombre': alias.replace('-', ' ').title(),
            'alias': alias
        },
        'total_contratos': total_contratos,
        'total_trabajadores': total_trabajadores,
        'total_finiquitos': total_finiquitos,
        'total_liquidaciones': total_liquidaciones,
        'contratos_por_vencer': contratos_por_vencer,
        'hoy': hoy,
    }
    
    return render(request, 'trabajadores/dashboard.html', context)