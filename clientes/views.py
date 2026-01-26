from django.shortcuts import render, redirect
from clientes.models import Cliente
from empresas.models import Empresa
from django.contrib.auth.models import User, Group
from django.db import IntegrityError, transaction

def crear_cliente(request, alias):
    slug = alias
    alias_db = f'db_{slug}'
    empresa = Empresa.objects.get(slug=slug)
    sectores = empresa.sectores()
    error = None
    credenciales = None

    if request.method == 'POST':
        rut = request.POST.get('rut')
        nombre = request.POST.get('nombre')
        email = request.POST.get('email')
        direccion = request.POST.get('direccion')
        medidor = request.POST.get('medidor')
        telefono = request.POST.get('telefono')
        sector = request.POST.get('sector')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        username = rut.replace('.', '').replace('-', '')

        if User.objects.filter(username=username).exists():
            error = 'Ya existe un usuario con ese RUT.'
        else:
            password = User.objects.make_random_password()

            try:
                with transaction.atomic():
                    # Crear usuario
                    usuario = User.objects.create_user(username=username, email=email, password=password)
                    usuario.first_name = nombre
                    usuario.save()

                    # Asignar al grupo "cliente"
                    grupo_cliente, _ = Group.objects.get_or_create(name='cliente')
                    usuario.groups.add(grupo_cliente)

                    # Crear cliente en base multiempresa
                    Cliente.objects.using(alias_db).create(
                        usuario_id=usuario.id,
                        empresa_slug=slug,
                        nombre=nombre,
                        rut=rut,
                        direccion=direccion,
                        medidor=medidor,
                        email=email,
                        telefono=telefono,
                        sector=sector,
                        latitude=latitude,
                        longitude=longitude,
                    )

                    credenciales = {'usuario': username, 'password': password}

            except Exception as e:
                # Rollback: eliminar usuario si falló la creación del cliente
                if User.objects.filter(username=username).exists():
                    User.objects.get(username=username).delete()
                error = f'Error al registrar el cliente: {str(e)}'

    return render(request, 'crear_cliente.html', {
        'empresa': empresa,
        'slug': slug,
        'sectores': sectores,
        'error': error,
        'credenciales': credenciales,
    })




from django.shortcuts import render, get_object_or_404
from clientes.models import Cliente
from lecturas.models import LecturaMovil
from faq.models import PreguntaFrecuente as FAQ
from empresas.models import Empresa
from avisos.models import Aviso
from faq.models import  PreguntaFrecuente # Si tenés una app para preguntas frecuentes
from boletas.models import Boleta

def perfil_cliente_view(request, alias):
    slug = alias
    alias_db = f'db_{slug}'

    empresa = get_object_or_404(Empresa.objects.using(alias_db), slug=slug)
    cliente = get_object_or_404(Cliente.objects.using(alias_db), usuario_id=request.user.id)

    # 🧾 Lecturas recientes del cliente
    lecturas = Lectura.objects.using(alias_db).filter(cliente=cliente).order_by('-fecha')[:10]

    # 📢 Avisos activos
    avisos = Aviso.objects.using(alias_db).filter(activo=True).order_by('-fecha_creacion')
    
    boletas = Boleta.objects.using(alias_db).filter(cliente=cliente).order_by('-fecha_emision')


    # ❓ Preguntas frecuentes
    faqs = FAQ.objects.using(alias_db).all()

    return render(request, 'clientes/perfil_cliente.html', {
        'empresa': empresa,
        'cliente': cliente,
        'slug': slug,
        'lecturas': lecturas,
        'avisos': avisos,
        'faqs': faqs,
        'boletas': boletas,
    })

from django.shortcuts import render
from clientes.models import Cliente
from empresas.models import Empresa

def listado_clientes(request, alias):
    slug = alias
    alias_db = f'db_{slug}'
    empresa = Empresa.objects.get(slug=slug)
    sectores = empresa.sectores()

    clientes = Cliente.objects.using(alias_db).all()

    sector = request.GET.get('sector')
    rut = request.GET.get('rut')

    if sector:
        clientes = clientes.filter(sector=sector)
    if rut:
        clientes = clientes.filter(rut__icontains=rut)

    clientes = clientes.order_by('nombre')

    return render(request, 'listado_clientes.html', {
        'empresa': empresa,
        'slug': slug,
        'clientes': clientes,
        'sectores': sectores,
    })

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from clientes.models import Cliente

def login_cliente(request):
    if request.method == 'POST':
        rut = request.POST.get('rut')
        password = request.POST.get('password')
        alias = request.POST.get('alias')

        user = authenticate(request, username=rut, password=password)
        if user and user.groups.filter(name='cliente').exists():
            login(request, user)
            return redirect('perfil_cliente', alias=alias)
        else:
            error = "Credenciales inválidas o rol incorrecto"

    empresas = Empresa.objects.all()
    return render(request, 'clientes/login_cliente.html', locals())


# usuarios/views.py
from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect('login_ssr')

from django.http import JsonResponse
from clientes.models import Cliente

