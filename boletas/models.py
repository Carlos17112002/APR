# boletas/models.py - VERSIÓN COMPLETA
from django.db import models
from django.utils import timezone

class Boleta(models.Model):
    ESTADOS_BOLETA = [
        ('generada', 'Generada'),
        ('enviada', 'Enviada al Cliente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
    ]
    
    # Relaciones
    cliente = models.ForeignKey('clientes.Cliente', on_delete=models.CASCADE, related_name='boletas')
    lectura = models.OneToOneField('lecturas.LecturaMovil', on_delete=models.SET_NULL, null=True, blank=True, related_name='boleta_asociada')
    
    # Campos básicos
    periodo = models.CharField(max_length=50, blank=True)
    fecha_emision = models.DateField(auto_now_add=True)
    fecha_vencimiento = models.DateField(default=timezone.now)  # ✅ NECESARIO
    
    # Datos de consumo
    lectura_anterior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lectura_actual = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    consumo = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Montos
    monto_consumo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cargo_fijo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    otros_cargos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)  # ✅ NECESARIO
    
    # Estado y tracking
    estado = models.CharField(max_length=20, choices=ESTADOS_BOLETA, default='generada')  # ✅ NECESARIO
    codigo_barras = models.CharField(max_length=100, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    empresa_slug = models.CharField(max_length=50, db_index=True)  # ✅ NECESARIO
    
    class Meta:
        ordering = ['-fecha_emision']
    
    def __str__(self):
        return f"Boleta {self.id} - {self.cliente.nombre} - ${self.total}"