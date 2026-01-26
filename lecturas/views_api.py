from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
import json
from .models import Empresa, DispositivoMovil, LecturaMovil
from .utils import generar_token_dispositivo
from clientes.models import Cliente
import uuid

@csrf_exempt
@require_POST
def api_autenticar_dispositivo(request, alias):
    try:
        print(f"DEBUG: Autenticando dispositivo para empresa: {alias}")
        data = json.loads(request.body)
        print(f"DEBUG: Datos recibidos: {data}")
        
        empresa_slug = alias
        identificador = data.get('identificador')
        nombre_dispositivo = data.get('nombre_dispositivo', 'Dispositivo Móvil')
        
        print(f"DEBUG: Identificador recibido: '{identificador}' (tipo: {type(identificador)})")
        
        if not identificador:
            return JsonResponse({
                'success': False,
                'error': 'El identificador es requerido'
            }, status=400)
        
        # Buscar empresa
        try:
            empresa = Empresa.objects.get(slug=empresa_slug)
        except Empresa.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Empresa no encontrada'
            }, status=404)
        
        print(f"DEBUG: Empresa encontrada: {empresa.nombre}")
        
        # Buscar o crear dispositivo
        dispositivo, created = DispositivoMovil.objects.get_or_create(
            empresa=empresa,
            identificador=identificador,
            defaults={
                'nombre_dispositivo': nombre_dispositivo,
                'token_acceso': uuid.uuid4()
            }
        )
        
        if not created:
            dispositivo.token_acceso = uuid.uuid4()
            dispositivo.ultima_conexion = timezone.now()
            dispositivo.save()
        
        print(f"DEBUG: Dispositivo {'creado' if created else 'actualizado'}: {dispositivo.id}")
        
        return JsonResponse({
            'success': True,
            'token': str(dispositivo.token_acceso),
            'empresa': {
                'id': empresa.id,
                'nombre': empresa.nombre,
                'slug': empresa.slug
            },
            'dispositivo': {
                'id': dispositivo.id,
                'nombre': dispositivo.nombre_dispositivo
            }
        })
        
    except Exception as e:
        print(f"DEBUG: Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    
# Vista específica para la app móvil con token en URL
@require_GET
def api_obtener_clientes_con_token(request, alias, token):
    """
    Versión alternativa que acepta token en la URL path
    Compatible con tu app Flutter actual
    """
    try:
        # Verificar que el dispositivo pertenece a la empresa del alias
        dispositivo = DispositivoMovil.objects.get(
            token_acceso=token, 
            activo=True,
            empresa__slug=alias
        )
        empresa = dispositivo.empresa
        
        # Obtener clientes activos
        clientes = Cliente.objects.filter(
            empresa=empresa, 
            activo=True
        ).order_by('codigo_cliente')
        
        clientes_data = []
        for cliente in clientes:
            # Obtener última lectura registrada
            ultima_lectura = cliente.lecturas.last()
            lectura_anterior = ultima_lectura.lectura_actual if ultima_lectura else 0
            
            clientes_data.append({
                'id': cliente.id,
                'uuid': str(cliente.uuid),  # <-- Añadir UUID
                'codigo': cliente.codigo_cliente,
                'nombre': cliente.nombre,
                'direccion': cliente.direccion,
                'medidor_numero': cliente.medidor_numero or '',
                'lectura_anterior': float(lectura_anterior),
                'ultima_fecha_lectura': ultima_lectura.fecha_lectura.isoformat() if ultima_lectura else None,
                'estado': cliente.estado,
                'medidor': cliente.medidor_numero or '',
                'fecha_ultima_lectura': ultima_lectura.fecha_lectura.strftime('%Y-%m-%d') if ultima_lectura else '',
                'sector': cliente.sector.nombre if cliente.sector else '',
                'zona': cliente.zona.nombre if cliente.zona else '',
            })
        
        # Actualizar última conexión del dispositivo
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.save()
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'total_clientes': len(clientes_data),
            'clientes': clientes_data,
            'fecha_sincronizacion': timezone.now().isoformat()
        })
        
    except DispositivoMovil.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido, dispositivo inactivo o no pertenece a esta empresa'
        }, status=401)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

