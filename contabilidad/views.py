from django.shortcuts import render

from django.db.models import Sum
from django.utils import timezone



def panel_libro_sii(request, alias):
    # Placeholder: lógica para mostrar panel del libro SII
    return render(request, 'contabilidad/panel_libro_sii.html', {'alias': alias})



from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from django.utils import timezone
from empresas.models import Empresa
from .models import Trabajador, Periodo, Liquidacion, CentroCosto

def panel_remuneraciones(request, alias):
    empresa = get_object_or_404(Empresa, slug=alias)
    
    hoy = timezone.now()
    
    # Período activo (prioritario)
    periodo_activo = Periodo.objects.filter(empresa=empresa, estado='ACTIVO').first()
    if periodo_activo:
        mes = periodo_activo.mes
        año = periodo_activo.anio
    else:
        mes = hoy.month
        año = hoy.year
    
    # Estadísticas
    total_trabajadores = Trabajador.objects.filter(empresa=empresa, esta_activo=True).count()
    
    trabajadores_con_afp = Trabajador.objects.filter(
        empresa=empresa, esta_activo=True
    ).exclude(afp='').count()
    
    # Número de Isapres distintas (planes) que tienen trabajadores activos
    isapres_distintas = Trabajador.objects.filter(
        empresa=empresa, esta_activo=True
    ).exclude(isapre='').values('isapre').distinct().count()
    
    periodos_activos = Periodo.objects.filter(empresa=empresa, estado='ACTIVO').count()
    
    liquidaciones_mes = Liquidacion.objects.filter(
        periodo__empresa=empresa,
        periodo__mes=mes,
        periodo__anio=año
    ).count()
    
    total_remuneraciones = Liquidacion.objects.filter(
        periodo__empresa=empresa,
        periodo__mes=mes,
        periodo__anio=año
    ).aggregate(total=Sum('liquido_pagable'))['total'] or 0
    
    ultima_liquidacion_obj = Liquidacion.objects.filter(
        periodo__empresa=empresa
    ).order_by('-fecha_generacion').first()
    ultima_liquidacion = (
        ultima_liquidacion_obj.fecha_generacion.strftime('%d/%m/%Y')
        if ultima_liquidacion_obj else 'No hay'
    )
    
    total_centros_costo = CentroCosto.objects.filter(empresa=empresa, activo=True).count()
    
    nombre_usuario = request.user.get_full_name() or request.user.username or 'Administrador'
    
    context = {
        'alias': alias,
        'empresa': empresa,
        'mes': mes,
        'año': año,
        'total_trabajadores': total_trabajadores,
        'afp': {'trabajadores': trabajadores_con_afp},
        'isapre': {'planes': isapres_distintas},
        'periodos_activos': periodos_activos,
        'liquidaciones_mes': liquidaciones_mes,
        'total_remuneraciones': total_remuneraciones,
        'ultima_liquidacion': ultima_liquidacion,
        'total_centros_costo': total_centros_costo,
        'usuario': {'nombre': nombre_usuario},
    }
    
    return render(request, 'contabilidad/panel_remuneraciones.html', context)

# contabilidad/views.py
# contabilidad/views.py
# contabilidad/views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from decimal import Decimal
import json
from .models import AFP, Isapre
from datetime import datetime
from django.views.decorators.http import require_GET
from empresas.models import Empresa

# contabilidad/views.py - en panel_afp
def panel_afp(request, alias):
    """
    Vista para administrar las AFP - Solo los campos de la imagen
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener todas las AFP desde el modelo
    afps = AFP.objects.all().order_by('codigo')
    
    # Crear una copia de los datos con valores formateados para el template
    afps_formateados = []
    for afp in afps:
        # Formatear la cotización para usar punto decimal
        cotizacion_formateada = format(afp.cotizacion_obligatoria, '.2f').replace(',', '.')
        
        afps_formateados.append({
            'id': afp.id,
            'codigo': afp.codigo,
            'nombre': afp.nombre,
            'cotizacion_obligatoria': cotizacion_formateada,  # Ya formateado
            'codigo_previred': afp.codigo_previred,
            'regimen': afp.regimen,
            'codigo_dt': afp.codigo_dt,
        })
    
    context = {
        'empresa': empresa,
        'alias': alias,
        'afps': afps_formateados,  # Usar la versión formateada
        'total_afp': len(afps_formateados),
    }
    
    return render(request, 'contabilidad/afp.html', context)

@require_POST
def actualizar_cotizacion(request, alias):
    """
    Actualiza solo la cotización obligatoria (campo editable de la imagen)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        afp_id = data.get('afp_id')
        nueva_cotizacion = data.get('cotizacion')
        
        if not afp_id or nueva_cotizacion is None:
            return JsonResponse({
                'success': False,
                'error': 'Datos incompletos'
            })
        
        # Actualizar la cotización desde el modelo
        afp = AFP.objects.get(id=afp_id)
        afp.cotizacion_obligatoria = Decimal(str(nueva_cotizacion))
        afp.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Cotización de {afp.codigo} actualizada a {nueva_cotizacion}%'
        })
        
    except AFP.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'AFP no encontrada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def agregar_afp(request, alias):
    """
    Agrega una nueva AFP (Botón "Agregar" de la imagen)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        
        # Validar campos requeridos
        codigo = data.get('codigo', '').strip().upper()
        nombre = data.get('nombre', '').strip()
        cotizacion = data.get('cotizacion', '0')
        codigo_previred = data.get('codigo_previred', '').strip()
        regimen = data.get('regimen', 'AFP')
        codigo_dt = data.get('codigo_dt', '').strip()
        
        if not codigo or not nombre:
            return JsonResponse({
                'success': False,
                'error': 'Código y Nombre son obligatorios'
            })
        
        # Verificar que no exista una AFP con el mismo código
        if AFP.objects.filter(codigo=codigo).exists():
            return JsonResponse({
                'success': False,
                'error': f'Ya existe una AFP con el código {codigo}'
            })
        
        # Determinar valores según régimen
        cotiz_empleador = Decimal('2.50') if regimen == 'AFP' else Decimal('0.00')
        sis_valor = Decimal('1.15') if regimen == 'AFP' else Decimal('0.00')
        
        # Crear la nueva AFP usando el modelo
        afp = AFP.objects.create(
            codigo=codigo,
            nombre=nombre,
            cotizacion_obligatoria=Decimal(str(cotizacion)),
            cotizacion_empleador=cotiz_empleador,
            sis=sis_valor,
            codigo_previred=codigo_previred,
            regimen=regimen,
            codigo_dt=codigo_dt,
            activa=True
        )
        
        return JsonResponse({
            'success': True,
            'message': f'AFP {codigo} - {nombre} agregada correctamente',
            'afp_id': afp.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def eliminar_afp(request, alias):
    """
    Eliminar una AFP
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        afp_id = data.get('afp_id')
        
        if not afp_id:
            return JsonResponse({
                'success': False,
                'error': 'ID de AFP es requerido'
            })
        
        # Buscar y eliminar la AFP desde el modelo
        afp = get_object_or_404(AFP, id=afp_id)
        codigo = afp.codigo
        nombre = afp.nombre
        
        # Eliminar la AFP
        afp.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'AFP {codigo} - {nombre} eliminada correctamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def buscar_afp(request, alias):
    """
    Buscar AFP (Botón "Buscar" de la imagen)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        busqueda = data.get('busqueda', '').strip().upper()
        
        if busqueda:
            # Buscar por código o nombre en el modelo
            afps = AFP.objects.filter(
                codigo__icontains=busqueda
            ) | AFP.objects.filter(
                nombre__icontains=busqueda
            )
        else:
            # Si no hay búsqueda, mostrar todas desde el modelo
            afps = AFP.objects.all()
        
        # Formatear resultados
        resultados = []
        for afp in afps.order_by('codigo'):
            resultados.append({
                'id': afp.id,
                'codigo': afp.codigo,
                'nombre': afp.nombre,
                'cotizacion': float(afp.cotizacion_obligatoria),
                'cotizacion_empleador': float(afp.cotizacion_empleador),
                'sis': float(afp.sis),
                'cotizacion_total': float(afp.cotizacion_obligatoria + afp.cotizacion_empleador + afp.sis),
                'codigo_previred': afp.codigo_previred,
                'regimen': afp.regimen,
                'regimen_display': afp.get_regimen_display(),
                'codigo_dt': afp.codigo_dt,
                'activa': afp.activa,
            })
        
        return JsonResponse({
            'success': True,
            'resultados': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def actualizar_cotizaciones(request, alias):
    """
    Endpoint para actualizar cotizaciones desde SII
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        # Aquí iría la lógica real para consultar el SII
        # Por ahora simulamos una actualización
        
        hoy = datetime.now().date()
        actualizadas = 0
        
        # Datos simulados del SII (en producción, estos vendrían de una API del SII)
        datos_sii = {
            'CUMP': {'cotizacion_obligatoria': Decimal('11.50')},
            'HABI': {'cotizacion_obligatoria': Decimal('11.30')},
            'MODE': {'cotizacion_obligatoria': Decimal('10.60')},
            'PROV': {'cotizacion_obligatoria': Decimal('11.50')},
            'PVIT': {'cotizacion_obligatoria': Decimal('11.20')},
            'STMA': {'cotizacion_obligatoria': Decimal('11.50')},
            'UNO': {'cotizacion_obligatoria': Decimal('10.50')},
        }
        
        with transaction.atomic():
            for codigo, valores in datos_sii.items():
                try:
                    afp = AFP.objects.get(codigo=codigo)
                    afp.cotizacion_obligatoria = valores['cotizacion_obligatoria']
                    afp.save()
                    actualizadas += 1
                except AFP.DoesNotExist:
                    continue
        
        return JsonResponse({
            'success': True,
            'message': f'Se actualizaron {actualizadas} AFP desde el SII',
            'fecha_actualizacion': hoy.strftime('%d/%m/%Y')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def guardar_cambios_afp(request, alias):
    """
    Endpoint para guardar cambios en las cotizaciones
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        cambios = data.get('cambios', [])
        
        if not cambios:
            return JsonResponse({
                'success': False,
                'error': 'No se recibieron datos para guardar'
            })
        
        with transaction.atomic():
            for cambio in cambios:
                afp_id = cambio.get('id')
                campo = cambio.get('campo')
                valor = cambio.get('valor')
                
                try:
                    afp = AFP.objects.get(id=afp_id)
                    
                    if campo == 'cotizacion_obligatoria':
                        afp.cotizacion_obligatoria = Decimal(str(valor))
                    elif campo == 'cotizacion_empleador':
                        afp.cotizacion_empleador = Decimal(str(valor))
                    elif campo == 'sis':
                        afp.sis = Decimal(str(valor))
                    elif campo == 'activa':
                        afp.activa = bool(valor)
                    elif campo == 'regimen':
                        afp.regimen = valor
                        # Actualizar valores derivados si cambia el régimen
                        if valor in ['INP', 'SIP']:
                            afp.cotizacion_empleador = Decimal('0.00')
                            afp.sis = Decimal('0.00')
                    
                    afp.save()
                    
                except (AFP.DoesNotExist, ValueError) as e:
                    continue
        
        return JsonResponse({
            'success': True,
            'message': f'Se guardaron {len(cambios)} cambios correctamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def toggle_afp_activa(request, alias):
    """
    Activar/desactivar una AFP en el sistema
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        afp_id = data.get('afp_id')
        activa = data.get('activa')
        
        afp = get_object_or_404(AFP, id=afp_id)
        
        # No permitir desactivar AFP predeterminadas principales
        if not activa and afp.codigo in ['CUMP', 'HABI', 'PROV', 'fona']:
            return JsonResponse({
                'success': False,
                'error': 'No se puede desactivar esta AFP principal'
            })
        
        afp.activa = activa
        afp.save()
        
        return JsonResponse({
            'success': True,
            'message': f'AFP {afp.nombre} {"activada" if activa else "desactivada"} en el sistema'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_GET
def obtener_datos_afp(request, alias):
    """
    Endpoint para obtener datos de AFP en formato JSON
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener AFP activas desde el modelo
    afps = AFP.objects.filter(activa=True).order_by('codigo')
    
    datos = []
    for afp in afps:
        datos.append({
            'id': afp.id,
            'codigo': afp.codigo,
            'nombre': afp.nombre,
            'cotizacion': float(afp.cotizacion_obligatoria),
            'cotizacion_empleador': float(afp.cotizacion_empleador),
            'sis': float(afp.sis),
            'cotizacion_total': float(afp.cotizacion_obligatoria + afp.cotizacion_empleador + afp.sis),
            'codigo_previred': afp.codigo_previred,
            'regimen': afp.regimen,
            'regimen_display': afp.get_regimen_display(),
            'codigo_dt': afp.codigo_dt,
            'activa': afp.activa,
        })
    
    return JsonResponse({
        'success': True,
        'datos': datos,
        'total': len(datos),
        'empresa': empresa.nombre
    })


# contabilidad/views.py - función panel_isapre
def panel_isapre(request, alias):
    """
    Vista para administrar las Isapres
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener el período actual
    hoy = datetime.now()
    mes_actual = hoy.month
    año_actual = hoy.year
    
    # Obtener todas las Isapres desde el modelo
    isapres = Isapre.objects.all().order_by('codigo')
    
    # Crear una copia de los datos con valores formateados para el template
    isapres_formateados = []
    for isapre in isapres:
        # Formatear la cotización para usar punto decimal
        cotizacion_formateada = format(isapre.cotizacion_obligatoria, '.2f').replace(',', '.')
        
        isapres_formateados.append({
            'id': isapre.id,
            'codigo': isapre.codigo,
            'nombre': isapre.nombre,
            'cotizacion_obligatoria': cotizacion_formateada,  # Ya formateado
            'codigo_previred': isapre.codigo_previred,
            'codigo_dt': isapre.codigo_dt,
            'tipo': isapre.tipo,
            'estado': isapre.estado,
            'activa': isapre.activa,
            # Campos para display (get_FOO_display)
            'tipo_display': isapre.get_tipo_display(),
            'estado_display': isapre.get_estado_display(),
        })
    
    # Calcular estadísticas
    total_isapres = isapres.filter(tipo='ISAPRE', activa=True).count()
    total_fonasa = isapres.filter(tipo='FONASA', activa=True).count()
    total_sin = isapres.filter(tipo='SIN', activa=True).count()
    total_todos = isapres.filter(activa=True).count()
    
    context = {
        'empresa': empresa,
        'alias': alias,
        'mes': mes_actual,
        'año': año_actual,
        'isapres': isapres_formateados,  # Usar la versión formateada
        'total_isapres': total_isapres,
        'total_fonasa': total_fonasa,
        'total_sin': total_sin,
        'total_todos': total_todos,
    }
    
    return render(request, 'contabilidad/isapre.html', context)

@require_POST
def actualizar_cotizacion_isapre(request, alias):
    """
    Actualiza la cotización de una Isapre
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        isapre_id = data.get('isapre_id')
        nueva_cotizacion = data.get('cotizacion')
        
        if not isapre_id or nueva_cotizacion is None:
            return JsonResponse({
                'success': False,
                'error': 'Datos incompletos'
            })
        
        # Verificar que no sea SIN ISAPRE (tiene cotización 0%)
        isapre = Isapre.objects.get(id=isapre_id)
        
        # Solo actualizar si es editable
        if isapre.codigo == 'SIN':
            return JsonResponse({
                'success': False,
                'error': 'No se puede modificar SIN ISAPRE'
            })
        
        # Actualizar la cotización desde el modelo
        isapre.cotizacion_obligatoria = Decimal(str(nueva_cotizacion))
        isapre.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Cotización de {isapre.codigo} actualizada a {nueva_cotizacion}%'
        })
        
    except Isapre.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Isapre no encontrada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def agregar_isapre(request, alias):
    """
    Agrega una nueva Isapre
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        
        # Validar campos requeridos
        codigo = data.get('codigo', '').strip()
        nombre = data.get('nombre', '').strip()
        cotizacion = data.get('cotizacion', '7.00')
        codigo_previred = data.get('codigo_previred', '').strip()
        codigo_dt = data.get('codigo_dt', '').strip()
        tipo = data.get('tipo', 'ISAPRE')
        estado = data.get('estado', 'ACTIVA')
        
        if not codigo or not nombre:
            return JsonResponse({
                'success': False,
                'error': 'Código y Nombre son obligatorios'
            })
        
        # Verificar que no exista una Isapre con el mismo código
        if Isapre.objects.filter(codigo=codigo).exists():
            return JsonResponse({
                'success': False,
                'error': f'Ya existe una Isapre con el código {codigo}'
            })
        
        # Crear la nueva Isapre usando el modelo
        isapre = Isapre.objects.create(
            codigo=codigo,
            nombre=nombre,
            cotizacion_obligatoria=Decimal(str(cotizacion)),
            codigo_previred=codigo_previred,
            codigo_dt=codigo_dt,
            tipo=tipo,
            estado=estado,
            activa=True
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Isapre {codigo} - {nombre} agregada correctamente',
            'isapre_id': isapre.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def buscar_isapre(request, alias):
    """
    Buscar Isapres
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        busqueda = data.get('busqueda', '').strip()
        
        if busqueda:
            # Buscar por código o nombre en el modelo
            isapres = Isapre.objects.filter(
                codigo__icontains=busqueda
            ) | Isapre.objects.filter(
                nombre__icontains=busqueda
            )
        else:
            # Si no hay búsqueda, mostrar todas desde el modelo
            isapres = Isapre.objects.all()
        
        # Formatear resultados
        resultados = []
        for isapre in isapres.order_by('codigo'):
            resultados.append({
                'id': isapre.id,
                'codigo': isapre.codigo,
                'nombre': isapre.nombre,
                'cotizacion': float(isapre.cotizacion_obligatoria),
                'codigo_previred': isapre.codigo_previred,
                'codigo_dt': isapre.codigo_dt,
                'tipo': isapre.tipo,
                'tipo_display': isapre.get_tipo_display(),
                'estado': isapre.estado,
                'estado_display': isapre.get_estado_display(),
                'activa': isapre.activa,
            })
        
        return JsonResponse({
            'success': True,
            'resultados': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def eliminar_isapre(request, alias):
    """
    Eliminar una Isapre
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        isapre_id = data.get('isapre_id')
        
        if not isapre_id:
            return JsonResponse({
                'success': False,
                'error': 'ID de Isapre es requerido'
            })
        
        # Buscar y eliminar la Isapre desde el modelo
        isapre = Isapre.objects.get(id=isapre_id)
        
        # Proteger Fonasa y SIN ISAPRE (predeterminadas)
        if isapre.codigo in ['fona', 'SIN']:
            return JsonResponse({
                'success': False,
                'error': 'No se puede eliminar Fonasa o SIN ISAPRE'
            })
        
        codigo = isapre.codigo
        nombre = isapre.nombre
        
        # Eliminar la Isapre
        isapre.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Isapre {codigo} - {nombre} eliminada correctamente'
        })
        
    except Isapre.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Isapre no encontrada'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def actualizar_desde_sii_isapre(request, alias):
    """
    Actualizar Isapres desde SII (simulación)
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        hoy = datetime.now().date()
        
        # En una implementación real, aquí se conectaría con el SII
        # Por ahora simulamos una actualización
        
        # Datos simulados del SII
        datos_sii = {
            'BANM': {'cotizacion_obligatoria': Decimal('7.00')},
            'CMN': {'cotizacion_obligatoria': Decimal('7.00')},
            'CRZB': {'cotizacion_obligatoria': Decimal('7.00')},
            'cons': {'cotizacion_obligatoria': Decimal('7.00')},
            'ESE': {'cotizacion_obligatoria': Decimal('7.00')},
            'fona': {'cotizacion_obligatoria': Decimal('7.00')},
        }
        
        actualizadas = 0
        with transaction.atomic():
            for codigo, valores in datos_sii.items():
                try:
                    isapre = Isapre.objects.get(codigo=codigo)
                    isapre.cotizacion_obligatoria = valores['cotizacion_obligatoria']
                    isapre.save()
                    actualizadas += 1
                except Isapre.DoesNotExist:
                    continue
        
        return JsonResponse({
            'success': True,
            'message': f'Se actualizaron {actualizadas} Isapres desde el SII',
            'fecha_actualizacion': hoy.strftime('%d/%m/%Y'),
            'actualizadas': actualizadas
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def toggle_isapre_activa(request, alias):
    """
    Activar/desactivar una Isapre en el sistema
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        isapre_id = data.get('isapre_id')
        activa = data.get('activa')
        
        isapre = get_object_or_404(Isapre, id=isapre_id)
        
        # No permitir desactivar Isapres predeterminadas principales
        if not activa and isapre.codigo in ['fona', 'SIN']:
            return JsonResponse({
                'success': False,
                'error': 'No se puede desactivar Fonasa o SIN ISAPRE'
            })
        
        isapre.activa = activa
        isapre.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Isapre {isapre.nombre} {"activada" if activa else "desactivada"} en el sistema'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_GET
def obtener_datos_isapre(request, alias):
    """
    Endpoint para obtener datos de Isapre en formato JSON
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener Isapres activas desde el modelo
    isapres = Isapre.objects.filter(activa=True).order_by('codigo')
    
    datos = []
    for isapre in isapres:
        datos.append({
            'id': isapre.id,
            'codigo': isapre.codigo,
            'nombre': isapre.nombre,
            'cotizacion': float(isapre.cotizacion_obligatoria),
            'codigo_previred': isapre.codigo_previred,
            'codigo_dt': isapre.codigo_dt,
            'tipo': isapre.tipo,
            'tipo_display': isapre.get_tipo_display(),
            'estado': isapre.estado,
            'estado_display': isapre.get_estado_display(),
            'activa': isapre.activa,
        })
    
    return JsonResponse({
        'success': True,
        'datos': datos,
        'total': len(datos),
        'empresa': empresa.nombre
    })

# contabilidad/views.py - Añade estas vistas
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import datetime, date
from decimal import Decimal
import json
from .models import Periodo

def panel_periodos(request, alias):
    """
    Vista principal para administrar períodos
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener el año actual
    año_actual = datetime.now().year
    
    # Obtener todos los períodos de la empresa
    periodos = Periodo.objects.filter(empresa=empresa).order_by('-anio', '-mes')
    
    # Calcular estadísticas
    total_periodos = periodos.count()
    periodos_activos = periodos.filter(estado='ACTIVO').count()
    periodos_anio_actual = periodos.filter(anio=año_actual).count()
    
    # Obtener el último período
    ultimo_periodo = periodos.first()
    
    context = {
        'empresa': empresa,
        'alias': alias,
        'año_actual': año_actual,
        'periodos': periodos,
        'total_periodos': total_periodos,
        'periodos_activos': periodos_activos,
        'periodos_anio_actual': periodos_anio_actual,
        'ultimo_periodo': ultimo_periodo,
    }
    
    return render(request, 'contabilidad/panel_periodo.html', context)


@require_POST
def agregar_periodo(request, alias):
    """
    Agregar un nuevo período
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        
        # Validar campos requeridos
        mes = int(data.get('mes', 0))
        anio = int(data.get('anio', 0))
        fecha_inicio_str = data.get('fecha_inicio', '')
        fecha_fin_str = data.get('fecha_fin', '')
        
        if not mes or not anio or not fecha_inicio_str or not fecha_fin_str:
            return JsonResponse({
                'success': False,
                'error': 'Todos los campos son obligatorios'
            })
        
        # Convertir fechas de DDMMAAAA a objeto date
        def parse_fecha(fecha_str):
            try:
                dia = int(fecha_str[:2])
                mes = int(fecha_str[2:4])
                anio = int(fecha_str[4:8])
                return date(anio, mes, dia)
            except (ValueError, IndexError):
                raise ValidationError('Formato de fecha inválido')
        
        fecha_inicio = parse_fecha(fecha_inicio_str)
        fecha_fin = parse_fecha(fecha_fin_str)
        
        # Verificar que no exista un período para el mismo mes/año/empresa
        if Periodo.objects.filter(
            empresa=empresa,
            mes=mes,
            anio=anio
        ).exists():
            return JsonResponse({
                'success': False,
                'error': f'Ya existe un período para {mes}/{anio}'
            })
        
        # Crear el nuevo período
        periodo = Periodo.objects.create(
            empresa=empresa,
            mes=mes,
            anio=anio,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            uf=Decimal(str(data.get('uf', '0'))),
            utm=Decimal(str(data.get('utm', '0'))),
            dias_habiles=int(data.get('dias_habiles', '22')),
            dias_no_habiles=int(data.get('dias_no_habiles', '9')),
            factor_actualizacion=Decimal(str(data.get('factor_actualizacion', '1.0000'))),
            estado=data.get('estado', 'ACTIVO').upper()
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Período {periodo.mes_anio} agregado correctamente',
            'periodo_id': periodo.id
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al crear período: {str(e)}'
        }, status=500)


@require_POST
def editar_periodo(request, alias, periodo_id):
    """
    Editar un período existente
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    periodo = get_object_or_404(Periodo, id=periodo_id, empresa=empresa)
    
    try:
        data = json.loads(request.body)
        
        # Convertir fechas de DDMMAAAA a objeto date
        def parse_fecha(fecha_str):
            try:
                dia = int(fecha_str[:2])
                mes_fecha = int(fecha_str[2:4])
                anio = int(fecha_str[4:8])
                return date(anio, mes_fecha, dia)
            except (ValueError, IndexError):
                raise ValidationError('Formato de fecha inválido')
        
        # Actualizar campos
        if 'fecha_inicio' in data:
            periodo.fecha_inicio = parse_fecha(data['fecha_inicio'])
        
        if 'fecha_fin' in data:
            periodo.fecha_fin = parse_fecha(data['fecha_fin'])
        
        if 'mes' in data:
            periodo.mes = int(data['mes'])
        
        if 'anio' in data:
            periodo.anio = int(data['anio'])
        
        if 'uf' in data:
            periodo.uf = Decimal(str(data['uf']))
        
        if 'utm' in data:
            periodo.utm = Decimal(str(data['utm']))
        
        if 'dias_habiles' in data:
            periodo.dias_habiles = int(data['dias_habiles'])
        
        if 'dias_no_habiles' in data:
            periodo.dias_no_habiles = int(data['dias_no_habiles'])
        
        if 'factor_actualizacion' in data:
            periodo.factor_actualizacion = Decimal(str(data['factor_actualizacion']))
        
        if 'estado' in data:
            periodo.estado = data['estado'].upper()
        
        # Validar y guardar
        periodo.full_clean()
        periodo.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Período {periodo.mes_anio} actualizado correctamente'
        })
        
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al actualizar período: {str(e)}'
        }, status=500)


