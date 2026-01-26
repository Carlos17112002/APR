import uuid
from django.utils import timezone
from django.db import transaction
import json
from decimal import Decimal

def generar_token_dispositivo():
    """Genera un token único para dispositivos móviles"""
    return str(uuid.uuid4())

def validar_lectura_data(data):
    """Valida los datos de una lectura antes de guardar"""
    errores = []
    
    # Validar campos requeridos
    campos_requeridos = ['cliente_id', 'lectura_actual']
    for campo in campos_requeridos:
        if campo not in data:
            errores.append(f'Campo requerido faltante: {campo}')
    
    # Validar tipos de datos
    if 'lectura_actual' in data:
        try:
            Decimal(str(data['lectura_actual']))
        except:
            errores.append('lectura_actual debe ser un número válido')
    
    # Validar ubicación si existe
    if 'latitud' in data and data['latitud'] is not None:
        try:
            lat = Decimal(str(data['latitud']))
            if not (-90 <= lat <= 90):
                errores.append('latitud debe estar entre -90 y 90')
        except:
            errores.append('latitud debe ser un número válido')
    
    if 'longitud' in data and data['longitud'] is not None:
        try:
            lon = Decimal(str(data['longitud']))
            if not (-180 <= lon <= 180):
                errores.append('longitud debe estar entre -180 y 180')
        except:
            errores.append('longitud debe ser un número válido')
    
    return errores

def calcular_consumo(lectura_actual, lectura_anterior):
    """Calcula el consumo basado en lecturas actual y anterior"""
    try:
        if lectura_anterior is None:
            return Decimal('0.00')
        
        consumo = Decimal(str(lectura_actual)) - Decimal(str(lectura_anterior))
        return max(consumo, Decimal('0.00'))  # No permitir consumos negativos
    except:
        return Decimal('0.00')

def guardar_lectura_offline(lectura_data, dispositivo_id):
    """
    Guarda una lectura para sincronización offline
    Retorna un ID temporal para referencia local
    """
    from .models import LecturaMovilTemporal
    
    try:
        lectura_temp = LecturaMovilTemporal.objects.create(
            dispositivo_id=dispositivo_id,
            datos=json.dumps(lectura_data),
            fecha_creacion=timezone.now(),
            estado='pendiente'
        )
        return lectura_temp.id
    except Exception as e:
        print(f"Error guardando lectura offline: {e}")
        return None

def sincronizar_lecturas_pendientes(dispositivo_id):
    """
    Sincroniza lecturas pendientes de un dispositivo
    Retorna el número de lecturas procesadas
    """
    from .models import LecturaMovilTemporal, LecturaMovil, Cliente, DispositivoMovil
    
    try:
        dispositivo = DispositivoMovil.objects.get(id=dispositivo_id)
        lecturas_pendientes = LecturaMovilTemporal.objects.filter(
            dispositivo_id=dispositivo_id,
            estado='pendiente'
        )
        
        procesadas = 0
        errores = []
        
        for lectura_temp in lecturas_pendientes:
            try:
                datos = json.loads(lectura_temp.datos)
                
                # Validar datos
                errores_validacion = validar_lectura_data(datos)
                if errores_validacion:
                    lectura_temp.estado = 'error'
                    lectura_temp.mensaje_error = '; '.join(errores_validacion)
                    lectura_temp.save()
                    errores.append(f"Lectura {lectura_temp.id}: {'; '.join(errores_validacion)}")
                    continue
                
                # Obtener cliente
                try:
                    cliente = Cliente.objects.get(
                        id=datos['cliente_id'],
                        empresa=dispositivo.empresa
                    )
                except Cliente.DoesNotExist:
                    lectura_temp.estado = 'error'
                    lectura_temp.mensaje_error = 'Cliente no encontrado'
                    lectura_temp.save()
                    errores.append(f"Lectura {lectura_temp.id}: Cliente no encontrado")
                    continue
                
                # Calcular consumo
                lectura_anterior = cliente.lecturas.last().lectura_actual if cliente.lecturas.exists() else None
                consumo = calcular_consumo(datos['lectura_actual'], lectura_anterior)
                
                # Crear lectura móvil
                lectura = LecturaMovil.objects.create(
                    dispositivo=dispositivo,
                    cliente=cliente,
                    lectura_actual=datos['lectura_actual'],
                    lectura_anterior=lectura_anterior,
                    consumo=consumo,
                    latitud=datos.get('latitud'),
                    longitud=datos.get('longitud'),
                    observaciones=datos.get('observaciones', ''),
                    estado='sincronizado'
                )
                
                # También crear en el sistema principal si existe el modelo
                try:
                    from .models import Lectura
                    Lectura.objects.create(
                        cliente=cliente,
                        lectura_actual=datos['lectura_actual'],
                        consumo=consumo,
                        fecha_lectura=timezone.now(),
                        observaciones=f"Desde móvil: {datos.get('observaciones', '')}"
                    )
                except:
                    pass  # Si no existe el modelo Lectura, continuar
                
                # Marcar como procesada
                lectura_temp.estado = 'procesada'
                lectura_temp.lectura_id = lectura.id
                lectura_temp.save()
                procesadas += 1
                
            except Exception as e:
                lectura_temp.estado = 'error'
                lectura_temp.mensaje_error = str(e)
                lectura_temp.save()
                errores.append(f"Lectura {lectura_temp.id}: {e}")
        
        return {
            'procesadas': procesadas,
            'errores': errores,
            'total': len(lecturas_pendientes)
        }
        
    except Exception as e:
        return {
            'procesadas': 0,
            'errores': [str(e)],
            'total': 0
        }

