from django.db import models
from django.utils import timezone
from empresas.models import Empresa

# contabilidad/models.py
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

# contabilidad/models.py
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

class AFP(models.Model):
    # Opciones para régimen previsional
    REGIMEN_CHOICES = [
        ('AFP', 'AFP'),
        ('INP', 'INP'),
        ('SIP', 'SIP'),
    ]
    
    # Datos predeterminados de AFP
    DATOS_AFP = [
        # Código, Nombre, Cotiz Empleado, Previred, Régimen, DT
        ('CUMP', 'Cuprum', Decimal('11.44'), '03', 'AFP', '13'),
        ('EMPA', 'Empart.', Decimal('21.84'), '0101', 'INP', '85'),
        ('HABI', 'Habitat', Decimal('11.27'), '05', 'AFP', '14'),
        ('MODE', 'Modelo', Decimal('10.58'), '34', 'AFP', '103'),
        ('PROV', 'Provida', Decimal('11.45'), '08', 'AFP', '6'),
        ('PVIT', 'Plan Vital', Decimal('11.16'), '29', 'AFP', '11'),
        ('SIN', 'SIN AFP', Decimal('0.00'), '00', 'SIP', '100'),
        ('SSS', 'Servicio Seguro social', Decimal('18.84'), '09', 'INP', '105'),
        ('STMA', 'Capital', Decimal('11.44'), '33', 'AFP', '31'),
        ('UNO', 'UNO', Decimal('10.46'), '35', 'AFP', '19'),
    ]
    
    codigo = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name="Código AFP"
    )
    nombre = models.CharField(
        max_length=100, 
        verbose_name="Nombre"
    )
    cotizacion_obligatoria = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="Cotización Obligatoria (%)",
        default=0.00
    )
    cotizacion_empleador = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="Cotización Empleador (%)",
        default=2.50
    )
    sis = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="Seguro Invalidez y Sobrevivencia (%)",
        default=1.15
    )
    codigo_previred = models.CharField(
        max_length=10, 
        verbose_name="Código Previred"
    )
    regimen = models.CharField(
        max_length=3, 
        choices=REGIMEN_CHOICES, 
        default='AFP',
        verbose_name="Régimen Previsional"
    )
    codigo_dt = models.CharField(
        max_length=10, 
        verbose_name="Código Dirección del Trabajo"
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )
    
    class Meta:
        verbose_name = "AFP"
        verbose_name_plural = "AFP"
        ordering = ['codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @classmethod
    def crear_datos_predeterminados(cls):
        """Crea todos los datos predeterminados de AFP"""
        for codigo, nombre, cotizacion, previred, regimen, dt in cls.DATOS_AFP:
            # Determinar valores según régimen
            cotiz_empleador = Decimal('2.50') if regimen == 'AFP' else Decimal('0.00')
            sis_valor = Decimal('1.15') if regimen == 'AFP' else Decimal('0.00')
            
            cls.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': nombre,
                    'cotizacion_obligatoria': cotizacion,
                    'cotizacion_empleador': cotiz_empleador,
                    'sis': sis_valor,
                    'codigo_previred': previred,
                    'regimen': regimen,
                    'codigo_dt': dt,
                    'activa': True
                }
            )
    
    def clean(self):
        """Validaciones"""
        if self.regimen in ['INP', 'SIP']:
            if self.cotizacion_empleador > 0:
                raise ValidationError("INP/SIP no tienen cotización empleador")
            if self.sis > 0:
                raise ValidationError("INP/SIP incluyen seguro en su cotización")

class AFPEmpresa(models.Model):
    """Relación entre empresa y AFP disponible"""
    empresa = models.ForeignKey(
        Empresa, 
        on_delete=models.CASCADE,
        related_name='afp_disponibles'
    )
    afp = models.ForeignKey(
        AFP, 
        on_delete=models.CASCADE,
        related_name='empresas'
    )
    activa = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['empresa', 'afp']
        verbose_name = "AFP por Empresa"
        verbose_name_plural = "AFP por Empresas"
    
    def __str__(self):
        return f"{self.empresa.nombre} - {self.afp.nombre}"


class ValorUF(models.Model):
    """Almacena valores históricos de la UF"""
    fecha = models.DateField(unique=True, verbose_name="Fecha valor")
    valor = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        verbose_name="Valor UF"
    )
    fuente = models.CharField(
        max_length=50, 
        default='SII',
        verbose_name="Fuente del valor"
    )
    
    class Meta:
        verbose_name = "Valor UF"
        verbose_name_plural = "Valores UF"
        ordering = ['-fecha']
    
    def __str__(self):
        return f"UF {self.fecha}: ${self.valor:,}"


class ValorUTM(models.Model):
    """Almacena valores históricos de la UTM"""
    mes = models.PositiveIntegerField(verbose_name="Mes")
    anio = models.PositiveIntegerField(verbose_name="Año")
    valor = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        verbose_name="Valor UTM"
    )
    fuente = models.CharField(
        max_length=50, 
        default='SII',
        verbose_name="Fuente del valor"
    )
    
    class Meta:
        verbose_name = "Valor UTM"
        verbose_name_plural = "Valores UTM"
        unique_together = ['mes', 'anio']
        ordering = ['-anio', '-mes']
    
    def __str__(self):
        return f"UTM {self.mes}/{self.anio}: ${self.valor:,}"