# API para obtener un cliente específico por UUID (PARA LECTURAS MÓVIL)
@require_GET
def api_obtener_cliente_por_uuid(request, alias, token, cliente_uuid):
    """
    Obtiene un cliente específico por su UUID para la app móvil
    """
    try:
        # Verificar que el dispositivo pertenece a la empresa del alias
        dispositivo = DispositivoMovil.objects.get(
            token_acceso=token, 
            activo=True,
            empresa__slug=alias  # Verificar empresa
        )
        empresa = dispositivo.empresa
        
        try:
            # Buscar cliente por UUID
            cliente = Cliente.objects.get(
                uuid=cliente_uuid,  # <-- Esto es lo importante
                empresa=empresa, 
                activo=True
            )
        except Cliente.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Cliente con UUID {cliente_uuid} no encontrado'
            }, status=404)
        
        # Obtener última lectura registrada
        ultima_lectura = cliente.lecturas.last()
        lectura_anterior = ultima_lectura.lectura_actual if ultima_lectura else 0
        
        cliente_data = {
            'id': cliente.id,
            'uuid': str(cliente.uuid),  # <-- Incluir UUID en respuesta
            'codigo': cliente.codigo_cliente,
            'nombre': cliente.nombre,
            'direccion': cliente.direccion,
            'medidor_numero': cliente.medidor_numero or '',
            'lectura_anterior': float(lectura_anterior),
            'ultima_fecha_lectura': ultima_lectura.fecha_lectura.isoformat() if ultima_lectura else None,
            'estado': cliente.estado,
            'medidor': cliente.medidor_numero or '',  # Para compatibilidad con Flutter
            'fecha_ultima_lectura': ultima_lectura.fecha_lectura.strftime('%Y-%m-%d') if ultima_lectura else '',
            'sector': cliente.sector.nombre if cliente.sector else '',
            'zona': cliente.zona.nombre if cliente.zona else '',
        }
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'cliente': cliente_data
        })
        
    except DispositivoMovil.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido, dispositivo inactivo o no pertenece a esta empresa'
        }, status=401)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
    