@require_POST
def eliminar_periodo(request, alias, periodo_id):
    """
    Eliminar un período
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    periodo = get_object_or_404(Periodo, id=periodo_id, empresa=empresa)
    
    try:
        # Verificar si el período tiene liquidaciones asociadas
        # (agregar esta verificación si tienes modelo Liquidacion)
        
        nombre_periodo = str(periodo)
        periodo.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Período {nombre_periodo} eliminado correctamente'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al eliminar período: {str(e)}'
        }, status=500)


@require_POST
def buscar_periodos(request, alias):
    """
    Buscar períodos por filtros
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    
    try:
        data = json.loads(request.body)
        filtro_anio = data.get('anio', '')
        
        # Construir consulta
        periodos_query = Periodo.objects.filter(empresa=empresa)
        
        if filtro_anio:
            periodos_query = periodos_query.filter(anio=int(filtro_anio))
        
        # Ordenar resultados
        periodos = periodos_query.order_by('-anio', '-mes')
        
        # Formatear resultados
        resultados = []
        for periodo in periodos:
            resultados.append({
                'id': periodo.id,
                'mes': periodo.mes,
                'anio': periodo.anio,
                'mes_anio': periodo.mes_anio,
                'fecha_inicio': periodo.fecha_inicio.strftime('%d/%m/%Y'),
                'fecha_fin': periodo.fecha_fin.strftime('%d/%m/%Y'),
                'uf': float(periodo.uf),
                'utm': float(periodo.utm),
                'dias_habiles': periodo.dias_habiles,
                'dias_no_habiles': periodo.dias_no_habiles,
                'factor_actualizacion': float(periodo.factor_actualizacion),
                'estado': periodo.estado,
                'estado_display': periodo.get_estado_display(),
            })
        
        return JsonResponse({
            'success': True,
            'resultados': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def crear_periodos_predeterminados(empresa):
    """
    Crear períodos predeterminados para una empresa
    """
    # Datos de ejemplo
    periodos_predeterminados = [
        {
            'mes': 1,
            'anio': 2025,
            'fecha_inicio': date(2025, 1, 1),
            'fecha_fin': date(2025, 1, 31),
            'uf': Decimal('36452.12'),
            'utm': Decimal('65048.00'),
            'dias_habiles': 22,
            'dias_no_habiles': 9,
            'factor_actualizacion': Decimal('1.0345'),
            'estado': 'ACTIVO'
        },
        {
            'mes': 2,
            'anio': 2025,
            'fecha_inicio': date(2025, 2, 1),
            'fecha_fin': date(2025, 2, 28),
            'uf': Decimal('36520.45'),
            'utm': Decimal('65120.00'),
            'dias_habiles': 20,
            'dias_no_habiles': 8,
            'factor_actualizacion': Decimal('1.0352'),
            'estado': 'ACTIVO'
        },
        {
            'mes': 3,
            'anio': 2025,
            'fecha_inicio': date(2025, 3, 1),
            'fecha_fin': date(2025, 3, 31),
            'uf': Decimal('36680.30'),
            'utm': Decimal('65200.00'),
            'dias_habiles': 21,
            'dias_no_habiles': 10,
            'factor_actualizacion': Decimal('1.0360'),
            'estado': 'ACTIVO'
        },
        {
            'mes': 12,
            'anio': 2024,
            'fecha_inicio': date(2024, 12, 1),
            'fecha_fin': date(2024, 12, 31),
            'uf': Decimal('36320.40'),
            'utm': Decimal('64800.00'),
            'dias_habiles': 22,
            'dias_no_habiles': 9,
            'factor_actualizacion': Decimal('1.0320'),
            'estado': 'CERRADO'
        },
    ]
    
    creados = 0
    for periodo_data in periodos_predeterminados:
        periodo_data['empresa'] = empresa
        Periodo.objects.get_or_create(
            empresa=empresa,
            mes=periodo_data['mes'],
            anio=periodo_data['anio'],
            defaults=periodo_data
        )
        creados += 1
    
    return creados

from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from datetime import datetime, timedelta
from django.http import JsonResponse
from .models import Trabajador
from empresas.models import Empresa
from django.db.models import Q

@login_required
def panel_trabajadores(request, alias):
    """
    Vista para listar trabajadores con datos REALES de la base de datos
    """
    # Obtener empresa real
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Obtener parámetros de búsqueda
    rut_buscar = request.GET.get('rut', '').strip()
    apellido_buscar = request.GET.get('apellido', '').strip()
    covid_buscar = request.GET.get('covid', '')
    centro_buscar = request.GET.get('centro', '').strip()
    
    # Obtener trabajadores REALES filtrados por empresa
    trabajadores_qs = Trabajador.objects.filter(empresa=empresa)
    
    # Aplicar filtros dinámicos
    if rut_buscar:
        # Buscar por RUT con o sin guión
        if '-' in rut_buscar:
            trabajadores_qs = trabajadores_qs.filter(rut__icontains=rut_buscar)
        else:
            # Si no tiene guión, buscar en la parte numérica
            trabajadores_qs = trabajadores_qs.filter(rut__startswith=rut_buscar)
    
    if apellido_buscar:
        # Buscar en ambos apellidos
        trabajadores_qs = trabajadores_qs.filter(
            Q(apellido_paterno__icontains=apellido_buscar) |
            Q(apellido_materno__icontains=apellido_buscar)
        )
    
    if covid_buscar:
        # Convertir 'SI'/'NO' a booleano para el filtro
        if covid_buscar == 'SI':
            trabajadores_qs = trabajadores_qs.filter(tiene_ficha_covid=True)
        elif covid_buscar == 'NO':
            trabajadores_qs = trabajadores_qs.filter(tiene_ficha_covid=False)
    
    if centro_buscar:
        # Buscar en nombre o código del centro de costo
        trabajadores_qs = trabajadores_qs.filter(
            Q(centro_costo_nombre__icontains=centro_buscar) |
            Q(centro_costo_codigo__icontains=centro_buscar)
        )
    
    # Preparar datos para la plantilla
    trabajadores_json = []
    for trabajador in trabajadores_qs:
        # Determinar estado del contrato
        estado_contrato = 'Activo'
        if trabajador.fecha_termino_contrato:
            hoy = timezone.now().date()
            dias_restantes = (trabajador.fecha_termino_contrato - hoy).days
            
            if dias_restantes < 0:
                estado_contrato = 'Vencido'
            elif dias_restantes <= 30:
                estado_contrato = 'Por Vencer'
        
        trabajadores_json.append({
            'id': trabajador.id,  # <--- AGREGAR ESTA LÍNEA
            'rut': trabajador.rut,
            'nombres': trabajador.nombres,
            'apellido_paterno': trabajador.apellido_paterno,
            'apellido_materno': trabajador.apellido_materno,
            'centro_costo': trabajador.centro_costo_nombre or trabajador.centro_costo_codigo,
            'fecha_contrato': trabajador.fecha_contrato.strftime('%d/%m/%Y') if trabajador.fecha_contrato else '',
            'fecha_termino': trabajador.fecha_termino_contrato.strftime('%d/%m/%Y') if trabajador.fecha_termino_contrato else '',
            'ficha_covid': 'SI' if trabajador.tiene_ficha_covid else 'NO',
            'estado_contrato': estado_contrato,
            'tiene_ficha_covid': trabajador.tiene_ficha_covid,
            'cargo': trabajador.cargo,
            'esta_activo': trabajador.esta_activo,
        })
    
    # Calcular estadísticas REALES
    total_trabajadores = trabajadores_qs.count()
    
    # Contratos activos: trabajadores con esta_activo=True
    contratos_activos = trabajadores_qs.filter(esta_activo=True).count()
    
    # Por vencer: contratos que terminan en los próximos 30 días
    hoy = timezone.now().date()
    fecha_limite = hoy + timedelta(days=30)
    por_vencer = trabajadores_qs.filter(
        fecha_termino_contrato__gte=hoy,
        fecha_termino_contrato__lte=fecha_limite,
        esta_activo=True
    ).count()
    
    # Con ficha COVID
    con_covid = trabajadores_qs.filter(tiene_ficha_covid=True).count()
    
    # Obtener centros de costo únicos para el dropdown
    centros_costo = []
    centros_costo_qs = Trabajador.objects.filter(
        empresa=empresa
    ).exclude(
        Q(centro_costo_nombre__isnull=True) | 
        Q(centro_costo_nombre='')
    ).values_list('centro_costo_nombre', flat=True).distinct()
    
    centros_costo = list(centros_costo_qs)
    
    # Si no hay centros de costo con nombre, usar códigos
    if not centros_costo:
        centros_costo_qs = Trabajador.objects.filter(
            empresa=empresa
        ).exclude(
            Q(centro_costo_codigo__isnull=True) | 
            Q(centro_costo_codigo='')
        ).values_list('centro_costo_codigo', flat=True).distinct()
        centros_costo = list(centros_costo_qs)
    
    # Si aún no hay centros, agregar algunos por defecto
    if not centros_costo:
        centros_costo = [
            'ADMINISTRACION',
            'PRODUCCION',
            'VENTAS',
            'LOGISTICA'
        ]
    
    context = {
        'alias': alias,
        'empresa': empresa,
        'trabajadores_json': trabajadores_json,
        'estadisticas': {
            'total': total_trabajadores,
            'activos': contratos_activos,
            'por_vencer': por_vencer,
            'con_covid': con_covid,
        },
        'filtros': {
            'rut': rut_buscar,
            'apellido': apellido_buscar,
            'covid': covid_buscar,
            'centro': centro_buscar,
        },
        'centros_costo': sorted(centros_costo)
    }
    
    return render(request, 'contabilidad/panel_trabajadores.html', context)


def generar_trabajadores_ejemplo():
    """
    Genera datos de ejemplo para trabajadores
    """
    nombres_masculinos = ['Juan', 'Pedro', 'Carlos', 'Luis', 'Miguel', 'Jorge', 'Francisco', 'Diego']
    nombres_femeninos = ['Ana', 'Maria', 'Carmen', 'Isabel', 'Laura', 'Patricia', 'Sofia', 'Elena']
    apellidos = ['García', 'Rodríguez', 'Martínez', 'López', 'González', 'Pérez', 'Sánchez', 'Ramírez']
    centros_costo = ['CENTRO ESTETICA RANC', 'ADMINISTRACION', 'PRODUCCION', 'VENTAS', 'LOGISTICA']
    
    trabajadores = []
    
    # Generar 30 trabajadores de ejemplo
    for i in range(1, 31):
        # Generar RUT ficticio
        rut_base = 16000000 + i
        rut_completo = f"{rut_base}-{random.choice(['1','2','3','4','5','6','7','8','9','k'])}"
        
        # Generar nombre
        es_masculino = random.choice([True, False])
        nombres = random.sample(nombres_masculinos if es_masculino else nombres_femeninos, random.randint(1, 2))
        nombres_str = ' '.join(nombres)
        
        # Generar apellidos
        apellido_paterno = random.choice(apellidos)
        apellido_materno = random.choice(apellidos)
        
        # Generar fechas
        fecha_inicio = datetime.now() - timedelta(days=random.randint(30, 1000))
        fecha_termino = fecha_inicio + timedelta(days=random.randint(180, 720))
        
        # Determinar estado del contrato
        dias_restantes = (fecha_termino - datetime.now()).days
        if dias_restantes < 0:
            estado = 'Vencido'
        elif dias_restantes <= 30:
            estado = 'Por Vencer'
        else:
            estado = 'Activo'
        
        # Determinar si tiene ficha COVID
        ficha_covid = random.choice(['SI', 'NO'])
        
        # Centro de costo aleatorio
        centro_costo = random.choice(centros_costo)
        
        trabajador = {
            'rut': rut_completo,
            'rut_sin_dv': str(rut_base),
            'nombres': nombres_str,
            'apellido_paterno': apellido_paterno,
            'apellido_materno': apellido_materno,
            'centro_costo': centro_costo,
            'fecha_contrato': fecha_inicio.strftime('%d/%m/%Y'),
            'fecha_termino': fecha_termino.strftime('%d/%m/%Y'),
            'ficha_covid': ficha_covid,
            'estado_contrato': estado,
            'cargo': random.choice(['Analista', 'Operario', 'Supervisor', 'Administrativo', 'Vendedor']),
            'sueldo_base': random.randint(450000, 1500000),
            'horas_semanales': random.choice([30, 35, 40, 44, 45]),
        }
        
        trabajadores.append(trabajador)
    
    return trabajadores


@login_required
def buscar_trabajadores_api(request, alias):
    """
    API simple para buscar trabajadores (para AJAX)
    """
    # Obtener parámetros de búsqueda
    rut = request.GET.get('rut', '')
    apellido = request.GET.get('apellido', '')
    covid = request.GET.get('covid', '')
    centro = request.GET.get('centro', '')
    
    # Generar datos de ejemplo
    trabajadores = generar_trabajadores_ejemplo()
    
    # Aplicar filtros
    resultados = []
    for trabajador in trabajadores:
        cumple_filtro = True
        
        if rut and rut not in trabajador['rut_sin_dv']:
            cumple_filtro = False
        if apellido and apellido.lower() not in trabajador['apellido_paterno'].lower():
            cumple_filtro = False
        if covid and covid != trabajador['ficha_covid']:
            cumple_filtro = False
        if centro and centro != trabajador['centro_costo']:
            cumple_filtro = False
            
        if cumple_filtro:
            resultados.append(trabajador)
    
    return JsonResponse({
        'success': True,
        'trabajadores': resultados,
        'total': len(resultados),
        'filtros': {
            'rut': rut,
            'apellido': apellido,
            'covid': covid,
            'centro': centro,
        }
    })


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import json
from datetime import datetime
from decimal import Decimal

from .models import Trabajador, AFP, Isapre, ValorUF, AFPEmpresa, Region, Comuna
from empresas.models import Empresa

# ------------------------------------------------------------
# Funciones auxiliares para cargar datos predeterminados
# ------------------------------------------------------------

def crear_afp_predeterminadas():
    """Crea AFP predeterminadas si no existen"""
    afps = [
        ('CAP', 'Capital', 11.44),
        ('CUPR', 'Cuprum', 11.44),
        ('HAB', 'Habitat', 11.27),
        ('MOD', 'Modelo', 10.77),
        ('PLAN', 'Planvital', 11.16),
        ('PRO', 'Provida', 11.44),
        ('UNO', 'Uno', 10.69),
    ]
    for codigo, nombre, cotizacion in afps:
        AFP.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': nombre,
                'cotizacion_obligatoria': cotizacion,
                'activa': True
            }
        )