# contabilidad/models.py - Añade este modelo
class Isapre(models.Model):
    # Opciones
    TIPO_CHOICES = [
        ('ISAPRE', 'Isapre'),
        ('FONASA', 'Fonasa'),
        ('SIN', 'Sin Isapre'),
    ]
    
    ESTADO_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('INACTIVA', 'Inactiva'),
        ('NO_VIGENTE', 'No Vigente'),
    ]
    
    # Datos predeterminados de Isapres
    DATOS_ISAPRE = [
        # Código, Nombre, Cotiz, Previred, DT, Tipo, Estado
        ('BANM', 'Banmedica', Decimal('7.00'), '01', '3', 'ISAPRE', 'ACTIVA'),
        ('BEST', 'BANCO ESTADO', Decimal('7.00'), '12', '40', 'ISAPRE', 'ACTIVA'),
        ('CMN', 'Colmena', Decimal('7.00'), '04', '4', 'ISAPRE', 'ACTIVA'),
        ('cons', 'Consalud', Decimal('7.00'), '02', '9', 'ISAPRE', 'ACTIVA'),
        ('CRZB', 'CRUZ BLANCA', Decimal('7.00'), '05', '1', 'ISAPRE', 'ACTIVA'),
        ('ESE', 'ESENCIAL', Decimal('7.00'), '28', '44', 'ISAPRE', 'ACTIVA'),
        ('fona', 'Fonasa', Decimal('7.00'), '07', '102', 'FONASA', 'ACTIVA'),
        ('ISAL', 'ISAPRE ISALUD', Decimal('7.00'), '11', '5', 'ISAPRE', 'ACTIVA'),
        ('MAS2', 'NUEVA MASVIDA', Decimal('7.00'), '10', '43', 'ISAPRE', 'ACTIVA'),
        ('masv', 'NO VIGENTE Mas Vida', Decimal('7.00'), '17', '43', 'ISAPRE', 'NO_VIGENTE'),
        ('SIN', 'SIN ISAPRE', Decimal('0.00'), '00', '102', 'SIN', 'ACTIVA'),
        ('VID3', 'VIDA TRES', Decimal('7.00'), '03', '12', 'ISAPRE', 'ACTIVA'),
    ]
    
    codigo = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name="Código Isapre"
    )
    nombre = models.CharField(
        max_length=100, 
        verbose_name="Nombre Isapre"
    )
    cotizacion_obligatoria = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        verbose_name="Cotización Obligatoria (%)",
        default=7.00
    )
    codigo_previred = models.CharField(
        max_length=10, 
        verbose_name="Código Previsión"
    )
    codigo_dt = models.CharField(
        max_length=10, 
        verbose_name="Código Dirección del Trabajo"
    )
    tipo = models.CharField(
        max_length=10, 
        choices=TIPO_CHOICES, 
        default='ISAPRE',
        verbose_name="Tipo"
    )
    estado = models.CharField(
        max_length=10, 
        choices=ESTADO_CHOICES, 
        default='ACTIVA',
        verbose_name="Estado"
    )
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa en sistema"
    )
    
    class Meta:
        verbose_name = "Isapre"
        verbose_name_plural = "Isapres"
        ordering = ['codigo']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    
    @classmethod
    def crear_datos_predeterminados(cls):
        """Crea todos los datos predeterminados de Isapre"""
        for codigo, nombre, cotizacion, previred, dt, tipo, estado in cls.DATOS_ISAPRE:
            activa = estado == 'ACTIVA'
            cls.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': nombre,
                    'cotizacion_obligatoria': cotizacion,
                    'codigo_previred': previred,
                    'codigo_dt': dt,
                    'tipo': tipo,
                    'estado': estado,
                    'activa': activa
                }
            )
    
# contabilidad/models.py - Añade este modelo
from django.db import models
from django.core.exceptions import ValidationError
from datetime import datetime

