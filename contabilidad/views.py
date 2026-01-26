from django.shortcuts import render
from .models import DocumentoCompra, DocumentoVenta
from django.db.models import Sum
from django.utils import timezone

def lista_compras(request, alias):
    compras = DocumentoCompra.objects.using(f'db_{alias}').order_by('-fecha_emision')
    return render(request, 'contabilidad/lista_compras.html', {'compras': compras, 'alias': alias})

def lista_ventas(request, alias):
    ventas = DocumentoVenta.objects.using(f'db_{alias}').order_by('-fecha_emision')
    return render(request, 'contabilidad/lista_ventas.html', {'ventas': ventas, 'alias': alias})

from datetime import datetime
from .helpers import obtener_resumen_contable


def panel_libro_sii(request, alias):
    mes_str = request.GET.get('mes')
    if mes_str:
        try:
            fecha = datetime.strptime(mes_str, "%Y-%m")
            mes = fecha.month
            año = fecha.year
        except ValueError:
            fecha = datetime.today()
            mes = fecha.month
            año = fecha.year
    else:
        fecha = datetime.today()
        mes = fecha.month
        año = fecha.year

    resumen = obtener_resumen_contable(alias, mes, año)  # tu helper
    return render(request, 'contabilidad/panel_libro_sii.html', {
        'alias': alias,
        'mes': f"{mes:02d}",
        'año': año,
        'mes_full': fecha.strftime("%Y-%m"),
        'resumen': resumen
    })


def exportar_libro_sii(request, alias):
    # Placeholder: lógica para exportar a CSV/XML
    return render(request, 'contabilidad/exportar_libro_sii.html', {'alias': alias})


import csv
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from .models import DocumentoCompra, DocumentoVenta, LibroSII

def subir_libro_sii(request, alias):
    año_actual = timezone.now().year
    meses = list(range(1, 13))

    if request.method == 'POST':
        mes = int(request.POST.get('mes'))
        año = int(request.POST.get('año'))
        tipo = request.POST.get('tipo')
        archivo = request.FILES.get('archivo')

        # Campos dinámicos
        codigo_compra = request.POST.get('codigo_compra')
        raw_comprobante = (
            request.POST.get('desde_comprobante') or
            request.POST.get('desde_comprobante_compra') or
            request.POST.get('desde_comprobante_retencion') or
            request.POST.get('desde_comprobante_ingreso')
        )
        desde_comprobante = int(raw_comprobante) if raw_comprobante else None

        cuenta_afecta = request.POST.get('cuenta_afecta') or request.POST.get('cuenta_afecta_retencion')
        cuenta_exenta = request.POST.get('cuenta_exenta')
        cuenta_ingreso = request.POST.get('cuenta_ingreso')
        cuenta_egreso = request.POST.get('cuenta_egreso')

        if not archivo:
            messages.error(request, "No se subió ningún archivo.")
            return redirect('subir_libro_sii', alias=alias)

        try:
            decoded_file = archivo.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
        except Exception as e:
            messages.error(request, f"Error al leer el archivo: {e}")
            return redirect('subir_libro_sii', alias=alias)

        registros = 0
        errores = 0
        errores_por_fila = []

        for i, row in enumerate(reader, start=1):
            try:
                fecha = row.get('FechaEmision') or row.get('fecha')
                rut = row.get('RUTEmisor') if tipo == 'compra' else row.get('RUTReceptor')
                razon = row.get('RazonSocial') or row.get('razon')
                tipo_doc = row.get('TipoDocumento')
                folio_raw = row.get('Folio')
                neto_raw = row.get('MontoNeto')
                iva_raw = row.get('IVA')
                total_raw = row.get('MontoTotal')

                # Validación de campos obligatorios
                if not fecha or not rut or not razon or not tipo_doc or not folio_raw or not neto_raw or not iva_raw or not total_raw:
                    raise ValueError("Faltan campos obligatorios")

                # Conversión segura
                folio = int(folio_raw)
                neto = float(neto_raw)
                iva = float(iva_raw)
                total = float(total_raw)

                # Guardado según tipo
                if tipo == 'compra':
                    DocumentoCompra.objects.using(f'db_{alias}').create(
                        fecha_emision=fecha,
                        rut_emisor=rut,
                        razon_social=razon,
                        tipo_documento=tipo_doc,
                        folio=folio,
                        monto_neto=neto,
                        iva=iva,
                        monto_total=total,
                        alias=alias
                    )
                elif tipo == 'venta':
                    DocumentoVenta.objects.using(f'db_{alias}').create(
                        fecha_emision=fecha,
                        rut_receptor=rut,
                        razon_social=razon,
                        tipo_documento=tipo_doc,
                        folio=folio,
                        monto_neto=neto,
                        iva=iva,
                        monto_total=total,
                        alias=alias
                    )
                # Podés agregar lógica para retenciones si tenés modelos definidos

                registros += 1

            except Exception as e:
                errores += 1
                errores_por_fila.append(f"⚠️ Fila {i}: {e}")

        # Mostrar errores por fila
        for error in errores_por_fila:
            messages.warning(request, error)

        # Registrar el libro
        LibroSII.objects.using(f'db_{alias}').create(
            alias=alias,
            mes=mes,
            año=año,
            tipo=tipo,
            estado='subido',
            usuario=request.user.username if request.user.is_authenticated else 'anonimo',
            desde_comprobante=desde_comprobante,
            cuenta_afecta=cuenta_afecta,
            cuenta_exenta=cuenta_exenta,
            cuenta_ingreso=cuenta_ingreso,
            cuenta_egreso=cuenta_egreso,
            archivo=archivo
        )

        messages.success(request, f"✅ {registros} documentos procesados. ⚠️ {errores} con error.")
        return redirect('lista_libros_sii', alias=alias)

    return render(request, 'contabilidad/subir_libro.html', {
        'alias': alias,
        'año_actual': año_actual,
        'meses': meses,
    })

