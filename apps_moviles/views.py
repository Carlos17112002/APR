import os
import json
import qrcode
import hashlib
import time
import base64
from pathlib import Path
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt
from empresas.models import Empresa
from lecturas.models import DispositivoMovil, ConfigAppMovil, LecturaMovil

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
    
    # Estadísticas
    total_empresas = empresas.count()
    empresas_con_app = empresas.filter(app_generada=True).count()
    
    # Obtener estadísticas de dispositivos y lecturas
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
    
    # Obtener o crear configuración
    config_app, created = ConfigAppMovil.objects.get_or_create(empresa=empresa)
    
    # Dispositivos de esta empresa
    dispositivos = empresa.dispositivos.all().order_by('-ultima_conexion')
    
    # Estadísticas
    lecturas_hoy = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_sincronizacion__date=timezone.now().date()
    ).count()
    
    lecturas_mes = LecturaMovil.objects.filter(
        empresa=empresa,
        fecha_sincronizacion__month=timezone.now().month,
        fecha_sincronizacion__year=timezone.now().year
    ).count()
    
    # Obtener estadísticas reales de clientes
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    total_clientes_real = 0
    total_sectores_real = 0
    
    try:
        total_clientes_real = Cliente.objects.using(alias_db).count()
        sectores_distintos = Cliente.objects.using(alias_db).values_list(
            'sector', flat=True
        ).distinct()
        total_sectores_real = len([s for s in sectores_distintos if s])
    except:
        total_clientes_real = 0
        total_sectores_real = 0
    
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
            # 1. Actualizar configuración básica
            empresa.color_app_primario = request.POST.get('color_primario', empresa.color_app_primario)
            empresa.color_app_secundario = request.POST.get('color_secundario', empresa.color_app_secundario)
            empresa.url_servidor = request.POST.get('url_servidor', empresa.url_servidor)
            
            # 2. Actualizar configuración de app
            config_app, created = ConfigAppMovil.objects.get_or_create(empresa=empresa)
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
            
            # 3. Generar configuración JSON
            config_json = empresa.generar_config_app()
            
            # Añadir configuración específica
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
            
            # 4. Crear directorios si no existen
            static_dir = Path(settings.BASE_DIR) / 'static'
            static_dir.mkdir(exist_ok=True, parents=True)
            
            apps_config_dir = static_dir / 'apps_config'
            apps_config_dir.mkdir(exist_ok=True, parents=True)
            
            apps_qr_dir = static_dir / 'apps_qr'
            apps_qr_dir.mkdir(exist_ok=True, parents=True)
            
            # 5. Guardar archivo de configuración
            config_file = apps_config_dir / f'{empresa.slug}_config.json'
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_json, f, indent=2, ensure_ascii=False)
            
            # 6. Obtener estadísticas de clientes
            from clientes.models import Cliente
            alias_db = f'db_{empresa.slug}'
            
            try:
                total_clientes = Cliente.objects.using(alias_db).count()
            except:
                total_clientes = 0
            
            # 7. USAR SIEMPRE QR CON ESTRATEGIA ÚNICA
            qr_data = _crear_qr_unico(request, empresa, total_clientes)
            qr_strategy = 'universal'
            
            # 8. Generar QR
            qr_img = qrcode.make(qr_data)
            
            qr_path = apps_qr_dir / f'{empresa.slug}.png'
            qr_img.save(qr_path)
            
            # 9. Actualizar empresa
            empresa.app_generada = True
            empresa.fecha_generacion_app = timezone.now()
            empresa.version_app = incrementar_version(empresa.version_app)
            empresa.save()
            
            messages.success(request, f'✅ App móvil generada para {empresa.nombre}')
            messages.info(request, f'Versión: {empresa.version_app}')
            messages.info(request, f'Clientes: {total_clientes}')
            messages.info(request, f'Estrategia QR: Universal (token)')
            messages.info(request, f'Tamaño QR: {len(qr_data)} caracteres')
            
            # Mostrar vista previa
            context = {
                'empresa': empresa,
                'qr_url': f'/static/apps_qr/{empresa.slug}.png',
                'qr_data_preview': qr_data[:100] + '...' if len(qr_data) > 100 else qr_data,
                'qr_data_length': len(qr_data),
                'total_clientes': total_clientes,
                'qr_strategy': qr_strategy,
            }
            
            return render(request, 'apps_moviles/qr_generado.html', context)
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
            import traceback
            traceback.print_exc()
            return redirect('generar_app_empresa', empresa_slug=empresa.slug)
    
    # GET: Mostrar formulario
    config_app, created = ConfigAppMovil.objects.get_or_create(empresa=empresa)
    
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
    
    # Obtener estadísticas reales
    from clientes.models import Cliente
    
    alias_db = f'db_{empresa.slug}'
    total_clientes = 0
    total_sectores = 0
    
    try:
        # Contar clientes reales
        total_clientes = Cliente.objects.using(alias_db).count()
        
        # Obtener sectores distintos
        sectores_distintos = Cliente.objects.using(alias_db).values_list(
            'sector', flat=True
        ).distinct()
        total_sectores = len([s for s in sectores_distintos if s])
    except:
        total_clientes = 0
        total_sectores = 0
    
    print(f"\n{'='*60}")
    print(f"EMPRESA: {empresa.nombre}")
    print(f"Total clientes en BD: {total_clientes}")
    print(f"Total sectores en BD: {total_sectores}")
    print(f"{'='*60}")
    
    # Usar siempre la estrategia universal
    return _ver_qr_universal(request, empresa, total_clientes, total_sectores)

