# contabilidad/templatetags/contabilidad_filters.py
from django import template

register = template.Library()

@register.filter
def format_decimal(value):
    """Formatea un número a 2 decimales con punto"""
    try:
        if value is None:
            return "0.00"
        
        # Convertir a string primero para manejar Decimal
        str_value = str(value)
        
        # Si tiene coma, reemplazar
        if ',' in str_value:
            str_value = str_value.replace(',', '.')
        
        # Convertir a float y formatear
        num = float(str_value)
        # Formatear a 2 decimales
        formatted = f"{num:.2f}"
        
        return formatted
    except (ValueError, TypeError, AttributeError):
        return "0.00"