# API para obtener clientes desde móvil
# En tu vista Django (views.py o views_movil.py)
# En tu views.py - versión con debug extendido
# En tu views.py o views_movil.py
@require_GET
def api_obtener_clientes(request, alias, token=None):
    """
    Obtiene clientes para la app móvil - SOPORTE PARA MÚLTIPLES BASES DE DATOS
    """
    try:
        print(f"\n=== API CLIENTES PARA: {alias} ===")
        
        # Obtener token
        token_param = token or request.GET.get('token')
        
        if not token_param:
            return JsonResponse({
                'success': False,
                'error': 'Token de autenticación requerido'
            }, status=400)
        
        # 1. Verificar dispositivo
        dispositivo = DispositivoMovil.objects.get(
            token_acceso=token_param,
            activo=True,
            empresa__slug=alias
        )
        empresa = dispositivo.empresa
        print(f"✅ Empresa: {empresa.nombre}")
        
        # 2. Determinar nombre de la base de datos
        alias_db = f'db_{alias}'
        print(f"📊 Base de datos a usar: {alias_db}")
        
        # 3. Obtener clientes desde la base de datos específica
        try:
            # Verificar si la base de datos existe
            from django.db import connections
            if alias_db not in connections.databases:
                print(f"⚠️  Base de datos '{alias_db}' no configurada")
                raise Exception(f"Base de datos '{alias_db}' no encontrada")
            
            # Obtener clientes
            clientes = Cliente.objects.using(alias_db).all()
            print(f"📋 Total clientes en {alias_db}: {clientes.count()}")
            
            # Si no hay clientes, verificar en default como respaldo
            if clientes.count() == 0:
                print("⚠️  No hay clientes en BD específica. Probando default...")
                clientes = Cliente.objects.all()
                print(f"   Clientens en default: {clientes.count()}")
            
        except Exception as db_error:
            print(f"❌ Error accediendo a BD {alias_db}: {db_error}")
            # Intentar con base de datos default como respaldo
            clientes = Cliente.objects.all()
            print(f"📋 Usando BD default. Total: {clientes.count()}")
        
        # 4. Preparar datos para la app móvil
        clientes_data = []
        for cliente in clientes:
            # Verificar que el cliente pertenece a esta empresa
            # (si hay campo empresa_slug o alguna relación)
            pertenece_a_empresa = True  # Por defecto asumimos que sí
            
            # Si hay campo empresa_slug, verificar
            if hasattr(cliente, 'empresa_slug') and cliente.empresa_slug:
                pertenece_a_empresa = (cliente.empresa_slug == alias)
            
            # Si hay ForeignKey empresa, verificar
            elif hasattr(cliente, 'empresa') and cliente.empresa:
                pertenece_a_empresa = (cliente.empresa.slug == alias)
            
            if not pertenece_a_empresa:
                print(f"⚠️  Cliente {cliente.id} no pertenece a {alias}")
                continue
            
            # Obtener última lectura si existe
            ultima_lectura = None
            if hasattr(cliente, 'lecturas'):
                ultima_lectura = cliente.lecturas.last()
            elif hasattr(cliente, 'lecturamovil'):
                ultima_lectura = cliente.lecturamovil.last()
            
            lectura_anterior = ultima_lectura.lectura_actual if ultima_lectura else 0
            
            # Datos del cliente para la app móvil
            cliente_data = {
                'id': cliente.id,
                'codigo': cliente.codigo if hasattr(cliente, 'codigo') else str(cliente.id),
                'nombre': cliente.nombre,
                'direccion': cliente.direccion or '',
                'medidor': cliente.medidor or '',
                'lectura_anterior': float(lectura_anterior),
                'estado': 'activo',
                'fecha_ultima_lectura': ultima_lectura.fecha_lectura.strftime('%Y-%m-%d') if ultima_lectura else '',
                'rut': cliente.rut or '',
                'telefono': cliente.telefono or '',
                'email': cliente.email or '',
                'sector': cliente.sector.nombre if cliente.sector and hasattr(cliente.sector, 'nombre') else '',
                'zona': cliente.zona.nombre if hasattr(cliente, 'zona') and cliente.zona else '',
            }
            
            clientes_data.append(cliente_data)
            print(f"   ✓ Cliente: {cliente.id} - {cliente.nombre}")
        
        print(f"✅ Clientes preparados para app: {len(clientes_data)}")
        
        # 5. Si no hay clientes, crear datos de demostración
        if len(clientes_data) == 0:
            print("⚠️  No hay clientes. Creando datos de demostración...")
            clientes_data = crear_datos_demo(empresa)
        
        # 6. Actualizar última conexión del dispositivo
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.save()
        
        return JsonResponse({
            'success': True,
            'empresa': empresa.nombre,
            'empresa_id': empresa.id,
            'total_clientes': len(clientes_data),
            'clientes': clientes_data,
            'fecha_sincronizacion': timezone.now().isoformat(),
            'debug_info': {
                'base_datos_usada': alias_db,
                'alias': alias,
                'dispositivo_id': dispositivo.id,
            }
        })
        
    except DispositivoMovil.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido o dispositivo inactivo'
        }, status=401)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=400)
        
        
