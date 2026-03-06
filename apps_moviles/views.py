import os
import json
import qrcode
import hashlib
import time
import base64
import logging
import socket
from pathlib import Path
from io import BytesIO

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt

from empresas.models import Empresa
from lecturas.models import DispositivoMovil, ConfigAppMovil, LecturaMovil

# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_local_ip():
    """Obtiene la IP local de la máquina para desarrollo."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_base_url(request):
    """Retorna la URL base del sitio según el entorno."""
    if settings.DEBUG:
        # En desarrollo, usar IP local (ajusta si prefieres 10.0.2.2 para emulador)
        local_ip = get_local_ip()
        return f"http://{local_ip}:8000"
    else:
        # En producción, usar el dominio real
        return f"{request.scheme}://{request.get_host()}"

def _qr_a_base64(qr_img):
    """Convierte QR a base64"""
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"

def _guardar_qr_archivo(slug, qr_img):
    """Guarda el QR en archivo"""
    static_dir = Path(settings.BASE_DIR) / 'static'
    static_dir.mkdir(exist_ok=True, parents=True)
    apps_qr_dir = static_dir / 'apps_qr'
    apps_qr_dir.mkdir(exist_ok=True, parents=True)
    qr_path = apps_qr_dir / f'{slug}.png'
    qr_img.save(qr_path)
    return qr_path

def incrementar_version(version):
    """Incrementa la versión"""
    if not version:
        return '1.0.0'
    parts = version.split('.')
    if len(parts) == 3:
        try:
            minor = int(parts[2]) + 1
            return f"{parts[0]}.{parts[1]}.{minor}"
        except:
            return version
    elif len(parts) == 2:
        return f"{parts[0]}.{parts[1]}.1"
    else:
        return '1.0.1'

# ============================================================================
# ESTRATEGIA QR UNIVERSAL
# ============================================================================

def _crear_qr_unico(request, empresa, total_clientes):
    """Crea QR con token único usando la URL base adecuada."""
    base_url = get_base_url(request)
    token_unico = hashlib.sha256(
        f"{empresa.slug}-UNIVERSAL-{time.time()}".encode()
    ).hexdigest()[:32]
    
    request.session[f'qr_token_{empresa.slug}'] = token_unico
    request.session[f'empresa_token_{token_unico}'] = {
        'slug': empresa.slug,
        'timestamp': time.time(),
        'total_clientes': total_clientes,
    }
    
    url_publica = f'{base_url}/apps/api/config/{empresa.slug}/?token={token_unico}'
    
    qr_data = {
        't': 'universal',
        'e': empresa.slug,
        'tk': token_unico,
        'u': url_publica,
        'cn': total_clientes,
        'v': '1.0.0',
        'empresa_nombre': empresa.nombre,
        'color_primario': empresa.color_app_primario or '#10b981',
        'color_secundario': empresa.color_app_secundario or '#047857',
        'base_url': f"{base_url}/api/{empresa.slug}/",
        'config_url': url_publica,
        'servidor_url': base_url,
        'is_public_url': True,
    }
    
    print(f"🔗 QR generado con URL pública: {url_publica}")
    return json.dumps(qr_data, separators=(',', ':'), ensure_ascii=False)

def _ver_qr_universal(request, empresa, total_clientes, total_sectores):
    """Muestra QR usando la estrategia universal."""
    base_url = get_base_url(request)
    token_unico = hashlib.sha256(
        f"{empresa.slug}-UNIVERSAL-{time.time()}".encode()
    ).hexdigest()[:32]
    
    request.session[f'qr_token_{empresa.slug}'] = token_unico
    request.session[f'empresa_token_{token_unico}'] = {
        'slug': empresa.slug,
        'timestamp': time.time(),
        'total_clientes': total_clientes,
        'total_sectores': total_sectores,
    }
    
    qr_info = {
        't': 'universal',
        'e': empresa.slug,
        'tk': token_unico,
        'u': f'{base_url}/apps/api/config/{empresa.slug}/?token={token_unico}',
        'cn': str(total_clientes),
        'v': '1',
        'servidor_url': base_url,
    }
    
    qr_data = json.dumps(qr_info, separators=(',', ':'), ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"EMPRESA: {empresa.nombre}")
    print(f"Estrategia: UNIVERSAL")
    print(f"Token: {token_unico}")
    print(f"Tamaño QR: {len(qr_data)} caracteres")
    print(f"Total clientes: {total_clientes}")
    print(f"Total sectores: {total_sectores}")
    print(f"QR Data: {qr_data}")
    print(f"{'='*60}")
    
    try:
        config_app = ConfigAppMovil.objects.get(empresa=empresa)
    except ConfigAppMovil.DoesNotExist:
        config_app = None
    
    json_config = {
        'qr_info': qr_info,
        'empresa': {
            'nombre': empresa.nombre,
            'slug': empresa.slug,
            'version_app': empresa.version_app or '1.0.0',
            'color_primario': empresa.color_app_primario or '#1E40AF',
            'color_secundario': empresa.color_app_secundario or '#DC2626',
            'url_servidor': empresa.url_servidor or '',
        },
        'config_app': {
            'habilitar_mapa': config_app.habilitar_mapa if config_app else True,
            'habilitar_offline': config_app.habilitar_offline if config_app else True,
            'validar_gps': config_app.validar_gps if config_app else True,
            'sincronizacion_auto': config_app.sincronizacion_auto if config_app else True,
            'mostrar_logo': config_app.mostrar_logo if config_app else True,
            'intervalo_sincronizacion': config_app.intervalo_sincronizacion if config_app else 5,
            'mensaje_bienvenida': config_app.mensaje_bienvenida if config_app else f'Bienvenido a {empresa.nombre}',
        },
        'estadisticas': {
            'total_clientes': total_clientes,
            'total_sectores': total_sectores,
        }
    }
    
    qr_img = qrcode.make(qr_data)
    context = {
        'empresa': empresa,
        'qr_url': _qr_a_base64(qr_img),
        'qr_path': f'/static/apps_qr/{empresa.slug}.png',
        'api_url': f'{base_url}/apps/api/config/{empresa.slug}/?token={token_unico}',
        'qr_data_preview': qr_data[:100] + '...',
        'qr_data_length': len(qr_data),
        'total_clientes': total_clientes,
        'total_sectores': total_sectores,
        'page_title': f'QR App - {empresa.nombre}',
        'usando_token': True,
        'token': token_unico,
        'mensaje_especial': f'✅ Configuración universal aplicada ({total_clientes} clientes)',
        'json_config': json.dumps(json_config, indent=2, ensure_ascii=False),
    }
    
    _guardar_qr_archivo(empresa.slug, qr_img)
    return render(request, 'apps_moviles/ver_qr.html', context)

# ============================================================================
# VISTAS PRINCIPALES
# ============================================================================

@login_required
def panel_apps_moviles(request):
    """Panel principal de gestión de apps móviles"""
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard_admin_ssr')
    
    empresas = Empresa.objects.all().order_by('-fecha_creacion')
    total_empresas = empresas.count()
    empresas_con_app = empresas.filter(app_generada=True).count()
    
    stats = {
        'total_empresas': total_empresas,
        'empresas_con_app': empresas_con_app,
        'empresas_sin_app': total_empresas - empresas_con_app,
        'total_dispositivos': DispositivoMovil.objects.count(),
        'dispositivos_activos': DispositivoMovil.objects.filter(activo=True).count(),
        'lecturas_hoy': LecturaMovil.objects.filter(
            fecha_sincronizacion__date=timezone.now().date()
        ).count(),
        'lecturas_pendientes': LecturaMovil.objects.filter(estado='pendiente').count(),
    }
    
    context = {
        'empresas': empresas,
        'stats': stats,
        'page_title': 'Panel Apps Móviles',
    }
    return render(request, 'apps_moviles/panel.html', context)

@login_required
def detalle_app_empresa(request, empresa_slug):
    """Detalle de la app móvil de una empresa"""
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard_admin_ssr')
    
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    config_app, _ = ConfigAppMovil.objects.get_or_create(empresa=empresa)
    dispositivos = empresa.dispositivos.all().order_by('-ultima_conexion')
    
    lecturas_hoy = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_sincronizacion__date=timezone.now().date()
    ).count()
    
    lecturas_mes = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_sincronizacion__month=timezone.now().month,
        fecha_sincronizacion__year=timezone.now().year
    ).count()
    
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    total_clientes_real = 0
    total_sectores_real = 0
    try:
        total_clientes_real = Cliente.objects.using(alias_db).count()
        sectores_distintos = Cliente.objects.using(alias_db).values_list('sector', flat=True).distinct()
        total_sectores_real = len([s for s in sectores_distintos if s])
    except:
        pass
    
    context = {
        'empresa': empresa,
        'config_app': config_app,
        'dispositivos': dispositivos,
        'lecturas_hoy': lecturas_hoy,
        'lecturas_mes': lecturas_mes,
        'total_dispositivos': dispositivos.count(),
        'dispositivos_activos': dispositivos.filter(activo=True).count(),
        'total_clientes_real': total_clientes_real,
        'total_sectores_real': total_sectores_real,
        'page_title': f'App Móvil - {empresa.nombre}',
    }
    return render(request, 'apps_moviles/detalle_empresa.html', context)

@login_required
def generar_app_empresa(request, empresa_slug):
    """Genera/actualiza la app móvil para una empresa"""
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para esta acción')
        return redirect('dashboard_admin_ssr')
    
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    
    if request.method == 'POST':
        try:
            # Actualizar configuración básica
            empresa.color_app_primario = request.POST.get('color_primario', empresa.color_app_primario)
            empresa.color_app_secundario = request.POST.get('color_secundario', empresa.color_app_secundario)
            empresa.url_servidor = request.POST.get('url_servidor', empresa.url_servidor)
            
            # Actualizar configuración de app
            config_app, _ = ConfigAppMovil.objects.get_or_create(empresa=empresa)
            config_app.habilitar_mapa = 'habilitar_mapa' in request.POST
            config_app.habilitar_offline = 'habilitar_offline' in request.POST
            config_app.validar_gps = 'validar_gps' in request.POST
            config_app.sincronizacion_auto = 'sincronizacion_auto' in request.POST
            config_app.mostrar_logo = 'mostrar_logo' in request.POST
            
            if 'mensaje_bienvenida' in request.POST:
                config_app.mensaje_bienvenida = request.POST['mensaje_bienvenida']
            if 'intervalo_sincronizacion' in request.POST:
                try:
                    config_app.intervalo_sincronizacion = int(request.POST['intervalo_sincronizacion'])
                except:
                    pass
            config_app.save()
            
            # Generar configuración JSON
            config_json = empresa.generar_config_app()
            config_json.update({
                'app_name': f'SSR {empresa.nombre}',
                'empresa_nombre': empresa.nombre,
                'empresa_slug': empresa.slug,
                'version': empresa.version_app,
                'primary_color': empresa.color_app_primario,
                'secondary_color': empresa.color_app_secundario,
                'base_url': f'{empresa.url_servidor}/api/{empresa.slug}/',
                'api_key': empresa.api_key_app,
                'habilitar_mapa': config_app.habilitar_mapa,
                'habilitar_offline': config_app.habilitar_offline,
                'validar_gps': config_app.validar_gps,
                'sincronizacion_auto': config_app.sincronizacion_auto,
                'mostrar_logo': config_app.mostrar_logo,
                'intervalo_sincronizacion': config_app.intervalo_sincronizacion,
                'mensaje_bienvenida': config_app.mensaje_bienvenida,
                'clientes': config_json.get('clientes', []),
                'sectores': config_json.get('sectores', []),
            })
            
            # Guardar archivo de configuración
            static_dir = Path(settings.BASE_DIR) / 'static'
            static_dir.mkdir(exist_ok=True, parents=True)
            apps_config_dir = static_dir / 'apps_config'
            apps_config_dir.mkdir(exist_ok=True, parents=True)
            config_file = apps_config_dir / f'{empresa.slug}_config.json'
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_json, f, indent=2, ensure_ascii=False)
            
            # Obtener total de clientes
            from clientes.models import Cliente
            alias_db = f'db_{empresa.slug}'
            try:
                total_clientes = Cliente.objects.using(alias_db).count()
            except:
                total_clientes = 0
            
            # Generar QR
            qr_data = _crear_qr_unico(request, empresa, total_clientes)
            apps_qr_dir = static_dir / 'apps_qr'
            apps_qr_dir.mkdir(exist_ok=True, parents=True)
            qr_img = qrcode.make(qr_data)
            qr_path = apps_qr_dir / f'{empresa.slug}.png'
            qr_img.save(qr_path)
            
            # Actualizar empresa
            empresa.app_generada = True
            empresa.fecha_generacion_app = timezone.now()
            empresa.version_app = incrementar_version(empresa.version_app)
            empresa.save()
            
            messages.success(request, f'✅ App móvil generada para {empresa.nombre}')
            messages.info(request, f'Versión: {empresa.version_app}')
            messages.info(request, f'Clientes: {total_clientes}')
            messages.info(request, f'Tamaño QR: {len(qr_data)} caracteres')
            
            context = {
                'empresa': empresa,
                'qr_url': f'/static/apps_qr/{empresa.slug}.png',
                'qr_data_preview': qr_data[:100] + '...' if len(qr_data) > 100 else qr_data,
                'qr_data_length': len(qr_data),
                'total_clientes': total_clientes,
                'qr_strategy': 'universal',
            }
            return render(request, 'apps_moviles/ver_qr.html', context)
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
            import traceback
            traceback.print_exc()
            return redirect('generar_app_empresa', empresa_slug=empresa.slug)
    
    # GET: mostrar formulario
    config_app, _ = ConfigAppMovil.objects.get_or_create(empresa=empresa)
    context = {
        'empresa': empresa,
        'config_app': config_app,
        'page_title': f'Generar App - {empresa.nombre}',
    }
    return render(request, 'apps_moviles/generar_app.html', context)

@login_required
def ver_qr_app(request, empresa_slug):
    """Muestra el QR usando la estrategia única"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    if not empresa.app_generada:
        messages.error(request, 'La app no ha sido generada aún')
        return redirect('detalle_app_empresa', empresa_slug=empresa.slug)
    
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    total_clientes = 0
    total_sectores = 0
    try:
        total_clientes = Cliente.objects.using(alias_db).count()
        sectores_distintos = Cliente.objects.using(alias_db).values_list('sector', flat=True).distinct()
        total_sectores = len([s for s in sectores_distintos if s])
    except:
        pass
    
    return _ver_qr_universal(request, empresa, total_clientes, total_sectores)

