from django.db import models

# Create your models here.

from django.db import models
from empresas.models import Empresa

class TokenQR(models.Model):
    token = models.CharField(max_length=64, unique=True, db_index=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    total_clientes = models.IntegerField(default=0)
    usado = models.BooleanField(default=False)

    def is_valid(self):
        from django.utils import timezone
        # Token válido por 24 horas
        return not self.usado and (timezone.now() - self.created_at).total_seconds() < 86400