from django.shortcuts import render
from .models import LibroSII

def lista_libros_sii(request, alias):
    libros = LibroSII.objects.using(f'db_{alias}').all()

    mes = request.GET.get('mes')
    año = request.GET.get('año')
    tipo = request.GET.get('tipo')
    estado = request.GET.get('estado')

    if mes:
        libros = libros.filter(mes=int(mes))
    if año:
        libros = libros.filter(año=int(año))
    if tipo:
        libros = libros.filter(tipo=tipo)
    if estado:
        libros = libros.filter(estado=estado)

    libros = libros.order_by('-año', '-mes')

    meses = list(range(1, 13))

    return render(request, 'contabilidad/lista_libros.html', {
        'alias': alias,
        'libros': libros,
        'meses': meses,
    })

import csv
from django.shortcuts import render, get_object_or_404
from .models import LibroSII
from django.conf import settings
import os

def revisar_libro_sii(request, alias, libro_id):
    libro = get_object_or_404(LibroSII.objects.using(f'db_{alias}'), id=libro_id)

    preview = []
    totales = {
        'documentos': 0,
        'neto': 0,
        'iva': 0,
        'total': 0,
    }

    if libro.archivo:
        try:
            archivo_path = os.path.join(settings.MEDIA_ROOT, libro.archivo.name)
            with open(archivo_path, encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i < 10:
                        preview.append(row)
                    try:
                        totales['documentos'] += 1
                        totales['neto'] += float(row.get('MontoNeto', 0))
                        totales['iva'] += float(row.get('IVA', 0))
                        totales['total'] += float(row.get('MontoTotal', 0))
                    except Exception as e:
                        print(f"[ERROR] Fila inválida: {row} → {e}")
        except Exception as e:
            print(f"[ERROR] No se pudo abrir el archivo: {e}")
    else:
        print("[INFO] El libro no tiene archivo guardado.")

    return render(request, 'contabilidad/revisar_libro.html', {
        'alias': alias,
        'libro': libro,
        'preview': preview,
        'totales': totales,
    })

from django.shortcuts import get_object_or_404
from django.contrib import messages
from .models import LibroSII

def eliminar_libro_sii(request, alias, libro_id):
    if request.method == 'POST':
        libro = get_object_or_404(LibroSII.objects.using(f'db_{alias}'), id=libro_id)
        libro.delete()
        messages.success(request, f"🗑️ Libro eliminado correctamente.")
    return redirect('lista_libros_sii', alias=alias)


from django.shortcuts import render
from django.http import HttpResponse
from datetime import datetime

from django.shortcuts import render
from datetime import datetime
from contabilidad.helpers import generar_libro_sii, obtener_resumen_libro  # asegúrate de tener estas funciones

def exportar_libro_sii(request, alias):
    mensaje = ""
    archivo = None
    resumen = []

    if request.method == 'POST':
        mes = request.POST.get('mes')
        tipo = request.POST.get('tipo')  # compras, ventas, etc.

        try:
            fecha = datetime.strptime(mes, "%Y-%m")
            archivo = generar_libro_sii(alias, mes, tipo)  # genera archivo PDF o Excel
            resumen = obtener_resumen_libro(alias, mes, tipo)  # devuelve lista de dicts
            mensaje = f"✅ Libro {tipo} para {mes} exportado correctamente."
        except ValueError:
            mensaje = "⚠️ Formato de mes inválido. Usa YYYY-MM."

    return render(request, 'contabilidad/exportar_libro_sii.html', {
        'alias': alias,
        'mensaje': mensaje,
        'archivo': archivo,
        'resumen': resumen
    })

        
