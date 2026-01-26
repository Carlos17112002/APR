# boletas/admin.py - VERSIÓN MÍNIMA
from django.contrib import admin
from .models import Boleta

class BoletaAdmin(admin.ModelAdmin):
    # SOLUCIÓN: Elimina 'pagada' completamente
    list_display = [
        'id', 
        'cliente', 
        'periodo', 
        'total', 
        'fecha_emision', 
        'fecha_vencimiento',
        'estado',
        'empresa_slug'
    ]
    
    list_filter = [
        'estado',
        'empresa_slug',
        'fecha_emision'
    ]
    
    search_fields = ['cliente__nombre', 'periodo']

admin.site.register(Boleta, BoletaAdmin)