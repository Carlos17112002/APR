# apps_moviles/api_views.py (al inicio del archivo)
import json
import socket
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from empresas.models import Empresa
from clientes.models import Cliente
from lecturas.models import LecturaMovil

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
    return JsonResponse({
        'status': 'success',
        'message': 'API funcionando correctamente',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0'
    })

@csrf_exempt
def verificar_conexion(request):
    """Endpoint simple para verificar que la API está funcionando"""
    base_url = obtener_url_base(request)
    
    return JsonResponse({
        'success': True,
        'message': 'API funcionando correctamente',
        'timestamp': timezone.now().isoformat(),
        'version': '1.0.0',
        'server_url': base_url,
        'endpoints': {
            'config': f"{base_url}/apps/api/config/",
            'verify': f"{base_url}/apps/api/verificar/",
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