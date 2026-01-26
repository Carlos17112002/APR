import uuid
import secrets
from datetime import datetime, timedelta
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import json
from django.utils import timezone  # Añade esta importación

class Empresa(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    color_dashboard = models.CharField(max_length=20, default='#008000')
    sectores_json = models.TextField(blank=True, default='[]')
    
    # Nuevos campos para app móvil
    color_app_primario = models.CharField(max_length=7, default='#1E40AF')
    color_app_secundario = models.CharField(max_length=7, default='#DC2626')
    logo_app = models.ImageField(upload_to='logos_apps/', blank=True, null=True)
    
    # Configuración app
    app_generada = models.BooleanField(default=False)
    fecha_generacion_app = models.DateTimeField(null=True, blank=True)
    version_app = models.CharField(max_length=20, default='1.0.0')
    api_key_app = models.CharField(max_length=64, blank=True)
    
    # URLs
    url_servidor = models.CharField(max_length=200, blank=True, default='http://localhost:8000')
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nombre)
        
        if not self.api_key_app:
            self.api_key_app = secrets.token_hex(32)
            
        super().save(*args, **kwargs)
    
    def sectores(self):
        try:
            return json.loads(self.sectores_json)
        except:
            return []
    
    def generar_config_app(self):
        """Genera configuración JSON para la app móvil"""
        print(f"\n{'='*60}")
        print(f"DEBUG: Generando config app para empresa: {self.nombre}")
        print(f"DEBUG: Slug: {self.slug}")
        print(f"DEBUG: Alias DB: db_{self.slug}")
        print(f"{'='*60}")
        
        config = {
            'app_name': f'SSR {self.nombre}',
            'empresa_nombre': self.nombre,
            'empresa_slug': self.slug,
            'version': self.version_app,
            'primary_color': self.color_app_primario,
            'secondary_color': self.color_app_secundario,
            'base_url': f'{self.url_servidor}/api/{self.slug}/',
            'api_key': self.api_key_app,
            'sectores': self.sectores(),
        }
        
        # Añadir configuración de la app móvil si existe
        try:
            from lecturas.models import ConfigAppMovil
            config_app = self.config_app
            
            mensaje_bienvenida = config_app.mensaje_bienvenida
            if not mensaje_bienvenida:
                mensaje_bienvenida = f'Bienvenido a la app de {self.nombre}'
                
            config.update({
                'habilitar_mapa': config_app.habilitar_mapa,
                'habilitar_offline': config_app.habilitar_offline,
                'sincronizacion_auto': config_app.sincronizacion_auto,
                'validar_gps': config_app.validar_gps,
                'mensaje_bienvenida': mensaje_bienvenida,
                'mostrar_logo': config_app.mostrar_logo,
                'intervalo_sincronizacion': config_app.intervalo_sincronizacion,
                'max_lecturas_pendientes': config_app.max_lecturas_pendientes,
            })
            
            print(f"DEBUG: ConfigAppMovil encontrada")
            
        except Exception as e:
            config.update({
                'habilitar_mapa': True,
                'habilitar_offline': True,
                'sincronizacion_auto': True,
                'validar_gps': True,
                'mensaje_bienvenida': f'Bienvenido a la app de {self.nombre}',
                'mostrar_logo': True,
                'intervalo_sincronizacion': 5,
                'max_lecturas_pendientes': 100,
            })
            print(f"DEBUG: No hay ConfigAppMovil, usando valores por defecto")
        
        # ¡IMPORTANTE! Cargar clientes desde la base de datos correcta
        try:
            from clientes.models import Cliente
            
            alias_db = f'db_{self.slug}'
            print(f"DEBUG: Usando base de datos: {alias_db}")
            
            # Verificar si la base de datos existe y es accesible
            try:
                # Contar clientes en la BD de la empresa
                clientes_count = Cliente.objects.using(alias_db).count()
                print(f"DEBUG: Clientes en BD {alias_db}: {clientes_count}")
                
                # Obtener todos los clientes
                clientes_qs = Cliente.objects.using(alias_db).all()
                
                # Procesar clientes
                clientes_list = []
                sectores_cliente_set = set()
                
                for cliente in clientes_qs:
                    try:
                        cliente_data = {
                            'id': cliente.id,
                            'codigo': cliente.rut if cliente.rut else f"CL-{cliente.id:03d}",
                            'nombre': cliente.nombre if cliente.nombre else f"Cliente {cliente.id}",
                            'rut': cliente.rut or '',
                            'direccion': cliente.direccion or '',
                            'telefono': cliente.telefono or '',
                            'email': cliente.email or '',
                            'numero_medidor': cliente.medidor or f"MED-{cliente.id:04d}",
                            'sector': cliente.sector or 'Sin Sector',
                            'latitud': float(cliente.latitude) if cliente.latitude else 0.0,
                            'longitud': float(cliente.longitude) if cliente.longitude else 0.0,
                            'estado': 'Activo',
                        }
                        
                        clientes_list.append(cliente_data)
                        
                        # Añadir sector a la lista
                        if cliente.sector and cliente.sector.strip():
                            sectores_cliente_set.add(cliente.sector.strip())
                            
                    except Exception as e:
                        print(f"DEBUG: Error procesando cliente ID {cliente.id}: {e}")
                        continue
                
                print(f"DEBUG: Clientes procesados exitosamente: {len(clientes_list)}")
                print(f"DEBUG: Sectores de clientes: {list(sectores_cliente_set)}")
                
                # Actualizar la configuración
                config['clientes'] = clientes_list
                
                # Combinar sectores del JSON con sectores de clientes
                sectores_json = self.sectores()
                sectores_combinados = list(set(sectores_json + list(sectores_cliente_set)))
                config['sectores'] = sectores_combinados
                
                print(f"DEBUG: Sectores combinados: {sectores_combinados}")
                print(f"DEBUG: Total sectores: {len(sectores_combinados)}")
                
            except Exception as db_error:
                print(f"DEBUG: Error accediendo a BD {alias_db}: {db_error}")
                config['clientes'] = []
                config['sectores'] = self.sectores()
                
        except Exception as e:
            config['clientes'] = []
            print(f"⚠️  ERROR general cargando clientes: {e}")
            import traceback
            traceback.print_exc()
        
        print(f"DEBUG: Configuración final - Clientes: {len(config.get('clientes', []))}")
        print(f"DEBUG: Configuración final - Sectores: {len(config.get('sectores', []))}")
        print(f"{'='*60}\n")
        
        return config
    
    # Métodos auxiliares para templates
    def get_logo_url(self):
        """Retorna la URL del logo para la app"""
        if self.logo_app:
            return self.logo_app.url
        return None
    
    def get_api_url(self):
        """Retorna la URL base de la API"""
        return f'{self.url_servidor}/api/{self.slug}/'
    
    def get_lecturas_count(self):
        """Retorna el número total de lecturas"""
        from lecturas.models import LecturaMovil
        return LecturaMovil.objects.filter(empresa=self).count()
    
    def get_dispositivos_activos_count(self):
        """Retorna el número de dispositivos activos"""
        return self.dispositivos.filter(activo=True).count()
    
    def get_lecturas_hoy_count(self):
        """Retorna el número de lecturas hoy"""
        from lecturas.models import LecturaMovil
        return LecturaMovil.objects.filter(
            empresa=self,
            fecha_sincronizacion__date=timezone.now().date()
        ).count()
    
    def get_app_status_display(self):
        """Retorna el estado de la app formateado"""
        if self.app_generada:
            return {
                'text': 'Generada',
                'class': 'success',
                'icon': 'bi-check-circle'
            }
        else:
            return {
                'text': 'No generada',
                'class': 'warning',
                'icon': 'bi-exclamation-triangle'
            }
    
    def get_generation_date_display(self):
        """Retorna la fecha de generación formateada"""
        if self.fecha_generacion_app:
            return self.fecha_generacion_app.strftime('%d/%m/%Y %H:%M')
        return 'Nunca'
    
    def get_qr_url(self):
        """Retorna la URL del QR"""
        return f'/static/apps_qr/{self.slug}.png'
    
    def get_config_download_url(self):
        """Retorna la URL para descargar la configuración"""
        return f'/apps/descargar-config/{self.slug}/'
    
    def get_generate_app_url(self):
        """Retorna la URL para generar la app"""
        return f'/apps/generar/{self.slug}/'
    
    def get_manage_devices_url(self):
        """Retorna la URL para gestionar dispositivos"""
        return f'/apps/dispositivos/{self.slug}/'
    
    def get_view_qr_url(self):
        """Retorna la URL para ver el QR"""
        return f'/apps/ver-qr/{self.slug}/'
    
    def get_detail_url(self):
        """Retorna la URL del detalle de la app"""
        return f'/apps/detalle/{self.slug}/'
    
    def __str__(self):
        return self.nombre
    def debug_clientes_y_sectores(self):
        """Método para debug: ver qué clientes y sectores tiene la empresa"""
        from clientes.models import Cliente
        
        debug_info = {
            'empresa': self.nombre,
            'slug': self.slug,
            'sectores_del_json': self.sectores(),
            'sectores_json_raw': self.sectores_json,
        }
        
        # Verificar clientes
        try:
            # Intentar todas las formas posibles de encontrar clientes
            clientes_por_slug = Cliente.objects.filter(empresa_slug__iexact=self.slug)
            debug_info['clientes_por_slug'] = {
                'cantidad': clientes_por_slug.count(),
                'ejemplos': list(clientes_por_slug.values('id', 'nombre', 'rut', 'empresa_slug')[:5])
            }
            
            # Ver todos los slugs distintos en clientes
            todos_slugs = Cliente.objects.values_list('empresa_slug', flat=True).distinct()
            debug_info['todos_los_slugs_en_clientes'] = list(todos_slugs)
            
            # Ver todos los clientes sin filtrar (primeros 10)
            todos_clientes = Cliente.objects.all()[:10]
            debug_info['todos_clientes_primeros_10'] = [
                {'id': c.id, 'nombre': c.nombre, 'empresa_slug': c.empresa_slug}
                for c in todos_clientes
            ]
            
        except Exception as e:
            debug_info['error_cliente'] = str(e)
        
        return debug_info

from django.db import models
from django.contrib.auth.models import User

class EliminacionEmpresa(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.CharField(max_length=50)
    ejecutado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.slug} eliminado por {self.ejecutado_por} el {self.fecha.strftime('%d/%m/%Y %H:%M')}"

