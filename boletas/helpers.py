from boletas.models import Boleta
from clientes.models import Cliente
from lecturas.models import LecturaMovil  # Cambiado aquí
from datetime import date

# 🧮 Tarifa escalonada por bloques
def calcular_monto_escalonado(consumo):
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

    return total / 100  # Dividir por 100 si los precios están en centavos

# 🧾 Generador de boletas por alias - VERSIÓN ACTUALIZADA
def generar_boletas_por_alias(alias):
    alias_db = f'db_{alias}'
    hoy = date.today()
    periodo = hoy.strftime('%B %Y')

    clientes = Cliente.objects.using(alias_db).all()
    generadas = []

    for cliente in clientes:
        # Buscar lecturas del mes actual que no hayan sido usadas para boleta
        lecturas = LecturaMovil.objects.using(alias_db).filter(
            cliente=cliente,
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
        mes_anterior = hoy.replace(day=1)  # Primer día del mes actual
        mes_anterior = mes_anterior.replace(month=mes_anterior.month-1) if mes_anterior.month > 1 else mes_anterior.replace(year=mes_anterior.year-1, month=12)
        
        lecturas_anteriores = LecturaMovil.objects.using(alias_db).filter(
            cliente=cliente,
            fecha_lectura__lt=lectura_actual.fecha_lectura,
            estado='cargada'
        ).order_by('-fecha_lectura')
        
        lectura_anterior_valor = lecturas_anteriores.first().lectura_actual if lecturas_anteriores.exists() else 0
        
        # Calcular consumo
        consumo = lectura_actual.lectura_actual - lectura_anterior_valor
        
        # Si no hay consumo calculado en el modelo, calcularlo
        if not lectura_actual.consumo and consumo > 0:
            lectura_actual.consumo = consumo
            lectura_actual.save()

        if consumo <= 0:
            print(f"[Boleta] Cliente {cliente.nombre} tiene consumo negativo o nulo ({consumo}). Saltando.")
            continue

        # Evitar duplicados - ahora verificar por lectura asociada
        existe = Boleta.objects.using(alias_db).filter(
            lectura=lectura_actual
        ).exists()
        
        if existe:
            print(f"[Boleta] Ya existe boleta para {cliente.nombre} con lectura del {lectura_actual.fecha_lectura}. Saltando.")
            continue

        # Calcular montos
        monto_variable = calcular_monto_escalonado(consumo)
        monto_total = monto_variable + 1700  # 🧱 cargo fijo

        # Crear boleta
        boleta = Boleta.objects.using(alias_db).create(
            cliente=cliente,
            lectura=lectura_actual,  # Relación con la lectura
            periodo=periodo,
            fecha_vencimiento=hoy.replace(day=15) if hoy.day <= 15 else hoy.replace(month=hoy.month+1, day=15) if hoy.month < 12 else hoy.replace(year=hoy.year+1, month=1, day=15),
            consumo=consumo,
            monto_consumo=monto_variable,
            cargo_fijo=1700,
            total=monto_total,
            empresa_slug=alias,
            codigo_barras=f"{alias}-{cliente.id}-{hoy.strftime('%Y%m%d')}"
        )
        
        # Marcar lectura como procesada
        lectura_actual.estado = 'procesada'
        lectura_actual.usada_para_boleta = True
        lectura_actual.boleta_generada = boleta
        lectura_actual.save()
        
        generadas.append(boleta)
        print(f"[Boleta] Generada para {cliente.nombre} → {consumo} m³ → ${monto_total}")

    return generadas


# 🧾 Versión alternativa: generar boletas desde lecturas específicas
def generar_boleta_desde_lectura(lectura_id, alias):
    """
    Genera una boleta para una lectura específica
    """
    alias_db = f'db_{alias}'
    
    try:
        lectura = LecturaMovil.objects.using(alias_db).get(id=lectura_id)
    except LecturaMovil.DoesNotExist:
        print(f"[Error] Lectura {lectura_id} no encontrada")
        return None
    
    # Verificar si ya tiene boleta
    if lectura.usada_para_boleta:
        print(f"[Info] Lectura {lectura_id} ya tiene boleta asociada")
        return lectura.boleta_generada
    
    hoy = date.today()
    
    # Buscar lectura anterior
    lecturas_anteriores = LecturaMovil.objects.using(alias_db).filter(
        cliente=lectura.cliente,
        fecha_lectura__lt=lectura.fecha_lectura,
        estado='cargada'
    ).order_by('-fecha_lectura')
    
    lectura_anterior_valor = lecturas_anteriores.first().lectura_actual if lecturas_anteriores.exists() else 0
    
    # Calcular consumo
    consumo = lectura.lectura_actual - lectura_anterior_valor
    
    if consumo <= 0:
        print(f"[Error] Consumo negativo o nulo para cliente {lectura.cliente.nombre}")
        return None
    
    # Calcular montos
    monto_variable = calcular_monto_escalonado(consumo)
    monto_total = monto_variable + 1700  # cargo fijo
    
    # Crear boleta
    boleta = Boleta.objects.using(alias_db).create(
        cliente=lectura.cliente,
        lectura=lectura,
        periodo=hoy.strftime('%B %Y'),
        fecha_vencimiento=hoy.replace(day=15) if hoy.day <= 15 else hoy.replace(month=hoy.month+1, day=15) if hoy.month < 12 else hoy.replace(year=hoy.year+1, month=1, day=15),
        consumo=consumo,
        monto_consumo=monto_variable,
        cargo_fijo=1700,
        total=monto_total,
        empresa_slug=alias,
        codigo_barras=f"{alias}-{lectura.cliente.id}-{hoy.strftime('%Y%m%d')}"
    )
    
    # Marcar lectura como procesada
    lectura.estado = 'procesada'
    lectura.usada_para_boleta = True
    lectura.boleta_generada = boleta
    lectura.save()
    
    print(f"[Boleta] Generada individual para {lectura.cliente.nombre} → {consumo} m³ → ${monto_total}")
    return boleta