# ============================================================================
# VISTAS ADICIONALES (dispositivos, QR manual, etc.)
# ============================================================================

@login_required
def gestionar_dispositivos(request, empresa_slug):
    """Gestiona dispositivos móviles de una empresa con usuario/contraseña"""
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permisos para esta acción')
        return redirect('dashboard_admin_ssr')
    
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    dispositivos = empresa.dispositivos.all().order_by('-ultima_conexion')
    total_dispositivos = dispositivos.count()
    dispositivos_activos = dispositivos.filter(activo=True).count()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'crear':
            usuario = request.POST.get('usuario', '').strip()
            password = request.POST.get('password', '').strip()
            nombre = request.POST.get('nombre', '').strip() or 'Dispositivo Móvil'
            
            if not usuario or not password:
                messages.error(request, 'Usuario y contraseña son obligatorios.')
                return redirect('apps_moviles:gestionar_dispositivos', empresa_slug=empresa.slug)
            
            if DispositivoMovil.objects.filter(empresa=empresa, usuario=usuario).exists():
                messages.error(request, f'Ya existe un dispositivo con el usuario "{usuario}" en esta empresa.')
                return redirect('apps_moviles:gestionar_dispositivos', empresa_slug=empresa.slug)
            
            dispositivo = DispositivoMovil(
                empresa=empresa,
                usuario=usuario,
                nombre_dispositivo=nombre,
                activo=True
            )
            dispositivo.set_password(password)
            dispositivo.save()
            
            messages.success(request, f'✅ Dispositivo creado: {dispositivo.nombre_dispositivo}')
            messages.info(request, f'Usuario: {usuario}')
            messages.info(request, f'Token interno: {dispositivo.token_acceso}')
            
        elif action == 'renovar_token':
            dispositivo_id = request.POST.get('dispositivo_id')
            dispositivo = get_object_or_404(DispositivoMovil, id=dispositivo_id, empresa=empresa)
            nuevo_token = dispositivo.renovar_token()
            messages.success(request, f'✅ Token renovado para {dispositivo.usuario}: {nuevo_token}')
            
        elif action == 'toggle_activo':
            dispositivo_id = request.POST.get('dispositivo_id')
            dispositivo = get_object_or_404(DispositivoMovil, id=dispositivo_id, empresa=empresa)
            dispositivo.activo = not dispositivo.activo
            dispositivo.save()
            estado = "activado" if dispositivo.activo else "desactivado"
            messages.success(request, f'✅ Dispositivo {dispositivo.usuario} {estado}')
        
        elif action == 'eliminar':
            dispositivo_id = request.POST.get('dispositivo_id')
            dispositivo = get_object_or_404(DispositivoMovil, id=dispositivo_id, empresa=empresa)
            nombre = dispositivo.nombre_dispositivo
            usuario = dispositivo.usuario
            dispositivo.delete()
            messages.success(request, f'✅ Dispositivo "{nombre}" (usuario: {usuario}) eliminado.')
        
        return redirect('apps_moviles:gestionar_dispositivos', empresa_slug=empresa.slug)
    
    context = {
        'empresa': empresa,
        'dispositivos': dispositivos,
        'total_dispositivos': total_dispositivos,
        'dispositivos_activos': dispositivos_activos,
        'page_title': f'Dispositivos - {empresa.nombre}',
    }
    return render(request, 'apps_moviles/gestionar_dispositivos.html', context)

