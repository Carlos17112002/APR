from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from empresas.models import Empresa
from . import helpers
from .models import AccionSSRLog

# Create your views here.
# ssr_tools/views.py
@login_required
def reparar_entorno(request, alias):
    empresa = get_object_or_404(Empresa, slug=alias)
    resultado = helpers.reparar_entorno(empresa)
    AccionSSRLog.objects.create(usuario=request.user, alias=alias, accion="Reparar entorno", resultado=resultado)
    return render(request, "ssr_tools/reparar_entorno.html", {"resultado": resultado})

@login_required
def ver_logs_alias(request, alias):
    logs = AccionSSRLog.objects.filter(alias=alias).order_by("-fecha")[:100]
    return render(request, "ssr_tools/ver_logs.html", {"logs": logs})


@login_required
def exportar_datos(request, alias):
    if request.method == "POST":
        tipo = request.POST.get("tipo")
        datos = helpers.exportar_por_tipo(tipo, alias)
        response = HttpResponse(datos, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{tipo}_{alias}.csv"'
        return response
    return render(request, "ssr_tools/exportar_datos.html")

# ssr_tools/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
import subprocess
from .models import AccionSSRLog

@login_required
def validar_migraciones(request, alias):
    resultado = []
    try:
        # Ejecuta el comando showmigrations con --plan para ver el estado
        output = subprocess.check_output(
            ["python", "manage.py", "showmigrations", "--plan"],
            stderr=subprocess.STDOUT
        )
        for line in output.decode().splitlines():
            if alias.lower() in line.lower():
                resultado.append(line)
    except subprocess.CalledProcessError as e:
        resultado.append(f"[ERROR] {e.output.decode()}")

    # Guarda log de acción
    AccionSSRLog.objects.create(
        usuario=request.user,
        alias=alias,
        accion="Validar migraciones",
        resultado=resultado
    )

    return render(request, "ssr_tools/validar_migraciones.html", {
        "alias": alias,
        "resultado": resultado
    })
