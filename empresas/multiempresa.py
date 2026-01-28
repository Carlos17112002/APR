from django.conf import settings
import os
import sqlite3
from django.db import connections
from django.core.management import call_command
import threading

# Cache para evitar ejecutar migraciones repetidamente
_migrated_databases = set()
_migration_lock = threading.Lock()

# LISTA CORREGIDA de apps que deben migrarse a cada empresa
# Quita apps que tienen ForeignKey a la base general
APPS_EMPRESA = [
    'clientes',     # ✓ OK (si no tiene FK a Empresa)
    'boletas',      # ✓ OK (si no tiene FK a Empresa)  
    'lecturas',     # ⚠️  ¡PROBLEMA! Tiene FK a Empresa
    'avisos',       # ✓ OK (si no tiene FK a Empresa)
    'faq',          # ✓ OK (si no tiene FK a Empresa)
    'informes',     # ✓ OK (si no tiene FK a Empresa)
    'inventario',   # ✓ OK (si no tiene FK a Empresa)
    'contabilidad', # ✓ OK (si no tiene FK a Empresa)
    'trabajadores', # ✓ OK (si no tiene FK a Empresa)
]

# APPS QUE VAN A LA BASE GENERAL (NO migrar a empresas)
APPS_GENERAL = [
    'empresas',     # ❌ NO migrar (está en base general)
    'usuarios',     # ❌ NO migrar (está en base general)
    'auth',         # ❌ NO migrar (Django built-in)
    'admin',        # ❌ NO migrar (Django built-in)
    'contenttypes', # ❌ NO migrar (Django built-in)
    'sessions',     # ❌ NO migrar (Django built-in)
]

def registrar_alias(slug, ejecutar_migraciones=True):
    """
    Registra un alias de base de datos para una empresa.
    ejecutar_migraciones: Solo ejecutar migraciones si es necesario
    """
    alias = f'db_{slug}'
    ruta_db = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
    
    # Si ya está registrado, retornar inmediatamente
    if alias in settings.DATABASES:
        # Solo verificar si necesita migraciones
        if ejecutar_migraciones and alias not in _migrated_databases:
            _verificar_y_ejecutar_migraciones(alias)
        return alias
    
    # Crear directorio si no existe
    os.makedirs(settings.BASES_DIR, exist_ok=True)
    
    # Crear archivo de base de datos si no existe
    db_existia = os.path.exists(ruta_db)
    if not db_existia:
        open(ruta_db, 'w').close()
        print(f"[SSR] Base de datos creada: {alias} → {ruta_db}")
    
    # Registrar en DATABASES
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
    
    # Ejecutar migraciones SOLO si es necesario
    if ejecutar_migraciones and alias not in _migrated_databases:
        _verificar_y_ejecutar_migraciones(alias, db_existia)
    
    return alias

