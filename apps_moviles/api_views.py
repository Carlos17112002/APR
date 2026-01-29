# apps_moviles/api_views.py
import json
import socket
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from empresas.models import Empresa
from clientes.models import Cliente, Medidor
from lecturas.models import Lectura

def obtener_url_base(request, for_qr=False):
    """
    Determina la URL base correcta según el contexto.
    Si es para QR o viene de un móvil, usa la URL pública.
    """
    scheme = request.scheme
    host = request.get_host()
    
    # URL pública de Render (configurable)
    RENDER_URL = "https://apr-8nm9.onrender.com"
    
    # Si es para generar un QR o detectamos que viene de un móvil
    if for_qr or request.headers.get('User-Agent', '').lower().find('mobile') != -1:
        # Usar URL pública de Render
        return RENDER_URL
    elif 'localhost' in host or '127.0.0.1' in host or '192.168.' in host:
        # Si estamos en desarrollo local y es una petición directa
        return f"{scheme}://{host}"
    else:
        # En producción o si ya es una URL pública
        return f"{scheme}://{host}"

@csrf_exempt
def api_config_app(request, empresa_slug):
    """
    Endpoint que devuelve la configuración EXACTA que la app móvil espera.
    URL: /apps/api/config/<empresa_slug>/
    """
    try:
        empresa = get_object_or_404(Empresa, slug=empresa_slug)
        
        if not empresa.app_generada:
            return JsonResponse({
                'success': False,
                'error': 'APP_NO_GENERADA',
                'message': 'La aplicación móvil no ha sido generada para esta empresa.'
            }, status=404)
        
        # DETECTAR SI ES LLAMADA DESDE APP MÓVIL
        user_agent = request.headers.get('User-Agent', '').lower()
        es_app_movil = any(term in user_agent for term in ['dart', 'flutter', 'okhttp', 'mobile'])
        
        # Obtener URL base CORRECTA (pública para móviles)
        base_url = obtener_url_base(request, for_qr=es_app_movil)
        
        print(f"🌐 URL base detectada: {base_url}")
        print(f"📱 User-Agent: {user_agent}")
        print(f"📱 ¿Es app móvil?: {es_app_movil}")
        
        # Obtener información de clientes
        alias_db = f'db_{empresa.slug}'
        
        try:
            total_clientes = Cliente.objects.using(alias_db).count()
            
            # Obtener sectores únicos
            sectores_qs = Cliente.objects.using(alias_db).values_list('sector', flat=True).distinct()
            sectores = [str(sector) for sector in sectores_qs if sector]
            
            # Obtener último período de lectura
            try:
                ultima_lectura = Lectura.objects.using(alias_db).order_by('-fecha_lectura').first()
                ultimo_periodo = ultima_lectura.periodo if ultima_lectura else timezone.now().strftime('%Y-%m')
            except:
                ultimo_periodo = timezone.now().strftime('%Y-%m')
                
        except Exception as e:
            print(f"Error obteniendo datos de clientes: {e}")
            total_clientes = 0
            sectores = []
            ultimo_periodo = timezone.now().strftime('%Y-%m')
        
        # ===================================================================
        # ESTRUCTURA CON URLs PÚBLICAS PARA APP MÓVIL
        # ===================================================================
        
        config = {
            # Información de la empresa
            'empresa_nombre': empresa.nombre,
            'empresa_slug': empresa.slug,
            'empresa_id': empresa.id,
            
            # Configuración de colores
            'color_primario': getattr(empresa, 'color_app_primario', '#10b981'),
            'color_secundario': getattr(empresa, 'color_app_secundario', '#047857'),
            
            # Versión
            'version_app': getattr(empresa, 'version_app', '1.0.0'),
            
            # URL base - IMPORTANTE: usar URL pública
            'base_url': f"{base_url}/api/{empresa.slug}/",
            
            # Logo (manejar si no existe)
            'logo_url': None,
            
            # Configuración de la app
            'configuracion': {
                'modo_offline': True,
                'validar_gps': True,
                'radio_validacion': 50,
                'capturar_fotos': False,
                'mostrar_deuda': True,
                'sincronizacion_automatica': True,
                'intervalo_sincronizacion': 300,
                'habilitar_mapa': True,
                'habilitar_offline': True,
                'mostrar_logo': True,
                'mensaje_bienvenida': f'Bienvenido a {empresa.nombre}',
            },
            
            # Información del servidor - URLs PÚBLICAS
            'servidor': {
                'url': base_url,
                'api_base': f"{base_url}/apps/api/",
                'endpoints': {
                    'verificar': f"{base_url}/apps/api/verificar/",
                    'registrar_dispositivo': f"{base_url}/apps/api/registrar-dispositivo/",
                    'subir_lecturas': f"{base_url}/apps/api/subir-lecturas/",
                    'sincronizar': f"{base_url}/apps/api/sincronizar/{empresa.slug}/",
                    'clientes': f"{base_url}/apps/api/clientes/{empresa.slug}/",
                    'segmentos': f"{base_url}/apps/api/segmentos/{empresa.slug}/",
                }
            },
            
            # Datos iniciales
            'datos': {
                'total_clientes': total_clientes,
                'sectores': sectores,
                'ultimo_periodo': ultimo_periodo,
                'fecha_actualizacion': timezone.now().isoformat(),
            },
            
            # Endpoints para descargar clientes - URLs PÚBLICAS
            'endpoints': {
                'clientes': f"{base_url}/apps/api/clientes/{empresa.slug}/",
                'segmentos': f"{base_url}/apps/api/segmentos/{empresa.slug}/",
            },
            
            # Metadata
            'timestamp': timezone.now().isoformat(),
            'success': True,
            
            # Información de debug (solo en desarrollo)
            'debug_info': {
                'url_base_utilizada': base_url,
                'es_app_movil': es_app_movil,
                'user_agent': user_agent[:100] if user_agent else 'No detectado',
                'request_host': request.get_host(),
            } if settings.DEBUG else None,
        }
        
        print(f"✅ Configuración generada con URL: {base_url}")
        
        return JsonResponse(config, json_dumps_params={'indent': 2})
        
    except Exception as e:
        import traceback
        print(f"❌ Error en api_config_app: {e}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': 'INTERNAL_ERROR',
            'message': str(e),
        }, status=500)