def crear_isapres_predeterminadas():
    """Crea Isapres predeterminadas si no existen"""
    isapres = [
        ('BANM', 'Banmedica', 7.0),
        ('COLM', 'Colmena', 7.0),
        ('CONS', 'Consalud', 7.0),
        ('CRUZ', 'Cruz Blanca', 7.0),
        ('MAS', 'Más Vida', 7.0),
        ('VIDA', 'Vida Tres', 7.0),
        ('FONASA', 'FONASA', 7.0),
    ]
    for codigo, nombre, cotizacion in isapres:
        Isapre.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': nombre,
                'cotizacion_obligatoria': cotizacion,
                'estado': 'ACTIVA'
            }
        )

def cargar_regiones_comunas():
    """
    Carga todas las regiones y comunas de Chile en la base de datos.
    Si ya existen, no las duplica.
    """
    regiones_data = [
        {'codigo': 'XV', 'nombre': 'Arica y Parinacota', 'orden': 1},
        {'codigo': 'I', 'nombre': 'Tarapacá', 'orden': 2},
        {'codigo': 'II', 'nombre': 'Antofagasta', 'orden': 3},
        {'codigo': 'III', 'nombre': 'Atacama', 'orden': 4},
        {'codigo': 'IV', 'nombre': 'Coquimbo', 'orden': 5},
        {'codigo': 'V', 'nombre': 'Valparaíso', 'orden': 6},
        {'codigo': 'RM', 'nombre': 'Metropolitana de Santiago', 'orden': 7},
        {'codigo': 'VI', 'nombre': "Libertador General Bernardo O'Higgins", 'orden': 8},
        {'codigo': 'VII', 'nombre': 'Maule', 'orden': 9},
        {'codigo': 'VIII', 'nombre': 'Biobío', 'orden': 10},
        {'codigo': 'IX', 'nombre': 'La Araucanía', 'orden': 11},
        {'codigo': 'XIV', 'nombre': 'Los Ríos', 'orden': 12},
        {'codigo': 'X', 'nombre': 'Los Lagos', 'orden': 13},
        {'codigo': 'XI', 'nombre': 'Aysén del General Carlos Ibáñez del Campo', 'orden': 14},
        {'codigo': 'XII', 'nombre': 'Magallanes y de la Antártica Chilena', 'orden': 15},
        {'codigo': 'XVI', 'nombre': 'Ñuble', 'orden': 16},
    ]
    
    comunas_data = {
        'XV': ['Arica', 'Camarones', 'Putre', 'General Lagos'],
        'I': ['Iquique', 'Alto Hospicio', 'Pozo Almonte', 'Camiña', 'Colchane', 'Huara', 'Pica'],
        'II': ['Antofagasta', 'Mejillones', 'Sierra Gorda', 'Taltal', 'Calama', 'Ollagüe', 'San Pedro de Atacama', 'Tocopilla', 'María Elena'],
        'III': ['Copiapó', 'Caldera', 'Tierra Amarilla', 'Chañaral', 'Diego de Almagro', 'Vallenar', 'Alto del Carmen', 'Freirina', 'Huasco'],
        'IV': [
            'La Serena', 'Coquimbo', 'Andacollo', 'La Higuera', 'Paiguano', 'Vicuña',
            'Illapel', 'Canela', 'Los Vilos', 'Salamanca',
            'Ovalle', 'Combarbalá', 'Monte Patria', 'Punitaqui', 'Río Hurtado'
        ],
        'V': [
            'Valparaíso', 'Casablanca', 'Concón', 'Juan Fernández', 'Puchuncaví', 'Quintero', 'Viña del Mar',
            'Isla de Pascua',
            'Los Andes', 'Calle Larga', 'Rinconada', 'San Esteban',
            'La Ligua', 'Cabildo', 'Papudo', 'Petorca', 'Zapallar',
            'Quillota', 'Calera', 'Hijuelas', 'La Cruz', 'Nogales',
            'San Antonio', 'Algarrobo', 'Cartagena', 'El Quisco', 'El Tabo', 'Santo Domingo',
            'San Felipe', 'Catemu', 'Llaillay', 'Panquehue', 'Putaendo', 'Santa María',
            'Limache', 'Olmué', 'Villa Alemana', 'Quilpué'
        ],
        'RM': [
            'Santiago', 'Cerrillos', 'Cerro Navia', 'Conchalí', 'El Bosque', 'Estación Central', 'Huechuraba',
            'Independencia', 'La Cisterna', 'La Florida', 'La Granja', 'La Pintana', 'La Reina', 'Las Condes',
            'Lo Barnechea', 'Lo Espejo', 'Lo Prado', 'Macul', 'Maipú', 'Ñuñoa', 'Pedro Aguirre Cerda',
            'Peñalolén', 'Providencia', 'Pudahuel', 'Quilicura', 'Quinta Normal', 'Recoleta', 'Renca',
            'San Joaquín', 'San Miguel', 'San Ramón', 'Vitacura',
            'Puente Alto', 'Pirque', 'San José de Maipo',
            'Colina', 'Lampa', 'Til Til',
            'San Bernardo', 'Buin', 'Calera de Tango', 'Paine',
            'Melipilla', 'Alhué', 'Curacaví', 'María Pinto', 'San Pedro',
            'Talagante', 'El Monte', 'Isla de Maipo', 'Padre Hurtado', 'Peñaflor'
        ],
        'VI': [
            'Rancagua', 'Codegua', 'Coinco', 'Coltauco', 'Doñihue', 'Graneros', 'Las Cabras', 'Machalí', 'Malloa',
            'Mostazal', 'Olivar', 'Peumo', 'Pichidegua', 'Quinta de Tilcoco', 'Rengo', 'Requínoa', 'San Vicente',
            'Pichilemu', 'La Estrella', 'Litueche', 'Marchihue', 'Navidad', 'Paredones',
            'San Fernando', 'Chépica', 'Chimbarongo', 'Lolol', 'Nancagua', 'Palmilla', 'Peralillo', 'Placilla',
            'Pumanque', 'Santa Cruz'
        ],
        'VII': [
            'Talca', 'Constitución', 'Curepto', 'Empedrado', 'Maule', 'Pelarco', 'Pencahue', 'Río Claro', 'San Clemente', 'San Rafael',
            'Cauquenes', 'Chanco', 'Pelluhue',
            'Curicó', 'Hualañé', 'Licantén', 'Molina', 'Rauco', 'Romeral', 'Sagrada Familia', 'Teno', 'Vichuquén',
            'Linares', 'Colbún', 'Longaví', 'Parral', 'Retiro', 'San Javier', 'Villa Alegre', 'Yerbas Buenas'
        ],
        'VIII': [
            'Concepción', 'Coronel', 'Chiguayante', 'Florida', 'Hualpén', 'Hualqui', 'Lota', 'Penco', 'San Pedro de la Paz', 'Santa Juana', 'Talcahuano', 'Tomé',
            'Lebu', 'Arauco', 'Cañete', 'Contulmo', 'Curanilahue', 'Los Álamos', 'Tirúa',
            'Los Ángeles', 'Antuco', 'Cabrero', 'Laja', 'Mulchén', 'Nacimiento', 'Negrete', 'Quilaco', 'Quilleco', 'San Rosendo', 'Santa Bárbara', 'Tucapel', 'Yumbel', 'Alto Biobío',
            'Chillán', 'Bulnes', 'Cobquecura', 'Coelemu', 'Coihueco', 'Chillán Viejo', 'El Carmen', 'Ninhue', 'Ñiquén', 'Pemuco', 'Pinto', 'Portezuelo', 'Quillón', 'Quirihue', 'Ránquil', 'San Carlos', 'San Fabián', 'San Ignacio', 'San Nicolás', 'Treguaco', 'Yungay'
        ],
        'IX': [
            'Temuco', 'Carahue', 'Cunco', 'Curarrehue', 'Freire', 'Galvarino', 'Gorbea', 'Lautaro', 'Loncoche', 'Melipeuco', 'Nueva Imperial', 'Padre Las Casas', 'Perquenco', 'Pitrufquén', 'Pucón', 'Saavedra', 'Teodoro Schmidt', 'Toltén', 'Vilcún', 'Villarrica', 'Cholchol',
            'Angol', 'Collipulli', 'Curacautín', 'Ercilla', 'Lonquimay', 'Los Sauces', 'Lumaco', 'Purén', 'Renaico', 'Traiguén', 'Victoria'
        ],
        'XIV': [
            'Valdivia', 'Corral', 'Lanco', 'Los Lagos', 'Máfil', 'Mariquina', 'Paillaco', 'Panguipulli',
            'La Unión', 'Futrono', 'Lago Ranco', 'Río Bueno'
        ],
        'X': [
            'Puerto Montt', 'Calbuco', 'Cochamó', 'Fresia', 'Frutillar', 'Los Muermos', 'Llanquihue', 'Maullín', 'Puerto Varas',
            'Castro', 'Ancud', 'Chonchi', 'Curaco de Vélez', 'Dalcahue', 'Puqueldón', 'Queilén', 'Quellón', 'Quemchi', 'Quinchao',
            'Osorno', 'Puerto Octay', 'Purranque', 'Puyehue', 'Río Negro', 'San Juan de la Costa', 'San Pablo',
            'Chaitén', 'Futaleufú', 'Hualaihué', 'Palena'
        ],
        'XI': [
            'Coyhaique', 'Lago Verde', 'Aysén', 'Cisnes', 'Guaitecas', 'Cochrane', 'O\'Higgins', 'Tortel', 'Chile Chico', 'Río Ibáñez'
        ],
        'XII': [
            'Punta Arenas', 'Laguna Blanca', 'Río Verde', 'San Gregorio', 'Cabo de Hornos', 'Antártica', 'Porvenir', 'Primavera', 'Timaukel', 'Natales', 'Torres del Paine'
        ],
        'XVI': [
            'Chillán', 'Bulnes', 'Cobquecura', 'Coelemu', 'Coihueco', 'Chillán Viejo', 'El Carmen', 'Ninhue', 'Ñiquén', 'Pemuco', 'Pinto', 'Portezuelo', 'Quillón', 'Quirihue', 'Ránquil', 'San Carlos', 'San Fabián', 'San Ignacio', 'San Nicolás', 'Treguaco', 'Yungay'
        ],
    }
    
    # Crear regiones
    for region_info in regiones_data:
        region, created = Region.objects.get_or_create(
            codigo=region_info['codigo'],
            defaults={
                'nombre': region_info['nombre'],
                'orden': region_info['orden']
            }
        )
        
        # Crear comunas para esta región
        if region.codigo in comunas_data:
            for comuna_nombre in comunas_data[region.codigo]:
                # Crear código simple para la comuna (primeras letras sin espacios)
                codigo_comuna = comuna_nombre.upper().replace(' ', '_')[:10]
                Comuna.objects.get_or_create(
                    region=region,
                    nombre=comuna_nombre,
                    defaults={'codigo': codigo_comuna}
                )