def crear_respuesta_api(success=True, data=None, error=None, message=None):
    """Crea una respuesta API estandarizada"""
    respuesta = {
        'success': success,
        'timestamp': timezone.now().isoformat(),
    }
    
    if data is not None:
        respuesta['data'] = data
    
    if error is not None:
        respuesta['error'] = error
    
    if message is not None:
        respuesta['message'] = message
    
    return respuesta

def obtener_clientes_para_movil(empresa):
    """
    Obtiene clientes formateados para app móvil
    Incluye última lectura si existe
    """
    from .models import Cliente
    
    clientes = Cliente.objects.filter(
        empresa=empresa,
        activo=True
    ).select_related('empresa').prefetch_related('lecturas')
    
    clientes_data = []
    
    for cliente in clientes:
        ultima_lectura = cliente.lecturas.last()
        
        cliente_data = {
            'id': cliente.id,
            'codigo': cliente.codigo_cliente,
            'nombre': cliente.nombre,
            'direccion': cliente.direccion,
            'medidor': cliente.medidor_numero or '',
            'lectura_anterior': float(ultima_lectura.lectura_actual) if ultima_lectura else 0.0,
            'fecha_ultima_lectura': ultima_lectura.fecha_lectura.isoformat() if ultima_lectura else None,
            'estado': cliente.estado,
            'zona': cliente.zona or '',
            'ruta': cliente.ruta or '',
        }
        
        clientes_data.append(cliente_data)
    
    return clientes_data

def generar_reporte_lecturas_movil(dispositivo, fecha_inicio, fecha_fin):
    """
    Genera un reporte de lecturas tomadas por dispositivo móvil
    """
    from .models import LecturaMovil
    from django.db.models import Count, Sum
    
    lecturas = LecturaMovil.objects.filter(
        dispositivo=dispositivo,
        fecha_lectura__date__gte=fecha_inicio,
        fecha_lectura__date__lte=fecha_fin
    ).select_related('cliente')
    
    total_lecturas = lecturas.count()
    lecturas_sincronizadas = lecturas.filter(estado='sincronizado').count()
    total_consumo = lecturas.aggregate(Sum('consumo'))['consumo__sum'] or 0
    
    reporte = {
        'dispositivo': dispositivo.nombre_dispositivo,
        'empresa': dispositivo.empresa.nombre,
        'periodo': {
            'inicio': fecha_inicio.isoformat(),
            'fin': fecha_fin.isoformat()
        },
        'estadisticas': {
            'total_lecturas': total_lecturas,
            'lecturas_sincronizadas': lecturas_sincronizadas,
            'pendientes': total_lecturas - lecturas_sincronizadas,
            'total_consumo': float(total_consumo),
            'promedio_consumo': float(total_consumo / total_lecturas) if total_lecturas > 0 else 0
        },
        'detalle_lecturas': []
    }
    
    for lectura in lecturas:
        reporte['detalle_lecturas'].append({
            'cliente': lectura.cliente.nombre,
            'codigo_cliente': lectura.cliente.codigo_cliente,
            'fecha': lectura.fecha_lectura.isoformat(),
            'lectura_actual': float(lectura.lectura_actual),
            'consumo': float(lectura.consumo) if lectura.consumo else 0,
            'estado': lectura.estado,
            'latitud': float(lectura.latitud) if lectura.latitud else None,
            'longitud': float(lectura.longitud) if lectura.longitud else None,
        })
    
    return reporte