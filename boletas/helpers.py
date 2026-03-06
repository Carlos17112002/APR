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
def generar_boletas_por_alias(alias):
    alias_db = f'db_{alias}'
    hoy = date.today()
    periodo = hoy.strftime('%B %Y')  # Ej: "March 2026"

    clientes = Cliente.objects.using(alias_db).all()
    generadas = []

    for cliente in clientes:
        # Buscar lecturas del mes actual que no hayan sido usadas para boleta
        lecturas = LecturaMovil.objects.using(alias_db).filter(
            cliente=cliente.id,          # cliente es IntegerField en LecturaMovil
            fecha_lectura__month=hoy.month,
            fecha_lectura__year=hoy.year,
            estado='cargada',
            usada_para_boleta=False
        ).order_by('-fecha_lectura')

        if not lecturas.exists():
            print(f"[Boleta] Cliente {cliente.nombre} no tiene lecturas del mes actual. Saltando.")
            continue

        # Tomar la última lectura del mes
        lectura_actual = lecturas.first()
        
        # Buscar lectura anterior del mes pasado
        # Calcular primer día del mes anterior
        if hoy.month == 1:
            mes_anterior = hoy.replace(year=hoy.year-1, month=12, day=1)
        else:
            mes_anterior = hoy.replace(month=hoy.month-1, day=1)
        
        lecturas_anteriores = LecturaMovil.objects.using(alias_db).filter(
            cliente=cliente.id,
            fecha_lectura__lt=lectura_actual.fecha_lectura,
            estado='cargada'
        ).order_by('-fecha_lectura')
        
        lectura_anterior_valor = 0
        if lecturas_anteriores.exists():
            lectura_anterior = lecturas_anteriores.first()
            lectura_anterior_valor = lectura_anterior.lectura_actual
        
        # Calcular consumo
        consumo = lectura_actual.lectura_actual - lectura_anterior_valor
        
        # Actualizar el campo consumo de la lectura
        if consumo > 0:
            lectura_actual.consumo = consumo
            lectura_actual.save()
        else:
            print(f"[Boleta] Cliente {cliente.nombre} tiene consumo negativo o nulo ({consumo}). Saltando.")
            continue

        # Evitar duplicados: verificar si ya existe boleta para esta lectura
        existe = Boleta.objects.using(alias_db).filter(
            lectura=lectura_actual.id  # pasamos el ID
        ).exists()
        
        if existe:
            print(f"[Boleta] Ya existe boleta para {cliente.nombre} con lectura del {lectura_actual.fecha_lectura}. Saltando.")
            continue

        # Calcular montos
        monto_variable = calcular_monto_escalonado(consumo)
        cargo_fijo = 1700
        monto_total = monto_variable + cargo_fijo

        # Calcular fecha de vencimiento (por ejemplo, 15 del mes actual o siguiente)
        if hoy.day <= 15:
            fecha_vencimiento = hoy.replace(day=15)
        else:
            # Si hoy es después del 15, vence el 15 del mes siguiente
            if hoy.month == 12:
                fecha_vencimiento = hoy.replace(year=hoy.year+1, month=1, day=15)
            else:
                fecha_vencimiento = hoy.replace(month=hoy.month+1, day=15)

        # Crear boleta - pasando los IDs correctamente
        boleta = Boleta.objects.using(alias_db).create(
            cliente=cliente.id,                  # ✅ ID numérico
            lectura=lectura_actual,               # ✅ objeto (ya existe)
            periodo=periodo,
            fecha_emision=hoy,
            fecha_vencimiento=fecha_vencimiento,
            lectura_anterior=lectura_anterior_valor,
            lectura_actual=lectura_actual.lectura_actual,
            consumo=consumo,
            monto_consumo=monto_variable,
            cargo_fijo=cargo_fijo,
            otros_cargos=0,
            total=monto_total,
            estado='generada',
            empresa_slug=alias,
            codigo_barras=f"{alias}-{cliente.id}-{hoy.strftime('%Y%m%d')}"
        )
        
        # Marcar lectura como procesada
        lectura_actual.estado = 'procesada'
        lectura_actual.usada_para_boleta = True
        lectura_actual.boleta_generada = boleta   # ✅ asignar objeto
        lectura_actual.save()
        
        generadas.append(boleta)
        print(f"[Boleta] Generada para {cliente.nombre} → {consumo} m³ → ${monto_total}")

    return generadas