@csrf_exempt
@require_POST
def api_enviar_lecturas(request, alias, token):
    """
    Recibe lecturas desde la app móvil - VERSIÓN FINAL CORREGIDA CON ESTRUCTURA REAL
    """
    try:
        print(f"\n=== 📤 RECIBIENDO LECTURAS PARA: {alias} ===")
        print(f"🔑 Token: {token}")
        
        from django.utils import timezone
        from decimal import Decimal
        import json
        import uuid
        
        # 1. Verificar dispositivo y empresa
        dispositivo = DispositivoMovil.objects.get(
            token_acceso=token,
            activo=True,
            empresa__slug=alias
        )
        
        empresa = dispositivo.empresa
        print(f"✅ Dispositivo validado: {dispositivo.id}")
        print(f"🏢 Empresa: {empresa.nombre} (ID: {empresa.id}, Slug: {empresa.slug})")
        
        # 2. Procesar datos recibidos
        data = json.loads(request.body)
        lecturas = data.get('lecturas', [])
        print(f"📋 Total lecturas a procesar: {len(lecturas)}")
        
        if not lecturas:
            return JsonResponse({
                'success': False,
                'error': 'No se recibieron lecturas'
            }, status=400)
        
        lecturas_procesadas = []
        errores = []
        
        for i, lectura_data in enumerate(lecturas):
            try:
                print(f"\n  📝 Procesando lectura {i+1}:")
                
                # 3. Extraer y validar datos
                cliente_id_val = lectura_data.get('cliente_id')
                if not cliente_id_val:
                    raise Exception('cliente_id es requerido')
                
                # Convertir cliente_id a entero
                try:
                    cliente_id_val = int(cliente_id_val)
                except (ValueError, TypeError):
                    raise Exception(f'cliente_id debe ser número entero: {cliente_id_val}')
                
                lectura_actual_str = lectura_data.get('lectura_actual')
                if not lectura_actual_str:
                    raise Exception('lectura_actual es requerido')
                
                # Convertir lectura_actual a Decimal
                try:
                    lectura_actual = Decimal(str(lectura_actual_str))
                except:
                    raise Exception(f'lectura_actual no es un número válido: {lectura_actual_str}')
                
                # Datos opcionales
                latitud = lectura_data.get('latitud')
                longitud = lectura_data.get('longitud')
                observaciones = lectura_data.get('observaciones', '')
                medidor = lectura_data.get('medidor', '')
                
                print(f"     Cliente ID: {cliente_id_val}")
                print(f"     Lectura: {lectura_actual}")
                
                # 4. Verificar que el cliente existe en la BD de la empresa
                cliente_encontrado = False
                cliente_nombre = "Desconocido"
                alias_db = f'db_{alias}'
                
                try:
                    cliente = Cliente.objects.using(alias_db).get(
                        id=cliente_id_val,
                        empresa_slug=alias
                    )
                    cliente_encontrado = True
                    cliente_nombre = cliente.nombre
                    print(f"     ✅ Cliente existe en {alias_db}: {cliente_nombre}")
                except Cliente.DoesNotExist:
                    raise Exception(f'Cliente ID {cliente_id_val} no encontrado en empresa {alias}')
                except Exception as e:
                    print(f"     ⚠️  Error buscando cliente: {str(e)}")
                    raise Exception(f'Error buscando cliente: {str(e)}')
                
                # 5. Buscar última lectura usando cliente_id (entero)
                # La tabla tiene 'cliente' como int(11), no como ForeignKey en la BD
                from django.db import connection
                
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT lectura_actual 
                        FROM lecturas_lecturamovil 
                        WHERE cliente = %s AND empresa_slug = %s 
                        ORDER BY fecha_lectura DESC LIMIT 1
                    """, [cliente_id_val, alias])
                    
                    row = cursor.fetchone()
                    if row:
                        lectura_anterior = Decimal(str(row[0])) if row[0] else Decimal('0.0')
                        print(f"     📊 Última lectura anterior: {lectura_anterior}")
                    else:
                        lectura_anterior = Decimal('0.0')
                        print(f"     📊 No hay lecturas anteriores, usando 0")
                
                # 6. Calcular consumo
                consumo = lectura_actual - lectura_anterior
                if consumo < Decimal('0.0'):
                    print(f"     ⚠️  Consumo negativo ({consumo}), ajustado a 0")
                    consumo = Decimal('0.0')
                
                print(f"     📈 Consumo calculado: {consumo}")
                
                # 7. Crear nueva lectura usando SQL directo para coincidir con estructura real
                # Generar UUID de 32 caracteres (sin guiones)
                lectura_uuid = uuid.uuid4().hex  # Esto da 32 caracteres
                
                # Preparar valores para la consulta SQL
                fecha_actual = timezone.now().date()
                lectura_actual_str = str(lectura_actual)
                lectura_anterior_str = str(lectura_anterior)
                consumo_str = str(consumo)
                
                # Para MySQL booleano
                usada_para_boleta = 0  # False
                
                with connection.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO lecturas_lecturamovil 
                        (id, empresa_id, cliente, fecha_lectura, lectura_actual, 
                         lectura_anterior, consumo, latitud, longitud, estado, 
                         observaciones_app, usuario_app, empresa_slug, usada_para_boleta, 
                         fecha_sincronizacion)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, [
                        lectura_uuid,           # id - 32 caracteres
                        empresa.id,             # empresa_id
                        cliente_id_val,         # cliente (int)
                        fecha_actual,           # fecha_lectura
                        lectura_actual_str,     # lectura_actual
                        lectura_anterior_str,   # lectura_anterior
                        consumo_str,            # consumo
                        latitud,                # latitud
                        longitud,               # longitud
                        'cargada',              # estado
                        observaciones,          # observaciones_app
                        f"App: {dispositivo.nombre_dispositivo}",  # usuario_app
                        alias,                  # empresa_slug
                        usada_para_boleta,      # usada_para_boleta (0 = False)
                        timezone.now(),         # fecha_sincronizacion
                    ])
                
                print(f"     ✅ Lectura guardada: ID {lectura_uuid}")
                
                lecturas_procesadas.append({
                    'cliente_id': cliente_id_val,
                    'cliente_nombre': cliente_nombre,
                    'lectura_id': lectura_uuid,
                    'lectura_actual': float(lectura_actual),
                    'lectura_anterior': float(lectura_anterior),
                    'consumo': float(consumo),
                    'fecha_lectura': fecha_actual.isoformat(),
                    'estado': 'cargada',
                })
                
            except Exception as e:
                error_msg = str(e)
                print(f"     ❌ Error: {error_msg}")
                import traceback
                traceback.print_exc()
                errores.append({
                    'indice': i + 1,
                    'cliente_id': cliente_id_val if 'cliente_id_val' in locals() else 'desconocido',
                    'error': error_msg
                })
        
        # 8. Actualizar dispositivo
        dispositivo.ultima_conexion = timezone.now()
        dispositivo.save()
        
        print(f"\n=== 📊 RESULTADO FINAL ===")
        print(f"✅ Lecturas procesadas exitosamente: {len(lecturas_procesadas)}")
        print(f"⚠️  Errores: {len(errores)}")
        
        # 9. Preparar respuesta
        response_data = {
            'success': True if len(lecturas_procesadas) > 0 else False,
            'message': f'Procesadas {len(lecturas_procesadas)} de {len(lecturas)} lecturas',
            'procesadas': len(lecturas_procesadas),
            'errores': len(errores),
            'lecturas': lecturas_procesadas,
            'empresa': empresa.nombre,
            'fecha': timezone.now().isoformat(),
        }
        
        if errores:
            response_data['errores_detalle'] = errores
        
        return JsonResponse(response_data)
        
    except DispositivoMovil.DoesNotExist:
        print(f"❌ ERROR: Dispositivo no encontrado con token: {token}")
        return JsonResponse({
            'success': False,
            'error': 'Token inválido o dispositivo inactivo'
        }, status=401)
    except Exception as e:
        print(f"❌ ERROR INESPERADO: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': f'Error interno del servidor: {str(e)}'
        }, status=500)

# API para obtener lecturas pendientes (para sincronización offline)
@require_GET
def api_obtener_lecturas_pendientes(request, alias, token):  # <-- Añadido 'alias'
    try:
        # Verificar que el dispositivo pertenece a la empresa del alias
        dispositivo = DispositivoMovil.objects.get(
            token_acceso=token, 
            activo=True,
            empresa__slug=alias  # <-- Verificar empresa
        )
        
        lecturas_pendientes = LecturaMovil.objects.filter(
            dispositivo=dispositivo,
            estado='pendiente'
        ).select_related('cliente')
        
        lecturas_data = []
        for lectura in lecturas_pendientes:
            lecturas_data.append({
                'id': lectura.id,
                'cliente_id': lectura.cliente.id,
                'cliente_codigo': lectura.cliente.codigo_cliente,
                'cliente_nombre': lectura.cliente.nombre,
                'lectura_actual': float(lectura.lectura_actual),
                'lectura_anterior': float(lectura.lectura_anterior) if lectura.lectura_anterior else 0,
                'consumo': float(lectura.consumo) if lectura.consumo else 0,
                'fecha_lectura': lectura.fecha_lectura.isoformat() if lectura.fecha_lectura else lectura.fecha_registro_servidor.isoformat(),
                'latitud': float(lectura.latitud) if lectura.latitud else None,
                'longitud': float(lectura.longitud) if lectura.longitud else None,
                'observaciones': lectura.observaciones
            })
        
        return JsonResponse({
            'success': True,
            'pendientes': len(lecturas_data),
            'lecturas': lecturas_data
        })
        
    except DispositivoMovil.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Token inválido, dispositivo inactivo o no pertenece a esta empresa'
        }, status=401)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

# API para autenticar dispositivo móvil (esta ya la tienes corregida)
@csrf_exempt
@require_POST
def api_autenticar_dispositivo(request, alias):  # <-- Ya tiene 'alias'
    try:
        print(f"DEBUG: Autenticando dispositivo para empresa: {alias}")
        data = json.loads(request.body)
        print(f"DEBUG: Datos recibidos: {data}")
        
        empresa_slug = alias
        identificador = data.get('identificador')
        nombre_dispositivo = data.get('nombre_dispositivo', 'Dispositivo Móvil')
        
        print(f"DEBUG: Identificador recibido: '{identificador}' (tipo: {type(identificador)})")
        
        if not identificador:
            return JsonResponse({
                'success': False,
                'error': 'El identificador es requerido'
            }, status=400)
        
        # Buscar empresa
        try:
            empresa = Empresa.objects.get(slug=empresa_slug)
        except Empresa.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Empresa no encontrada'
            }, status=404)
        
        print(f"DEBUG: Empresa encontrada: {empresa.nombre}")
        
        # Buscar o crear dispositivo
        dispositivo, created = DispositivoMovil.objects.get_or_create(
            empresa=empresa,
            identificador=identificador,
            defaults={
                'nombre_dispositivo': nombre_dispositivo,
                'token_acceso': uuid.uuid4(),
                'activo': True
            }
        )
        
        if not created:
            dispositivo.token_acceso = uuid.uuid4()
            dispositivo.ultima_conexion = timezone.now()
            dispositivo.activo = True
            dispositivo.save()
        
        print(f"DEBUG: Dispositivo {'creado' if created else 'actualizado'}: {dispositivo.id}")
        
        return JsonResponse({
            'success': True,
            'token': str(dispositivo.token_acceso),
            'empresa': {
                'id': empresa.id,
                'nombre': empresa.nombre,
                'slug': empresa.slug
            },
            'dispositivo': {
                'id': dispositivo.id,
                'nombre': dispositivo.nombre_dispositivo
            }
        })
        
    except Exception as e:
        print(f"DEBUG: Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)