class Periodo(models.Model):
    """
    Modelo para gestionar períodos de liquidación
    """
    # Opciones para estado
    ESTADO_CHOICES = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
        ('PROCESADO', 'Procesado'),
        ('CERRADO', 'Cerrado'),
    ]
    
    mes = models.PositiveIntegerField(
        verbose_name="Mes",
        choices=[(i, i) for i in range(1, 13)]
    )
    anio = models.PositiveIntegerField(
        verbose_name="Año",
        default=2025
    )
    fecha_inicio = models.DateField(verbose_name="Fecha Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha Fin")
    uf = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        verbose_name="Valor UF"
    )
    utm = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        verbose_name="Valor UTM"
    )
    dias_habiles = models.PositiveIntegerField(
        verbose_name="Días Hábitos",
        default=22
    )
    dias_no_habiles = models.PositiveIntegerField(
        verbose_name="Días Domingo y Festivos",
        default=9
    )
    factor_actualizacion = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        verbose_name="Factor de Actualización",
        default=1.0000
    )
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='ACTIVO',
        verbose_name="Estado"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    # Relación con empresa (si es necesario)
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='periodos',
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Período"
        verbose_name_plural = "Períodos"
        ordering = ['-anio', '-mes']
        unique_together = ['mes', 'anio', 'empresa']
    
    def __str__(self):
        meses = [
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        nombre_mes = meses[self.mes - 1]
        return f"{nombre_mes} {self.anio}"
    
    def clean(self):
        # Validar que las fechas sean consistentes
        if self.fecha_inicio >= self.fecha_fin:
            raise ValidationError({
                'fecha_fin': 'La fecha fin debe ser posterior a la fecha inicio.'
            })
        
        # Validar que el mes coincida con las fechas
        if self.fecha_inicio.month != self.mes or self.fecha_fin.month != self.mes:
            raise ValidationError({
                'mes': 'El mes debe coincidir con las fechas de inicio y fin.'
            })
        
        # Validar que el año coincida
        if self.fecha_inicio.year != self.anio or self.fecha_fin.year != self.anio:
            raise ValidationError({
                'anio': 'El año debe coincidir con las fechas de inicio y fin.'
            })
        
        # Validar valores numéricos positivos
        if self.uf <= 0 or self.utm <= 0:
            raise ValidationError({
                'uf': 'Los valores de UF y UTM deben ser positivos.'
            })
        
        if self.dias_habiles <= 0 or self.dias_no_habiles < 0:
            raise ValidationError({
                'dias_habiles': 'Los días deben ser valores positivos.'
            })
    
    @property
    def nombre_mes(self):
        """Devuelve el nombre del mes"""
        meses = [
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ]
        return meses[self.mes - 1]
    
    @property
    def mes_anio(self):
        """Devuelve mes/año formateado"""
        return f"{self.nombre_mes}/{self.anio}"
    
    @property
    def total_dias(self):
        """Calcula el total de días del período"""
        return self.dias_habiles + self.dias_no_habiles
    
    @property
    def periodo_actual(self):
        """Verifica si es el período actual"""
        hoy = datetime.now()
        return self.fecha_inicio <= hoy.date() <= self.fecha_fin

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date

class Trabajador(models.Model):
    # Relaciones
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='trabajadores')
    usuario_creacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trabajadores_creados')
    usuario_modificacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajadores_modificados')
    # --- OTROS CAMPOS (agregar después de los existentes) ---
    profesion = models.CharField(max_length=100, blank=True, verbose_name="Profesión")
    horario = models.CharField(max_length=100, blank=True, verbose_name="Horario de trabajo")
    tipo_cuenta = models.CharField(max_length=50, blank=True, verbose_name="Tipo de cuenta")
    forma_pago = models.CharField(max_length=50, blank=True, verbose_name="Forma de pago")
    estado_civil = models.CharField(max_length=20, blank=True, verbose_name="Estado civil")
    afp_trabajo_pesado = models.BooleanField(default=False, verbose_name="Trabajo pesado (AFP)")
    gratificacion_legal = models.BooleanField(default=False, verbose_name="Gratificación legal")
    # --- DATOS PERSONALES ---
    rut = models.CharField(max_length=12, unique=True, help_text="Formato: 12345678-9")
    dv = models.CharField(max_length=1)
    nombres = models.CharField(max_length=100)
    apellido_paterno = models.CharField(max_length=100)
    apellido_materno = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=1, choices=[('M', 'Masculino'), ('F', 'Femenino')], blank=True)
    nacionalidad = models.CharField(max_length=50, default='Chilena')
    es_chileno = models.BooleanField(default=True)
    
    # Contacto
    direccion = models.CharField(max_length=200, blank=True)
    comuna = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    
    # Laborales
    cargo = models.CharField(max_length=100, blank=True)
    centro_costo_codigo = models.CharField(max_length=20, blank=True)
    centro_costo_nombre = models.CharField(max_length=100, blank=True)
    
    # --- SUELDO ---
    sueldo_mensual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sueldo_hora = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sueldo_mensual_uf = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    sueldo_diario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sueldo_empresarial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # --- PREVISIÓN ---
    # Salud
    isapre = models.CharField(max_length=100, blank=True)
    cotizacion_salud_pesos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cotizacion_salud_uf = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    porcentaje_salud_colectivo = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fun_isapre = models.CharField(max_length=100, blank=True)
    
    # AFP
    afp = models.CharField(max_length=100, blank=True)
    cuenta_2_afp = models.CharField(max_length=50, blank=True)
    seguro_cesantia_trabajador = models.DecimalField(max_digits=5, decimal_places=2, default=2.4)
    seguro_cesantia_empleador = models.DecimalField(max_digits=5, decimal_places=2, default=0.8)
    
    # APV
    apv = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pago_apv = models.CharField(max_length=20, choices=[
        ('voluntario', 'Voluntario'),
        ('obligatorio', 'Obligatorio')
    ], blank=True)
    apv_uf = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    apv2 = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pago_apv2 = models.CharField(max_length=20, choices=[
        ('voluntario', 'Voluntario'),
        ('obligatorio', 'Obligatorio')
    ], blank=True)
    apv2_uf = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    # APV Colectivo
    empresa_apv_colectivo = models.CharField(max_length=100, blank=True)
    apv_colectivo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    apv_uf_colectivo = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    porcentaje_trabajador_apvc = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    forma_pago_apvc = models.CharField(max_length=20, blank=True)
    
    # Otros previsionales
    tipo_trabajador = models.CharField(max_length=50, choices=[
        ('dependiente', 'Dependiente'),
        ('independiente', 'Independiente'),
        ('agricola', 'Agrícola')
    ], default='dependiente')
    
    segunda_caja = models.CharField(max_length=100, blank=True)
    prestamo_2da_caja = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prestamo_solidario = models.BooleanField(default=False)
    prestamo_caja = models.BooleanField(default=False)
    
    numero_cargas = models.IntegerField(default=0)
    seguro_accidentes = models.BooleanField(default=False)
    
    # Tipo de impuesto
    tipo_impuesto = models.CharField(max_length=20, choices=[
        ('global', 'Global Complementario'),
        ('segunda', 'Segunda Categoría')
    ], default='global')
    
    # Fechas previsionales
    fecha_primera_afiliacion = models.DateField(null=True, blank=True)
    es_afiliado_voluntario = models.BooleanField(default=False)
    
    # --- CONTRATO ---
    fecha_contrato = models.DateField(null=True, blank=True)
    fecha_termino_contrato = models.DateField(null=True, blank=True)
    clausula_termino = models.TextField(blank=True)
    tipo_jornada = models.CharField(max_length=50, choices=[
        ('completa', 'Jornada Completa'),
        ('parcial', 'Jornada Parcial'),
        ('turnos', 'Turnos')
    ], default='completa')
    # En models.py, dentro de la clase Trabajador, después de fecha_contrato, agrega:

    TIPO_CONTRATO_CHOICES = [
        ('INDEFINIDO', 'Indefinido'),
        ('FIJO', 'Plazo Fijo'),
        ('OBRA', 'Por Obra'),
        ('CASA_PARTICULAR', 'Casa Particular'),
    ]
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES, blank=True, null=True)

    # Beneficios
    colacion_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    colacion_diaria = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    movilizacion_mensual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    movilizacion_diaria = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # --- HORAS EXTRA ---
    horas_trabajadas = models.DecimalField(max_digits=6, decimal_places=2, default=45)
    dias_semana_parttime = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(7)])
    usar_sueldo_minimo = models.BooleanField(default=False)
    factor_especial_horas_extra = models.DecimalField(max_digits=4, decimal_places=2, default=1.5)
    
    # --- OTROS ---
    porcentaje_trabajo_pesado_trabajador = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    porcentaje_trabajo_pesado_empleador = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    persona_discapacidad = models.BooleanField(default=False)
    pension_invalidez = models.BooleanField(default=False)
    
    dias_vacaciones_progresivas = models.IntegerField(default=0)
    anios_iniciar_vacaciones_prog = models.IntegerField(default=3)
    
    tecnico_extranjero_exencion = models.BooleanField(default=False)
    tiene_ficha_covid = models.BooleanField(default=False)
    
    # Datos bancarios
    banco = models.CharField(max_length=100, blank=True)
    numero_cuenta = models.CharField(max_length=50, blank=True)
    
    es_zona_extrema = models.BooleanField(default=False)
    es_trabajador_agricola = models.BooleanField(default=False)
    
    # --- METADATOS ---
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    esta_activo = models.BooleanField(default=True)
    
    # Campos calculados
    nombre_completo = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = "Trabajador"
        verbose_name_plural = "Trabajadores"
        ordering = ['apellido_paterno', 'apellido_materno', 'nombres']
        unique_together = ['empresa', 'rut']
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.rut})"
    
    def save(self, *args, **kwargs):
        # Calcular nombre completo
        self.nombre_completo = f"{self.nombres} {self.apellido_paterno} {self.apellido_materno}".strip()
        
        # Formatear RUT si es necesario
        if self.rut and '-' not in self.rut:
            rut_num = self.rut[:-1]
            dv = self.rut[-1].upper()
            self.rut = f"{rut_num}-{dv}"
            self.dv = dv
        
        super().save(*args, **kwargs)
    
    def get_edad(self):
        if self.fecha_nacimiento:
            today = date.today()
            return today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        return None
    
    @property
    def tiene_contrato_vigente(self):
        if not self.fecha_contrato:
            return False
        if not self.fecha_termino_contrato:
            return True
        return date.today() <= self.fecha_termino_contrato

