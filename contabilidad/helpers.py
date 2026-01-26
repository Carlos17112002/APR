# contabilidad/helpers.py
from django.core.files.base import ContentFile
from datetime import datetime

def generar_libro_sii(alias, mes, tipo='compras'):
    # Simulación de contenido exportado
    contenido = f"Libro SII · Alias: {alias} · Mes: {mes} · Tipo: {tipo}\n"
    contenido += "Fecha;Documento;Monto;IVA\n"
    contenido += "2025-09-01;FAC001;100000;19000\n"
    contenido += "2025-09-05;FAC002;85000;16150\n"
    contenido += "2025-09-12;FAC003;120000;22800\n"

    nombre_archivo = f"libro_{tipo}_{alias}_{mes}.txt"
    return ContentFile(contenido.encode('utf-8'), name=nombre_archivo)

# contabilidad/helpers.py
# contabilidad/helpers.py
from decimal import Decimal
from .models import DocumentoCompra, DocumentoVenta

def obtener_resumen_contable(alias, mes, año):
    resumen = {
        'total_compras': 0,
        'iva_compras': 0,
        'total_ventas': 0,
        'iva_ventas': 0,
    }

    compras = DocumentoCompra.objects.filter(alias=alias, fecha_emision__year=año, fecha_emision__month=mes)
    ventas = DocumentoVenta.objects.filter(alias=alias, fecha_emision__year=año, fecha_emision__month=mes)

    for compra in compras:
        resumen['total_compras'] += compra.monto_neto or 0
        resumen['iva_compras'] += compra.iva or 0

    for venta in ventas:
        resumen['total_ventas'] += venta.monto_neto or 0
        resumen['iva_ventas'] += venta.iva or 0

    # Redondeo visual
    for key in resumen:
        if isinstance(resumen[key], Decimal):
            resumen[key] = int(resumen[key])

    return resumen

from contabilidad.models import DocumentoCompra, DocumentoVenta
from datetime import datetime

def obtener_resumen_libro(alias, mes, tipo):
    resumen = []
    año, mes_num = map(int, mes.split('-'))

    if tipo == 'compra':
        compras = DocumentoCompra.objects.filter(
            alias=alias,
            fecha_emision__year=año,
            fecha_emision__month=mes_num
        )
        for doc in compras:
            resumen.append({
                'fecha': doc.fecha_emision.strftime('%Y-%m-%d'),
                'proveedor': doc.razon_social,
                'documento': f"{doc.get_tipo_documento_display()} #{doc.folio}",
                'neto': doc.monto_neto,
                'iva': doc.iva,
                'total': doc.monto_total
            })

    elif tipo == 'venta':
        ventas = DocumentoVenta.objects.filter(
            alias=alias,
            fecha_emision__year=año,
            fecha_emision__month=mes_num
        )
        for doc in ventas:
            resumen.append({
                'fecha': doc.fecha_emision.strftime('%Y-%m-%d'),
                'proveedor': doc.razon_social,
                'documento': f"{doc.get_tipo_documento_display()} #{doc.folio}",
                'neto': doc.monto_neto,
                'iva': doc.iva,
                'total': doc.monto_total
            })

    return resumen