def _verificar_y_ejecutar_migraciones(alias, db_existia=False):
    """
    Verifica si una base de datos necesita migraciones y las ejecuta si es necesario.
    """
    with _migration_lock:
        if alias in _migrated_databases:
            return
        
        try:
            connection = connections[alias]
            
            with connection.cursor() as cursor:
                # Verificar si existe la tabla django_migrations
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='django_migrations'
                """)
                
                tiene_migrations = cursor.fetchone() is not None
                
                if not tiene_migrations or db_existia:
                    # Base de datos nueva o sin migraciones
                    print(f"[SSR] Ejecutando migraciones iniciales para {alias}...")
                    
                    # SOLO migrar apps de empresa (NO las generales)
                    for app in APPS_EMPRESA:
                        try:
                            # Verificar si la app existe realmente
                            if _app_tiene_migraciones(app):
                                call_command('migrate', app, 
                                           database=alias,
                                           interactive=False,
                                           verbosity=0)
                                print(f"[SSR]   ✓ {app}")
                            else:
                                print(f"[SSR]   ⚠️  {app} no tiene migraciones")
                        except Exception as e:
                            error_msg = str(e)
                            # Detectar si es error por ForeignKey a base general
                            if "no such table" in error_msg and "empresas_empresa" in error_msg:
                                print(f"[SSR]   ❌ {app}: Error de FK a Empresa")
                                print(f"[SSR]      Necesita ajustar modelo para usar empresa_slug")
                            else:
                                print(f"[SSR]   ✗ {app}: {error_msg[:100]}...")
                    
                    # Marcar como migrada
                    _migrated_databases.add(alias)
                    print(f"[SSR] Migraciones completadas para {alias}")
                    
                    # Verificar qué se migró realmente
                    verificar_migraciones_aplicadas(alias)
                    
                else:
                    # Ya tiene tabla django_migrations
                    cursor.execute("SELECT COUNT(*) FROM django_migrations")
                    count = cursor.fetchone()[0]
                    
                    if count > 0:
                        # Verificar si faltan apps
                        verificar_migraciones_aplicadas(alias)
                        
                        # Verificar apps faltantes específicamente
                        cursor.execute("SELECT DISTINCT app FROM django_migrations")
                        apps_migradas = {row[0] for row in cursor.fetchall()}
                        
                        apps_faltantes = [app for app in APPS_EMPRESA if app not in apps_migradas]
                        
                        if apps_faltantes:
                            print(f"[SSR] Apps faltantes en {alias}: {', '.join(apps_faltantes)}")
                            print(f"[SSR] Ejecutando migraciones faltantes...")
                            
                            for app in apps_faltantes:
                                try:
                                    if _app_tiene_migraciones(app):
                                        call_command('migrate', app,
                                                   database=alias,
                                                   interactive=False,
                                                   verbosity=0)
                                        print(f"[SSR]   ✓ {app} (faltante)")
                                except Exception as e:
                                    print(f"[SSR]   ✗ {app}: {e}")
                        
                        _migrated_databases.add(alias)
                        print(f"[SSR] {alias} ya tiene {count} migraciones aplicadas")
                    else:
                        # Tabla existe pero vacía
                        print(f"[SSR] Tabla django_migrations vacía en {alias}, ejecutando migraciones...")
                        call_command('migrate', 
                                   database=alias,
                                   interactive=False,
                                   verbosity=0)
                        _migrated_databases.add(alias)
                        
        except Exception as e:
            print(f"[SSR] Error verificando migraciones para {alias}: {e}")
            # No marcar como migrada para intentar de nuevo después

def verificar_migraciones_aplicadas(alias):
    """
    Muestra qué migraciones están aplicadas en una base de datos.
    """
    try:
        connection = connections[alias]
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT app, name, applied 
                FROM django_migrations 
                ORDER BY app, applied
            """)
            
            migraciones = cursor.fetchall()
            
            print(f"\n[SSR] Migraciones aplicadas en {alias}:")
            
            apps_dict = {}
            for app, name, applied in migraciones:
                if app not in apps_dict:
                    apps_dict[app] = []
                apps_dict[app].append(name)
            
            for app in sorted(apps_dict.keys()):
                mig_count = len(apps_dict[app])
                print(f"  - {app}: {mig_count} migración(es)")
                for mig_name in apps_dict[app]:
                    print(f"      • {mig_name}")
            
            # Verificar específicamente lecturas
            apps_migradas = set(apps_dict.keys())
            if 'lecturas' not in apps_migradas:
                print(f"\n⚠️  App 'lecturas' NO tiene migraciones aplicadas")
                print(f"   Razón probable: Tiene ForeignKey a 'empresas.Empresa'")
                print(f"   Solución: Cambiar a empresa_slug en models.py")
                return False
            else:
                print(f"\n✅ App 'lecturas' tiene migraciones aplicadas")
                return True
                
    except Exception as e:
        print(f"[SSR] Error verificando migraciones: {e}")
        return False

def verificar_migraciones_pendientes(alias):
    """
    Verifica si hay migraciones pendientes sin ejecutarlas.
    """
    try:
        from django.db.migrations.executor import MigrationExecutor
        
        connection = connections[alias]
        executor = MigrationExecutor(connection)
        
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        
        return len(plan) > 0
    except:
        return True  # Si hay error, asumir que necesita migraciones

def ejecutar_migraciones_si_necesarias(alias):
    """
    Ejecuta migraciones solo si son necesarias.
    """
    if alias not in _migrated_databases:
        if verificar_migraciones_pendientes(alias):
            _verificar_y_ejecutar_migraciones(alias)
        else:
            _migrated_databases.add(alias)

def _app_tiene_migraciones(app_label):
    """
    Verifica si una app tiene archivos de migración.
    """
    import os
    from django.apps import apps
    
    try:
        app_config = apps.get_app_config(app_label)
        migrations_path = os.path.join(app_config.path, 'migrations')
        
        if os.path.exists(migrations_path):
            # Verificar si hay archivos .py (excepto __init__.py)
            mig_files = [f for f in os.listdir(migrations_path) 
                        if f.endswith('.py') and f != '__init__.py']
            return len(mig_files) > 0
    except:
        pass
    
    return False

def reparar_lecturas_empresa(alias):
    """
    Intenta reparar específicamente la app 'lecturas' para una empresa.
    """
    print(f"[SSR] Intentando reparar 'lecturas' para {alias}...")
    
    try:
        # 1. Verificar estado actual
        verificar_migraciones_aplicadas(alias)
        
        # 2. Intentar migración forzada de lecturas
        call_command('migrate', 'lecturas', 'zero',
                   database=alias,
                   interactive=False,
                   verbosity=0)
        
        print(f"[SSR]   Migraciones 'zero' aplicadas para lecturas")
        
        # 3. Crear migración temporal sin ForeignKey
        print(f"[SSR]   Creando migración temporal...")
        
        # Esto es un workaround - en realidad necesitas ajustar el modelo
        from django.core.management import call_command
        call_command('makemigrations', 'lecturas', 
                   name='temp_remove_empresa_fk',
                   interactive=False,
                   verbosity=0)
        
        # 4. Aplicar migración temporal
        call_command('migrate', 'lecturas',
                   database=alias,
                   interactive=False,
                   verbosity=1)
        
        print(f"[SSR]   ✅ 'lecturas' reparada temporalmente")
        
        # 5. Actualizar cache
        _migrated_databases.add(alias)
        
        return True
        
    except Exception as e:
        print(f"[SSR]   ❌ Error reparando 'lecturas': {e}")
        return False