@login_required
def generar_qr_manual(request, empresa_slug):
    """Genera manualmente el QR"""
    if not request.user.is_superuser:
        messages.error(request, 'No tienes permisos')
        return redirect('dashboard_admin_ssr')
    
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    try:
        total_clientes = Cliente.objects.using(alias_db).count()
    except:
        total_clientes = 0
    
    return _ver_qr_universal(request, empresa, total_clientes, 0)

def ver_config_app(request, empresa_slug):
    """Vista para ver la configuración JSON generada"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    config = empresa.generar_config_app()
    debug_info = {
        'empresa': empresa.nombre,
        'slug': empresa.slug,
        'total_clientes': len(config.get('clientes', [])),
        'sectores': config.get('sectores', []),
        'sectores_count': len(config.get('sectores', [])),
        'config_completa': config,
    }
    return JsonResponse(debug_info, safe=False)

@csrf_exempt
def debug_config_json(request, empresa_slug):
    """Vista para debug directo del JSON"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    config_json = empresa.generar_config_app()
    debug_info = {
        'empresa': {
            'nombre': empresa.nombre,
            'slug': empresa.slug,
            'id': empresa.id,
        },
        'config_json_keys': list(config_json.keys()),
        'clientes_count': len(config_json.get('clientes', [])),
        'sectores_count': len(config_json.get('sectores', [])),
        'sectores_list': config_json.get('sectores', []),
        'clientes_sample': config_json.get('clientes', [])[:3] if config_json.get('clientes') else [],
        'config_json_completo': config_json,
    }
    return JsonResponse(debug_info, safe=False, json_dumps_params={'indent': 2})