# Añade estos modelos a tu archivo models.py

class Region(models.Model):
    """Modelo para regiones de Chile"""
    codigo = models.CharField(max_length=5, unique=True, verbose_name="Código de Región")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de Región")
    orden = models.IntegerField(default=0, verbose_name="Orden de visualización")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    
    class Meta:
        verbose_name = "Región"
        verbose_name_plural = "Regiones"
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Comuna(models.Model):
    """Modelo para comunas de Chile"""
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name='comunas')
    codigo = models.CharField(max_length=10, verbose_name="Código de Comuna")
    nombre = models.CharField(max_length=100, verbose_name="Nombre de Comuna")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    
    class Meta:
        verbose_name = "Comuna"
        verbose_name_plural = "Comunas"
        ordering = ['nombre']
        unique_together = ['codigo', 'region']
    
    def __str__(self):
        return f"{self.nombre} ({self.region.nombre})"


def cargar_regiones_comunas():
    """
    Carga todas las regiones y comunas de Chile en la base de datos.
    Si ya existen, no las duplica.
    """
    regiones_data = [
        {'codigo': 'XV', 'nombre': 'Arica y Parinacota', 'orden': 1},
        {'codigo': 'I', 'nombre': 'Tarapacá', 'orden': 2},
        {'codigo': 'II', 'nombre': 'Antofagasta', 'orden': 3},
        {'codigo': 'III', 'nombre': 'Atacama', 'orden': 4},
        {'codigo': 'IV', 'nombre': 'Coquimbo', 'orden': 5},
        {'codigo': 'V', 'nombre': 'Valparaíso', 'orden': 6},
        {'codigo': 'RM', 'nombre': 'Metropolitana de Santiago', 'orden': 7},
        {'codigo': 'VI', 'nombre': "Libertador General Bernardo O'Higgins", 'orden': 8},
        {'codigo': 'VII', 'nombre': 'Maule', 'orden': 9},
        {'codigo': 'VIII', 'nombre': 'Biobío', 'orden': 10},
        {'codigo': 'IX', 'nombre': 'La Araucanía', 'orden': 11},
        {'codigo': 'XIV', 'nombre': 'Los Ríos', 'orden': 12},
        {'codigo': 'X', 'nombre': 'Los Lagos', 'orden': 13},
        {'codigo': 'XI', 'nombre': 'Aysén del General Carlos Ibáñez del Campo', 'orden': 14},
        {'codigo': 'XII', 'nombre': 'Magallanes y de la Antártica Chilena', 'orden': 15},
        {'codigo': 'XVI', 'nombre': 'Ñuble', 'orden': 16},
    ]
    
    comunas_data = {
        'XV': ['Arica', 'Camarones', 'Putre', 'General Lagos'],
        'I': ['Iquique', 'Alto Hospicio', 'Pozo Almonte', 'Camiña', 'Colchane', 'Huara', 'Pica'],
        'II': ['Antofagasta', 'Mejillones', 'Sierra Gorda', 'Taltal', 'Calama', 'Ollagüe', 'San Pedro de Atacama', 'Tocopilla', 'María Elena'],
        'III': ['Copiapó', 'Caldera', 'Tierra Amarilla', 'Chañaral', 'Diego de Almagro', 'Vallenar', 'Alto del Carmen', 'Freirina', 'Huasco'],
        'IV': [
            'La Serena', 'Coquimbo', 'Andacollo', 'La Higuera', 'Paiguano', 'Vicuña',
            'Illapel', 'Canela', 'Los Vilos', 'Salamanca',
            'Ovalle', 'Combarbalá', 'Monte Patria', 'Punitaqui', 'Río Hurtado'
        ],
        'V': [
            'Valparaíso', 'Casablanca', 'Concón', 'Juan Fernández', 'Puchuncaví', 'Quintero', 'Viña del Mar',
            'Isla de Pascua',
            'Los Andes', 'Calle Larga', 'Rinconada', 'San Esteban',
            'La Ligua', 'Cabildo', 'Papudo', 'Petorca', 'Zapallar',
            'Quillota', 'Calera', 'Hijuelas', 'La Cruz', 'Nogales',
            'San Antonio', 'Algarrobo', 'Cartagena', 'El Quisco', 'El Tabo', 'Santo Domingo',
            'San Felipe', 'Catemu', 'Llaillay', 'Panquehue', 'Putaendo', 'Santa María',
            'Limache', 'Olmué', 'Villa Alemana', 'Quilpué'
        ],
        'RM': [
            'Santiago', 'Cerrillos', 'Cerro Navia', 'Conchalí', 'El Bosque', 'Estación Central', 'Huechuraba',
            'Independencia', 'La Cisterna', 'La Florida', 'La Granja', 'La Pintana', 'La Reina', 'Las Condes',
            'Lo Barnechea', 'Lo Espejo', 'Lo Prado', 'Macul', 'Maipú', 'Ñuñoa', 'Pedro Aguirre Cerda',
            'Peñalolén', 'Providencia', 'Pudahuel', 'Quilicura', 'Quinta Normal', 'Recoleta', 'Renca',
            'San Joaquín', 'San Miguel', 'San Ramón', 'Vitacura',
            'Puente Alto', 'Pirque', 'San José de Maipo',
            'Colina', 'Lampa', 'Til Til',
            'San Bernardo', 'Buin', 'Calera de Tango', 'Paine',
            'Melipilla', 'Alhué', 'Curacaví', 'María Pinto', 'San Pedro',
            'Talagante', 'El Monte', 'Isla de Maipo', 'Padre Hurtado', 'Peñaflor'
        ],
        'VI': [
            'Rancagua', 'Codegua', 'Coinco', 'Coltauco', 'Doñihue', 'Graneros', 'Las Cabras', 'Machalí', 'Malloa',
            'Mostazal', 'Olivar', 'Peumo', 'Pichidegua', 'Quinta de Tilcoco', 'Rengo', 'Requínoa', 'San Vicente',
            'Pichilemu', 'La Estrella', 'Litueche', 'Marchihue', 'Navidad', 'Paredones',
            'San Fernando', 'Chépica', 'Chimbarongo', 'Lolol', 'Nancagua', 'Palmilla', 'Peralillo', 'Placilla',
            'Pumanque', 'Santa Cruz'
        ],
        'VII': [
            'Talca', 'Constitución', 'Curepto', 'Empedrado', 'Maule', 'Pelarco', 'Pencahue', 'Río Claro', 'San Clemente', 'San Rafael',
            'Cauquenes', 'Chanco', 'Pelluhue',
            'Curicó', 'Hualañé', 'Licantén', 'Molina', 'Rauco', 'Romeral', 'Sagrada Familia', 'Teno', 'Vichuquén',
            'Linares', 'Colbún', 'Longaví', 'Parral', 'Retiro', 'San Javier', 'Villa Alegre', 'Yerbas Buenas'
        ],
        'VIII': [
            'Concepción', 'Coronel', 'Chiguayante', 'Florida', 'Hualpén', 'Hualqui', 'Lota', 'Penco', 'San Pedro de la Paz', 'Santa Juana', 'Talcahuano', 'Tomé',
            'Lebu', 'Arauco', 'Cañete', 'Contulmo', 'Curanilahue', 'Los Álamos', 'Tirúa',
            'Los Ángeles', 'Antuco', 'Cabrero', 'Laja', 'Mulchén', 'Nacimiento', 'Negrete', 'Quilaco', 'Quilleco', 'San Rosendo', 'Santa Bárbara', 'Tucapel', 'Yumbel', 'Alto Biobío',
            'Chillán', 'Bulnes', 'Cobquecura', 'Coelemu', 'Coihueco', 'Chillán Viejo', 'El Carmen', 'Ninhue', 'Ñiquén', 'Pemuco', 'Pinto', 'Portezuelo', 'Quillón', 'Quirihue', 'Ránquil', 'San Carlos', 'San Fabián', 'San Ignacio', 'San Nicolás', 'Treguaco', 'Yungay'
        ],
        'IX': [
            'Temuco', 'Carahue', 'Cunco', 'Curarrehue', 'Freire', 'Galvarino', 'Gorbea', 'Lautaro', 'Loncoche', 'Melipeuco', 'Nueva Imperial', 'Padre Las Casas', 'Perquenco', 'Pitrufquén', 'Pucón', 'Saavedra', 'Teodoro Schmidt', 'Toltén', 'Vilcún', 'Villarrica', 'Cholchol',
            'Angol', 'Collipulli', 'Curacautín', 'Ercilla', 'Lonquimay', 'Los Sauces', 'Lumaco', 'Purén', 'Renaico', 'Traiguén', 'Victoria'
        ],
        'XIV': [
            'Valdivia', 'Corral', 'Lanco', 'Los Lagos', 'Máfil', 'Mariquina', 'Paillaco', 'Panguipulli',
            'La Unión', 'Futrono', 'Lago Ranco', 'Río Bueno'
        ],
        'X': [
            'Puerto Montt', 'Calbuco', 'Cochamó', 'Fresia', 'Frutillar', 'Los Muermos', 'Llanquihue', 'Maullín', 'Puerto Varas',
            'Castro', 'Ancud', 'Chonchi', 'Curaco de Vélez', 'Dalcahue', 'Puqueldón', 'Queilén', 'Quellón', 'Quemchi', 'Quinchao',
            'Osorno', 'Puerto Octay', 'Purranque', 'Puyehue', 'Río Negro', 'San Juan de la Costa', 'San Pablo',
            'Chaitén', 'Futaleufú', 'Hualaihué', 'Palena'
        ],
        'XI': [
            'Coyhaique', 'Lago Verde', 'Aysén', 'Cisnes', 'Guaitecas', 'Cochrane', 'O\'Higgins', 'Tortel', 'Chile Chico', 'Río Ibáñez'
        ],
        'XII': [
            'Punta Arenas', 'Laguna Blanca', 'Río Verde', 'San Gregorio', 'Cabo de Hornos', 'Antártica', 'Porvenir', 'Primavera', 'Timaukel', 'Natales', 'Torres del Paine'
        ],
        'XVI': [
            'Chillán', 'Bulnes', 'Cobquecura', 'Coelemu', 'Coihueco', 'Chillán Viejo', 'El Carmen', 'Ninhue', 'Ñiquén', 'Pemuco', 'Pinto', 'Portezuelo', 'Quillón', 'Quirihue', 'Ránquil', 'San Carlos', 'San Fabián', 'San Ignacio', 'San Nicolás', 'Treguaco', 'Yungay'
        ],
    }
    
    # Crear regiones
    for region_info in regiones_data:
        region, created = Region.objects.get_or_create(
            codigo=region_info['codigo'],
            defaults={
                'nombre': region_info['nombre'],
                'orden': region_info['orden']
            }
        )
        
        # Crear comunas para esta región
        if region.codigo in comunas_data:
            for comuna_nombre in comunas_data[region.codigo]:
                # Crear código simple para la comuna (primeras letras sin espacios)
                codigo_comuna = comuna_nombre.upper().replace(' ', '_')[:10]
                Comuna.objects.get_or_create(
                    region=region,
                    nombre=comuna_nombre,
                    defaults={'codigo': codigo_comuna}
                )
    