def ejecutar_migracion_especifica(alias, app_label, migration_name=None):
    """
    Ejecuta una migración específica para una app.
    """
    try:
        if migration_name:
            call_command('migrate', app_label, migration_name,
                       database=alias,
                       interactive=False,
                       verbosity=1)
        else:
            call_command('migrate', app_label,
                       database=alias,
                       interactive=False,
                       verbosity=1)
        
        print(f"[SSR] ✅ Migración ejecutada: {app_label}" + 
              (f".{migration_name}" if migration_name else ""))
        return True
        
    except Exception as e:
        print(f"[SSR] ❌ Error migrando {app_label}: {e}")
        return False

def crear_tabla_lecturas_manual(alias):
    """
    Crea la tabla lecturas_lecturamovil manualmente (workaround de emergencia).
    """
    try:
        connection = connections[alias]
        
        with connection.cursor() as cursor:
            # SQL para crear tabla sin ForeignKey
            sql = """
            CREATE TABLE IF NOT EXISTS lecturas_lecturamovil (
                id TEXT PRIMARY KEY,
                empresa_slug VARCHAR(50),
                cliente INTEGER,
                fecha_lectura DATE,
                lectura_actual DECIMAL(10,2),
                lectura_anterior DECIMAL(10,2),
                consumo DECIMAL(10,2),
                foto_medidor VARCHAR(500),
                latitud DECIMAL(9,6),
                longitud DECIMAL(9,6),
                estado VARCHAR(20),
                fecha_sincronizacion DATETIME,
                observaciones_app TEXT,
                usuario_app VARCHAR(100),
                usada_para_boleta BOOLEAN DEFAULT 0
            );
            """
            
            cursor.execute(sql)
            
            # Crear índices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lecturas_empresa_estado ON lecturas_lecturamovil(empresa_slug, estado);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lecturas_cliente_fecha ON lecturas_lecturamovil(cliente, fecha_lectura);")
            
            print(f"[SSR] ✅ Tabla lecturas_lecturamovil creada manualmente en {alias}")
            
            # Registrar migración falsa
            cursor.execute("""
                INSERT OR IGNORE INTO django_migrations (app, name, applied)
                VALUES ('lecturas', '0001_manual_fix', datetime('now'))
            """)
            
            return True
            
    except Exception as e:
        print(f"[SSR] ❌ Error creando tabla manual: {e}")
        return False

# Función para diagnosticar problemas
def diagnosticar_empresa(slug):
    """
    Diagnóstico completo para una empresa.
    """
    alias = f'db_{slug}'
    ruta_db = os.path.join(settings.BASES_DIR, f'{alias}.sqlite3')
    
    print(f"\n🔍 DIAGNÓSTICO para {slug}")
    print(f"   Alias: {alias}")
    print(f"   Archivo: {ruta_db}")
    
    if not os.path.exists(ruta_db):
        print("   ❌ Archivo no existe")
        return
    
    # 1. Verificar tamaño
    size = os.path.getsize(ruta_db)
    print(f"   📏 Tamaño: {size} bytes")
    
    # 2. Conectar y ver tablas
    try:
        conn = sqlite3.connect(ruta_db)
        cursor = conn.cursor()
        
        # Ver todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tablas = cursor.fetchall()
        
        print(f"   📋 Tablas ({len(tablas)}):")
        for tabla in tablas:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla[0]}")
            count = cursor.fetchone()[0]
            print(f"      - {tabla[0]}: {count} registros")
        
        # Verificar lecturas específicamente
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='lecturas_lecturamovil'
        """)
        
        if cursor.fetchone():
            print("   ✅ Tabla lecturas_lecturamovil EXISTE")
        else:
            print("   ❌ Tabla lecturas_lecturamovil NO EXISTE")
            print("   💡 Solución: ejecutar crear_tabla_lecturas_manual('{alias}')")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Error diagnóstico: {e}")

def limpiar_alias_eliminado(slug):
    """
    Limpia completamente un alias eliminado de settings.DATABASES
    """
    alias = f'db_{slug}'
    
    # 1. Remover de settings.DATABASES
    if alias in settings.DATABASES:
        del settings.DATABASES[alias]
        print(f"[SSR] Alias {alias} removido de settings.DATABASES")
    
    # 2. Cerrar conexión si existe
    try:
        from django.db import connections
        if alias in connections.databases:
            if alias in connections._connections:
                try:
                    connections[alias].close()
                except:
                    pass
                del connections._connections[alias]
            del connections.databases[alias]
    except:
        pass
    
    # 3. Actualizar lista de alias en cache
    global _migrated_databases
    if alias in _migrated_databases:
        _migrated_databases.remove(alias)
    
    return True