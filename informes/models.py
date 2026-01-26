from django.db import models

class LibroContable(models.Model):
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=[
        ('compras', 'Compras'),
        ('ventas', 'Ventas'),
        ('retenciones', 'Retenciones'),
    ])
    periodo = models.CharField(max_length=7)  # Ej: "2025-09"
    neto = models.DecimalField(max_digits=12, decimal_places=2)
    iva = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=20, choices=[
        ('procesando', 'Procesando'),
        ('validado', 'Validado'),
        ('error', 'Error'),
    ], default='procesando')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-periodo']
        verbose_name = 'Libro Contable'
        verbose_name_plural = 'Libros Contables'

    def __str__(self):
        return f"{self.tipo.title()} · {self.periodo}"



from django.db import models

