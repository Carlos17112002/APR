from django.contrib import admin
from .models import DocumentoContable

@admin.register(DocumentoContable)
class DocumentoContableAdmin(admin.ModelAdmin):
    list_display = (
        'tipo',
        'alias',
        'nombre_trabajador',
        'cargo',
        'inicio',
        'tipo_contrato',
        'fecha_finiquito',
        'motivo_finiquito',
        'total_finiquito',
        'mes_liquidacion',
        'total_liquido',
        'creado',
    )
    list_filter = ('tipo', 'alias', 'creado')
    search_fields = ('nombre_trabajador', 'descripcion', 'alias', 'motivo_finiquito')
    readonly_fields = ('creado',)
    fieldsets = (
        (None, {
            'fields': ('tipo', 'alias', 'archivo', 'descripcion')
        }),
        ('Contrato laboral', {
            'fields': ('nombre_trabajador', 'cargo', 'inicio', 'tipo_contrato'),
            'classes': ('collapse',),
        }),
        ('Finiquito', {
            'fields': ('fecha_finiquito', 'motivo_finiquito', 'total_finiquito'),
            'classes': ('collapse',),
        }),
        ('Liquidación', {
            'fields': ('mes_liquidacion', 'total_liquido'),
            'classes': ('collapse',),
        }),
        ('Auditoría', {
            'fields': ('creado',),
        }),
    )
