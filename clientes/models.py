# clientes/models.py

from django.db import models
from django.contrib.auth.models import User
from empresas.models import Empresa

class Cliente(models.Model):
    # Campos existentes
    usuario_id = models.IntegerField(null=True, blank=True)
    empresa_slug = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    nombre = models.CharField(max_length=100)          # Ahora será el primer nombre
    apellido_paterno = models.CharField(max_length=100, blank=True)  # Nuevo
    apellido_materno = models.CharField(max_length=100, blank=True)  # Nuevo
    rut = models.CharField(max_length=12, unique=True)
    direccion = models.CharField(max_length=150)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    medidor = models.CharField(max_length=20, unique=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    sector = models.CharField(max_length=50, blank=True)

    # Datos Cliente (adicionales)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    fecha_defuncion = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=10, blank=True)
    estado_civil = models.CharField(max_length=20, blank=True)
    profesion = models.CharField(max_length=100, blank=True)
    email_contacto = models.EmailField(blank=True)
    contacto1 = models.CharField(max_length=50, blank=True)
    contacto2 = models.CharField(max_length=50, blank=True)
    fecha_incorporacion = models.DateField(null=True, blank=True)
    numero_libro = models.CharField(max_length=50, blank=True)

    def __str__(self):
        # Mostrar nombre completo
        partes = [self.nombre]
        if self.apellido_paterno:
            partes.append(self.apellido_paterno)
        if self.apellido_materno:
            partes.append(self.apellido_materno)
        return f"{' '.join(partes)} ({self.rut})"

class Contrato(models.Model):
    """
    Modelo que almacena los datos del contrato del cliente: información de arranque y facturación.
    Relacionado uno a uno con Cliente.
    """
    cliente = models.OneToOneField(Cliente, on_delete=models.CASCADE, related_name='contrato')
    numero_contrato = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    # Datos Arranque (según template)
    tipo_cliente = models.CharField(max_length=50, blank=True)
    tipo_servicio_ssr = models.CharField(max_length=50, blank=True)  # Tipo SSR
    fecha_contrato = models.DateField(null=True, blank=True)
    comuna = models.CharField(max_length=100, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    sector_arranque = models.CharField(max_length=100, blank=True)  # sector del arranque (podría ser igual al del cliente)
    direccion_arranque = models.CharField(max_length=200, blank=True)
    utm_norte = models.CharField(max_length=50, blank=True)
    utm_este = models.CharField(max_length=50, blank=True)
    rol = models.CharField(max_length=50, blank=True)
    socio = models.BooleanField(default=False)  # Sí/No
    servicio = models.CharField(max_length=50, blank=True)
    diametro = models.CharField(max_length=20, blank=True)
    marca_medidor = models.CharField(max_length=50, blank=True)
    numero_medidor = models.CharField(max_length=20, blank=True)  # podría ser el mismo que cliente.medidor, pero lo dejamos por si hay histórico
    ano_medidor = models.IntegerField(null=True, blank=True)
    tipo_medidor = models.CharField(max_length=50, blank=True)
    sello_medidor = models.CharField(max_length=50, blank=True)
    codigo_union_domiciliaria = models.CharField(max_length=50, blank=True)

    # Datos Facturación
    email_recepcion_documento = models.EmailField(blank=True)
    tarifa = models.CharField(max_length=50, blank=True)
    tipo_documento = models.CharField(max_length=50, blank=True)  # Boleta, Factura, etc.
    tipo_servicio = models.CharField(max_length=50, blank=True)   # Agua potable, Alcantarillado, etc.

    def __str__(self):
        return f"Contrato de {self.cliente.nombre}"


# clientes/models.py

from django.db import models
from django.utils import timezone
from decimal import Decimal

class CambioMedidor(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE, related_name='cambios_medidor')
    
    # Medidor retirado
    medidor_retirado_marca = models.CharField(max_length=100, blank=True, null=True)
    medidor_retirado_numero = models.CharField(max_length=100)
    medidor_retirado_anio = models.PositiveSmallIntegerField(blank=True, null=True)
    
    fecha_lectura_anterior = models.DateField(blank=True, null=True)
    lectura_anterior = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    lectura_retiro = models.DecimalField(max_digits=10, decimal_places=2)
    consumo_final = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    
    # Medidor nuevo
    medidor_nuevo_marca = models.CharField(max_length=100, blank=True, null=True)
    medidor_nuevo_numero = models.CharField(max_length=100)
    medidor_nuevo_anio = models.PositiveSmallIntegerField(blank=True, null=True)
    fecha_instalacion = models.DateField()
    lectura_inicial = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Auditoría
    fecha_registro = models.DateTimeField(default=timezone.now)
    usuario = models.CharField(max_length=100, blank=True, null=True)
    periodo = models.CharField(max_length=7, blank=True, null=True)
    
    class Meta:
        ordering = ['-fecha_registro']
        verbose_name = "Cambio de Medidor"
        verbose_name_plural = "Cambios de Medidor"
    
    def save(self, *args, **kwargs):
        # Calcular consumo automáticamente
        if self.lectura_anterior is not None and self.lectura_retiro is not None:
            self.consumo_final = self.lectura_retiro - self.lectura_anterior
        
        # Asignar período automáticamente
        if self.fecha_instalacion and not self.periodo:
            self.periodo = self.fecha_instalacion.strftime('%Y-%m')
        
        # Actualizar medidor en cliente
        if self.medidor_nuevo_numero:
            cliente = self.cliente
            cliente.medidor = self.medidor_nuevo_numero
            cliente.save(update_fields=['medidor'])
            
            # Actualizar también el contrato si existe
            try:
                contrato = cliente.contrato
                if self.medidor_nuevo_marca:
                    contrato.marca_medidor = self.medidor_nuevo_marca
                contrato.numero_medidor = self.medidor_nuevo_numero
                if self.medidor_nuevo_anio:
                    contrato.ano_medidor = self.medidor_nuevo_anio
                contrato.save(update_fields=['marca_medidor', 'numero_medidor', 'ano_medidor'])
            except Exception:
                pass  # Si no tiene contrato, simplemente se ignora
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Cambio medidor {self.cliente.nombre} - {self.fecha_registro.strftime('%d/%m/%Y')}"