from django.db import models
from django.contrib.auth.models import User
# Create your models here.
class AccionSSRLog(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    alias = models.CharField(max_length=50)
    accion = models.CharField(max_length=100)
    resultado = models.JSONField()
    fecha = models.DateTimeField(auto_now_add=True)
