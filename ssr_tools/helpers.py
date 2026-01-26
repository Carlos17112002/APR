# ssr_tools/helpers.py

from django.core.management import call_command
from django.shortcuts import get_object_or_404
from empresas.models import Empresa
from clientes.models import Cliente
from ssr_tools.models import AccionSSRLog
import subprocess
import csv
import io   


def reparar_entorno(empresa):
    logs = []
    for app in empresa.apps_activas():
        try:
            call_command("migrate", app, verbosity=0)
            logs.append(f"[OK] Migración aplicada: {app}")
        except Exception as e:
            logs.append(f"[ERROR] {app}: {str(e)}")
    return logs

from django.core.management import call_command
from io import StringIO

def validar_migraciones(alias):
    buffer = StringIO()
    try:
        call_command("showmigrations", stdout=buffer, plan=True)
        resultado = []
        for line in buffer.getvalue().splitlines():
            if alias.lower() in line.lower():
                resultado.append(line)
        return resultado
    except Exception as e:
        return [f"[ERROR] {str(e)}"]


def exportar_por_tipo(tipo, alias):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if tipo == "clientes":
        clientes = Cliente.objects.filter(empresa_slug=alias)
        writer.writerow(["ID", "Nombre", "Rut"])
        for c in clientes:
            writer.writerow([c.id, c.nombre, c.rut])
    # Agrega más tipos según necesidad
    return buffer.getvalue()