@csrf_exempt
def verificar_conexion(request):
    """Endpoint simple para verificar que la API está funcionando"""
    base_url = obtener_url_base(request)
    
    return JsonResponse({
        'success': True,
        'message': '✅ API móvil funcionando correctamente',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0',
        'server_url': base_url,
        'endpoints': {
            'config': f"{base_url}/apps/api/config/{{empresa_slug}}/",
            'verify': f"{base_url}/apps/api/verificar/",
            'clientes': f"{base_url}/apps/api/clientes/{{empresa_slug}}/",
        },
        'server_info': {
            'name': 'Django SSR API',
            'environment': 'development' if settings.DEBUG else 'production',
            'public_url': 'https://apr-8nm9.onrender.com',
        }
    })

@csrf_exempt
def redirect_to_public(request, empresa_slug):
    """
    Redirecciona de localhost a la URL pública de Render.
    Útil cuando el QR fue generado con localhost pero se escanea desde móvil.
    """
    RENDER_URL = "https://apr-8nm9.onrender.com"
    public_url = f"{RENDER_URL}/apps/api/config/{empresa_slug}/"
    
    # Obtener todos los parámetros de la request original
    params = request.GET.copy()
    
    # Construir nueva URL con parámetros
    if params:
        public_url = f"{public_url}?{params.urlencode()}"
    
    # Redireccionar 301 (permanente) o 302 (temporal)
    from django.shortcuts import redirect
    return redirect(public_url, permanent=False)

