from django.db import models

class DocumentoCompra(models.Model):
    fecha_emision = models.DateField()
    rut_emisor = models.CharField(max_length=12)
    razon_social = models.CharField(max_length=200)
    tipo_documento = models.CharField(max_length=10, choices=[
        ('33', 'Factura'),
        ('34', 'Factura Exenta'),
        ('46', 'Boleta'),
        ('56', 'Nota Débito'),
        ('61', 'Nota Crédito'),
    ])
    folio = models.IntegerField()
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    alias = models.CharField(max_length=50)
    cuenta_contable = models.CharField(max_length=100, null=True, blank=True)


class DocumentoVenta(models.Model):
    fecha_emision = models.DateField()
    rut_receptor = models.CharField(max_length=12)
    razon_social = models.CharField(max_length=200)
    tipo_documento = models.CharField(max_length=10, choices=[
        ('33', 'Factura'),
        ('34', 'Factura Exenta'),
        ('39', 'Boleta'),
        ('56', 'Nota Débito'),
        ('61', 'Nota Crédito'),
    ])
    folio = models.IntegerField()
    monto_neto = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2)
    alias = models.CharField(max_length=50)
    cuenta_contable = models.CharField(max_length=100, null=True, blank=True)
class LibroSII(models.Model):
    alias = models.CharField(max_length=50)
    mes = models.IntegerField()
    año = models.IntegerField()
    tipo = models.CharField(max_length=25, choices=[
        ('compra', 'Compra'),
        ('venta', 'Venta'),
        ('retenciones', 'Retenciones'),
        ('ingreso_retenciones', 'Ingreso de retenciones'),
    ])
    estado = models.CharField(max_length=20, choices=[
        ('subido', 'Subido'),
        ('procesando', 'Procesando'),
        ('validado', 'Validado'),
        ('error', 'Con error'),
    ])
    fecha_subida = models.DateTimeField(auto_now_add=True)
    usuario = models.CharField(max_length=100)

    # Opcionales para trazabilidad contable
    desde_comprobante = models.IntegerField(null=True, blank=True)
    cuenta_afecta = models.CharField(max_length=100, null=True, blank=True)
    cuenta_exenta = models.CharField(max_length=100, null=True, blank=True)
    cuenta_ingreso = models.CharField(max_length=100, null=True, blank=True)
    cuenta_egreso = models.CharField(max_length=100, null=True, blank=True)
    archivo = models.FileField(upload_to='libros_sii/', null=True, blank=True)

class DocumentoContable(models.Model):
    alias = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    archivo = models.FileField(upload_to='documentos/')
    descripcion = models.TextField(blank=True)

    # Contrato
    nombre_trabajador = models.CharField(max_length=100, blank=True)
    cargo = models.CharField(max_length=100, blank=True)
    inicio = models.DateField(null=True, blank=True)
    tipo_contrato = models.CharField(max_length=50, blank=True)

    # Finiquito
    fecha_finiquito = models.DateField(null=True, blank=True)
    motivo_finiquito = models.CharField(max_length=200, blank=True)
    total_finiquito = models.PositiveIntegerField(null=True, blank=True)

    # Liquidación
    mes_liquidacion = models.CharField(max_length=7, blank=True)  # Ej: "2025-09"
    total_liquido = models.PositiveIntegerField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)