# contabilidad/models.py
from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils import timezone

class Liquidacion(models.Model):
    """
    Modelo completo para almacenar liquidaciones de sueldo
    Incluye todos los campos del tercer template
    """
    
    # Estados de la liquidación
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('GENERADA', 'Generada'),
        ('PROCESADA', 'Procesada'),
        ('CERRADA', 'Cerrada'),
        ('ANULADA', 'Anulada'),
        ('PAGADA', 'Pagada'),
    ]
    
    # --- RELACIONES PRINCIPALES ---
    periodo = models.ForeignKey(
        'Periodo',
        on_delete=models.CASCADE,
        related_name='liquidaciones',
        verbose_name="Período de Liquidación"
    )
    
    trabajador = models.ForeignKey(
        'Trabajador',
        on_delete=models.CASCADE,
        related_name='liquidaciones',
        verbose_name="Trabajador"
    )
    
    # --- CONFIGURACIÓN DE LA LIQUIDACIÓN ---
    haberes_colegio = models.BooleanField(
        default=False,
        verbose_name="Haberes Colegio"
    )
    
    glosa = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Glosa de Liquidación",
        help_text="Ej: Liquidación Sueldo, Finiquito, etc."
    )
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='BORRADOR',
        verbose_name="Estado"
    )
    
    # --- HABERES: DÍAS Y HORAS ---
    dias_trabajados = models.PositiveIntegerField(
        default=0,
        verbose_name="Días Trabajados"
    )
    
    horas_trabajadas = models.PositiveIntegerField(
        default=0,
        verbose_name="Horas Trabajadas"
    )
    
    horas_atraso = models.PositiveIntegerField(
        default=0,
        verbose_name="Horas Atraso"
    )
    
    dias_habiles_trabajados = models.PositiveIntegerField(
        default=0,
        verbose_name="Días Hábiles Trabajados"
    )
    
    # --- SUELDO ---
    sueldo_diario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Sueldo Diario"
    )
    
    sueldo_mensual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Sueldo Mensual"
    )
    
    atraso = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Monto Atraso"
    )
    
    # --- HORAS EXTRA ---
    horas_extra_50 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name="Horas Extra 50%"
    )
    
    horas_extra_100 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name="Horas Extra 100%"
    )
    porcentaje_gratificacion = models.DecimalField(max_digits=5, decimal_places=2, default=25.00)
    base_gratificacion = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    horas_extra_150 = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        verbose_name="Horas Extra 150%"
    )
    
    monto_horas_extra = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Monto Horas Extra"
    )
    
    total_horas_extra = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Horas Extra"
    )
    
    # --- COMISIONES Y CARGOS ---
    total_comision = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Comisión"
    )
    
    horas_cargo_domingo = models.PositiveIntegerField(
        default=0,
        verbose_name="Horas Cargo Domingo"
    )
    
    monto_cargo_domingo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Monto Cargo Domingo"
    )
    
    # --- DÍAS DEL PERÍODO ---
    dias_habiles = models.PositiveIntegerField(
        default=0,
        verbose_name="Días Hábiles"
    )
    
    dias_domingo_festivos = models.PositiveIntegerField(
        default=0,
        verbose_name="Días Domingo y Festivos"
    )
    
    # --- UTILIDADES Y SEMANA CORRIDA ---
    utilidades = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Utilidades"
    )
    
    total_haberes_variables = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Haberes Variables"
    )
    
    semana_corrida = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Semana Corrida"
    )
    
    total_semana_corrida = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Semana Corrida"
    )
    
    # --- GRATIFICACIÓN ---
    TIPO_GRATIFICACION_CHOICES = [
        ('CON_TOPE', 'Con Tope'),
        ('SIN_TOPE', 'Sin Tope'),
        ('MONTO_FIJO', 'Monto Fijo'),
    ]
    
    tipo_gratificacion = models.CharField(
        max_length=20,
        choices=TIPO_GRATIFICACION_CHOICES,
        default='CON_TOPE',
        verbose_name="Tipo de Gratificación"
    )
    
    monto_gratificacion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Monto Gratificación"
    )
    
    # --- BONOS ---
    bonos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Bonos"
    )
    
    total_imponible = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Imponible"
    )
    
    # --- CARGAS FAMILIARES ---
    numero_cargas = models.IntegerField(
        default=0,
        verbose_name="Número de Cargas"
    )
    
    promedio_ingresos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Promedio de Ingresos"
    )
    
    numero_cargas_maternales = models.IntegerField(
        default=0,
        verbose_name="Número Cargas Maternales"
    )
    
    retroactiva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Retroactiva"
    )
    
    # --- ASIGNACIONES ---
    colacion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Colación"
    )
    
    movilizacion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Movilización"
    )
    
    # --- OTROS BONOS ---
    nombre_otro_bono_1 = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nombre Otro Bono 1"
    )
    
    valor_otro_bono_1 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valor Otro Bono 1"
    )
    
    nombre_otro_bono_2 = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nombre Otro Bono 2"
    )
    
    valor_otro_bono_2 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valor Otro Bono 2"
    )
    
    # --- DESCUENTOS: AFP ---
    afp_nombre = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="AFP"
    )
    
    porcentaje_afp = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="% AFP"
    )
    
    base_afp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Base AFP"
    )
    
    cotizacion_afp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Cotización AFP"
    )
    
    cuenta_2_afp = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Cuenta 2 AFP"
    )
    
    # --- AFC Y TRABAJO PESADO ---
    base_afc = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Base AFC"
    )
    tipo_contrato = models.CharField(
    max_length=20,
    choices=[
        ('indefinido', 'Contrato Indefinido'),
        ('plazo_fijo', 'Plazo Fijo'),
        ('obra', 'Obra o Faena'),
        ('casa_particular', 'Trabajador de Casa Particular'),
        ('independiente', 'Trabajador Independiente'),
    ],
    default='indefinido',
    verbose_name="Tipo de Contrato"
    )

    fecha_contrato = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Contrato"
    )

    porcentaje_afc_trabajador = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="% AFC Trabajador"
    )

    porcentaje_afc_empleador = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="% AFC Empleador"
    )
    
    porcentaje_trabajo_pesado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="% Trabajo Pesado"
    )
    
    cotizacion_afc = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Cotización AFC"
    )
    
    # --- APV ---
    apv = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="APV"
    )
    
    apv2 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="APV2"
    )
    
    afiliado_voluntario = models.BooleanField(
        default=False,
        verbose_name="Afiliado Voluntario"
    )
    
    apv_colectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="APV Colectivo"
    )
    
    # --- SALUD (ISAPRE) ---
    isapre_nombre = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Isapre"
    )
    
    cotizacion_salud_pactada = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Cotización Salud Pactada %"
    )
    
    cotizacion_salud_obligatoria = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=7.00,
        verbose_name="Cotización Salud Obligatoria %"
    )
    
    diferencia_isapre = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Diferencia Isapre"
    )
    
    total_prevision = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Previsión"
    )
    
    # --- IMPUESTO A LA RENTA ---
    base_impuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Base Impuesto"
    )
    
    anticipo_impuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Anticipo Impuesto"
    )
    
    cuota_impuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Cuota Impuesto"
    )
    
    # --- PRÉSTAMOS Y SEGUROS ---
    prestamo_ccaf = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Préstamo CCAF"
    )
    
    prestamo_solidario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Préstamo Solidario"
    )
    
    programa_ahorro_leasing = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Programa Ahorro/Leasing"
    )
    
    seguro_ccaf = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Seguro CCAF"
    )
    
    cuota_ccaf = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Cuota CCAF"
    )
    
    prestamo_empresa = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Préstamo Empresa"
    )
    
    # --- OTROS DESCUENTOS ---
    nombre_otro_descuento_1 = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nombre Otro Descuento 1"
    )
    
    valor_otro_descuento_1 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valor Otro Descuento 1"
    )
    
    nombre_otro_descuento_2 = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nombre Otro Descuento 2"
    )
    
    valor_otro_descuento_2 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Valor Otro Descuento 2"
    )
    
    # --- INFORMACIÓN ADICIONAL ---
    centro_costo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Centro de Costo"
    )
    
    costo_empleador = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Costo Empleador"
    )
    
    afc_empleador = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="AFC Empleador"
    )
    
    renta_imponible_anterior = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Renta Imponible Anterior"
    )
    
    seguro_accidentes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Seguro Accidentes"
    )
    
    sis = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="SIS"
    )
    
    apv_colectivo_empleador = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="APV Colectivo Empleador"
    )
    
    trabajo_pesado_empleador = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Trabajo Pesado Empleador"
    )
    
    # --- AUSENCIAS ---
    vacaciones_dias = models.IntegerField(
        default=0,
        verbose_name="Vacaciones - Días"
    )
    
    vacaciones_glosa = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Vacaciones - Glosa"
    )
    
    licencias_dias = models.IntegerField(
        default=0,
        verbose_name="Licencias Médicas - Días"
    )
    
    licencias_glosa = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Licencias Médicas - Glosa"
    )
    
    faltas_dias = models.IntegerField(
        default=0,
        verbose_name="Faltas - Días"
    )
    
    faltas_glosa = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Faltas - Glosa"
    )
    
    # --- MOVIMIENTOS PREVIRED ---
    movimiento_previred_0 = models.BooleanField(default=False, verbose_name="0 - Sin movimientos")
    movimiento_previred_1 = models.BooleanField(default=False, verbose_name="1 - Contratación plazo indefinido")
    movimiento_previred_2 = models.BooleanField(default=False, verbose_name="2 - Retiro")
    movimiento_previred_3 = models.BooleanField(default=False, verbose_name="3 - Subsidios")
    movimiento_previred_4 = models.BooleanField(default=False, verbose_name="4 - Permiso sin goce")
    movimiento_previred_5 = models.BooleanField(default=False, verbose_name="5 - Incorporación")
    movimiento_previred_6 = models.BooleanField(default=False, verbose_name="6 - Accidentes trabajo")
    movimiento_previred_7 = models.BooleanField(default=False, verbose_name="7 - Contratación plazo fijo")
    movimiento_previred_8 = models.BooleanField(default=False, verbose_name="8 - Cambio a indefinido")
    movimiento_previred_11 = models.BooleanField(default=False, verbose_name="11 - Otros movimientos")
    movimiento_previred_12 = models.BooleanField(default=False, verbose_name="12 - Requilidación premio/bono")
    movimiento_previred_13 = models.BooleanField(default=False, verbose_name="13 - Suspensión acto autoridad")
    movimiento_previred_14 = models.BooleanField(default=False, verbose_name="14 - Suspensión pacto")
    movimiento_previred_15 = models.BooleanField(default=False, verbose_name="15 - Reducción jornada")
    
    movimiento_desde = models.DateField(
        null=True,
        blank=True,
        verbose_name="Movimiento Desde"
    )
    
    movimiento_hasta = models.DateField(
        null=True,
        blank=True,
        verbose_name="Movimiento Hasta"
    )
    
    # --- REFORMA PREVISIONAL ---
    cuenta_afp_empleador = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Cuenta AFP Empleador"
    )
    
    renta_protegida = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Renta Protegida"
    )
    
    expectativa_vida = models.IntegerField(
        default=0,
        verbose_name="Expectativa de Vida (años)"
    )
    
    # --- TOTALES ---
    total_haberes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Haberes"
    )
    
    total_descuentos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Total Descuentos"
    )
    
    liquido_pagable = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Líquido Pagable"
    )
    
    # --- METADATOS ---
    fecha_generacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Generación"
    )
    
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Fecha de Actualización"
    )
    
    fecha_pago = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Pago"
    )
    
    observaciones = models.TextField(
        blank=True,
        verbose_name="Observaciones"
    )
    
    # Archivos adjuntos
    archivo_pdf = models.FileField(
        upload_to='liquidaciones/pdf/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Archivo PDF"
    )
    
    archivo_excel = models.FileField(
        upload_to='liquidaciones/excel/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Archivo Excel"
    )
    
    class Meta:
        verbose_name = "Liquidación"
        verbose_name_plural = "Liquidaciones"
        ordering = ['-periodo__anio', '-periodo__mes', 'trabajador__apellido_paterno']
        unique_together = ['periodo', 'trabajador']
        indexes = [
            models.Index(fields=['periodo', 'trabajador']),
            models.Index(fields=['estado']),
            models.Index(fields=['fecha_generacion']),
        ]
    
    def __str__(self):
        return f"Liquidación {self.trabajador} - {self.periodo}"
    
    def clean(self):
        """Validaciones"""
        # Validar que trabajador pertenezca a la misma empresa que el período
        if self.periodo.empresa != self.trabajador.empresa:
            raise ValidationError({
                'trabajador': 'El trabajador debe pertenecer a la misma empresa que el período.'
            })
        
        # Validar que líquido sea positivo o cero
        if self.liquido_pagable < 0:
            raise ValidationError({
                'liquido_pagable': 'El líquido pagable no puede ser negativo.'
            })
    
    def save(self, *args, **kwargs):
        """Cálculos automáticos al guardar"""
        
        # Calcular sueldo diario si no está definido
        if self.sueldo_diario == 0 and self.sueldo_mensual > 0 and self.dias_habiles > 0:
            self.sueldo_diario = self.sueldo_mensual / self.dias_habiles
        
        # Calcular total haberes si no está definido
        if self.total_haberes == 0:
            self.total_haberes = (
                self.sueldo_mensual +
                self.monto_gratificacion +
                self.bonos +
                self.colacion +
                self.movilizacion +
                self.total_horas_extra +
                self.total_comision +
                self.monto_cargo_domingo +
                self.utilidades +
                self.semana_corrida +
                self.valor_otro_bono_1 +
                self.valor_otro_bono_2
            )
        
        # Calcular total descuentos si no está definido
        if self.total_descuentos == 0:
            self.total_descuentos = (
                self.cotizacion_afp +
                self.diferencia_isapre +
                self.cuenta_2_afp +
                self.cotizacion_afc +
                self.apv +
                self.apv2 +
                self.apv_colectivo +
                self.cuota_impuesto +
                self.prestamo_ccaf +
                self.prestamo_solidario +
                self.programa_ahorro_leasing +
                self.seguro_ccaf +
                self.cuota_ccaf +
                self.prestamo_empresa +
                self.valor_otro_descuento_1 +
                self.valor_otro_descuento_2
            )
        
        # Calcular líquido pagable
        self.liquido_pagable = self.total_haberes - self.total_descuentos
        
        # Establecer centro de costo del trabajador
        if not self.centro_costo and self.trabajador.centro_costo_nombre:
            self.centro_costo = self.trabajador.centro_costo_nombre
        
        # Si es nueva liquidación, establecer algunos valores por defecto
        if not self.pk:
            # Valores del período
            self.dias_habiles = self.periodo.dias_habiles
            self.dias_domingo_festivos = self.periodo.dias_no_habiles
            
            # Valores del trabajador
            self.sueldo_mensual = self.trabajador.sueldo_mensual
            self.numero_cargas = self.trabajador.numero_cargas
            self.colacion = self.trabajador.colacion_mensual
            self.movilizacion = self.trabajador.movilizacion_mensual
            self.apv = self.trabajador.apv
            self.apv2 = self.trabajador.apv2
            self.apv_colectivo = self.trabajador.apv_colectivo
            self.afiliado_voluntario = self.trabajador.es_afiliado_voluntario
            self.porcentaje_trabajo_pesado = self.trabajador.porcentaje_trabajo_pesado_trabajador
        
        super().save(*args, **kwargs)
    
    @property
    def empresa(self):
        """Empresa a la que pertenece la liquidación"""
        return self.periodo.empresa
    
    @property
    def trabajador_nombre_completo(self):
        """Nombre completo del trabajador"""
        return self.trabajador.nombre_completo
    
    @property
    def trabajador_rut(self):
        """RUT del trabajador"""
        return self.trabajador.rut
    
    @property
    def periodo_nombre(self):
        """Nombre del período (Mes Año)"""
        return str(self.periodo)
    
    @property
    def movimientos_previred_seleccionados(self):
        """Lista de movimientos Previred seleccionados"""
        movimientos = []
        campos = [
            (self.movimiento_previred_0, '0 - Sin movimientos'),
            (self.movimiento_previred_1, '1 - Contratación plazo indefinido'),
            (self.movimiento_previred_2, '2 - Retiro'),
            (self.movimiento_previred_3, '3 - Subsidios'),
            (self.movimiento_previred_4, '4 - Permiso sin goce'),
            (self.movimiento_previred_5, '5 - Incorporación'),
            (self.movimiento_previred_6, '6 - Accidentes trabajo'),
            (self.movimiento_previred_7, '7 - Contratación plazo fijo'),
            (self.movimiento_previred_8, '8 - Cambio a indefinido'),
            (self.movimiento_previred_11, '11 - Otros movimientos'),
            (self.movimiento_previred_12, '12 - Requilidación premio/bono'),
            (self.movimiento_previred_13, '13 - Suspensión acto autoridad'),
            (self.movimiento_previred_14, '14 - Suspensión pacto'),
            (self.movimiento_previred_15, '15 - Reducción jornada'),
        ]
        
        for campo, descripcion in campos:
            if campo:
                movimientos.append(descripcion)
        
        return movimientos
    
    @property
    def dias_no_trabajados(self):
        """Total de días no trabajados"""
        return self.vacaciones_dias + self.licencias_dias + self.faltas_dias
    
    @property
    def sueldo_proporcional(self):
        """Sueldo proporcional a días trabajados"""
        if self.dias_habiles > 0:
            return (self.sueldo_mensual / self.dias_habiles) * self.dias_trabajados
        return Decimal('0')
    
    @property
    def costo_total_empleador(self):
        """Costo total para el empleador (haberes + cargas patronales)"""
        # Aproximadamente 1.5 veces los haberes (incluye cotizaciones patronales)
        return self.total_haberes * Decimal('1.5')
    
    def generar_pdf(self):
        """Generar archivo PDF de la liquidación"""
        # Implementación para generar PDF
        pass
    
    def generar_excel(self):
        """Generar archivo Excel de la liquidación"""
        # Implementación para generar Excel
        pass
    
    def cerrar_liquidacion(self):
        """Cerrar la liquidación (cambiar estado a CERRADA)"""
        self.estado = 'CERRADA'
        self.save()
    
    def anular_liquidacion(self):
        """Anular la liquidación (cambiar estado a ANULADA)"""
        self.estado = 'ANULADA'
        self.save()
    
    def marcar_como_pagada(self, fecha_pago=None):
        """Marcar liquidación como pagada"""
        self.estado = 'PAGADA'
        if fecha_pago:
            self.fecha_pago = fecha_pago
        else:
            self.fecha_pago = timezone.now().date()
        self.save()

from django.db import models
from empresas.models import Empresa

class CentroCosto(models.Model):
    """
    Modelo para gestionar centros de costo de una empresa.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='centros_costo')
    codigo = models.CharField(max_length=20, verbose_name="Código")
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última modificación")

    class Meta:
        verbose_name = "Centro de Costo"
        verbose_name_plural = "Centros de Costo"
        ordering = ['codigo']
        unique_together = ['empresa', 'codigo']  # Un código único por empresa

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"