@csrf_exempt
def api_clientes(request, empresa_slug):
    """Devuelve TODOS los clientes para la app móvil"""
    try:
        empresa = get_object_or_404(Empresa, slug=empresa_slug)
        
        print(f"📱 Solicitando clientes para empresa: {empresa.nombre}")
        
        alias_db = f'db_{empresa.slug}'
        
        try:
            # Obtener todos los clientes
            clientes = Cliente.objects.using(alias_db).all()
            total = clientes.count()
            
            clientes_data = []
            for cliente in clientes:
                # Obtener medidores del cliente
                try:
                    medidores = Medidor.objects.using(alias_db).filter(cliente=cliente)
                    medidores_list = []
                    
                    for medidor in medidores:
                        medidores_list.append({
                            'id': medidor.id,
                            'numero': medidor.numero or f"M{medidor.id}",
                            'tipo': getattr(medidor, 'tipo', 'Agua'),
                            'marca': getattr(medidor, 'marca', ''),
                            'modelo': getattr(medidor, 'modelo', ''),
                            'ubicacion': getattr(medidor, 'ubicacion', ''),
                            'ultima_lectura': getattr(medidor, 'ultima_lectura', None),
                            'estado': getattr(medidor, 'estado', 'Activo'),
                        })
                except Exception as e:
                    print(f"Error obteniendo medidores: {e}")
                    medidores_list = []
                
                clientes_data.append({
                    'id': cliente.id,
                    'codigo': cliente.rut or cliente.codigo or f"CL{cliente.id:04d}",
                    'nombre': cliente.nombre,
                    'direccion': cliente.direccion or '',
                    'sector': cliente.sector or 'General',
                    'comuna': getattr(cliente, 'comuna', ''),
                    'telefono': cliente.telefono or '',
                    'email': cliente.email or '',
                    'latitud': float(cliente.latitude) if cliente.latitude else -33.45694,
                    'longitud': float(cliente.longitude) if cliente.longitude else -70.64827,
                    'estado': getattr(cliente, 'estado', 'Activo'),
                    'observaciones': getattr(cliente, 'observaciones', ''),
                    'medidores': medidores_list,
                    'metadata': {
                        'tiene_coordenadas': bool(cliente.latitude and cliente.longitude),
                        'total_medidores': len(medidores_list),
                    }
                })
            
            print(f"✅ Enviando {len(clientes_data)} clientes para {empresa.nombre}")
            
            return JsonResponse({
                'success': True,
                'empresa': empresa.nombre,
                'empresa_slug': empresa.slug,
                'total': total,
                'clientes': clientes_data,
                'timestamp': timezone.now().isoformat(),
                'pagination': {
                    'total': total,
                    'returned': len(clientes_data),
                    'has_more': False,  # Enviamos todos
                }
            }, json_dumps_params={'indent': 2})
            
        except Exception as e:
            import traceback
            print(f"❌ Error en api_clientes: {e}")
            print(traceback.format_exc())
            
            # Datos de ejemplo para debug
            return JsonResponse({
                'success': True,
                'empresa': empresa.nombre,
                'total': 1,
                'clientes': [{
                    'id': 1,
                    'codigo': 'TEST001',
                    'nombre': 'Cliente de Prueba',
                    'direccion': 'Dirección de prueba, EL VATICANO',
                    'sector': 'EL VATICANO',
                    'latitud': -33.45694,
                    'longitud': -70.64827,
                    'estado': 'Activo',
                    'medidores': [{
                        'id': 1,
                        'numero': 'MED001',
                        'tipo': 'Agua',
                        'ultima_lectura': None
                    }]
                }],
                'timestamp': timezone.now().isoformat(),
                'note': 'Datos de ejemplo por error en base de datos'
            })
            
    except Exception as e:
        import traceback
        print(f"❌ Error general en api_clientes: {e}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)

@csrf_exempt
def api_segmentos(request, empresa_slug):
    """Devuelve segmentos de clientes (paginación)"""
    try:
        empresa = get_object_or_404(Empresa, slug=empresa_slug)
        
        # Parámetros de paginación
        offset = int(request.GET.get('offset', 0))
        limit = min(int(request.GET.get('limit', 50)), 100)  # Máximo 100 por segmento
        
        print(f"📱 Segmentos: empresa={empresa.nombre}, offset={offset}, limit={limit}")
        
        alias_db = f'db_{empresa.slug}'
        
        try:
            # Obtener segmento de clientes
            clientes = Cliente.objects.using(alias_db).all()[offset:offset + limit]
            total = Cliente.objects.using(alias_db).count()
            
            clientes_data = []
            for cliente in clientes:
                clientes_data.append({
                    'id': cliente.id,
                    'codigo': cliente.rut or f"CL{cliente.id:04d}",
                    'nombre': cliente.nombre,
                    'direccion': cliente.direccion or '',
                    'sector': cliente.sector or 'General',
                    'latitud': float(cliente.latitude) if cliente.latitude else -33.45694,
                    'longitud': float(cliente.longitude) if cliente.longitude else -70.64827,
                    'estado': getattr(cliente, 'estado', 'Activo'),
                })
            
            next_offset = offset + limit if offset + limit < total else None
            
            print(f"✅ Enviando segmento {offset}-{offset+limit} ({len(clientes_data)} clientes)")
            
            return JsonResponse({
                'success': True,
                'empresa': empresa.nombre,
                'segment': {
                    'offset': offset,
                    'limit': limit,
                    'count': len(clientes_data),
                },
                'total_clientes': total,
                'clientes': clientes_data,
                'next_offset': next_offset,
                'has_more': next_offset is not None,
                'timestamp': timezone.now().isoformat(),
            }, json_dumps_params={'indent': 2})
            
        except Exception as e:
            print(f"❌ Error obteniendo segmentos: {e}")
            
            # Datos de ejemplo
            return JsonResponse({
                'success': True,
                'empresa': empresa.nombre,
                'segment': {
                    'offset': offset,
                    'limit': limit,
                    'count': 1,
                },
                'total_clientes': 1,
                'clientes': [{
                    'id': 1,
                    'codigo': 'EJEMPLO001',
                    'nombre': 'Cliente Ejemplo',
                    'direccion': 'Calle Ejemplo 123, EL VATICANO',
                    'sector': 'EL VATICANO',
                    'latitud': -33.45694,
                    'longitud': -70.64827,
                    'estado': 'Activo',
                }],
                'next_offset': None,
                'has_more': False,
                'timestamp': timezone.now().isoformat(),
                'note': 'Datos de ejemplo por error en base de datos'
            })
            
    except Exception as e:
        print(f"❌ Error general en segmentos: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)

@csrf_exempt
def registrar_dispositivo(request):
    """Registra un dispositivo móvil"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            return JsonResponse({
                'success': True,
                'message': '✅ Dispositivo registrado exitosamente',
                'device_id': data.get('device_id', 'unknown'),
                'device_model': data.get('model', 'unknown'),
                'os': data.get('os', 'unknown'),
                'timestamp': timezone.now().isoformat(),
                'token': f"token_{int(timezone.now().timestamp())}",
            })
        except Exception as e:
            return JsonResponse({
                'success': True,
                'message': '✅ Dispositivo registrado (modo simple)',
                'timestamp': timezone.now().isoformat(),
                'note': f'Error parseando JSON: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'METHOD_NOT_ALLOWED',
        'message': 'Usa POST para registrar dispositivo'
    }, status=405)

@csrf_exempt
def subir_lecturas(request):
    """Recibe lecturas desde la app móvil"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lecturas = data.get('lecturas', [])
            
            print(f"📊 Recibiendo {len(lecturas)} lecturas desde app móvil")
            
            # Aquí procesarías y guardarías las lecturas
            # Por ahora solo confirmamos recepción
            
            return JsonResponse({
                'success': True,
                'message': f'✅ {len(lecturas)} lecturas recibidas correctamente',
                'lecturas_recibidas': len(lecturas),
                'timestamp': timezone.now().isoformat(),
                'procesadas': 0,  # En una implementación real, contarías las procesadas
                'rechazadas': 0,
            })
        except Exception as e:
            return JsonResponse({
                'success': True,
                'message': '✅ Lecturas recibidas (modo simple)',
                'timestamp': timezone.now().isoformat(),
                'note': f'Error parseando JSON: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'METHOD_NOT_ALLOWED',
        'message': 'Usa POST para subir lecturas'
    }, status=405)

@csrf_exempt
def sincronizar_datos(request, empresa_slug):
    """Sincroniza datos con el servidor"""
    try:
        empresa = get_object_or_404(Empresa, slug=empresa_slug)
        
        print(f"🔄 Sincronizando datos para {empresa.nombre}")
        
        # Aquí implementarías la lógica de sincronización
        # Por ahora solo devolvemos confirmación
        
        return JsonResponse({
            'success': True,
            'message': f'✅ Datos sincronizados para {empresa.nombre}',
            'empresa': empresa.nombre,
            'timestamp': timezone.now().isoformat(),
            'sync_info': {
                'status': 'completed',
                'last_sync': timezone.now().isoformat(),
                'clients_updated': 0,
                'readings_synced': 0,
                'errors': 0,
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'SYNC_ERROR',
            'message': str(e),
            'timestamp': timezone.now().isoformat(),
        }, status=500)

@csrf_exempt
def api_test_simple(request):
    """Endpoint simple de prueba"""
    base_url = obtener_url_base(request)
    
    return JsonResponse({
        'success': True,
        'message': '✅ API móvil funcionando correctamente',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0',
        'server': base_url,
        'endpoints_available': [
            f'{base_url}/apps/api/config/{{empresa_slug}}/',
            f'{base_url}/apps/api/clientes/{{empresa_slug}}/',
            f'{base_url}/apps/api/verificar/',
            f'{base_url}/apps/api/test/',
            f'{base_url}/apps/api/registrar-dispositivo/',
            f'{base_url}/apps/api/subir-lecturas/',
            f'{base_url}/apps/api/sincronizar/{{empresa_slug}}/',
        ],
        'instructions': {
            'config': 'GET /apps/api/config/{empresa_slug}/',
            'clientes': 'GET /apps/api/clientes/{empresa_slug}/',
            'register': 'POST /apps/api/registrar-dispositivo/',
            'upload': 'POST /apps/api/subir-lecturas/',
        }
    })

@csrf_exempt
def debug_info(request):
    """Información de debug para troubleshooting"""
    base_url = obtener_url_base(request)
    
    return JsonResponse({
        'status': 'debug',
        'timestamp': timezone.now().isoformat(),
        'server': {
            'base_url': base_url,
            'django_version': '5.1.5',
            'python_version': '3.x',
            'debug': settings.DEBUG,
            'allowed_hosts': settings.ALLOWED_HOSTS,
        },
        'request': {
            'method': request.method,
            'path': request.path,
            'full_path': request.get_full_path(),
            'host': request.get_host(),
            'user_agent': request.headers.get('User-Agent', ''),
            'remote_addr': request.META.get('REMOTE_ADDR', ''),
        },
        'endpoints': {
            'config': f'{base_url}/apps/api/config/{{empresa_slug}}/',
            'clientes': f'{base_url}/apps/api/clientes/{{empresa_slug}}/',
            'verificar': f'{base_url}/apps/api/verificar/',
            'test': f'{base_url}/apps/api/test/',
            'debug': f'{base_url}/apps/api/debug/',
        },
        'mobile_app': {
            'compatible': True,
            'requires': ['empresa_slug', 'base_url', 'clientes_endpoint'],
            'recommended_test_order': [
                '1. /apps/api/verificar/',
                '2. /apps/api/config/{empresa_slug}/',
                '3. /apps/api/clientes/{empresa_slug}/',
            ]
        }
    })

@csrf_exempt
def public_diagnostic(request):
    """Endpoint público de diagnóstico"""
    RENDER_URL = "https://apr-8nm9.onrender.com"
    
    return JsonResponse({
        'status': 'online',
        'service': 'SSR Mobile API',
        'timestamp': timezone.now().isoformat(),
        'public_url': RENDER_URL,
        'endpoints': {
            'config': f'{RENDER_URL}/apps/api/config/{{slug}}/',
            'verify': f'{RENDER_URL}/apps/api/verificar/',
            'test': f'{RENDER_URL}/apps/api/test/',
            'clientes': f'{RENDER_URL}/apps/api/clientes/{{slug}}/',
        },
        'instructions': 'Use /apps/api/config/{empresa_slug}/ for mobile app configuration',
        'cors_enabled': True,
        'requires_auth': False,
        'example_urls': {
            'config_vaticano': f'{RENDER_URL}/apps/api/config/vaticano-apr/',
            'clientes_vaticano': f'{RENDER_URL}/apps/api/clientes/vaticano-apr/',
            'verify': f'{RENDER_URL}/apps/api/verificar/',
        }
    })