# ============================================================================
# ESTRATEGIA ÚNICA - QR UNIVERSAL
# ============================================================================

def _crear_qr_unico(request, empresa, total_clientes):
    """Crea QR usando la estrategia única universal"""
    # Generar token único
    token_unico = hashlib.sha256(
        f"{empresa.slug}-UNIVERSAL-{time.time()}".encode()
    ).hexdigest()[:32]
    
    # Guardar en sesión
    request.session[f'qr_token_{empresa.slug}'] = token_unico
    request.session[f'empresa_token_{token_unico}'] = {
        'slug': empresa.slug,
        'timestamp': time.time(),
        'total_clientes': total_clientes,
    }
    
    # Datos para el QR
    qr_info = {
        't': 'universal',       # type = universal (único tipo)
        'e': empresa.slug,      # empresa slug
        'tk': token_unico,      # token
        'u': f'{request.scheme}://{request.get_host()}/apps/api/config/{empresa.slug}/?token={token_unico}',
        'cn': total_clientes,   # client count
        'v': 1                  # versión
    }
    
    return json.dumps(qr_info, separators=(',', ':'), ensure_ascii=False)

def _ver_qr_universal(request, empresa, total_clientes, total_sectores):
    """Muestra QR usando la estrategia universal"""
    # Generar token único
    token_unico = hashlib.sha256(
        f"{empresa.slug}-UNIVERSAL-{time.time()}".encode()
    ).hexdigest()[:32]
    
    # Guardar en sesión
    request.session[f'qr_token_{empresa.slug}'] = token_unico
    request.session[f'empresa_token_{token_unico}'] = {
        'slug': empresa.slug,
        'timestamp': time.time(),
        'total_clientes': total_clientes,
        'total_sectores': total_sectores,
    }
    
    # Asegurar valores no nulos
    empresa_slug = empresa.slug or ""
    total_clientes_str = str(total_clientes) if total_clientes is not None else "0"
    
    # Datos para el QR - TODOS COMO STRINGS
    qr_info = {
        't': 'universal',
        'e': empresa_slug,
        'tk': token_unico,
        'u': f'{request.scheme}://{request.get_host()}/apps/api/config/{empresa_slug}/',
        'cn': total_clientes_str,
        'v': '1'
    }
    
    # Validar que no haya nulos
    for key, value in qr_info.items():
        if value is None:
            qr_info[key] = ""
    
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
    
    # Generar JSON de configuración para mostrar en template
    try:
        config_app = ConfigAppMovil.objects.get(empresa=empresa)
    except ConfigAppMovil.DoesNotExist:
        config_app = None
    
    # Crear JSON de configuración completo para mostrar
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
        'api_url': f'{request.scheme}://{request.get_host()}/apps/api/config/{empresa.slug}/?token={token_unico}',
        'qr_data_preview': qr_data[:100] + '...',
        'qr_data_length': len(qr_data),
        'total_clientes': total_clientes,
        'total_sectores': total_sectores,
        'page_title': f'QR App - {empresa.nombre}',
        'usando_token': True,
        'token': token_unico,
        'mensaje_especial': f'✅ Configuración universal aplicada ({total_clientes} clientes)',
        'json_config': json.dumps(json_config, indent=2, ensure_ascii=False),  # <-- AÑADIDO
    }
    
    _guardar_qr_archivo(empresa.slug, qr_img)
    
    return render(request, 'apps_moviles/ver_qr.html', context)

# ============================================================================
# APIS PARA LA APP MÓVIL (endpoints que escaneará el QR)
# ============================================================================

