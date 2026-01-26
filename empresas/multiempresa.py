from django.conf import settings
import os
from django.core.management import call_command

def registrar_alias(slug):
    alias = f'db_{slug}'
    ruta_db = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')

    os.makedirs(settings.BASES_DIR, exist_ok=True)
    if not os.path.exists(ruta_db):
        open(ruta_db, 'w').close()

    settings.DATABASES[alias] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ruta_db,
        'TIME_ZONE': settings.TIME_ZONE,
        'ATOMIC_REQUESTS': False,
        'AUTOCOMMIT': True,
        'CONN_MAX_AGE': 0,
        'CONN_HEALTH_CHECKS': False,
        'OPTIONS': {},
    }

    print(f"[SSR] Alias registrado: {alias} → {ruta_db}")
 # ← 💡 esta línea es clave