def clientes_por_alias(request, alias):
    try:
        clientes = Cliente.objects.using(f'db_{alias}').exclude(latitude=None).exclude(longitude=None)
        data = list(clientes.values('id', 'nombre', 'direccion', 'latitude', 'longitude'))
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from clientes.models import Cliente
from empresas.models import Empresa

@require_POST
@csrf_protect
def eliminar_cliente(request, alias, cliente_id):
    """
    Vista para eliminar un cliente
    """
    try:
        # Obtener la empresa usando el alias correcto
        db_alias = f'db_{alias}'
        
        # Obtener el cliente
        cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)
        
        # Verificar si es una petición AJAX
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        # Verificar si hay datos relacionados antes de eliminar
        # (Esta parte depende de tu estructura de datos)
        
        try:
            # Intentar eliminar el cliente
            cliente.delete()
            
            # Preparar la respuesta
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': 'Cliente eliminado exitosamente'
                })
            else:
                messages.success(request, f'Cliente {cliente.nombre} eliminado exitosamente.')
                return redirect('listado_clientes', alias=alias)
                
        except Exception as e:
            # Si hay error por relaciones existentes
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'error': f'No se puede eliminar el cliente. {str(e)}'
                })
            else:
                messages.error(request, f'No se puede eliminar el cliente. {str(e)}')
                return redirect('listado_clientes', alias=alias)
                
    except Cliente.DoesNotExist:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Cliente no encontrado'
            })
        else:
            messages.error(request, 'Cliente no encontrado.')
            return redirect('listado_clientes', alias=alias)
            
    except Exception as e:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': f'Error al procesar la solicitud: {str(e)}'
            })
        else:
            messages.error(request, f'Error al procesar la solicitud: {str(e)}')
            return redirect('listado_clientes', alias=alias)


from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from datetime import date, timedelta
from decimal import Decimal

def detalle_cliente(request, alias, cliente_id):
    """Vista para ver el detalle completo de un cliente"""
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa.objects.using(db_alias), slug=alias)
    
    # Obtener el cliente con toda su información
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)
    
    # Obtener contratos del cliente
    from contratos.models import Contrato
    contratos = Contrato.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_inicio')
    
    # Obtener lecturas recientes
    from lecturas.models import Lectura
    lecturas = Lectura.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')[:10]
    
    # Obtener pagos recientes
    from pagos.models import Pago
    pagos = Pago.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')[:10]
    
    # Calcular estadísticas
    consumo_promedio = lecturas.aggregate(Avg('consumo'))['consumo__avg'] or 0
    total_pagado = pagos.aggregate(Sum('monto'))['monto__sum'] or 0
    
    # Calcular deuda actual (si existe módulo de facturación)
    deuda_actual = Decimal('0.00')
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'contratos': contratos,
        'lecturas': lecturas,
        'pagos': pagos,
        'consumo_promedio': consumo_promedio,
        'total_pagado': total_pagado,
        'deuda_actual': deuda_actual,
        'hoy': date.today(),
    }
    
    return render(request, 'clientes/detalle_cliente.html', context)

def editar_cliente(request, alias, cliente_id):
    """Vista para editar un cliente existente"""
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa.objects.using(db_alias), slug=alias)
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)
    
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save(using=db_alias)
            messages.success(request, f'Cliente {cliente.nombre} actualizado exitosamente.')
            return redirect('detalle_cliente', alias=alias, cliente_id=cliente.id)
    else:
        form = ClienteForm(instance=cliente)
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'form': form,
    }
    
    return render(request, 'clientes/editar_cliente.html', context)


def historial_cliente(request, alias, cliente_id):
    """Vista para ver el historial completo del cliente"""
    db_alias = f'db_{alias}'
    empresa = get_object_or_404(Empresa.objects.using(db_alias), slug=alias)
    cliente = get_object_or_404(Cliente.objects.using(db_alias), id=cliente_id)
    
    # Obtener todos los registros del cliente
    from lecturas.models import Lectura
    from pagos.models import Pago
    from contratos.models import Contrato
    from avisos.models import Aviso
    
    lecturas_completas = Lectura.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    pagos_completos = Pago.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha')
    contratos_completos = Contrato.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_inicio')
    avisos = Aviso.objects.using(db_alias).filter(cliente=cliente).order_by('-fecha_creacion')
    
    # Estadísticas avanzadas
    consumo_total = lecturas_completas.aggregate(Sum('consumo'))['consumo__sum'] or 0
    pago_total = pagos_completos.aggregate(Sum('monto'))['monto__sum'] or 0
    consumo_promedio = lecturas_completas.aggregate(Avg('consumo'))['consumo__avg'] or 0
    
    context = {
        'empresa': empresa,
        'slug': alias,
        'cliente': cliente,
        'lecturas': lecturas_completas,
        'pagos': pagos_completos,
        'contratos': contratos_completos,
        'avisos': avisos,
        'consumo_total': consumo_total,
        'pago_total': pago_total,
        'consumo_promedio': consumo_promedio,
        'total_registros': lecturas_completas.count() + pagos_completos.count() + contratos_completos.count(),
    }
    
    return render(request, 'clientes/historial_cliente.html', context)