@csrf_exempt
def api_descargar_config(request, empresa_slug):
    """API para descargar configuración (endpoint del QR)"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    
    # Verificar token
    token = request.GET.get('token')
    session_data = request.session.get(f'empresa_token_{token}')
    
    if not token or not session_data or session_data.get('slug') != empresa.slug:
        return JsonResponse({'error': 'Token inválido o expirado'}, status=403)
    
    # Obtener configuración de app
    try:
        config_app = ConfigAppMovil.objects.get(empresa=empresa)
    except ConfigAppMovil.DoesNotExist:
        config_app = None
    
    # Obtener sectores
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    sectores = []
    
    try:
        sectores_distintos = Cliente.objects.using(alias_db).values_list(
            'sector', flat=True
        ).distinct()
        sectores = [s for s in sectores_distintos if s]
    except:
        pass
    
    # Configuración básica
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
        'descarga_segmentada': False,  # Por defecto descarga completa
        'endpoints': {
            'clientes': f'{request.scheme}://{request.get_host()}/apps/descargar-clientes/{empresa.slug}/?token={token}',
        },
    }
    
    # Añadir configuración de app si existe
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
    
    # Verificar token
    token = request.GET.get('token')
    session_data = request.session.get(f'empresa_token_{token}')
    
    if not token or not session_data or session_data.get('slug') != empresa.slug:
        return JsonResponse({'error': 'Token inválido o expirado'}, status=403)
    
    from clientes.models import Cliente
    
    alias_db = f'db_{empresa.slug}'
    clientes = []
    
    try:
        # Obtener TODOS los clientes
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
        
        print(f"Descargando {len(clientes)} clientes para {empresa.nombre}")
        
        # Preparar respuesta
        response_data = {
            'empresa': empresa.nombre,
            'empresa_slug': empresa.slug,
            'total_clientes': len(clientes),
            'clientes': clientes,
            'timestamp': time.time(),
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error descargando clientes: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def descargar_clientes_segmento(request, empresa_slug):
    """API para descargar segmentos de clientes"""
    empresa = get_object_or_404(Empresa, slug=empresa_slug)
    
    # Verificar token
    token = request.GET.get('token')
    session_data = request.session.get(f'empresa_token_{token}')
    
    if not token or not session_data or session_data.get('slug') != empresa.slug:
        return JsonResponse({'error': 'Token inválido o expirado'}, status=403)
    
    from clientes.models import Cliente
    
    # Parámetros de segmentación
    try:
        offset = int(request.GET.get('offset', 0))
        limit = int(request.GET.get('limit', 200))
    except:
        offset = 0
        limit = 200
    
    alias_db = f'db_{empresa.slug}'
    clientes = []
    
    try:
        # Obtener el total de clientes
        total_clientes = Cliente.objects.using(alias_db).count()
        
        # Obtener segmento de clientes
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
        
        print(f"Descargando segmento {offset}-{offset + limit} ({len(clientes)} clientes)")
        
        # Calcular si hay más segmentos
        next_offset = offset + limit if offset + limit < total_clientes else None
        
        # Preparar respuesta
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
        print(f"Error descargando segmento: {e}")
        return JsonResponse({'error': str(e)}, status=500)

# ============================================================================
# FUNCIONES AUXILIARES COMUNES
# ============================================================================

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
# VISTAS ADICIONALES
# ============================================================================

@login_required
def gestionar_dispositivos(request, empresa_slug):
    """Gestiona dispositivos móviles de una empresa"""
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
            nombre = request.POST.get('nombre', 'Nuevo Dispositivo')
            identificador = request.POST.get('identificador', '').strip()
            
            if not identificador:
                identificador = f"dev_{empresa.slug}_{int(time.time())}"
            
            if DispositivoMovil.objects.filter(identificador=identificador).exists():
                messages.error(request, 'Ya existe un dispositivo con este identificador')
            else:
                dispositivo = DispositivoMovil.objects.create(
                    empresa=empresa,
                    nombre_dispositivo=nombre,
                    identificador=identificador,
                    activo=True
                )
                messages.success(request, f'✅ Dispositivo creado: {dispositivo.nombre_dispositivo}')
                messages.info(request, f'Token: {dispositivo.token_acceso}')
            
        elif action == 'renovar_token':
            dispositivo_id = request.POST.get('dispositivo_id')
            dispositivo = get_object_or_404(DispositivoMovil, id=dispositivo_id, empresa=empresa)
            nuevo_token = dispositivo.renovar_token()
            messages.success(request, f'✅ Token renovado: {nuevo_token}')
            
        elif action == 'toggle_activo':
            dispositivo_id = request.POST.get('dispositivo_id')
            dispositivo = get_object_or_404(DispositivoMovil, id=dispositivo_id, empresa=empresa)
            dispositivo.activo = not dispositivo.activo
            dispositivo.save()
            
            estado = "activado" if dispositivo.activo else "desactivado"
            messages.success(request, f'✅ Dispositivo {estado}')
        
        elif action == 'eliminar':
            dispositivo_id = request.POST.get('dispositivo_id')
            dispositivo = get_object_or_404(DispositivoMovil, id=dispositivo_id, empresa=empresa)
            nombre = dispositivo.nombre_dispositivo
            dispositivo.delete()
            messages.success(request, f'✅ Dispositivo eliminado: {nombre}')
        
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
    
    # Obtener estadísticas
    from clientes.models import Cliente
    alias_db = f'db_{empresa.slug}'
    
    try:
        total_clientes = Cliente.objects.using(alias_db).count()
    except:
        total_clientes = 0
    
    # Usar la función _ver_qr_universal
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
    
    # Generar configuración
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
# APIS PÚBLICAS (para la app móvil)
# ============================================================================

@csrf_exempt
def api_publica_config(request, empresa_slug):
    """Alias para mantener compatibilidad"""
    return api_descargar_config(request, empresa_slug)