# ============================================================================
# APIS PARA LA APP MÓVIL (endpoints que escaneará el QR)
# ============================================================================

@csrf_exempt
def api_descargar_config(request, empresa_slug):
    """API para descargar configuración (endpoint del QR)"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    token = request.GET.get('token')
    session_data = request.session.get(f'empresa_token_{token}')
    
    if not token or not session_data or session_data.get('slug') != empresa.slug:
        return JsonResponse({'error': 'Token inválido o expirado'}, status=403)
    
    try:
        config_app = ConfigAppMovil.objects.get(empresa=empresa)
    except ConfigAppMovil.DoesNotExist:
        config_app = None
    
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    sectores = []
    try:
        sectores_distintos = Cliente.objects.using(alias_db).values_list('sector', flat=True).distinct()
        sectores = [s for s in sectores_distintos if s]
    except:
        pass
    
    config_json = {
        'app_name': f'SSR {empresa.nombre}',
        'empresa_nombre': empresa.nombre,
        'empresa_slug': empresa.slug,
        'version': empresa.version_app or '1.0.0',
        'primary_color': empresa.color_app_primario or '#1E40AF',
        'secondary_color': empresa.color_app_secundario or '#DC2626',
        'base_url': f'{empresa.url_servidor}/api/{empresa.slug}/',
        'api_key': empresa.api_key_app or '',
        'sectores': sectores,
        'total_clientes': session_data.get('total_clientes', 0),
        'descarga_segmentada': False,
        'endpoints': {
            'clientes': f'{request.scheme}://{request.get_host()}/apps/descargar-clientes/{empresa.slug}/?token={token}',
        },
    }
    
    if config_app:
        config_json.update({
            'habilitar_mapa': config_app.habilitar_mapa,
            'habilitar_offline': config_app.habilitar_offline,
            'validar_gps': config_app.validar_gps,
            'sincronizacion_auto': config_app.sincronizacion_auto,
            'mostrar_logo': config_app.mostrar_logo,
            'intervalo_sincronizacion': config_app.intervalo_sincronizacion,
            'mensaje_bienvenida': config_app.mensaje_bienvenida or f'Bienvenido a {empresa.nombre}',
        })
    
    return JsonResponse(config_json)

def descargar_config_grande(request, empresa_slug):
    """Alias para mantener compatibilidad con URLs existentes"""
    return api_descargar_config(request, empresa_slug)

@csrf_exempt
def descargar_clientes_completo(request, empresa_slug):
    """API para descargar clientes completos"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    token = request.GET.get('token')
    session_data = request.session.get(f'empresa_token_{token}')
    
    if not token or not session_data or session_data.get('slug') != empresa.slug:
        return JsonResponse({'error': 'Token inválido o expirado'}, status=403)
    
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    clientes = []
    try:
        clientes_qs = Cliente.objects.using(alias_db).all()
        for cliente in clientes_qs:
            clientes.append({
                'id': cliente.id,
                'codigo': cliente.rut or f"CL-{cliente.id:04d}",
                'nombre': cliente.nombre,
                'direccion': cliente.direccion or '',
                'sector': cliente.sector or 'Sin Sector',
                'numero_medidor': cliente.medidor or f"MED-{cliente.id:05d}",
                'latitud': cliente.latitude or 0.0,
                'longitud': cliente.longitude or 0.0,
                'estado': 'Activo',
            })
        response_data = {
            'empresa': empresa.nombre,
            'empresa_slug': empresa.slug,
            'total_clientes': len(clientes),
            'clientes': clientes,
            'timestamp': time.time(),
        }
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def descargar_clientes_segmento(request, empresa_slug):
    """API para descargar segmentos de clientes"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    token = request.GET.get('token')
    session_data = request.session.get(f'empresa_token_{token}')
    
    if not token or not session_data or session_data.get('slug') != empresa.slug:
        return JsonResponse({'error': 'Token inválido o expirado'}, status=403)
    
    from clientes.models import Cliente
    try:
        offset = int(request.GET.get('offset', 0))
        limit = int(request.GET.get('limit', 200))
    except:
        offset = 0
        limit = 200
    
    alias_db = f'db_{empresa.slug}'
    clientes = []
    try:
        total_clientes = Cliente.objects.using(alias_db).count()
        clientes_qs = Cliente.objects.using(alias_db).all()[offset:offset + limit]
        for cliente in clientes_qs:
            clientes.append({
                'id': cliente.id,
                'codigo': cliente.rut or f"CL-{cliente.id:04d}",
                'nombre': cliente.nombre,
                'direccion': cliente.direccion or '',
                'sector': cliente.sector or 'Sin Sector',
                'numero_medidor': cliente.medidor or f"MED-{cliente.id:05d}",
                'latitud': cliente.latitude or 0.0,
                'longitud': cliente.longitude or 0.0,
                'estado': 'Activo',
            })
        next_offset = offset + limit if offset + limit < total_clientes else None
        response_data = {
            'empresa': empresa.nombre,
            'segmento': f'{offset}-{offset + limit}',
            'total_en_segmento': len(clientes),
            'next_offset': next_offset,
            'has_more': next_offset is not None,
            'clientes': clientes,
            'total_clientes': total_clientes,
        }
        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def api_publica_config(request, empresa_slug):
    """Alias para mantener compatibilidad"""
    return api_descargar_config(request, empresa_slug)

# ============================================================================
# AUTENTICACIÓN DE DISPOSITIVOS
# ============================================================================

@csrf_exempt
def login_dispositivo(request):
    """
    Endpoint para que la app móvil se autentique con usuario y contraseña.
    Devuelve un token de acceso si las credenciales son válidas.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    print("="*50)
    print("Body recibido (raw):", request.body)
    print("Tipo:", type(request.body))
    print("Longitud:", len(request.body))
    print("="*50)
    
    try:
        data = json.loads(request.body)
        empresa_slug = data.get('empresa_slug')
        usuario = data.get('usuario')
        password = data.get('password')
    except:
        return JsonResponse({'error': 'Datos inválidos o JSON mal formado'}, status=400)
    
    if not empresa_slug or not usuario or not password:
        return JsonResponse({'error': 'Faltan campos: empresa_slug, usuario, password'}, status=400)
    
    try:
        dispositivo = DispositivoMovil.objects.get(
            empresa__slug=empresa_slug,
            usuario=usuario,
            activo=True
        )
    except DispositivoMovil.DoesNotExist:
        return JsonResponse({'error': 'Credenciales inválidas'}, status=401)
    
    if not dispositivo.check_password(password):
        return JsonResponse({'error': 'Credenciales inválidas'}, status=401)
    
    nuevo_token = dispositivo.renovar_token()
    return JsonResponse({
        'mensaje': 'Login exitoso',
        'token': str(nuevo_token),
        'dispositivo_id': dispositivo.id,
        'nombre_dispositivo': dispositivo.nombre_dispositivo,
        'empresa': empresa_slug
    })

# ============================================================================
# DESCARGA DE APK
# ============================================================================

@login_required
def descargar_apk(request, empresa_slug):
    """Permite descargar el archivo APK de la aplicación móvil."""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    
    if not empresa.app_generada:
        raise Http404("La aplicación no está disponible para esta empresa.")
    
    # Ruta del archivo APK (ajusta según tu estructura real)
    # Según el usuario, el archivo está en /asesora_ssr/media/apps/v1.apk
    ruta_apk = os.path.join(settings.MEDIA_ROOT, 'apps', 'app-release.apk')
    
    logger = logging.getLogger(__name__)
    logger.info(f"Intentando descargar APK desde: {ruta_apk}")
    
    if not os.path.exists(ruta_apk):
        logger.error(f"Archivo APK no encontrado en: {ruta_apk}")
        raise Http404("El archivo APK no se encuentra en el servidor.")
    
    response = FileResponse(
        open(ruta_apk, 'rb'),
        as_attachment=True,
        filename=f'ssr_app_{empresa.slug}.apk'
    )
    return response