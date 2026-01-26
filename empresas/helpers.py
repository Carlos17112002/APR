from datetime import date
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal

def obtener_certificado_firma():
    fecha_valido = date(2022, 12, 16)
    fecha_vencimiento = date(2025, 12, 15)
    hoy = date.today()
    dias_restantes = (fecha_vencimiento - hoy).days
    return {
        "nombre": "Cristian Omar Marchant Pinto",
        "fecha_valido": fecha_valido.strftime("%d-%m-%Y"),
        "fecha_vencimiento": fecha_vencimiento.strftime("%d-%m-%Y"),
        "dias_restantes": dias_restantes
    }

def obtener_estado_folios():
    return [
        {"tipo": "FACTURA EXENTA ELECTRONICA", "a_generar": 51, "disponibles": 183, "obs": ""},
        {"tipo": "BOLETA ELECTRONICA EXENTA", "a_generar": 982, "disponibles": 2487, "obs": ""},
        {"tipo": "NOTA DE DEBITO ELECTRONICA", "a_generar": "-", "disponibles": 0, "obs": "Folios No Disponible"},
        {"tipo": "NOTA DE CREDITO ELECTRONICA", "a_generar": "-", "disponibles": 1, "obs": ""},
    ]

def obtener_tasa_interes():
    return {
        "anual": "31,84",
        "diario": "0,0884",
        "sistema": "0,0000"
    }

def obtener_reajuste_sii():
    return {
        "julio": "108,62",
        "agosto": "108,66",
        "sugerido": "0.03",
        "sistema": "0.00"
    }

def obtener_contratos_corte(alias):
    from boletas.models import Boleta
    from clientes.models import Cliente
    
    # PRIMERO: Verificar que ambas tablas existen en la misma BD
    try:
        # Obtener IDs de clientes que tienen boletas en ESTA BD
        cliente_ids_con_boletas = Boleta.objects.using(alias).values_list('cliente_id', flat=True).distinct()
        
        # Luego filtrar clientes por esos IDs
        clientes_con_deuda = (
            Cliente.objects.using(alias)
            .filter(id__in=cliente_ids_con_boletas)
            .annotate(
                deuda=Sum(
                    'boletas__total',
                    filter=Q(boletas__estado__in=['generada', 'enviada', 'vencida'])
                )
            )
            .filter(deuda__gt=0)
            .values("id", "nombre", "sector", "deuda")
            .order_by("-deuda")[:15]
        )
    except Exception as e:
        print(f"Error en obtener_contratos_corte: {e}")
        # Debug: ver qué hay en la BD
        print(f"Clientes en BD {alias}: {Cliente.objects.using(alias).count()}")
        print(f"Boletas en BD {alias}: {Boleta.objects.using(alias).count()}")
        return []
    
    return list(clientes_con_deuda)

def obtener_detalle_recaudacion(alias, fecha):
    """
    CORRECCIÓN: El modelo Boleta no tiene campo 'metodo_pago'
    """
    from boletas.models import Boleta
    from decimal import Decimal
    
    # Filtrar boletas pagadas en el mes actual
    boletas = Boleta.objects.using(alias).filter(
        estado='pagada',
        fecha_pago__month=fecha.month,
        fecha_pago__year=fecha.year
    )

    total = boletas.aggregate(total=Sum("total"))["total"] or Decimal('1')
    
    # ⚠️ CORRECCIÓN: No usar 'metodo_pago' porque no existe
    # En su lugar, devolver el total general sin desglose por método
    
    cantidad = boletas.count()
    monto_total = total if total != Decimal('1') else Decimal('0')
    
    # Si hay boletas, calcular porcentaje (100% ya que es un solo grupo)
    if cantidad > 0:
        porcentaje = 100.0
    else:
        porcentaje = 0.0
    
    return [
        {
            "forma": "General",  # Ya que no tenemos método de pago
            "cantidad": cantidad,
            "monto": monto_total,
            "porcentaje": porcentaje
        }
    ]

def obtener_produccion_consumo(alias):
    """
    CORRECCIÓN: Usar campos actualizados del modelo Boleta
    """
    from boletas.models import Boleta
    from collections import defaultdict
    
    # Usamos .using(alias) para arquitectura multiempresa
    boletas = Boleta.objects.using(alias).all()

    # Agrupamos por periodo
    resumen = defaultdict(lambda: {"produccion": 0, "consumo": 0})
    for b in boletas:
        # Usar lectura_actual si existe, o calcular de otra forma
        produccion = float(b.lectura_actual) if b.lectura_actual else 0
        consumo = float(b.consumo) if b.consumo else 0
        
        resumen[b.periodo]["produccion"] += produccion
        resumen[b.periodo]["consumo"] += consumo

    # Ordenamos por periodo (asumiendo formato "Mes Año")
    # Si no hay periodo, usar fecha_emision
    if not resumen:
        return [], [], []
        
    ordenado = sorted(resumen.items(), key=lambda x: x[0], reverse=True)[:13]
    ordenado.reverse()  # Para mostrar de más antiguo a más reciente

    meses = [p for p, _ in ordenado]
    produccion = [round(d["produccion"], 2) for _, d in ordenado]
    consumo = [round(d["consumo"], 2) for _, d in ordenado]

    return meses, produccion, consumo

def obtener_puntos_lectura(alias):
    from lecturas.models import LecturaMovil
    from clientes.models import Cliente
    
    clientes = Cliente.objects.using(alias).filter(
        latitude__isnull=False,
        longitude__isnull=False
    )
    
    puntos = []
    hoy = timezone.now()
    
    for cliente in clientes:
        # SOLUCIÓN: Pasar el ID numérico, no el objeto
        lectura = LecturaMovil.objects.using(alias).filter(
            cliente=cliente.id  # ← ¡IMPORTANTE: cliente.id, no cliente!
        ).order_by('-fecha_lectura').first()
        
        if lectura:
            if lectura.fecha_lectura.month == hoy.month:
                estado = "Normal"
            else:
                estado = "Término medio"
        else:
            estado = "Faltante"
        
        puntos.append({
            "id": cliente.id,
            "nombre": cliente.nombre,
            "lat": cliente.latitude,
            "lng": cliente.longitude,
            "estado": estado,
            "medidor": cliente.medidor or "",
            "ultima_lectura": lectura.fecha_lectura if lectura else "Nunca"
        })
    
    return puntos