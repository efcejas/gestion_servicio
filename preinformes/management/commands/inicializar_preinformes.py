from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from preinformes.models import TipoEstudio, Region, PlantillaPreinforme

User = get_user_model()


class Command(BaseCommand):
    help = 'Inicializa los datos básicos para el sistema de preinformes'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando carga de datos básicos...')
        
        # Crear tipos de estudios
        tipos_estudios = [
            {'nombre': 'Radiografía Simple', 'descripcion': 'Radiografía convencional'},
            {'nombre': 'Tomografía Computada', 'descripcion': 'TC con o sin contraste'},
            {'nombre': 'Resonancia Magnética', 'descripcion': 'RM con o sin contraste'},
            {'nombre': 'Ecografía', 'descripcion': 'Ultrasonografía'},
            {'nombre': 'Mamografía', 'descripcion': 'Estudio mamográfico'},
            {'nombre': 'Angiografía', 'descripcion': 'Estudio angiográfico'},
            {'nombre': 'Fluoroscopía', 'descripcion': 'Estudio con fluoroscopio'},
        ]
        
        for tipo_data in tipos_estudios:
            tipo, created = TipoEstudio.objects.get_or_create(
                nombre=tipo_data['nombre'],
                defaults={'descripcion': tipo_data['descripcion']}
            )
            if created:
                self.stdout.write(f'  ✓ Creado tipo de estudio: {tipo.nombre}')
        
        # Crear regiones
        regiones = [
            {'nombre': 'Tórax', 'descripcion': 'Región torácica'},
            {'nombre': 'Abdomen', 'descripcion': 'Región abdominal'},
            {'nombre': 'Pelvis', 'descripcion': 'Región pélvica'},
            {'nombre': 'Cráneo', 'descripcion': 'Región craneal'},
            {'nombre': 'Cuello', 'descripcion': 'Región cervical'},
            {'nombre': 'Columna Vertebral', 'descripcion': 'Columna cervical, dorsal y lumbar'},
            {'nombre': 'Miembros Superiores', 'descripcion': 'Brazos, antebrazos, manos'},
            {'nombre': 'Miembros Inferiores', 'descripcion': 'Muslos, piernas, pies'},
            {'nombre': 'Esqueleto Axial', 'descripcion': 'Estructuras del esqueleto central'},
            {'nombre': 'Sistema Cardiovascular', 'descripcion': 'Corazón y vasos sanguíneos'},
        ]
        
        for region_data in regiones:
            region, created = Region.objects.get_or_create(
                nombre=region_data['nombre'],
                defaults={'descripcion': region_data['descripcion']}
            )
            if created:
                self.stdout.write(f'  ✓ Creada región: {region.nombre}')
        
        # Buscar un usuario staff para crear plantillas
        try:
            staff_user = User.objects.filter(
                rol__in=['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
            ).first()
            
            if not staff_user:
                self.stdout.write(
                    self.style.WARNING('No se encontró usuario staff. Creando plantillas sin usuario asociado.')
                )
                # Crear un usuario temporal para las plantillas
                staff_user = User.objects.create_user(
                    username='admin_plantillas',
                    email='admin@example.com',
                    password='temp_password',
                    rol='medico_staff',
                    first_name='Admin',
                    last_name='Plantillas'
                )
                self.stdout.write(f'  ✓ Usuario temporal creado: {staff_user.username}')
            
            # Crear plantillas básicas
            plantillas = [
                {
                    'nombre': 'RX Tórax Normal',
                    'tipo_estudio': 'Radiografía Simple',
                    'region': 'Tórax',
                    'contenido': '''TÉCNICA:
Se realiza radiografía de tórax en proyección PA y lateral en inspiración.

HALLAZGOS:
{HALLAZGOS}

CONCLUSIÓN:
Sin hallazgos patológicos evidentes en el momento actual.'''
                },
                {
                    'nombre': 'TC Abdomen con Contraste',
                    'tipo_estudio': 'Tomografía Computada',
                    'region': 'Abdomen',
                    'contenido': '''TÉCNICA:
Se realiza TC de abdomen con administración de contraste endovenoso.

HALLAZGOS:
{HALLAZGOS}

CONCLUSIÓN:
Estudio dentro de los parámetros normales.'''
                },
                {
                    'nombre': 'Ecografía Abdominal',
                    'tipo_estudio': 'Ecografía',
                    'region': 'Abdomen',
                    'contenido': '''TÉCNICA:
Ecografía abdominal con transductor convexo de 3,5 MHz.

HALLAZGOS:
{HALLAZGOS}

CONCLUSIÓN:
Estudio ecográfico abdominal normal.'''
                },
                {
                    'nombre': 'RM Cráneo',
                    'tipo_estudio': 'Resonancia Magnética',
                    'region': 'Cráneo',
                    'contenido': '''TÉCNICA:
RM de cráneo en secuencias T1, T2, FLAIR y DWI.

HALLAZGOS:
{HALLAZGOS}

CONCLUSIÓN:
RM de cráneo sin alteraciones.'''
                }
            ]
            
            for plantilla_data in plantillas:
                try:
                    tipo_estudio = TipoEstudio.objects.get(nombre=plantilla_data['tipo_estudio'])
                    region = Region.objects.get(nombre=plantilla_data['region'])
                    
                    plantilla, created = PlantillaPreinforme.objects.get_or_create(
                        nombre=plantilla_data['nombre'],
                        tipo_estudio=tipo_estudio,
                        region=region,
                        defaults={
                            'contenido': plantilla_data['contenido'],
                            'creada_por': staff_user
                        }
                    )
                    if created:
                        self.stdout.write(f'  ✓ Creada plantilla: {plantilla.nombre}')
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error creando plantilla {plantilla_data["nombre"]}: {e}')
                    )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creando plantillas: {e}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('✓ Datos básicos cargados exitosamente!')
        )
        self.stdout.write('')
        self.stdout.write('Puedes empezar a usar el sistema de preinformes ahora.')
        self.stdout.write('URLs principales:')
        self.stdout.write('  - Dashboard Residente: /preinformes/')
        self.stdout.write('  - Dashboard Staff: /preinformes/staff/')
        self.stdout.write('  - Admin: /admin/ (para gestionar tipos, regiones y plantillas)')