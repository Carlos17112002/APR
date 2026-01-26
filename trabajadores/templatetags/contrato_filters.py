# trabajadores/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_color(value, index):
    """Devuelve un color basado en el índice."""
    colors = [
        '#10B981',  # verde
        '#3B82F6',  # azul
        '#F59E0B',  # ámbar
        '#8B5CF6',  # violeta
        '#EF4444',  # rojo
        '#EC4899',  # rosa
        '#14B8A6',  # turquesa
        '#F97316',  # naranja
        '#6366F1',  # índigo
        '#84CC16',  # lima
    ]
    return colors[index % len(colors)]

@register.filter
def get_tipo_display(tipo_contrato):
    """Devuelve el display de tipo de contrato."""
    tipos = {
        'indefinido': 'Indefinido',
        'plazo_fijo': 'Plazo Fijo',
        'faena': 'Por Faena',
    }
    return tipos.get(tipo_contrato, tipo_contrato)

@register.filter
def widthratio(value, max_value, max_width=100):
    """Calcula el porcentaje."""
    try:
        return (float(value) / float(max_value)) * max_width
    except (ValueError, ZeroDivisionError):
        return 0