def cargar_datos_predeterminados():
    """
    Carga datos predeterminados si no existen: AFP, Isapres, regiones y comunas.
    """
    if AFP.objects.count() == 0:
        crear_afp_predeterminadas()
    
    if Isapre.objects.count() == 0:
        crear_isapres_predeterminadas()
    
    if Region.objects.count() == 0:
        cargar_regiones_comunas()


def get_decimal(value, default='0'):
    """Convierte de forma segura a Decimal."""
    if value is None:
        return Decimal(default)
    try:
        str_value = str(value).strip()
        return Decimal(str_value) if str_value else Decimal(default)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)

# ------------------------------------------------------------
# Vista principal
# ------------------------------------------------------------

@login_required
def agregar_trabajador(request, alias):
    empresa = get_object_or_404(Empresa, slug=alias)
    cargar_datos_predeterminados()

    if request.method == 'POST':
        try:
            data = request.POST

            rut = data.get('rut', '').strip()
            if not rut:
                return JsonResponse({'success': False, 'message': 'El RUT es obligatorio'}, status=400)

            

            # ----- Campos obligatorios -----
            nombres = data.get('nombres', '').strip()
            apellido_paterno = data.get('apellido_paterno', '').strip()
            if not nombres or not apellido_paterno:
                return JsonResponse({'success': False, 'message': 'Nombres y apellido paterno son obligatorios'}, status=400)

            sueldo_str = data.get('sueldo_mensual', '0').strip()
            try:
                sueldo_mensual = Decimal(sueldo_str) if sueldo_str else Decimal('0')
                if sueldo_mensual <= 0:
                    return JsonResponse({'success': False, 'message': 'El sueldo mensual debe ser mayor a 0'}, status=400)
            except InvalidOperation:
                return JsonResponse({'success': False, 'message': 'Sueldo mensual inválido'}, status=400)

            afp_codigo = data.get('afp')
            isapre_codigo = data.get('isapre')
            if not afp_codigo or not isapre_codigo:
                return JsonResponse({'success': False, 'message': 'Debe seleccionar AFP e Isapre'}, status=400)

            # Validar que existan en BD
            if not AFP.objects.filter(codigo=afp_codigo).exists():
                return JsonResponse({'success': False, 'message': f'AFP con código {afp_codigo} no encontrada'}, status=400)
            if not Isapre.objects.filter(codigo=isapre_codigo).exists():
                return JsonResponse({'success': False, 'message': f'Isapre con código {isapre_codigo} no encontrada'}, status=400)

            # ----- CENTRO DE COSTO (NUEVO) -----
            centro_costo_codigo = ''
            centro_costo_nombre = ''
            centro_costo_id = data.get('centro_costo')
            if centro_costo_id:
                try:
                    centro_costo = CentroCosto.objects.get(id=centro_costo_id, empresa=empresa, activo=True)
                    centro_costo_codigo = centro_costo.codigo
                    centro_costo_nombre = centro_costo.nombre
                except CentroCosto.DoesNotExist:
                    # Si no existe, dejamos vacío (no es obligatorio)
                    pass

            # ----- Comuna -----
            comuna_id = data.get('comuna')
            comuna_nombre = ''
            if comuna_id:
                try:
                    comuna = Comuna.objects.get(id=comuna_id)
                    comuna_nombre = comuna.nombre
                except Comuna.DoesNotExist:
                    comuna_nombre = data.get('comuna_nombre', '')

            # ----- Fecha de contrato -----
            fecha_contrato_str = data.get('fecha_contrato')
            fecha_contrato = None
            if fecha_contrato_str:
                try:
                    fecha_contrato = datetime.strptime(fecha_contrato_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            # ----- Construcción del diccionario -----
            trabajador_data = {
                'empresa': empresa,
                'usuario_creacion': request.user,
                'rut': rut,
                'nombres': nombres,
                'apellido_paterno': apellido_paterno,
                'apellido_materno': data.get('apellido_materno', '').strip(),
                'fecha_contrato': fecha_contrato,
                'fecha_termino_contrato': data.get('fecha_termino_contrato') or None,
                'tipo_contrato': data.get('tipo_contrato', '').strip(),
                'tipo_jornada': data.get('tipo_jornada', 'completa').strip(),
                'afp': afp_codigo,
                'isapre': isapre_codigo,
                'seguro_cesantia_trabajador': get_decimal(data.get('seguro_cesantia_trabajador'), '0.6'),
                'seguro_cesantia_empleador': get_decimal(data.get('seguro_cesantia_empleador'), '2.4'),
                'sueldo_mensual': sueldo_mensual,
                'colacion_mensual': get_decimal(data.get('asignacion_colacion'), '0'),
                'movilizacion_mensual': get_decimal(data.get('asignacion_movilizacion'), '0'),
                'numero_cargas': int(data.get('carga_familiar', '0') or '0'),
                'direccion': data.get('direccion', '').strip(),
                'comuna': comuna_nombre,
                'region': data.get('region_nombre', '').strip(),
                'telefono': data.get('telefono', '').strip(),
                'celular': data.get('celular', '').strip(),
                'email': data.get('email', '').strip(),
                'cargo': data.get('profesion', '').strip(),
                # CENTRO DE COSTO - ahora guardamos código y nombre por separado
                'centro_costo_codigo': centro_costo_codigo,
                'centro_costo_nombre': centro_costo_nombre,
                # Nuevos campos
                'horario': data.get('horario', '').strip(),
                'banco': data.get('banco', '').strip(),
                'numero_cuenta': data.get('numero_cuenta', '').strip(),
                'tipo_cuenta': data.get('tipo_cuenta', '').strip(),
                'forma_pago': data.get('forma_pago', '').strip(),
                'estado_civil': data.get('estado_civil', '').strip(),
                # Booleanos
                'afp_trabajo_pesado': data.get('afp_trabajo_pesado') == 'on',
                'gratificacion_legal': data.get('gratificacion_legal') == 'on',
                'persona_discapacidad': data.get('persona_discapacidad') == 'on',
                'pension_invalidez': data.get('pension_invalidez') == 'on',
                'tiene_ficha_covid': data.get('tiene_ficha_covid') == 'on',
                'es_zona_extrema': data.get('es_zona_extrema') == 'on',
                'esta_activo': True,
                # Otros campos
                'fecha_nacimiento': data.get('fecha_nacimiento') or None,
                'sexo': data.get('sexo', ''),
                'nacionalidad': data.get('nacionalidad', 'Chilena').strip(),
                'clausula_termino': data.get('clausula_termino', '').strip(),
            }

            # Crear trabajador
            trabajador = Trabajador(**trabajador_data)
            trabajador.save()

            return JsonResponse({
                'success': True,
                'message': 'Trabajador agregado exitosamente',
                'redirect_url': f'/contabilidad/{alias}/trabajadores/',
                'trabajador_id': trabajador.id
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'message': f'Error interno: {str(e)}'
            }, status=500)

    # ----- GET: mostrar formulario -----
    regiones = Region.objects.filter(activa=True).order_by('orden')
    afps_disponibles = AFP.objects.filter(activa=True).order_by('codigo')
    isapres_disponibles = Isapre.objects.filter(estado='ACTIVA').order_by('codigo')

    # Obtener centros de costo reales desde la base de datos
    centros_costo = CentroCosto.objects.filter(empresa=empresa, activo=True).order_by('codigo')

    valor_uf = 36000
    try:
        uf_obj = ValorUF.objects.latest('fecha')
        valor_uf = uf_obj.valor
    except ValorUF.DoesNotExist:
        pass

    regiones_data = []
    for region in regiones:
        comunas_region = region.comunas.filter(activa=True).order_by('nombre')
        regiones_data.append({
            'id': region.id,
            'codigo': region.codigo,
            'nombre': region.nombre,
            'comunas': [{'id': c.id, 'nombre': c.nombre} for c in comunas_region]
        })

    context = {
        'alias': alias,
        'empresa': empresa,
        'hoy': datetime.now().strftime('%Y-%m-%d'),
        'valor_uf': valor_uf,
        'regiones_json': json.dumps(regiones_data),
        'regiones': regiones,
        'opciones_afp': [
            {'codigo': afp.codigo, 'nombre': afp.nombre, 'cotizacion': float(afp.cotizacion_obligatoria)}
            for afp in afps_disponibles
        ],
        'opciones_isapre': [
            {'codigo': isapre.codigo, 'nombre': isapre.nombre, 'cotizacion': float(isapre.cotizacion_obligatoria)}
            for isapre in isapres_disponibles
        ],
        # CENTROS DE COSTO - ahora usando el modelo real
        'centros_costo': [
            {'id': cc.id, 'codigo': cc.codigo, 'nombre': cc.nombre}
            for cc in centros_costo
        ],
        'opciones_bancos': ['Banco de Chile', 'Banco Estado', 'Santander', 'BCI', 'Scotiabank'],
        'estado_civil_opciones': [
            {'valor': 'SOLTERO', 'nombre': 'Soltero'},
            {'valor': 'CASADO', 'nombre': 'Casado'},
            {'valor': 'VIUDO', 'nombre': 'Viudo'},
            {'valor': 'DIVORCIADO', 'nombre': 'Divorciado'},
        ],
        'tipo_contrato_opciones': [
            {'valor': 'INDEFINIDO', 'nombre': 'Indefinido'},
            {'valor': 'FIJO', 'nombre': 'Plazo Fijo'},
            {'valor': 'OBRA', 'nombre': 'Por Obra'},
            {'valor': 'CASA_PARTICULAR', 'nombre': 'Casa Particular'},
        ],
        'jornada_opciones': [
            {'valor': 'completa', 'nombre': 'Completa'},
            {'valor': 'parcial', 'nombre': 'Parcial'},
            {'valor': 'turnos', 'nombre': 'Por Turnos'},
        ],
        'forma_pago_opciones': [
            {'valor': 'EFECTIVO', 'nombre': 'Efectivo'},
            {'valor': 'CHEQUE', 'nombre': 'Cheque'},
            {'valor': 'TRANSFERENCIA', 'nombre': 'Transferencia'},
        ],
        'tipo_cuenta_opciones': [
            {'valor': 'CORRIENTE', 'nombre': 'Cuenta Corriente'},
            {'valor': 'AHORRO', 'nombre': 'Cuenta de Ahorro'},
            {'valor': 'VISTA', 'nombre': 'Cuenta Vista'},
        ],
    }
    return render(request, 'contabilidad/agregar_trabajador.html', context)


# ------------------------------------------------------------
# APIs para obtener comunas (AJAX)
# ------------------------------------------------------------

@require_GET
def obtener_comunas_por_region(request, region_id):
    try:
        region = Region.objects.get(id=region_id)
        comunas = region.comunas.filter(activa=True).order_by('nombre')
        comunas_data = [{'id': c.id, 'nombre': c.nombre} for c in comunas]
        return JsonResponse({'success': True, 'comunas': comunas_data, 'region_nombre': region.nombre})
    except Region.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Región no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@require_GET
def obtener_comunas_por_codigo_region(request, codigo_region):
    try:
        region = Region.objects.get(codigo=codigo_region)
        comunas = region.comunas.filter(activa=True).order_by('nombre')
        comunas_data = [{'id': c.id, 'nombre': c.nombre} for c in comunas]
        return JsonResponse({'success': True, 'comunas': comunas_data, 'region_nombre': region.nombre})
    except Region.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Región no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def editar_trabajador(request, alias, trabajador_id):
    """
    Vista para editar un trabajador existente
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    trabajador = get_object_or_404(Trabajador, id=trabajador_id, empresa=empresa)
    
    # Asegurar que existan datos básicos
    cargar_datos_predeterminados()
    
    if request.method == 'POST':
        try:
            data = request.POST
            
            # Actualizar campos básicos
            trabajador.rut = data.get('rut', trabajador.rut)
            trabajador.nombres = data.get('nombres', trabajador.nombres)
            trabajador.apellido_paterno = data.get('apellido_paterno', trabajador.apellido_paterno)
            trabajador.apellido_materno = data.get('apellido_materno', trabajador.apellido_materno)
            
            # Fecha de nacimiento
            fecha_nac = data.get('fecha_nacimiento')
            if fecha_nac:
                try:
                    trabajador.fecha_nacimiento = datetime.strptime(fecha_nac, '%Y-%m-%d').date()
                except:
                    pass
            
            # Campos de contacto
            trabajador.direccion = data.get('direccion', '')
            trabajador.telefono = data.get('telefono', '')
            trabajador.celular = data.get('celular', '')
            trabajador.email = data.get('email', '')
            
            # Región y comuna
            trabajador.region = data.get('region', '')
            comuna_id = data.get('comuna')
            if comuna_id:
                try:
                    comuna = Comuna.objects.get(id=comuna_id)
                    trabajador.comuna = comuna.nombre
                except:
                    trabajador.comuna = data.get('comuna_nombre', '')
            
            # Datos laborales
            trabajador.cargo = data.get('cargo', '')
            trabajador.centro_costo_codigo = data.get('centro_costo_codigo', '')
            trabajador.centro_costo_nombre = data.get('centro_costo_nombre', '')
            
            # Sueldo
            sueldo = data.get('sueldo_mensual', '0')
            try:
                trabajador.sueldo_mensual = Decimal(sueldo) if sueldo else Decimal('0')
            except:
                trabajador.sueldo_mensual = Decimal('0')
            
            # Previsión
            trabajador.afp = data.get('afp', '')
            trabajador.isapre = data.get('isapre', '')
            
            # Fechas de contrato
            fecha_contrato = data.get('fecha_contrato')
            if fecha_contrato:
                try:
                    trabajador.fecha_contrato = datetime.strptime(fecha_contrato, '%Y-%m-%d').date()
                except:
                    pass
            
            fecha_termino = data.get('fecha_termino_contrato')
            if fecha_termino:
                try:
                    trabajador.fecha_termino_contrato = datetime.strptime(fecha_termino, '%Y-%m-%d').date()
                except:
                    trabajador.fecha_termino_contrato = None
            
            # Tipo de contrato y jornada
            trabajador.tipo_jornada = data.get('tipo_jornada', 'completa')
            
            # Beneficios
            colacion = data.get('colacion_mensual', '0')
            try:
                trabajador.colacion_mensual = Decimal(colacion) if colacion else Decimal('0')
            except:
                trabajador.colacion_mensual = Decimal('0')
            
            movilizacion = data.get('movilizacion_mensual', '0')
            try:
                trabajador.movilizacion_mensual = Decimal(movilizacion) if movilizacion else Decimal('0')
            except:
                trabajador.movilizacion_mensual = Decimal('0')
            
            # Horas trabajadas
            horas = data.get('horas_trabajadas', '45')
            try:
                trabajador.horas_trabajadas = Decimal(horas) if horas else Decimal('45')
            except:
                trabajador.horas_trabajadas = Decimal('45')
            
            # Ficha COVID
            trabajador.tiene_ficha_covid = data.get('tiene_ficha_covid') == 'SI'
            
            # Datos bancarios
            trabajador.banco = data.get('banco', '')
            trabajador.numero_cuenta = data.get('numero_cuenta', '')
            
            # Estado activo
            trabajador.esta_activo = data.get('esta_activo') == 'on'
            
            # Usuario de modificación
            trabajador.usuario_modificacion = request.user
            
            # Guardar cambios
            trabajador.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Trabajador actualizado exitosamente',
                'redirect_url': f'/contabilidad/{alias}/trabajadores/'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al actualizar: {str(e)}'
            }, status=500)
    
    # Para GET: preparar el formulario con los datos del trabajador
    
    # Obtener regiones activas
    regiones = Region.objects.filter(activa=True).order_by('orden')
    
    # Obtener AFPs disponibles
    afps_disponibles = ['AFP Modelo', 'AFP Habitat', 'AFP Capital', 'AFP Cuprum', 'AFP Provida']
    
    # Obtener Isapres disponibles
    isapres_disponibles = ['Banmédica', 'Colmena', 'Consalud', 'Cruz Blanca', 'Nueva Masvida', 'Vida Tres']
    
    # Obtener comunas de la región del trabajador
    comunas_region = []
    region_actual = None
    
    if trabajador.region:
        try:
            region_actual = Region.objects.filter(nombre=trabajador.region).first()
            if region_actual:
                comunas_region = region_actual.comunas.filter(activa=True).order_by('nombre')
        except:
            pass
    
    # Preparar datos de regiones para el template
    regiones_data = []
    for region in regiones:
        comunas = region.comunas.filter(activa=True).order_by('nombre')
        regiones_data.append({
            'id': region.id,
            'codigo': region.codigo,
            'nombre': region.nombre,
            'comunas': [
                {'id': comuna.id, 'nombre': comuna.nombre}
                for comuna in comunas
            ]
        })
    
    # Opciones para selects
    centros_costo = [
        {'codigo': 'CC001', 'nombre': 'ADMINISTRACION'},
        {'codigo': 'CC002', 'nombre': 'PRODUCCION'},
        {'codigo': 'CC003', 'nombre': 'VENTAS'},
        {'codigo': 'CC004', 'nombre': 'OPERACIONES'},
    ]
    
    opciones_bancos = [
        'Banco de Chile', 'Banco Estado', 'Santander', 'BCI', 
        'Scotiabank', 'ITAU', 'Banco Falabella', 'Banco Ripley'
    ]
    
    context = {
        'alias': alias,
        'empresa': empresa,
        'trabajador': trabajador,
        'hoy': datetime.now().strftime('%Y-%m-%d'),
        
        # Datos dinámicos
        'regiones_json': json.dumps(regiones_data),
        'regiones': regiones,
        'region_actual': region_actual,
        'comunas_region': comunas_region,
        
        # Opciones
        'opciones_afp': afps_disponibles,
        'opciones_isapre': isapres_disponibles,
        'centros_costo': centros_costo,
        'opciones_bancos': opciones_bancos,
        
        # Filtros (para mantener consistencia con el template de lista)
        'filtros': {},
    }
    
    return render(request, 'contabilidad/editar_trabajador.html', context)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Count, Q
from datetime import datetime, date
import json

from empresas.models import Empresa
from contabilidad.models import Periodo, Trabajador

@login_required
def panel_liquidaciones(request, alias):
    """
    Vista principal para el panel de liquidaciones
    """
    try:
        empresa = get_object_or_404(Empresa, slug=alias)
    except:
        empresa = get_object_or_404(Empresa, alias=alias)  # Intentar con alias si slug falla
    
    # Verificar permisos - versión más permisiva para desarrollo
    # Opción 1: Permitir a todos los usuarios autenticados
    if not request.user.is_authenticated:
        messages.error(request, "Debe iniciar sesión para acceder a esta sección")
        return redirect('login')
    
    # Opción 2: Solo verificar que esté autenticado (comentar las otras opciones)
    # if not request.user.is_authenticated:
    #     return JsonResponse({
    #         'success': False,
    #         'message': 'Debe iniciar sesión para acceder a esta sección'
    #     }, status=403)
    
    # Opción 3: Si quieres mantener permisos estrictos, usa:
    # if not (request.user.is_superuser or request.user.is_staff):
    #     messages.error(request, "No tiene permisos para acceder a esta sección")
    #     return redirect('dashboard')
    
    # Si es una petición AJAX para obtener períodos
    if request.method == 'GET' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Obtener parámetros de filtro
            anio = request.GET.get('anio')
            mes = request.GET.get('mes')
            estado = request.GET.get('estado')
            
            # Construir query base
            periodos_qs = Periodo.objects.filter(empresa=empresa)
            
            # Aplicar filtros
            if anio and anio != '':
                periodos_qs = periodos_qs.filter(anio=int(anio))
            
            if mes and mes != '':
                periodos_qs = periodos_qs.filter(mes=int(mes))
            
            if estado and estado != '':
                periodos_qs = periodos_qs.filter(estado__iexact=estado)
            
            # Ordenar por año y mes descendente
            periodos_qs = periodos_qs.order_by('-anio', '-mes')
            
            # Preparar datos para la respuesta
            periodos_data = []
            for periodo in periodos_qs:
                try:
                    # Contar trabajadores activos en el período
                    total_trabajadores = Trabajador.objects.filter(
                        empresa=empresa,
                        esta_activo=True
                    ).count()
                except:
                    total_trabajadores = 0
                
                try:
                    # Contar liquidaciones generadas para este período
                    liquidaciones_generadas = Liquidacion.objects.filter(periodo=periodo).count()
                except:
                    liquidaciones_generadas = 0
                
                # Formatear las fechas
                fecha_inicio_str = periodo.fecha_inicio.strftime('%d-%m-%Y') if periodo.fecha_inicio else ''
                fecha_fin_str = periodo.fecha_fin.strftime('%d-%m-%Y') if periodo.fecha_fin else ''
                
                periodos_data.append({
                    'id': periodo.id,
                    'mes': periodo.mes,
                    'anio': periodo.anio,
                    'empresa': empresa.nombre,
                    'estado': periodo.estado,
                    'uf': float(periodo.uf) if periodo.uf else 0,
                    'utm': float(periodo.utm) if periodo.utm else 0,
                    'dias_habiles': periodo.dias_habiles or 0,
                    'dias_no_habiles': periodo.dias_no_habiles or 0,
                    'total_trabajadores': total_trabajadores,
                    'fecha_inicio': fecha_inicio_str,
                    'fecha_fin': fecha_fin_str,
                    'liquidaciones_generadas': liquidaciones_generadas,
                    'factor_actualizacion': float(periodo.factor_actualizacion) if periodo.factor_actualizacion else 1.0,
                    'nombre_mes': periodo.nombre_mes,
                    'mes_anio': periodo.mes_anio,
                    'total_dias': periodo.total_dias if hasattr(periodo, 'total_dias') else 0,
                    'es_periodo_actual': periodo.periodo_actual if hasattr(periodo, 'periodo_actual') else False,
                })
            
            # Calcular estadísticas
            total_periodos = periodos_qs.count()
            periodos_activos = periodos_qs.filter(estado='ACTIVO').count()
            periodos_cerrados = periodos_qs.filter(estado='CERRADO').count()
            periodos_procesados = periodos_qs.filter(estado='PROCESADO').count()
            periodos_inactivos = periodos_qs.filter(estado='INACTIVO').count()
            
            # Último período
            ultimo_periodo = periodos_qs.first()
            ultimo_periodo_str = f"{ultimo_periodo.mes:02d}/{ultimo_periodo.anio}" if ultimo_periodo else "--/----"
            
            return JsonResponse({
                'success': True,
                'periodos': periodos_data,
                'estadisticas': {
                    'total_periodos': total_periodos,
                    'periodos_activos': periodos_activos,
                    'periodos_cerrados': periodos_cerrados,
                    'periodos_procesados': periodos_procesados,
                    'periodos_inactivos': periodos_inactivos,
                    'ultimo_periodo': ultimo_periodo_str,
                }
            })
            
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'message': f'Error al cargar períodos: {str(e)}',
                'traceback': traceback.format_exc()
            }, status=500)
    
    # Si es una petición normal GET, renderizar template
    # Preparar años disponibles (últimos 5 años y futuro)
    anio_actual = datetime.now().year
    anios_disponibles = list(range(anio_actual - 2, anio_actual + 3))
    
    # Meses para el select
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    try:
        # Obtener períodos para estadísticas iniciales
        periodos_iniciales = Periodo.objects.filter(empresa=empresa).order_by('-anio', '-mes')
        total_periodos = periodos_iniciales.count()
        periodos_activos = periodos_iniciales.filter(estado='ACTIVO').count()
        periodos_cerrados = periodos_iniciales.filter(estado='CERRADO').count()
    except:
        total_periodos = 0
        periodos_activos = 0
        periodos_cerrados = 0
    
    context = {
        'alias': alias,
        'empresa': empresa,
        'titulo': 'Panel de Liquidaciones',
        'anio_actual': anio_actual,
        'mes_actual': datetime.now().month,
        'hoy': datetime.now().strftime('%Y-%m-%d'),
        'anios_disponibles': anios_disponibles,
        'meses': meses,
        'total_periodos': total_periodos,
        'periodos_activos': periodos_activos,
        'periodos_cerrados': periodos_cerrados,
    }
    
    return render(request, 'contabilidad/panel_liquidaciones.html', context)


@login_required
def seleccionar_periodo(request, alias):
    """
    Vista para seleccionar un período y redirigir al listado de liquidaciones
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            periodo_id = data.get('periodo_id')
            
            if not periodo_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Debe seleccionar un período'
                }, status=400)
            
            # Verificar que el período existe y pertenece a la empresa
            empresa = get_object_or_404(Empresa, alias=alias)
            periodo = get_object_or_404(Periodo, id=periodo_id, empresa=empresa)
            
            # Guardar el período seleccionado en la sesión
            request.session['periodo_liquidacion_id'] = periodo_id
            request.session['periodo_mes'] = periodo.mes
            request.session['periodo_anio'] = periodo.anio
            request.session['alias_empresa'] = alias
            
            return JsonResponse({
                'success': True,
                'message': 'Período seleccionado correctamente',
                'periodo': {
                    'id': periodo.id,
                    'mes': periodo.mes,
                    'anio': periodo.anio,
                    'nombre': str(periodo),
                },
                'redirect_url': f'/contabilidad/{alias}/liquidaciones/'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Error en el formato de los datos'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al seleccionar período: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)


@login_required
def crear_periodo_rapido(request, alias):
    """
    Vista para crear un nuevo período rápidamente
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            empresa = get_object_or_404(Empresa, alias=alias)
            
            # Validar que no exista ya el período
            mes = data.get('mes')
            anio = data.get('anio')
            
            if Periodo.objects.filter(empresa=empresa, mes=mes, anio=anio).exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Ya existe un período para {mes}/{anio}'
                }, status=400)
            
            # Crear fechas aproximadas
            from datetime import datetime
            fecha_inicio = datetime(anio, mes, 1).date()
            
            # Calcular fecha fin (último día del mes)
            if mes == 12:
                fecha_fin = datetime(anio + 1, 1, 1).date()
            else:
                fecha_fin = datetime(anio, mes + 1, 1).date()
            
            fecha_fin = fecha_fin.replace(day=1)  # Primero del mes siguiente
            from datetime import timedelta
            fecha_fin = fecha_fin - timedelta(days=1)  # Último día del mes actual
            
            # Valores por defecto (puedes obtener estos de una API o config)
            uf = data.get('uf', 36000)  # Valor de ejemplo
            utm = data.get('utm', 63000)  # Valor de ejemplo
            
            # Crear período
            periodo = Periodo.objects.create(
                empresa=empresa,
                mes=mes,
                anio=anio,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                uf=uf,
                utm=utm,
                dias_habiles=22,
                dias_no_habiles=9,
                factor_actualizacion=1.0000,
                estado='ACTIVO'
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Período {periodo.nombre_mes} {anio} creado correctamente',
                'periodo_id': periodo.id,
                'periodo_nombre': str(periodo)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al crear período: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)


@login_required
def cambiar_estado_periodo(request, alias):
    """
    Vista para cambiar el estado de un período
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            periodo_id = data.get('periodo_id')
            nuevo_estado = data.get('estado')
            
            if not periodo_id or not nuevo_estado:
                return JsonResponse({
                    'success': False,
                    'message': 'Datos incompletos'
                }, status=400)
            
            empresa = get_object_or_404(Empresa, alias=alias)
            periodo = get_object_or_404(Periodo, id=periodo_id, empresa=empresa)
            
            # Validar transición de estado
            estados_validos = ['ACTIVO', 'INACTIVO', 'PROCESADO', 'CERRADO']
            if nuevo_estado not in estados_validos:
                return JsonResponse({
                    'success': False,
                    'message': f'Estado inválido. Debe ser uno de: {", ".join(estados_validos)}'
                }, status=400)
            
            # Cambiar estado
            periodo.estado = nuevo_estado
            periodo.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Estado cambiado a {nuevo_estado} correctamente',
                'periodo_estado': periodo.estado
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al cambiar estado: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método no permitido'
    }, status=405)

