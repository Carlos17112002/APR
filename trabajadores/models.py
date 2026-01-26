from django.db import models


class ContratoLaboral(models.Model):
    alias = models.CharField(max_length=100)
    rut_trabajador = models.CharField(max_length=12)
    nombre = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100)

    jornada = models.CharField(max_length=50, choices=[
        ('completa', 'Completa'),
        ('parcial', 'Parcial'),
        ('turnos', 'Por turnos'),
    ])

    tipo_contrato = models.CharField(max_length=50, choices=[
        ('indefinido', 'Indefinido'),
        ('plazo_fijo', 'Plazo Fijo'),
        ('faena', 'Por Faena'),
    ])

    afp = models.CharField(
    max_length=50,
    choices=[
        ('modelo', 'AFP Modelo'),
        ('provida', 'AFP Provida'),
        ('cuprum', 'AFP Cuprum'),
        ('habitat', 'AFP Habitat'),
        ('planvital', 'AFP PlanVital'),
    ],
    default='modelo'  # ← valor por defecto para registros existentes
)


    salud = models.CharField(
    max_length=50,
    choices=[
        ('fonasa', 'Fonasa'),
        ('isapre', 'Isapre'),
        ('fuerzas armadas', 'Fuerzas Armadas'),

    ],
    default='fonasa'  # ← valor por defecto para contratos antiguos
)
    sistema_gratificacion = models.CharField(
    max_length=20,
    choices=[
        ('art_47', 'Proporcional a utilidades (Art. 47)'),
        ('art_50', '25% del sueldo base (Art. 50)'),
        ('sin_gratificacion', 'No aplica'),
    ],
    default='art_50'
)
    sueldo_base = models.PositiveIntegerField()
    gratificacion = models.PositiveIntegerField(default=0)
    bonos = models.PositiveIntegerField(default=0)

    fecha_inicio = models.DateField()
    fecha_termino = models.DateField(null=True, blank=True)
    documento_pdf = models.FileField(upload_to='contratos/', null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    
    TIPOS_GRATIFICACION = [
    ('fija', 'Fija mensual (25%)'),
    ('proporcional', 'Proporcional a utilidades'),
    ]

    tipo_gratificacion = models.CharField(
        max_length=20,
        choices=TIPOS_GRATIFICACION,
        default='fija'
    )


    def __str__(self):
        return f"{self.nombre} · {self.alias}"

class FiniquitoLaboral(models.Model):
    alias = models.CharField(max_length=100)
    trabajador = models.ForeignKey('ContratoLaboral', on_delete=models.CASCADE)
    fecha_finiquito = models.DateField()
    motivo = models.CharField(max_length=200)
    indemnizacion = models.PositiveIntegerField(default=0)
    vacaciones_pendientes = models.PositiveIntegerField(default=0)
    otros = models.PositiveIntegerField(default=0)
    documento_pdf = models.FileField(upload_to='finiquitos/', null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    def total(self):
        return self.indemnizacion + self.vacaciones_pendientes + self.otros

    def __str__(self):
        return f"Finiquito · {self.trabajador.nombre} · {self.alias}"
class LiquidacionLaboral(models.Model):
    alias = models.CharField(max_length=100)
    trabajador = models.ForeignKey('ContratoLaboral', on_delete=models.CASCADE)
    mes = models.CharField(max_length=7)  # Ej: "2025-09"

    # Haberes
    sueldo_base = models.PositiveIntegerField()
    gratificacion = models.PositiveIntegerField(default=0)
    bonos = models.PositiveIntegerField(default=0)
    horas_extra_50 = models.PositiveIntegerField(default=0)
    horas_extra_100 = models.PositiveIntegerField(default=0)

    # Descuentos previsionales
    afp = models.PositiveIntegerField(default=0)
    salud = models.PositiveIntegerField(default=0)
    seguro_cesantia = models.PositiveIntegerField(default=0)
    otros_descuentos = models.PositiveIntegerField(default=0)

    # Días
    dias_trabajados = models.PositiveIntegerField(default=30)
    dias_licencia = models.PositiveIntegerField(default=0)
    dias_vacaciones = models.PositiveIntegerField(default=0)
    dias_ausente = models.PositiveIntegerField(default=0)

    # PDF generado
    documento_pdf = models.FileField(upload_to='liquidaciones/', null=True, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    def valor_hora(self):
        return self.sueldo_base / 30 / 8

    def total_horas_extra(self):
        return round(
            self.horas_extra_50 * self.valor_hora() * 1.5 +
            self.horas_extra_100 * self.valor_hora() * 2.0
        )

    def sueldo_proporcional(self):
        return round((self.sueldo_base / 30) * self.dias_trabajados)

    def total_haberes(self):
        return self.sueldo_proporcional() + self.gratificacion + self.bonos + self.total_horas_extra()

    def total_descuentos(self):
        descuento_ausente = (self.sueldo_base / 30) * self.dias_ausente
        return round(self.afp + self.salud + self.seguro_cesantia + self.otros_descuentos + descuento_ausente)

    def liquido_pagado(self):
        return self.total_haberes() - self.total_descuentos()

class Trabajador(models.Model):
    alias = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, unique=True)
    nombre = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

