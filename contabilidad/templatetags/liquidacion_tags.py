# contabilidad/templatetags/liquidacion_tags.py
from django import template
from django.template.defaultfilters import stringfilter
import locale

register = template.Library()



@register.filter
def formato_clp(value):
    """
    Formatea un número como moneda chilena (CLP).
    Ejemplo: 850998 → $850.998
    """
    if value is None or value == '':
        return '$0'
    
    try:
        # Convertir a entero si es posible
        valor_numero = int(float(str(value).replace(',', '.')))
        
        # Formatear con separadores de miles
        if valor_numero >= 0:
            # Usar formato chileno (punto para miles)
            return f"${valor_numero:,.0f}".replace(",", ".")
        else:
            return f"-${abs(valor_numero):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return f"${value}"

@register.filter
def formato_numero(value):
    """Formatea un número con separadores de miles: 1500000 -> 1.500.000"""
    try:
        value = int(float(value))
        return f"{value:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

@register.filter
def si_no(value):
    """Convierte True/False a Sí/No"""
    return "Sí" if value else "No"

@register.filter
def porcentaje(value):
    """Formatea un número como porcentaje"""
    try:
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "0%"

@register.filter
def num2words(value):
    """
    Convierte un número a palabras en español
    Ejemplo: 1500000 -> un millón quinientos mil pesos
    """
    if not value:
        return "cero pesos"
    
    try:
        num = int(float(value))
        
        # Unidades
        unidades = ["", "un", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
        especiales = ["diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve"]
        decenas = ["", "diez", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"]
        centenas = ["", "cien", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"]
        
        def convertir_tres_digitos(n):
            """Convierte números de hasta 3 dígitos"""
            texto = ""
            
            # Centenas
            c = n // 100
            if c > 0:
                if c == 1 and n % 100 == 0:
                    texto = "cien"
                else:
                    texto = centenas[c]
                n %= 100
                if n > 0:
                    texto += " "
            
            # Decenas y unidades
            if n > 0:
                if n < 10:
                    texto += unidades[n]
                elif n < 20:
                    texto += especiales[n - 10]
                else:
                    d = n // 10
                    u = n % 10
                    texto += decenas[d]
                    if u > 0:
                        if d == 2:
                            texto = texto.replace("veinte", "veinti")
                            texto += unidades[u]
                        else:
                            texto += " y " + unidades[u]
            
            return texto
        
        # Manejar millones, miles, etc.
        if num == 0:
            return "cero pesos"
        
        palabras = []
        
        # Millones
        millones = num // 1000000
        if millones > 0:
            if millones == 1:
                palabras.append("un millón")
            else:
                palabras.append(convertir_tres_digitos(millones) + " millones")
            num %= 1000000
        
        # Miles
        miles = num // 1000
        if miles > 0:
            if miles == 1:
                palabras.append("mil")
            else:
                palabras.append(convertir_tres_digitos(miles) + " mil")
            num %= 1000
        
        # Resto
        if num > 0:
            palabras.append(convertir_tres_digitos(num))
        
        return " ".join(palabras) + " pesos"
        
    except (ValueError, TypeError):
        return "cero pesos"

@register.filter
def multiply(value, arg):
    """
    Multiplica el valor por el argumento.
    Uso: {{ valor|multiply:2.5 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def restar(value, arg):
    """
    Resta el argumento del valor.
    Uso: {{ valor|restar:1000 }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def dividir(value, arg):
    """
    Divide el valor por el argumento.
    Uso: {{ valor|dividir:30 }}
    """
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0