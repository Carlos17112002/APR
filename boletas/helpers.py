from boletas.models import Boleta
from clientes.models import Cliente
from lecturas.models import LecturaMovil
from datetime import date, timedelta

# 🧮 Tarifa escalonada por bloques
def calcular_monto_escalonado(consumo):
    """
    Calcula el monto variable según la tabla de tarifas.
    Retorna el monto en pesos (enteros). Si los precios están en centavos,
    ajusta la división final.
    """
    bloques = [
        (10, 180),   # 1–10 m³
        (10, 315),   # 11–20
        (10, 470),   # 21–30
        (10, 840),   # 31–40
        (10, 1360),  # 41–50
        (10, 1800),  # 51–60
        (10, 2200),  # 61–70
        (429, 2300)  # 71–500
    ]

    restante = consumo
    total = 0

    for limite, precio in bloques:
        if restante <= 0:
            break
        cantidad = min(restante, limite)
        total += cantidad * precio
        restante -= cantidad

    # Si los precios están en centavos, divide por 100.
    # Según tu tabla, los montos parecen en pesos, así que no dividimos.
    return total

# 🧾 Generador de boletas por alias - VERSIÓN CORREGIDA
from decimal import Decimal
from django.utils import timezone
from .models import Boleta
from clientes.models import Cliente
from lecturas.models import LecturaMovil

def generar_boletas_por_alias(alias):
    """
    Genera boletas para todos los clientes de una empresa en el mes actual.
    Solo crea boleta si el cliente no tiene una ya en el período.
    """
    alias_db = f'db_{alias}'
    hoy = timezone.now()
    mes_actual = hoy.month
    año_actual = hoy.year
    periodo_actual = f"{año_actual}-{mes_actual:02d}"

    # Obtener todos los clientes de la empresa
    clientes = Cliente.objects.using(alias_db).all()
    boletas_creadas = []

    for cliente in clientes:
        # Verificar si ya tiene boleta este período
        if Boleta.objects.using(alias_db).filter(cliente=cliente, periodo=periodo_actual).exists():
            print(f"Cliente {cliente.nombre} ya tiene boleta. Saltando.")
            continue

        # Obtener la última lectura del cliente en el mes actual
        lecturas_mes = LecturaMovil.objects.using(alias_db).filter(
            cliente=cliente.id,
            fecha_lectura__month=mes_actual,
            fecha_lectura__year=año_actual,
            estado='cargada'  # Solo lecturas válidas
        ).order_by('-fecha_lectura')

        if not lecturas_mes.exists():
            print(f"Cliente {cliente.nombre} no tiene lecturas del mes actual. Saltando.")
            continue

        ultima_lectura = lecturas_mes.first()

        # Obtener la lectura anterior para calcular consumo
        lectura_anterior = LecturaMovil.objects.using(alias_db).filter(
            cliente=cliente.id,
            estado='cargada',
            fecha_lectura__lt=ultima_lectura.fecha_lectura
        ).order_by('-fecha_lectura').first()

        valor_anterior = lectura_anterior.lectura_actual if lectura_anterior else Decimal('0')
        valor_actual = ultima_lectura.lectura_actual
        consumo = valor_actual - valor_anterior
        if consumo < 0:
            consumo = Decimal('0')

        # Calcular montos usando tarifa escalonada
        monto_consumo = calcular_monto_escalonado(consumo)  # Devuelve entero (pesos)
        monto_consumo = Decimal(monto_consumo)  # Convertir a Decimal para consistencia

        # Cargo fijo (ajusta según tu negocio)
        cargo_fijo = Decimal('2000')
        total = cargo_fijo + monto_consumo

        # Crear boleta con todos los campos requeridos
        boleta = Boleta.objects.using(alias_db).create(
            cliente=cliente,
            lectura=ultima_lectura,
            periodo=periodo_actual,
            fecha_emision=hoy.date(),
            fecha_vencimiento=hoy.date() + timezone.timedelta(days=30),
            lectura_anterior=valor_anterior,
            lectura_actual=valor_actual,
            consumo=consumo,
            monto_consumo=monto_consumo,
            cargo_fijo=cargo_fijo,
            otros_cargos=Decimal('0'),
            total=total,
            estado='generada',
            empresa_slug=alias,
        )
        boletas_creadas.append(boleta)
        print(f"Boleta generada para {cliente.nombre}")

    return boletas_creadas