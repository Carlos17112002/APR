#!/usr/bin/env python
"""
ELIMINACIÓN NUCLEAR - Elimina empresas sin usar Django ORM
"""
import os
import sys
import time
import json
import shutil
from datetime import datetime

def eliminar_empresa_nuclear(slug):
    """
    Elimina una empresa COMPLETAMENTE sin usar Django.
    """
    print(f"\n{'='*70}")
    print(f"🚀 ELIMINACIÓN NUCLEAR - {slug}")
    print(f"{'='*70}")
    
    # Configuración de rutas
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BASES_DIR = os.path.join(BASE_DIR, 'bases')
    
    logs = []
    logs.append(f"=== ELIMINACIÓN NUCLEAR: {slug} ===")
    logs.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # ===== PASO 1: DETENER PROCESOS QUE USAN EL ARCHIVO =====
        print("\n[1] Deteniendo procesos...")
        logs.append("[1] Deteniendo procesos...")
        
        db_file = os.path.join(BASES_DIR, f'db_{slug}.sqlite3')
        
        # Método 1: Usar handle64.exe de Sysinternals
        try:
            import subprocess
            
            # Verificar qué procesos están usando el archivo
            print("  Buscando procesos que usan el archivo...")
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'python.exe' in result.stdout:
                print("  Procesos Python encontrados, terminando...")
                
                # Opcional: Terminar procesos Python (solo si es seguro)
                kill_choice = input("  ¿Terminar procesos Python? (s/n): ").lower()
                if kill_choice == 's':
                    subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                                 capture_output=True)
                    print("  ✓ Procesos Python terminados")
                    time.sleep(2)  # Esperar que se liberen los locks
                
        except Exception as e:
            print(f"  ⚠️  Error buscando procesos: {e}")
        
        # ===== PASO 2: ELIMINAR ARCHIVOS BLOQUEADOS =====
        print("\n[2] Eliminando archivos bloqueados...")
        logs.append("[2] Eliminando archivos bloqueados...")
        
        archivos = [
            db_file,
            db_file + '-wal',
            db_file + '-shm',
            db_file.replace('.sqlite3', '.db'),
        ]
        
        eliminados = 0
        for archivo in archivos:
            if os.path.exists(archivo):
                print(f"  Procesando: {os.path.basename(archivo)}")
                
                # Método 1: Intentar eliminar normalmente
                try:
                    os.remove(archivo)
                    print(f"    ✓ Eliminado normalmente")
                    eliminados += 1
                    logs.append(f"    ✓ {os.path.basename(archivo)} eliminado")
                    continue
                except:
                    pass
                
                # Método 2: Cambiar permisos y eliminar
                try:
                    os.chmod(archivo, 0o777)  # Dar todos los permisos
                    os.remove(archivo)
                    print(f"    ✓ Eliminado tras cambiar permisos")
                    eliminados += 1
                    logs.append(f"    ✓ {os.path.basename(archivo)} eliminado (cambió permisos)")
                    continue
                except:
                    pass
                
                # Método 3: Renombrar (funciona incluso si está abierto)
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nuevo_nombre = f"{archivo}.DELETED_{timestamp}"
                    os.rename(archivo, nuevo_nombre)
                    print(f"    ⚠️  Renombrado a: {os.path.basename(nuevo_nombre)}")
                    eliminados += 1
                    logs.append(f"    ⚠️  {os.path.basename(archivo)} renombrado")
                except Exception as e:
                    print(f"    ✗ Error: {e}")
                    logs.append(f"    ✗ {os.path.basename(archivo)}: {e}")
            else:
                print(f"  ℹ️  {os.path.basename(archivo)} no existe")
                logs.append(f"    ℹ️  {os.path.basename(archivo)} no existe")
        
        print(f"  Resumen: {eliminados}/{len(archivos)} archivos procesados")
        logs.append(f"  Resumen: {eliminados}/{len(archivos)} archivos procesados")
        
        # ===== PASO 3: ELIMINAR DIRECTORIOS =====
        print("\n[3] Eliminando directorios...")
        logs.append("[3] Eliminando directorios...")
        
        directorios = [
            os.path.join(BASE_DIR, 'apps_moviles', 'apps_generadas', slug),
            os.path.join(BASE_DIR, 'media', 'empresas', slug),
            os.path.join(BASE_DIR, 'media', 'logos', slug),
            os.path.join(BASE_DIR, 'static', 'empresas', slug),
            os.path.join(BASE_DIR, 'logs', slug),
        ]
        
        dir_eliminados = 0
        for dir_path in directorios:
            if os.path.exists(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    print(f"  ✓ Directorio eliminado: {os.path.basename(dir_path)}")
                    dir_eliminados += 1
                    logs.append(f"    ✓ {os.path.basename(dir_path)} eliminado")
                except Exception as e:
                    print(f"  ✗ Error eliminando {dir_path}: {e}")
                    logs.append(f"    ✗ {os.path.basename(dir_path)}: {e}")
        
        print(f"  Resumen: {dir_eliminados}/{len(directorios)} directorios eliminados")
        logs.append(f"  Resumen: {dir_eliminados}/{len(directorios)} directorios eliminados")
        
        # ===== PASO 4: ELIMINAR DESDE POSTGRESQL MANUALMENTE =====
        print("\n[4] Eliminando de PostgreSQL (manualmente)...")
        logs.append("[4] Eliminando de PostgreSQL...")
        
        try:
            # Conectar a PostgreSQL directamente (sin Django)
            import psycopg2
            
            # Lee las credenciales desde settings.py o environment
            # (Ajusta estas credenciales según tu configuración)
            conn_params = {
                'dbname': 'asesora_principal',
                'user': 'postgres',
                'password': 'rental123',  # ¡Cambia esto!
                'host': 'localhost',
                'port': '5433'
            }
            
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()
            
            # PRIMERO: Verificar si la empresa existe
            cursor.execute("SELECT id, nombre FROM empresas_empresa WHERE slug = %s", (slug,))
            empresa_data = cursor.fetchone()
            
            if empresa_data:
                empresa_id, empresa_nombre = empresa_data
                print(f"  Empresa encontrada: {empresa_nombre} (ID: {empresa_id})")
                logs.append(f"  Empresa encontrada: {empresa_nombre}")
                
                # Eliminar empresa de PostgreSQL
                cursor.execute("DELETE FROM empresas_empresa WHERE slug = %s", (slug,))
                conn.commit()
                print(f"  ✓ Empresa eliminada de PostgreSQL")
                logs.append(f"    ✓ Empresa eliminada de PostgreSQL")
                
                # También eliminar cualquier registro de auditoría
                try:
                    cursor.execute("DELETE FROM empresas_eliminacionempresa WHERE slug = %s", (slug,))
                    conn.commit()
                    print(f"  ✓ Registros de auditoría eliminados")
                    logs.append(f"    ✓ Registros de auditoría eliminados")
                except:
                    print(f"  ℹ️  No se pudieron eliminar registros de auditoría")
                    
            else:
                print(f"  ℹ️  Empresa no encontrada en PostgreSQL")
                logs.append(f"    ℹ️  Empresa no encontrada en PostgreSQL")
            
            conn.close()
            
        except Exception as e:
            print(f"  ⚠️  Error PostgreSQL: {e}")
            logs.append(f"    ⚠️  Error PostgreSQL: {e}")
            
            # Alternativa: Usar psql directamente
            print("  Intentando con psql...")
            try:
                import subprocess
                psql_cmd = f'psql -U postgres -d asesora_principal -c "DELETE FROM empresas_empresa WHERE slug = \'{slug}\';"'
                subprocess.run(psql_cmd, shell=True, timeout=10)
                print(f"  ✓ Eliminado via psql")
            except:
                print(f"  ✗ Falló psql también")
        
        # ===== PASO 5: ACTUALIZAR CONFIGURACIONES =====
        print("\n[5] Actualizando configuraciones...")
        logs.append("[5] Actualizando configuraciones...")
        
        # Actualizar settings.DATABASES manualmente
        try:
            # Buscar y eliminar de settings.py
            settings_path = os.path.join(BASE_DIR, 'asesora_ssr', 'settings.py')
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    content = f.read()
                
                # Buscar y eliminar la entrada
                alias = f"'db_{slug}'"
                if alias in content:
                    # Encontrar desde DATABASES = { hasta }
                    import re
                    pattern = r"DATABASES\s*=\s*\{[^}]+\}"
                    new_content = re.sub(
                        f"\\s*'{slug}':\\s*{{[^}}]+}},\\s*", 
                        "", 
                        content
                    )
                    
                    with open(settings_path, 'w') as f:
                        f.write(new_content)
                    
                    print(f"  ✓ Actualizado settings.py")
                    logs.append(f"    ✓ Actualizado settings.py")
        except Exception as e:
            print(f"  ⚠️  Error actualizando settings: {e}")
        
        # Actualizar empresas_alias.json si existe
        alias_json_path = os.path.join(BASE_DIR, 'asesora_ssr', 'empresas_alias.json')
        if os.path.exists(alias_json_path):
            try:
                with open(alias_json_path, 'r') as f:
                    aliases = json.load(f)
                
                if slug in aliases:
                    aliases.remove(slug)
                    
                with open(alias_json_path, 'w') as f:
                    json.dump(aliases, f, indent=2)
                
                print(f"  ✓ Actualizado empresas_alias.json")
                logs.append(f"    ✓ Actualizado empresas_alias.json")
            except Exception as e:
                print(f"  ⚠️  Error actualizando JSON: {e}")
        
        # ===== PASO 6: GUARDAR LOG Y MOSTRAR RESUMEN =====
        print(f"\n{'='*70}")
        print("✅ ELIMINACIÓN NUCLEAR COMPLETADA")
        print(f"{'='*70}")
        
        logs.append(f"\n{'='*70}")
        logs.append("✅ ELIMINACIÓN NUCLEAR COMPLETADA")
        logs.append(f"{'='*70}")
        
        # Guardar log
        log_dir = os.path.join(BASE_DIR, 'logs', 'eliminaciones_nucleares')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'nuclear_{slug}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write("\n".join(logs))
        
        print(f"\n📁 Log guardado en: {log_file}")
        print("\n⚠️  RECOMENDACIONES:")
        print("1. Reinicia el servidor Django")
        print("2. Verifica que la empresa ya no aparezca")
        print("3. Si hay problemas, revisa el log anterior")
        
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python eliminar_empresa_nuclear.py <slug_empresa>")
        print("Ejemplo: python eliminar_empresa_nuclear.py apr-santiago")
        print("\n¡ADVERTENCIA! Este script eliminará la empresa COMPLETAMENTE.")
        print("No se puede deshacer. Usar con precaución.")
        sys.exit(1)
    
    # Confirmación final
    slug = sys.argv[1]
    print(f"\n🚨 ¡ADVERTENCIA NUCLEAR! 🚨")
    print(f"Estás a punto de eliminar la empresa: {slug}")
    print(f"Esta acción:")
    print(f"• Eliminará archivos bloqueados")
    print(f"• Eliminará de PostgreSQL")
    print(f"• Eliminará directorios")
    print(f"• NO SE PUEDE DESHACER")
    
    confirm = input(f"\n¿Continuar con la eliminación nuclear de '{slug}'? (escribe 'SI-ELIMINAR'): ")
    
    if confirm == "SI-ELIMINAR":
        eliminar_empresa_nuclear(slug)
    else:
        print("❌ Eliminación cancelada.")