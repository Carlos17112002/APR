# lecturas/models.py
from django.db import models
from django.contrib.auth.models import User
import uuid
from empresas.models import Empresa

class LecturaMovil(models.Model):
    ESTADOS_LECTURA = [
        ('pendiente', 'Pendiente'),
        ('cargada', 'Cargada desde App'),
        ('procesada', 'Procesada para Boleta'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    cliente = models.IntegerField()
    fecha_lectura = models.DateField()
    lectura_actual = models.DecimalField(max_digits=10, decimal_places=2)
    lectura_anterior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    consumo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    foto_medidor = models.CharField(max_length=500, null=True, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_LECTURA, default='pendiente')
    fecha_sincronizacion = models.DateTimeField(auto_now_add=True)
    observaciones_app = models.TextField(blank=True)
    usuario_app = models.CharField(max_length=100, blank=True)
    empresa_slug = models.CharField(max_length=50, db_index=True)
    
    # Campos para generación de boleta
    usada_para_boleta = models.BooleanField(default=False)
    boleta_generada = models.ForeignKey('boletas.Boleta', on_delete=models.SET_NULL, null=True, blank=True, related_name='lecturas_asociadas')
    
    class Meta:
        ordering = ['-fecha_lectura', '-fecha_sincronizacion']
        indexes = [
            models.Index(fields=['empresa_slug', 'estado']),
            models.Index(fields=['cliente', 'fecha_lectura']),
        ]
    
    def __str__(self):
         return f"Lectura Cliente ID: {self.cliente} - {self.fecha_lectura} - {self.estado}"
    
    def calcular_consumo(self):
        if self.lectura_anterior:
            self.consumo = self.lectura_actual - self.lectura_anterior
            self.save()
        return self.consumo

from django.db import models
from empresas.models import Empresa

class ConfigAppMovil(models.Model):
    """Configuración específica para la app móvil de cada empresa"""
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, 
                                  related_name='config_app')
    
    # Funcionalidades
    habilitar_mapa = models.BooleanField(default=True)
    habilitar_offline = models.BooleanField(default=True)
    sincronizacion_auto = models.BooleanField(default=True)
    validar_gps = models.BooleanField(default=True)
    
    # Personalización
    mensaje_bienvenida = models.TextField(default='Bienvenido a la app de lecturas')
    mostrar_logo = models.BooleanField(default=True)
    
    # Configuración
    intervalo_sincronizacion = models.IntegerField(default=5, help_text='Minutos')
    max_lecturas_pendientes = models.IntegerField(default=100)
    
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Config App - {self.empresa.nombre}"
    
    # Métodos auxiliares para los templates
    def get_active_features_count(self):
        """Retorna el número de características activas"""
        features = [
            self.habilitar_mapa,
            self.habilitar_offline,
            self.validar_gps,
            self.sincronizacion_auto,
            self.mostrar_logo,
        ]
        return sum(1 for feature in features if feature)
    
    def get_total_features(self):
        """Retorna el número total de características disponibles"""
        return 5  # mapa, offline, gps, auto-sync, logo
    
    def get_features_list(self):
        """Retorna una lista de características con su estado"""
        return [
            {'nombre': 'Mapa', 'activo': self.habilitar_mapa, 'icono': 'bi-map'},
            {'nombre': 'Modo Offline', 'activo': self.habilitar_offline, 'icono': 'bi-wifi-off'},
            {'nombre': 'Validación GPS', 'activo': self.validar_gps, 'icono': 'bi-geo-alt'},
            {'nombre': 'Sincronización Automática', 'activo': self.sincronizacion_auto, 'icono': 'bi-arrow-clockwise'},
            {'nombre': 'Mostrar Logo', 'activo': self.mostrar_logo, 'icono': 'bi-image'},
        ]
    
    def get_sync_interval_display(self):
        """Retorna el intervalo de sincronización formateado"""
        if self.intervalo_sincronizacion < 60:
            return f"{self.intervalo_sincronizacion} minutos"
        else:
            hours = self.intervalo_sincronizacion // 60
            return f"{hours} hora{'s' if hours > 1 else ''}"
    
    def save(self, *args, **kwargs):
        # Validar intervalo de sincronización
        if self.intervalo_sincronizacion < 1:
            self.intervalo_sincronizacion = 1
        elif self.intervalo_sincronizacion > 1440:  # 24 horas
            self.intervalo_sincronizacion = 1440
        
        # Validar máximo de lecturas pendientes
        if self.max_lecturas_pendientes < 1:
            self.max_lecturas_pendientes = 1
        elif self.max_lecturas_pendientes > 1000:
            self.max_lecturas_pendientes = 1000
            
        super().save(*args, **kwargs)
# Tu modelo DispositivoMovil ya existe, solo actualízalo:
class DispositivoMovil(models.Model):
    """Dispositivos móviles autorizados por empresa"""
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='dispositivos')
    identificador = models.CharField(max_length=255, unique=True)
    nombre_dispositivo = models.CharField(max_length=100, default='Dispositivo Móvil')
    token_acceso = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    activo = models.BooleanField(default=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    ultima_conexion = models.DateTimeField(auto_now=True)
    
    # Campos extendidos
    modelo = models.CharField(max_length=100, blank=True)
    sistema_operativo = models.CharField(max_length=50, blank=True)
    version_app = models.CharField(max_length=20, default='1.0.0')
    usuario_asignado = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = "Dispositivo Móvil"
        verbose_name_plural = "Dispositivos Móviles"
    
    def renovar_token(self):
        """Renueva el token de acceso"""
        import uuid
        self.token_acceso = uuid.uuid4()
        self.save()
        return self.token_acceso
    
    def __str__(self):
        return f"{self.nombre_dispositivo} - {self.empresa.nombre}"