# contabilidad/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from .models import Periodo, Trabajador, Liquidacion
from empresas.models import Empresa

@login_required
def lista_liquidaciones(request, alias):
    empresa = get_object_or_404(Empresa, slug=alias)
    
    # Parámetros de la URL
    periodo_id = request.GET.get('periodo_id')
    anio = request.GET.get('anio')
    mes = request.GET.get('mes')
    
    # Filtros
    busqueda = request.GET.get('busqueda', '')
    centro = request.GET.get('centro', '')
    estado_filtro = request.GET.get('estado', '')
    
    periodo = None
    trabajadores_data = []
    centros_costo = []
    
    # Obtener el período seleccionado
    if periodo_id:
        try:
            periodo = Periodo.objects.get(id=periodo_id, empresa=empresa)
        except Periodo.DoesNotExist:
            periodo = None
    elif anio and mes:
        try:
            periodo = Periodo.objects.get(empresa=empresa, anio=int(anio), mes=int(mes))
        except (Periodo.DoesNotExist, ValueError):
            periodo = None
    
    if periodo:
        # Base de trabajadores activos
        trabajadores_qs = Trabajador.objects.filter(empresa=empresa, esta_activo=True)
        
        # Filtro por búsqueda (RUT, nombres, apellidos)
        if busqueda:
            trabajadores_qs = trabajadores_qs.filter(
                Q(rut__icontains=busqueda) |
                Q(nombres__icontains=busqueda) |
                Q(apellido_paterno__icontains=busqueda) |
                Q(apellido_materno__icontains=busqueda)
            )
        
        # Filtro por centro de costo
        if centro:
            trabajadores_qs = trabajadores_qs.filter(centro_costo_nombre=centro)
        
        # Obtener liquidaciones existentes para el período
        liquidaciones_existentes = Liquidacion.objects.filter(periodo=periodo)
        liquidaciones_dict = {liq.trabajador_id: liq for liq in liquidaciones_existentes}
        
        # Preparar datos de trabajadores
        for trabajador in trabajadores_qs:
            liquidacion_existente = liquidaciones_dict.get(trabajador.id)
            tiene_liquidacion = liquidacion_existente is not None
            liquidacion_estado = liquidacion_existente.estado if liquidacion_existente else 'PENDIENTE'
            
            trabajadores_data.append({
                'id': trabajador.id,
                'rut': trabajador.rut,
                'nombre_completo': trabajador.nombre_completo,
                'apellido_paterno': trabajador.apellido_paterno,
                'apellido_materno': trabajador.apellido_materno,
                'nombres': trabajador.nombres,
                'cargo': trabajador.cargo,
                'email': trabajador.email,
                'sueldo_mensual': float(trabajador.sueldo_mensual) if trabajador.sueldo_mensual else 0,
                'sueldo_diario': float(trabajador.sueldo_diario) if trabajador.sueldo_diario else 0,
                'centro_costo_nombre': trabajador.centro_costo_nombre,
                'centro_costo_codigo': trabajador.centro_costo_codigo,
                'tiene_liquidacion': tiene_liquidacion,
                'liquidacion_estado': liquidacion_estado,
                'liquidacion_id': liquidacion_existente.id if liquidacion_existente else None,
            })
        
        # Filtrar por estado (después de obtener los datos de liquidación)
        if estado_filtro:
            if estado_filtro == 'PENDIENTE':
                trabajadores_data = [t for t in trabajadores_data if not t['tiene_liquidacion']]
            else:
                trabajadores_data = [t for t in trabajadores_data if t['liquidacion_estado'] == estado_filtro]
        
        # Obtener centros de costo únicos para el selector (de todos los trabajadores activos)
        centros_costo = list(set(
            filter(None, Trabajador.objects.filter(empresa=empresa, esta_activo=True).values_list('centro_costo_nombre', flat=True))
        ))
    
    # Calcular estadísticas
    total_trabajadores = len(trabajadores_data)
    pendientes = sum(1 for t in trabajadores_data if not t['tiene_liquidacion'])
    generadas = sum(1 for t in trabajadores_data if t.get('liquidacion_estado') == 'GENERADA')
    cerradas = sum(1 for t in trabajadores_data if t.get('liquidacion_estado') == 'CERRADA')
    
    # Períodos disponibles para el selector
    periodos_disponibles = Periodo.objects.filter(empresa=empresa).order_by('-anio', '-mes')
    años_disponibles = periodos_disponibles.values_list('anio', flat=True).distinct().order_by('-anio')
    
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), 
        (4, 'Abril'), (5, 'Mayo'), (6, 'Junio'),
        (7, 'Julio'), (8, 'Agosto'), (9, 'Septiembre'),
        (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    context = {
        'alias': alias,
        'empresa': empresa,
        'periodo': periodo,
        'trabajadores': trabajadores_data,
        'centros_costo': sorted(centros_costo),
        'periodos_disponibles': periodos_disponibles,
        'anios_disponibles': años_disponibles,
        'meses': meses,
        'anio_seleccionado': int(anio) if anio and anio.isdigit() else None,
        'mes_seleccionado': int(mes) if mes and mes.isdigit() else None,
        'total_trabajadores': total_trabajadores,
        'pendientes': pendientes,
        'generadas': generadas,
        'cerradas': cerradas,
    }
    
    return render(request, 'contabilidad/lista_liquidaciones.html', context)

# contabilidad/views.py

@login_required
def generar_liquidacion_individual(request, alias, periodo_id, trabajador_id):
    """
    Formulario completo para generar liquidación individual
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    periodo = get_object_or_404(Periodo, id=periodo_id, empresa=empresa)
    trabajador = get_object_or_404(Trabajador, id=trabajador_id, empresa=empresa)
    
    # Verificar si ya existe liquidación
    liquidacion_existente = Liquidacion.objects.filter(
        periodo=periodo,
        trabajador=trabajador
    ).first()
    
    # Cargar datos de la liquidación existente si existe
    if liquidacion_existente:
        datos_liquidacion = {
            'sueldo_mensual': float(liquidacion_existente.sueldo_mensual) if liquidacion_existente.sueldo_mensual else float(trabajador.sueldo_mensual),
            'dias_trabajados': liquidacion_existente.dias_trabajados,
            'horas_trabajadas': liquidacion_existente.horas_trabajadas,
            'horas_extra_50': float(liquidacion_existente.horas_extra_50),
            'horas_extra_100': float(liquidacion_existente.horas_extra_100),
            'horas_extra_150': float(liquidacion_existente.horas_extra_150),
            'total_horas_extra': float(liquidacion_existente.total_horas_extra),
            'bonos': float(liquidacion_existente.bonos),
            'colacion': float(liquidacion_existente.colacion),
            'movilizacion': float(liquidacion_existente.movilizacion),
            'tipo_gratificacion': liquidacion_existente.tipo_gratificacion,
            'porcentaje_gratificacion': float(liquidacion_existente.porcentaje_gratificacion) if hasattr(liquidacion_existente, 'porcentaje_gratificacion') else 25.00,
            'monto_gratificacion': float(liquidacion_existente.monto_gratificacion),
            'afp_nombre': liquidacion_existente.afp_nombre,
            'porcentaje_afp': float(liquidacion_existente.porcentaje_afp),
            'cotizacion_afp': float(liquidacion_existente.cotizacion_afp),
            'isapre_nombre': liquidacion_existente.isapre_nombre,
            'cotizacion_salud_pactada': float(liquidacion_existente.cotizacion_salud_pactada),
            'diferencia_isapre': float(liquidacion_existente.diferencia_isapre),
            'total_haberes': float(liquidacion_existente.total_haberes),
            'total_descuentos': float(liquidacion_existente.total_descuentos),
            'liquido_pagable': float(liquidacion_existente.liquido_pagable),
            'estado': liquidacion_existente.estado,
        }
    else:
        # Valores por defecto basados en el trabajador
        sueldo_mensual = float(trabajador.sueldo_mensual) if trabajador.sueldo_mensual else 0
        
        datos_liquidacion = {
            'sueldo_mensual': sueldo_mensual,
            'dias_trabajados': periodo.dias_habiles,
            'horas_trabajadas': 180,
            'horas_extra_50': 0,
            'horas_extra_100': 0,
            'horas_extra_150': 0,
            'total_horas_extra': 0,
            'bonos': 0,
            'colacion': float(trabajador.colacion_mensual) if trabajador.colacion_mensual else 0,
            'movilizacion': float(trabajador.movilizacion_mensual) if trabajador.movilizacion_mensual else 0,
            'tipo_gratificacion': 'CON_TOPE',
            'porcentaje_gratificacion': 25.00,  # Porcentaje por defecto (25%)
            'monto_gratificacion': 0,
            'afp_nombre': trabajador.afp if trabajador.afp else '',
            'porcentaje_afp': 11.00,
            'cotizacion_afp': 0,
            'isapre_nombre': trabajador.isapre if trabajador.isapre else '',
            'cotizacion_salud_pactada': 7.00,
            'diferencia_isapre': 0,
            'total_haberes': sueldo_mensual,
            'total_descuentos': 0,
            'liquido_pagable': sueldo_mensual,
            'estado': 'BORRADOR',
        }
    
    todos_trabajadores = Trabajador.objects.filter(
        empresa=empresa,
        esta_activo=True
    ).order_by('apellido_paterno', 'apellido_materno', 'nombres')
    
    # Obtener AFP disponibles
    afps_disponibles = AFP.objects.filter(activa=True).order_by('codigo')
    
    # Obtener Isapres disponibles
    isapres_disponibles = Isapre.objects.filter(activa=True).order_by('codigo')
    
    # ============================================
    # CORRECCIÓN: SELECCIÓN CORRECTA DE AFP E ISAPRE
    # ============================================
    
    # Para AFP - Buscar por código (primeras letras)
    afp_seleccionada = None
    if trabajador.afp:
        # Extraer código (ej: "CUMP - Cuprum" -> "CUMP")
        codigo_afp = trabajador.afp.split(' - ')[0].strip() if ' - ' in trabajador.afp else trabajador.afp.strip()
        
        # Buscar por código exacto
        afp_seleccionada = AFP.objects.filter(codigo__iexact=codigo_afp).first()
        
        # Si no encuentra, buscar por nombre
        if not afp_seleccionada:
            nombre_afp = trabajador.afp.split(' - ')[1].strip() if ' - ' in trabajador.afp else trabajador.afp.strip()
            afp_seleccionada = AFP.objects.filter(nombre__icontains=nombre_afp).first()
    
    # Para Isapre - Buscar por código (primeras letras)
    isapre_seleccionada = None
    if trabajador.isapre:
        # Extraer código (ej: "BANM - Banmedica" -> "BANM")
        codigo_isapre = trabajador.isapre.split(' - ')[0].strip() if ' - ' in trabajador.isapre else trabajador.isapre.strip()
        
        # Buscar por código exacto
        isapre_seleccionada = Isapre.objects.filter(codigo__iexact=codigo_isapre).first()
        
        # Si no encuentra, buscar por nombre
        if not isapre_seleccionada:
            nombre_isapre = trabajador.isapre.split(' - ')[1].strip() if ' - ' in trabajador.isapre else trabajador.isapre.strip()
            isapre_seleccionada = Isapre.objects.filter(nombre__icontains=nombre_isapre).first()
    
    # Si aún no se encuentra, usar valores por defecto
    if not afp_seleccionada:
        afp_seleccionada = afps_disponibles.first()
        print(f"⚠️ AFP no encontrada, usando: {afp_seleccionada}")
    
    if not isapre_seleccionada:
        isapre_seleccionada = isapres_disponibles.first()
        print(f"⚠️ Isapre no encontrada, usando: {isapre_seleccionada}")
    
    # ============================================
    # DEBUG - Mostrar qué se está seleccionando
    # ============================================
    print(f"\n{'='*50}")
    print(f"DEBUG - Trabajador: {trabajador.nombre_completo}")
    print(f"DEBUG - RUT: {trabajador.rut}")
    print(f"DEBUG - AFP (CharField): {trabajador.afp}")
    print(f"DEBUG - Código AFP extraído: {codigo_afp if trabajador.afp else 'N/A'}")
    print(f"DEBUG - AFP seleccionada: {afp_seleccionada}")
    print(f"DEBUG - Cotización AFP: {afp_seleccionada.cotizacion_obligatoria if afp_seleccionada else 'N/A'}%")
    print(f"\nDEBUG - Isapre (CharField): {trabajador.isapre}")
    print(f"DEBUG - Código Isapre extraído: {codigo_isapre if trabajador.isapre else 'N/A'}")
    print(f"DEBUG - Isapre seleccionada: {isapre_seleccionada}")
    print(f"DEBUG - Cotización Isapre: {isapre_seleccionada.cotizacion_obligatoria if isapre_seleccionada else 'N/A'}%")
    print(f"{'='*50}\n")
    
    # Glosas disponibles
    glosas = [
        ('LIQUIDACION_SUELDO', 'Liquidación de Sueldo'),
        ('LIQUIDACION_FERIADO', 'Liquidación Feriado Legal'),
        ('LIQUIDACION_VACACIONES', 'Liquidación Vacaciones'),
        ('LIQUIDACION_FINIQUITO', 'Finiquito'),
        ('LIQUIDACION_BONO', 'Bono Especial'),
    ]
    
    # Tipos de gratificación
    tipos_gratificacion = [
        ('CON_TOPE', 'Con tope (4.75 IMM - $' + format(calcular_tope_gratificacion(), ',.0f').replace(',', '.') + ')'),
        ('SIN_TOPE', 'Sin tope'),
        ('EXENTO', 'Exento'),
    ]
    
    # Movimientos Previred
    movimientos_previred = [
        (0, '0 - Sin movimientos'),
        (1, '1 - Contratación plazo indefinido'),
        (2, '2 - Retiro'),
        (3, '3 - Subsidios'),
        (4, '4 - Permiso sin goce'),
        (5, '5 - Incorporación'),
        (6, '6 - Accidentes trabajo'),
        (7, '7 - Contratación plazo fijo'),
        (8, '8 - Cambio a indefinido'),
        (11, '11 - Otros movimientos'),
        (12, '12 - Requilidación premio/bono'),
        (13, '13 - Suspensión acto autoridad'),
        (14, '14 - Suspensión pacto'),
        (15, '15 - Reducción jornada'),
    ]
    
    context = {
        'alias': alias,
        'empresa': empresa,
        'periodo': periodo,
        'trabajador': trabajador,
        'todos_trabajadores': todos_trabajadores,
        'liquidacion_existente': liquidacion_existente,
        'datos_liquidacion': datos_liquidacion,
        'afps_disponibles': afps_disponibles,
        'isapres_disponibles': isapres_disponibles,
        'afp_seleccionada': afp_seleccionada,
        'isapre_seleccionada': isapre_seleccionada,
        'glosas': glosas,
        'tipos_gratificacion': tipos_gratificacion,
        'movimientos_previred': movimientos_previred,
    }
    
    return render(request, 'contabilidad/liquidacion.html', context)


def calcular_tope_gratificacion():
    """
    Calcula el tope de gratificación (4.75 IMM)
    """
    from datetime import date
    
    # Obtener IMM actual (esto debería venir de un modelo configurable)
    # Por ahora usamos un valor de ejemplo
    imm_actual = 460000  # Ingreso Mínimo Mensual (ajustar según corresponda)
    
    tope = imm_actual * 4.75
    return tope


@login_required
def guardar_liquidacion(request, alias):
    """
    Guardar la liquidación generada usando los campos correctos del modelo
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        data = json.loads(request.body)
        
        empresa = get_object_or_404(Empresa, slug=alias)
        periodo = get_object_or_404(Periodo, id=data.get('periodo_id'), empresa=empresa)
        trabajador = get_object_or_404(Trabajador, id=data.get('trabajador_id'), empresa=empresa)
        
        # Validar que la base de gratificación no sea None
        base_gratificacion = data.get('base_gratificacion', 0)
        if base_gratificacion is None:
            base_gratificacion = 0
        
        # Validar que el monto de gratificación no sea None
        monto_gratificacion = data.get('monto_gratificacion', 0)
        if monto_gratificacion is None:
            monto_gratificacion = 0
        
        # Mapear los datos del formulario a los campos correctos del modelo
        defaults = {
            # CONFIGURACIÓN
            'glosa': data.get('glosa', 'LIQUIDACION_SUELDO'),
            'estado': data.get('estado', 'GENERADA'),
            'haberes_colegio': data.get('haberes_colegio', False),
            
            # DÍAS Y HORAS
            'dias_trabajados': int(data.get('dias_trabajados', periodo.dias_habiles)),
            'horas_trabajadas': int(data.get('horas_trabajadas', 180)),
            'horas_atraso': Decimal(str(data.get('horas_atraso', 0))),
            'dias_habiles_trabajados': int(data.get('dias_habiles_trabajados', periodo.dias_habiles)),
            'dias_habiles': periodo.dias_habiles,
            'dias_domingo_festivos': periodo.dias_no_habiles,
            
            # SUELDO
            'sueldo_mensual': Decimal(str(data.get('sueldo_mensual', 0))),
            'sueldo_diario': Decimal(str(data.get('sueldo_diario', 0))),
            'atraso': Decimal(str(data.get('atraso', 0))),
            
            # HORAS EXTRA
            'horas_extra_50': Decimal(str(data.get('horas_extra_50', 0))),
            'horas_extra_100': Decimal(str(data.get('horas_extra_100', 0))),
            'horas_extra_150': Decimal(str(data.get('horas_extra_150', 0))),
            'monto_horas_extra': Decimal(str(data.get('monto_horas_extra', 0))),
            'total_horas_extra': Decimal(str(data.get('total_horas_extra', 0))),
            
            # COMISIONES Y CARGOS
            'total_comision': Decimal(str(data.get('total_comision', 0))),
            'horas_cargo_domingo': int(data.get('horas_cargo_domingo', 0)),
            'monto_cargo_domingo': Decimal(str(data.get('monto_cargo_domingo', 0))),
            
            # UTILIDADES Y SEMANA CORRIDA
            'utilidades': Decimal(str(data.get('utilidades', 0))),
            'semana_corrida': Decimal(str(data.get('semana_corrida', 0))),
            'total_semana_corrida': Decimal(str(data.get('total_semana_corrida', 0))),
            'total_haberes_variables': Decimal(str(data.get('total_haberes_variables', 0))),
            
            # GRATIFICACIÓN - MODIFICADO PARA PORCENTAJES
            'tipo_gratificacion': data.get('tipo_gratificacion', 'CON_TOPE'),
            'base_gratificacion': Decimal(str(base_gratificacion)),
            'porcentaje_gratificacion': Decimal(str(data.get('porcentaje_gratificacion', 25.00))),
            'monto_gratificacion': Decimal(str(monto_gratificacion)),
            
            # BONOS
            'bonos': Decimal(str(data.get('bonos', 0))),
            
            # CARGAS FAMILIARES
            'numero_cargas': int(data.get('numero_cargas', trabajador.numero_cargas)),
            'promedio_ingresos': Decimal(str(data.get('promedio_ingresos', 0))),
            'numero_cargas_maternales': int(data.get('numero_cargas_maternales', 0)),
            'retroactiva': Decimal(str(data.get('retroactiva', 0))),
            
            # ASIGNACIONES
            'colacion': Decimal(str(data.get('colacion', trabajador.colacion_mensual))),
            'movilizacion': Decimal(str(data.get('movilizacion', trabajador.movilizacion_mensual))),
            
            # OTROS BONOS
            'nombre_otro_bono_1': data.get('nombre_otro_bono_1', ''),
            'valor_otro_bono_1': Decimal(str(data.get('valor_otro_bono_1', 0))),
            'nombre_otro_bono_2': data.get('nombre_otro_bono_2', ''),
            'valor_otro_bono_2': Decimal(str(data.get('valor_otro_bono_2', 0))),
            
            # AFP
            'afp_nombre': data.get('afp_nombre', trabajador.afp),
            'porcentaje_afp': Decimal(str(data.get('porcentaje_afp', 11.0))),
            'base_afp': Decimal(str(data.get('base_afp', 0))),
            'cotizacion_afp': Decimal(str(data.get('cotizacion_afp', 0))),
            'cuenta_2_afp': Decimal(str(data.get('cuenta_2_afp', 0))),
            
            # AFC (SEGURO DE CESANTÍA) - NUEVOS CAMPOS
            'tipo_contrato': data.get('tipo_contrato', trabajador.tipo_contrato),
            'fecha_contrato': data.get('fecha_contrato') or trabajador.fecha_contrato,
            'porcentaje_afc_trabajador': Decimal(str(data.get('porcentaje_afc_trabajador', 0))),
            'porcentaje_afc_empleador': Decimal(str(data.get('porcentaje_afc_empleador', 0))),
            'porcentaje_trabajo_pesado': Decimal(str(data.get('porcentaje_trabajo_pesado', trabajador.porcentaje_trabajo_pesado_trabajador))),
            'base_afc': Decimal(str(data.get('base_afc', 0))),
            'cotizacion_afc': Decimal(str(data.get('cotizacion_afc', 0))),
            
            # APV
            'apv': Decimal(str(data.get('apv', trabajador.apv))),
            'apv2': Decimal(str(data.get('apv2', trabajador.apv2))),
            'afiliado_voluntario': data.get('afiliado_voluntario', trabajador.es_afiliado_voluntario),
            'apv_colectivo': Decimal(str(data.get('apv_colectivo', trabajador.apv_colectivo))),
            
            # SALUD
            'isapre_nombre': data.get('isapre_nombre', trabajador.isapre),
            'cotizacion_salud_pactada': Decimal(str(data.get('cotizacion_salud_pactada', 7.0))),
            'cotizacion_salud_obligatoria': Decimal(7.0),
            'diferencia_isapre': Decimal(str(data.get('diferencia_isapre', 0))),
            'total_prevision': Decimal(str(data.get('total_prevision', 0))),
            
            # IMPUESTO
            'base_impuesto': Decimal(str(data.get('base_impuesto', 0))),
            'anticipo_impuesto': Decimal(str(data.get('anticipo_impuesto', 0))),
            'cuota_impuesto': Decimal(str(data.get('cuota_impuesto', 0))),
            
            # PRÉSTAMOS
            'prestamo_ccaf': Decimal(str(data.get('prestamo_ccaf', trabajador.prestamo_2da_caja))),
            'prestamo_solidario': Decimal(str(data.get('prestamo_solidario', 0))),
            'programa_ahorro_leasing': Decimal(str(data.get('programa_ahorro_leasing', 0))),
            'seguro_ccaf': Decimal(str(data.get('seguro_ccaf', 0))),
            'cuota_ccaf': Decimal(str(data.get('cuota_ccaf', 0))),
            'prestamo_empresa': Decimal(str(data.get('prestamo_empresa', 0))),
            
            # OTROS DESCUENTOS
            'nombre_otro_descuento_1': data.get('nombre_otro_descuento_1', ''),
            'valor_otro_descuento_1': Decimal(str(data.get('valor_otro_descuento_1', 0))),
            'nombre_otro_descuento_2': data.get('nombre_otro_descuento_2', ''),
            'valor_otro_descuento_2': Decimal(str(data.get('valor_otro_descuento_2', 0))),
            
            # INFORMACIÓN ADICIONAL
            'centro_costo': data.get('centro_costo', trabajador.centro_costo_nombre),
            'costo_empleador': Decimal(str(data.get('costo_empleador', 0))),
            'afc_empleador': Decimal(str(data.get('afc_empleador', 0))),
            'renta_imponible_anterior': Decimal(str(data.get('renta_imponible_anterior', 0))),
            'seguro_accidentes': Decimal(str(data.get('seguro_accidentes', 0))),
            'sis': Decimal(str(data.get('sis', 0))),
            'apv_colectivo_empleador': Decimal(str(data.get('apv_colectivo_empleador', 0))),
            'trabajo_pesado_empleador': Decimal(str(data.get('trabajo_pesado_empleador', 0))),
            
            # AUSENCIAS
            'vacaciones_dias': int(data.get('vacaciones_dias', 0)),
            'vacaciones_glosa': data.get('vacaciones_glosa', ''),
            'licencias_dias': int(data.get('licencias_dias', 0)),
            'licencias_glosa': data.get('licencias_glosa', ''),
            'faltas_dias': int(data.get('faltas_dias', 0)),
            'faltas_glosa': data.get('faltas_glosa', ''),
            
            # MOVIMIENTOS PREVIRED
            'movimiento_previred_0': data.get('movimiento_previred_0', False),
            'movimiento_previred_1': data.get('movimiento_previred_1', False),
            'movimiento_previred_2': data.get('movimiento_previred_2', False),
            'movimiento_previred_3': data.get('movimiento_previred_3', False),
            'movimiento_previred_4': data.get('movimiento_previred_4', False),
            'movimiento_previred_5': data.get('movimiento_previred_5', False),
            'movimiento_previred_6': data.get('movimiento_previred_6', False),
            'movimiento_previred_7': data.get('movimiento_previred_7', False),
            'movimiento_previred_8': data.get('movimiento_previred_8', False),
            'movimiento_previred_11': data.get('movimiento_previred_11', False),
            'movimiento_previred_12': data.get('movimiento_previred_12', False),
            'movimiento_previred_13': data.get('movimiento_previred_13', False),
            'movimiento_previred_14': data.get('movimiento_previred_14', False),
            'movimiento_previred_15': data.get('movimiento_previred_15', False),
            'movimiento_desde': data.get('movimiento_desde'),
            'movimiento_hasta': data.get('movimiento_hasta'),
            
            # REFORMA PREVISIONAL
            'cuenta_afp_empleador': Decimal(str(data.get('cuenta_afp_empleador', 0))),
            'renta_protegida': Decimal(str(data.get('renta_protegida', 0))),
            'expectativa_vida': int(data.get('expectativa_vida', 0)),
            
            # TOTALES
            'total_imponible': Decimal(str(data.get('total_imponible', 0))),
            'total_haberes': Decimal(str(data.get('total_haberes', 0))),
            'total_descuentos': Decimal(str(data.get('total_descuentos', 0))),
            'liquido_pagable': Decimal(str(data.get('liquido_pagable', 0))),
            
            # OTROS
            'observaciones': data.get('observaciones', ''),
        }
        
        # Crear o actualizar liquidación
        liquidacion, created = Liquidacion.objects.update_or_create(
            periodo=periodo,
            trabajador=trabajador,
            defaults=defaults
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Liquidación guardada exitosamente',
            'liquidacion_id': liquidacion.id,
            'created': created
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({
            'success': False,
            'message': f'Error en el formato de datos: {str(e)}'
        })
    except KeyError as e:
        return JsonResponse({
            'success': False,
            'message': f'Falta campo requerido: {str(e)}'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()  # Para ver el error completo en la consola
        return JsonResponse({
            'success': False,
            'message': f'Error al guardar liquidación: {str(e)}'
        })
    
# contabilidad/views.py
# ============================================
# VISTAS PARA FORMATOS DE LIQUIDACIÓN (PDF)
# ============================================

import json
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from decimal import Decimal
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@login_required
@require_POST
def render_formato_basico(request, alias):
    """Renderiza el formato básico de liquidación"""
    try:
        data = json.loads(request.body)
        context = preparar_contexto_para_pdf(data)
        html = render_to_string('contabilidad/formatos/formato_basico.html', context, request)
        return HttpResponse(html)
    except Exception as e:
        logger.error(f"Error en formato básico: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=500)


@login_required
@require_POST
def render_formato_profesional(request, alias):
    try:
        data = json.loads(request.body)
        print("VALOR RECIBIDO cuota_impuesto:", data.get('cuota_impuesto'))
        context = preparar_contexto_para_pdf(data)
        html = render_to_string('contabilidad/formatos/formato_profesional.html', context, request)
        return HttpResponse(html)
    except Exception as e:
        logger.error(f"Error en formato profesional: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=500)


@login_required
@require_POST
def render_formato_detallado(request, alias):
    """Renderiza el formato detallado de liquidación"""
    try:
        data = json.loads(request.body)
        context = preparar_contexto_para_pdf(data)
        html = render_to_string('contabilidad/formatos/formato_detallado.html', context, request)
        return HttpResponse(html)
    except Exception as e:
        logger.error(f"Error en formato detallado: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=500)


@login_required
@require_POST
def render_formato_compacto(request, alias):
    """Renderiza el formato compacto (estético) de liquidación"""
    try:
        data = json.loads(request.body)
        context = preparar_contexto_para_pdf(data)
        html = render_to_string('contabilidad/formatos/formato_estetico.html', context, request)
        return HttpResponse(html)
    except Exception as e:
        logger.error(f"Error en formato compacto: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=500)


# ============================================
# FUNCIÓN PARA PREPARAR CONTEXTO DEL PDF
# ============================================

from decimal import Decimal, InvalidOperation
from datetime import datetime
import math

def numero_a_palabras(numero):
    """Convierte un número entero a su representación en palabras (español, hasta millones)."""
    if numero == 0:
        return "CERO"

    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    especiales = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISÉIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    decenas = ["", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def convertir_grupo(n):
        if n < 10:
            return unidades[n]
        elif 10 <= n < 20:
            return especiales[n-10]
        elif 20 <= n < 100:
            d = n // 10
            u = n % 10
            if u == 0:
                return decenas[d]
            else:
                return decenas[d] + " Y " + unidades[u]
        elif 100 <= n < 1000:
            c = n // 100
            resto = n % 100
            if n == 100:
                return "CIEN"
            if resto == 0:
                return centenas[c]
            else:
                return centenas[c] + " " + convertir_grupo(resto)
        else:
            return ""

    millones = numero // 1000000
    miles = (numero % 1000000) // 1000
    resto_unidades = numero % 1000

    partes = []
    if millones > 0:
        if millones == 1:
            partes.append("UN MILLÓN")
        else:
            partes.append(convertir_grupo(millones) + " MILLONES")
    if miles > 0:
        if miles == 1:
            partes.append("MIL")
        else:
            partes.append(convertir_grupo(miles) + " MIL")
    if resto_unidades > 0:
        if resto_unidades == 1 and millones == 0 and miles == 0:
            partes.append("UNO")
        else:
            partes.append(convertir_grupo(resto_unidades))

    return " ".join(partes).strip()

def preparar_contexto_para_pdf(data):
    """
    Prepara el contexto para los templates de PDF
    Solo recibe datos, no guarda nada en BD
    """
    context = {}

    # Función para convertir a Decimal
    def to_decimal(valor, default=0):
        try:
            if valor is None:
                return Decimal(str(default))
            return Decimal(str(valor))
        except (TypeError, ValueError, Decimal.InvalidOperation):
            return Decimal(str(default))

    # Función para formatear fecha
    def formatear_fecha(fecha_str):
        if not fecha_str:
            return ''
        try:
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                try:
                    fecha = datetime.strptime(fecha_str, fmt)
                    return fecha.strftime('%d/%m/%Y')
                except ValueError:
                    continue
            return fecha_str
        except:
            return fecha_str

    # ============================================
    # DATOS DE LA EMPRESA (para el PDF)
    # ============================================
    context['empresa_nombre'] = data.get('empresa_nombre', '')
    context['empresa_rut'] = data.get('empresa_rut', '')
    context['empresa_logo'] = data.get('empresa_logo', '')
    context['empresa_direccion'] = data.get('empresa_direccion', '')
    context['empresa_ciudad'] = data.get('empresa_ciudad', '')
    context['empresa_telefono'] = data.get('empresa_telefono', '')
    context['empresa_email'] = data.get('empresa_email', '')

    # ============================================
    # DATOS DEL TRABAJADOR (para el PDF)
    # ============================================
    context['trabajador_nombre'] = data.get('trabajador_nombre', '')
    context['trabajador_rut'] = data.get('trabajador_rut', '')
    context['trabajador_cargo'] = data.get('trabajador_cargo', '')
    context['trabajador_departamento'] = data.get('trabajador_departamento', '')
    context['trabajador_fecha_contrato'] = formatear_fecha(data.get('trabajador_fecha_contrato', ''))
    context['centro_costo'] = data.get('centro_costo', 'No asignado')

    # ============================================
    # DATOS DEL PERÍODO
    # ============================================
    context['periodo_mes'] = data.get('periodo_mes', '')
    context['periodo_anio'] = data.get('periodo_anio', '')
    context['periodo_dias_habiles'] = to_decimal(data.get('periodo_dias_habiles', 22))
    context['dias_trabajados'] = to_decimal(data.get('dias_trabajados', 0))
    context['horas_trabajadas'] = to_decimal(data.get('horas_trabajadas', 0))

    # ============================================
    # HABERES
    # ============================================
    context['sueldo_mensual'] = to_decimal(data.get('sueldo_mensual', 0))
    context['sueldo_diario'] = to_decimal(data.get('sueldo_diario', 0))
    context['atraso'] = to_decimal(data.get('atraso', 0))
    context['horas_extra_50'] = to_decimal(data.get('horas_extra_50', 0))
    context['horas_extra_100'] = to_decimal(data.get('horas_extra_100', 0))
    context['horas_extra_150'] = to_decimal(data.get('horas_extra_150', 0))
    context['total_horas_extra'] = to_decimal(data.get('total_horas_extra', 0))
    context['total_comision'] = to_decimal(data.get('total_comision', 0))
    context['monto_cargo_domingo'] = to_decimal(data.get('monto_cargo_domingo', 0))
    context['utilidades'] = to_decimal(data.get('utilidades', 0))
    context['semana_corrida'] = to_decimal(data.get('semana_corrida', 0))
    context['monto_gratificacion'] = to_decimal(data.get('monto_gratificacion', 0))
    context['bonos'] = to_decimal(data.get('bonos', 0))
    context['colacion'] = to_decimal(data.get('colacion', 0))
    context['movilizacion'] = to_decimal(data.get('movilizacion', 0))
    context['numero_cargas'] = to_decimal(data.get('numero_cargas', 0))
    context['asignacion_familiar'] = to_decimal(data.get('asignacion_familiar', 0))
    context['asignacion_maternal'] = to_decimal(data.get('asignacion_maternal', 0))
    context['otro_bono1_nombre'] = data.get('otro_bono1_nombre', '')
    context['otro_bono1_valor'] = to_decimal(data.get('otro_bono1_valor', 0))
    context['otro_bono2_nombre'] = data.get('otro_bono2_nombre', '')
    context['otro_bono2_valor'] = to_decimal(data.get('otro_bono2_valor', 0))

    # ============================================
    # DESCUENTOS
    # ============================================
    context['afp_nombre'] = data.get('afp_nombre', '')
    context['porcentaje_afp'] = to_decimal(data.get('porcentaje_afp', 11))
    context['cotizacion_afp'] = to_decimal(data.get('cotizacion_afp', 0))
    context['cuenta_2_afp'] = to_decimal(data.get('cuenta_2_afp', 0))
    context['trabajo_pesado'] = to_decimal(data.get('trabajo_pesado', 0))
    context['cotizacion_afc'] = to_decimal(data.get('cotizacion_afc', 0))
    context['apv'] = to_decimal(data.get('apv', 0))
    context['apv2'] = to_decimal(data.get('apv2', 0))
    context['apv_colectivo'] = to_decimal(data.get('apv_colectivo', 0))
    context['isapre_nombre'] = data.get('isapre_nombre', '')
    context['cotizacion_salud_pactada'] = to_decimal(data.get('cotizacion_salud_pactada', 7))
    context['diferencia_isapre'] = to_decimal(data.get('diferencia_isapre', 0))
    context['base_impuesto'] = to_decimal(data.get('base_impuesto', 0))
    context['cuota_impuesto'] = round(to_decimal(data.get('cuota_impuesto', 0)))  # entero
    context['anticipo_impuesto'] = to_decimal(data.get('anticipo_impuesto', 0))
    context['prestamo_ccaf'] = to_decimal(data.get('prestamo_ccaf', 0))
    context['prestamo_empresa'] = to_decimal(data.get('prestamo_empresa', 0))
    context['otro_descuento1_nombre'] = data.get('otro_descuento1_nombre', '')
    context['otro_descuento1_valor'] = to_decimal(data.get('otro_descuento1_valor', 0))
    context['otro_descuento2_nombre'] = data.get('otro_descuento2_nombre', '')
    context['otro_descuento2_valor'] = to_decimal(data.get('otro_descuento2_valor', 0))

    # ============================================
    # TOTALES
    # ============================================
    context['total_imponible'] = to_decimal(data.get('total_imponible', 0))
    context['total_no_imponible'] = to_decimal(data.get('total_no_imponible', 0))
    context['total_haberes_variables'] = to_decimal(data.get('total_haberes_variables', 0))
    context['total_semana_corrida'] = to_decimal(data.get('total_semana_corrida', 0))
    context['total_prevision'] = to_decimal(data.get('total_prevision', 0))
    context['total_haberes'] = to_decimal(data.get('total_haberes', 0))
    context['total_descuentos'] = to_decimal(data.get('total_descuentos', 0))
    context['liquido_pagable'] = to_decimal(data.get('liquido_pagable', 0))

    # ============================================
    # AUSENCIAS
    # ============================================
    context['vacaciones_dias'] = to_decimal(data.get('vacaciones_dias', 0))
    context['vacaciones_glosa'] = data.get('vacaciones_glosa', '')
    context['licencias_dias'] = to_decimal(data.get('licencias_dias', 0))
    context['licencias_glosa'] = data.get('licencias_glosa', '')
    context['faltas_dias'] = to_decimal(data.get('faltas_dias', 0))
    context['faltas_glosa'] = data.get('faltas_glosa', '')

    # ============================================
    # OPCIONES DEL PDF
    # ============================================
    context['incluir_firma'] = data.get('incluir_firma', False)
    context['incluir_logo'] = data.get('incluir_logo', False)
    context['fecha_generacion'] = formatear_fecha(data.get('fecha_generacion', datetime.now().strftime('%d/%m/%Y')))
    context['glosa'] = data.get('glosa', 'LIQUIDACION_SUELDO')

    # ============================================
    # MONTO EN PALABRAS (CORREGIDO)
    # ============================================
    # Convertir el líquido a entero (redondeado) y luego a palabras
    liquido_int = int(round(context['liquido_pagable']))
    context['liquido_pagable_palabras'] = numero_a_palabras(liquido_int)

    return context

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import CentroCosto
from empresas.models import Empresa

class CentroCostoMixin(LoginRequiredMixin):
    """Mixin para obtener la empresa a partir del slug en la URL."""
    def get_empresa(self):
        return Empresa.objects.get(slug=self.kwargs['alias'])

    def get_queryset(self):
        return CentroCosto.objects.filter(empresa=self.get_empresa())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['alias'] = self.kwargs['alias']
        context['empresa'] = self.get_empresa()
        return context

class CentroCostoListView(CentroCostoMixin, ListView):
    model = CentroCosto
    template_name = 'contabilidad/centro_costo/centrocosto_list.html'
    context_object_name = 'centros'

class CentroCostoCreateView(CentroCostoMixin, CreateView):
    model = CentroCosto
    fields = ['codigo', 'nombre', 'descripcion', 'activo']
    template_name = 'contabilidad/centro_costo/centrocosto_form.html'

    def form_valid(self, form):
        form.instance.empresa = self.get_empresa()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('centro_costo_list', kwargs={'alias': self.kwargs['alias']})

class CentroCostoUpdateView(CentroCostoMixin, UpdateView):
    model = CentroCosto
    fields = ['codigo', 'nombre', 'descripcion', 'activo']
    template_name = 'contabilidad/centro_costo/centrocosto_form.html'

    def get_success_url(self):
        return reverse_lazy('centro_costo_list', kwargs={'alias': self.kwargs['alias']})

class CentroCostoDeleteView(CentroCostoMixin, DeleteView):
    model = CentroCosto
    template_name = 'contabilidad/centro_costo/centrocosto_confirm_delete.html'

    def get_success_url(self):
        return reverse_lazy('centro_costo_list', kwargs={'alias': self.kwargs['alias']})

from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from .models import Liquidacion, Trabajador, Periodo, Empresa
from datetime import datetime

@login_required
def ver_liquidacion_pdf(request, alias, periodo_id, trabajador_id):
    """
    Vista que muestra la liquidación en formato HTML listo para imprimir.
    Además, incluye un script que genera el PDF automáticamente.
    """
    empresa = get_object_or_404(Empresa, slug=alias)
    periodo = get_object_or_404(Periodo, id=periodo_id, empresa=empresa)
    trabajador = get_object_or_404(Trabajador, id=trabajador_id, empresa=empresa)
    liquidacion = get_object_or_404(Liquidacion, periodo=periodo, trabajador=trabajador)

    # Preparar los datos en el mismo formato que espera preparar_contexto_para_pdf
    data = {
        # Datos de empresa
        'empresa_nombre': empresa.nombre,
        'empresa_rut': empresa.rut,
        'empresa_direccion': empresa.direccion,
        'empresa_ciudad': '',  # Ajusta si tu modelo tiene ciudad
        'empresa_logo': empresa.get_logo_url() if hasattr(empresa, 'get_logo_url') else '',
        
        # Datos del trabajador
        'trabajador_nombre': trabajador.nombre_completo,
        'trabajador_rut': trabajador.rut,
        'trabajador_cargo': trabajador.cargo,
        'trabajador_fecha_ingreso': trabajador.fecha_contrato.strftime('%Y-%m-%d') if trabajador.fecha_contrato else '',
        'centro_costo': trabajador.centro_costo_nombre or 'No asignado',
        
        # Período
        'periodo_mes': periodo.mes,
        'periodo_anio': periodo.anio,
        'periodo_dias_habiles': periodo.dias_habiles,
        'dias_trabajados': liquidacion.dias_trabajados,
        
        # Sueldo y valores base
        'sueldo_mensual': float(liquidacion.sueldo_mensual),
        'sueldo_diario': float(liquidacion.sueldo_diario),
        'atraso': float(liquidacion.atraso),
        
        # Horas extra
        'horas_extra_50': float(liquidacion.horas_extra_50),
        'horas_extra_100': float(liquidacion.horas_extra_100),
        'horas_extra_150': float(liquidacion.horas_extra_150),
        'total_horas_extra': float(liquidacion.total_horas_extra),
        
        # Comisiones y cargos
        'total_comision': float(liquidacion.total_comision),
        'monto_cargo_domingo': float(liquidacion.monto_cargo_domingo),
        
        # Utilidades y semana corrida
        'utilidades': float(liquidacion.utilidades),
        'semana_corrida': float(liquidacion.semana_corrida),
        
        # Gratificación y bonos
        'monto_gratificacion': float(liquidacion.monto_gratificacion),
        'bonos': float(liquidacion.bonos),
        
        # Asignaciones
        'colacion': float(liquidacion.colacion),
        'movilizacion': float(liquidacion.movilizacion),
        'numero_cargas': liquidacion.numero_cargas,
        'asignacion_familiar': float(liquidacion.asignacion_familiar) if hasattr(liquidacion, 'asignacion_familiar') else 0,
        'asignacion_maternal': float(liquidacion.asignacion_maternal) if hasattr(liquidacion, 'asignacion_maternal') else 0,
        
        # Otros bonos
        'otro_bono1_nombre': liquidacion.nombre_otro_bono_1,
        'otro_bono1_valor': float(liquidacion.valor_otro_bono_1),
        'otro_bono2_nombre': liquidacion.nombre_otro_bono_2,
        'otro_bono2_valor': float(liquidacion.valor_otro_bono_2),
        
        # AFP
        'afp_nombre': liquidacion.afp_nombre,
        'porcentaje_afp': float(liquidacion.porcentaje_afp),
        'cotizacion_afp': float(liquidacion.cotizacion_afp),
        'cuenta_2_afp': float(liquidacion.cuenta_2_afp),
        
        # AFC
        'cotizacion_afc': float(liquidacion.cotizacion_afc),
        'trabajo_pesado': float(liquidacion.trabajo_pesado) if hasattr(liquidacion, 'trabajo_pesado') else 0,
        
        # APV
        'apv': float(liquidacion.apv),
        'apv2': float(liquidacion.apv2),
        'apv_colectivo': float(liquidacion.apv_colectivo),
        
        # Salud
        'isapre_nombre': liquidacion.isapre_nombre,
        'cotizacion_salud_pactada': float(liquidacion.cotizacion_salud_pactada),
        'diferencia_isapre': float(liquidacion.diferencia_isapre),
        
        # Impuesto
        'base_impuesto': float(liquidacion.base_impuesto),
        'anticipo_impuesto': float(liquidacion.anticipo_impuesto),
        'cuota_impuesto': float(liquidacion.cuota_impuesto),
        
        # Préstamos
        'prestamo_ccaf': float(liquidacion.prestamo_ccaf),
        'prestamo_empresa': float(liquidacion.prestamo_empresa),
        
        # Otros descuentos
        'otro_descuento1_nombre': liquidacion.nombre_otro_descuento_1,
        'otro_descuento1_valor': float(liquidacion.valor_otro_descuento_1),
        'otro_descuento2_nombre': liquidacion.nombre_otro_descuento_2,
        'otro_descuento2_valor': float(liquidacion.valor_otro_descuento_2),
        
        # Ausencias
        'vacaciones_dias': liquidacion.vacaciones_dias,
        'vacaciones_glosa': liquidacion.vacaciones_glosa,
        'licencias_dias': liquidacion.licencias_dias,
        'licencias_glosa': liquidacion.licencias_glosa,
        'faltas_dias': liquidacion.faltas_dias,
        'faltas_glosa': liquidacion.faltas_glosa,
        
        # Totales
        'total_imponible': float(liquidacion.total_imponible),
        'total_no_imponible': float(liquidacion.total_no_imponible) if hasattr(liquidacion, 'total_no_imponible') else 0,
        'total_haberes': float(liquidacion.total_haberes),
        'total_descuentos': float(liquidacion.total_descuentos),
        'liquido_pagable': float(liquidacion.liquido_pagable),
        'total_prevision': float(liquidacion.total_prevision),
        
        # Opciones del PDF
        'incluir_firma': True,
        'incluir_logo': True,
        'fecha_generacion': datetime.now().strftime('%d/%m/%Y'),
        'glosa': liquidacion.glosa,
    }
    
    # Preparar contexto usando la función existente (asumo que está definida)
    context = preparar_contexto_para_pdf(data)
    
    # Renderizar el template del formato profesional (u otro)
    html = render_to_string('contabilidad/formatos/ver_liquidacion.html', context, request)
    
    # Devolver el HTML (que incluirá un script para generar PDF automáticamente)
    return HttpResponse(html)