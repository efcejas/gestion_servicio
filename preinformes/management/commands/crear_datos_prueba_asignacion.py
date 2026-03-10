"""
Comando Django para crear datos de prueba del sistema de asignación compartida
Crea usuarios con diferentes roles y preinformes en varios estados
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from preinformes.models import TipoEstudio, Region, PlantillaPreinforme, Preinforme, RevisionPreinforme

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea usuarios y preinformes de prueba para el sistema de asignación compartida'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Eliminar datos de prueba existentes antes de crear nuevos',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('🧪 CREANDO DATOS DE PRUEBA - ASIGNACIÓN COMPARTIDA'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        if options['reset']:
            self.limpiar_datos_prueba()

        # Crear usuarios
        usuarios = self.crear_usuarios()
        
        # Crear datos base si no existen
        self.crear_datos_base()
        
        # Crear preinformes de prueba
        self.crear_preinformes_prueba(usuarios)

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 70))
        self.stdout.write(self.style.SUCCESS('✅ DATOS DE PRUEBA CREADOS EXITOSAMENTE'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.mostrar_resumen(usuarios)

    def limpiar_datos_prueba(self):
        """Eliminar usuarios y preinformes de prueba existentes"""
        self.stdout.write('\n🧹 Limpiando datos de prueba existentes...')
        
        # Eliminar preinformes de usuarios de prueba
        usuarios_prueba = User.objects.filter(username__startswith='test_')
        preinformes_count = Preinforme.objects.filter(residente__in=usuarios_prueba).count()
        Preinforme.objects.filter(residente__in=usuarios_prueba).delete()
        
        # Eliminar usuarios de prueba
        usuarios_count = usuarios_prueba.count()
        usuarios_prueba.delete()
        
        self.stdout.write(self.style.WARNING(f'  - {usuarios_count} usuarios eliminados'))
        self.stdout.write(self.style.WARNING(f'  - {preinformes_count} preinformes eliminados'))

    def crear_usuarios(self):
        """Crear usuarios de prueba con diferentes roles"""
        self.stdout.write('\n👥 Creando usuarios de prueba...')
        
        usuarios = {}
        
        # Residentes
        residentes_data = [
            {
                'username': 'test_residente1',
                'password': 'test123',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'email': 'juan.perez@test.com',
                'rol': 'medico_residente',
                'perfil_completo': True,
            },
            {
                'username': 'test_residente2',
                'password': 'test123',
                'first_name': 'María',
                'last_name': 'González',
                'email': 'maria.gonzalez@test.com',
                'rol': 'medico_residente',
                'perfil_completo': True,
            },
            {
                'username': 'test_residente3',
                'password': 'test123',
                'first_name': 'Carlos',
                'last_name': 'Rodríguez',
                'email': 'carlos.rodriguez@test.com',
                'rol': 'medico_residente',
                'perfil_completo': True,
            }
        ]
        
        # Jefes de residentes
        jefes_data = [
            {
                'username': 'test_jefe1',
                'password': 'test123',
                'first_name': 'Laura',
                'last_name': 'Martínez',
                'email': 'laura.martinez@test.com',
                'rol': 'jefe_residentes',
                'perfil_completo': True,
            },
            {
                'username': 'test_jefe2',
                'password': 'test123',
                'first_name': 'Roberto',
                'last_name': 'Sánchez',
                'email': 'roberto.sanchez@test.com',
                'rol': 'jefe_residentes',
                'perfil_completo': True,
            }
        ]
        
        # Instructores
        instructores_data = [
            {
                'username': 'test_instructor1',
                'password': 'test123',
                'first_name': 'Ana',
                'last_name': 'López',
                'email': 'ana.lopez@test.com',
                'rol': 'instructor_residentes',
                'perfil_completo': True,
            }
        ]
        
        # Staff
        staff_data = [
            {
                'username': 'test_staff1',
                'password': 'test123',
                'first_name': 'Pedro',
                'last_name': 'Fernández',
                'email': 'pedro.fernandez@test.com',
                'rol': 'medico_staff',
                'perfil_completo': True,
            }
        ]
        
        # Crear todos los usuarios
        for data in residentes_data + jefes_data + instructores_data + staff_data:
            user, created = User.objects.get_or_create(
                username=data['username'],
                defaults=data
            )
            if created:
                user.set_password(data['password'])
                user.save()
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Creado: {data['first_name']} {data['last_name']} ({data['rol']})"
                ))
            else:
                self.stdout.write(f"  - Ya existe: {data['username']}")
            
            # Guardar referencias
            if data['rol'] == 'medico_residente':
                if 'residentes' not in usuarios:
                    usuarios['residentes'] = []
                usuarios['residentes'].append(user)
            elif data['rol'] == 'jefe_residentes':
                if 'jefes' not in usuarios:
                    usuarios['jefes'] = []
                usuarios['jefes'].append(user)
            elif data['rol'] == 'instructor_residentes':
                if 'instructores' not in usuarios:
                    usuarios['instructores'] = []
                usuarios['instructores'].append(user)
            elif data['rol'] == 'medico_staff':
                if 'staff' not in usuarios:
                    usuarios['staff'] = []
                usuarios['staff'].append(user)
        
        return usuarios

    def crear_datos_base(self):
        """Crear tipos de estudio, regiones y plantillas básicas si no existen"""
        self.stdout.write('\n📋 Verificando datos base...')
        
        # Crear tipo de estudio básico
        tipo, created = TipoEstudio.objects.get_or_create(
            nombre='Ecocardiograma Transtorácico',
            defaults={'activo': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  ✓ Tipo de estudio creado'))
        
        # Crear región básica
        region, created = Region.objects.get_or_create(
            nombre='Cardíaco',
            defaults={'activo': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  ✓ Región creada'))
        
        # Crear plantilla básica si no existe
        if not PlantillaPreinforme.objects.filter(
            tipo_estudio=tipo,
            region=region
        ).exists():
            PlantillaPreinforme.objects.create(
                nombre='Ecocardiograma Normal - Prueba',
                tipo_estudio=tipo,
                region=region,
                sistema_destino='eges',
                contenido='<p><strong>ECOCARDIOGRAMA TRANSTORÁCICO</strong></p><p>Ventrículo izquierdo de dimensiones normales.</p>',
                activa=True,
            )
            self.stdout.write(self.style.SUCCESS('  ✓ Plantilla creada'))

    def crear_preinformes_prueba(self, usuarios):
        """Crear preinformes de prueba en diferentes estados"""
        self.stdout.write('\n📝 Creando preinformes de prueba...')
        
        tipo = TipoEstudio.objects.get(nombre='Ecocardiograma Transtorácico')
        region = Region.objects.get(nombre='Cardíaco')
        plantilla = PlantillaPreinforme.objects.filter(tipo_estudio=tipo, region=region).first()
        
        residentes = usuarios.get('residentes', [])
        jefes = usuarios.get('jefes', [])
        staff = usuarios.get('staff', [])
        
        if not residentes:
            self.stdout.write(self.style.ERROR('  ✗ No hay residentes disponibles'))
            return
        
        residente1 = residentes[0]
        residente2 = residentes[1] if len(residentes) > 1 else residentes[0]
        jefe1 = jefes[0] if jefes else None
        staff1 = staff[0] if staff else None
        
        preinformes_data = [
            # Borradores (sin enviar a revisión)
            {
                'residente': residente1,
                'numero_estudio': 'TEST-2026-001',
                'estado': 'borrador',
                'nombre': 'García, Ana',
                'asignacion_compartida': False,
                'revisor': None,
            },
            {
                'residente': residente2,
                'numero_estudio': 'TEST-2026-002',
                'estado': 'borrador',
                'nombre': 'Fernández, Luis',
                'asignacion_compartida': False,
                'revisor': None,
            },
            # Pendientes con asignación compartida
            {
                'residente': residente1,
                'numero_estudio': 'TEST-2026-003',
                'estado': 'pendiente_revision',
                'nombre': 'López, Carmen',
                'asignacion_compartida': True,
                'revisor': None,
            },
            {
                'residente': residente2,
                'numero_estudio': 'TEST-2026-004',
                'estado': 'pendiente_revision',
                'nombre': 'Martínez, Jorge',
                'asignacion_compartida': True,
                'revisor': None,
            },
            {
                'residente': residente1,
                'numero_estudio': 'TEST-2026-005',
                'estado': 'pendiente_revision',
                'nombre': 'Sánchez, Rosa',
                'asignacion_compartida': True,
                'revisor': None,
            },
            # Pendientes con revisor asignado (no compartido)
            {
                'residente': residente2,
                'numero_estudio': 'TEST-2026-006',
                'estado': 'pendiente_revision',
                'nombre': 'Ramírez, Pedro',
                'asignacion_compartida': False,
                'revisor': jefe1,
            },
            {
                'residente': residente1,
                'numero_estudio': 'TEST-2026-007',
                'estado': 'pendiente_revision',
                'nombre': 'Torres, Elena',
                'asignacion_compartida': False,
                'revisor': staff1,
            },
            # Sin revisor asignado (pool tradicional)
            {
                'residente': residente2,
                'numero_estudio': 'TEST-2026-008',
                'estado': 'pendiente_revision',
                'nombre': 'Gómez, Miguel',
                'asignacion_compartida': False,
                'revisor': None,
            },
            # En revisión
            {
                'residente': residente1,
                'numero_estudio': 'TEST-2026-009',
                'estado': 'en_revision',
                'nombre': 'Díaz, Laura',
                'asignacion_compartida': False,
                'revisor': jefe1,
            },
            # Finalizado
            {
                'residente': residente2,
                'numero_estudio': 'TEST-2026-010',
                'estado': 'finalizado',
                'nombre': 'Ruiz, Antonio',
                'asignacion_compartida': False,
                'revisor': staff1,
            },
        ]
        
        for data in preinformes_data:
            # Verificar si ya existe
            if Preinforme.objects.filter(numero_estudio=data['numero_estudio']).exists():
                self.stdout.write(f"  - Ya existe: {data['numero_estudio']}")
                continue
            
            # Crear preinforme
            preinforme = Preinforme.objects.create(
                residente=data['residente'],
                numero_estudio=data['numero_estudio'],
                tipo_estudio=tipo,
                region=region,
                sistema_destino='eges',
                plantilla_utilizada=plantilla,
                apellido_paciente=data['nombre'].split(',')[0].strip(),
                nombre_paciente=data['nombre'].split(',')[1].strip() if ',' in data['nombre'] else 'Paciente',
                dni_paciente='12345678',
                edad_paciente=45,
                sexo_paciente='M',
                estado=data['estado'],
                revisor=data['revisor'],
                asignacion_compartida=data['asignacion_compartida'],
                informe_html=plantilla.contenido if plantilla else '<p>Contenido de prueba</p>',
            )
            
            # Ajustar fechas según estado
            if data['estado'] in ['pendiente_revision', 'en_revision', 'finalizado']:
                preinforme.fecha_envio_revision = timezone.now() - timedelta(hours=2)
            
            if data['estado'] in ['en_revision', 'finalizado']:
                preinforme.fecha_inicio_revision = timezone.now() - timedelta(hours=1)
            
            if data['estado'] == 'finalizado':
                preinforme.fecha_finalizacion = timezone.now()
                # Crear revisión
                RevisionPreinforme.objects.create(
                    preinforme=preinforme,
                    revisor=data['revisor'],
                    informe_final_html=plantilla.contenido if plantilla else '<p>Informe revisado</p>',
                    puntuacion=8,
                    comentarios_generales='Informe correcto para pruebas',
                )
            
            preinforme.save()
            
            # Mostrar mensaje según tipo
            badge = ""
            if data['asignacion_compartida']:
                badge = "🟣 COMPARTIDO"
            elif data['revisor']:
                badge = f"👤 Asignado a {data['revisor'].first_name}"
            else:
                badge = "⚪ Sin asignar"
            
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {data['numero_estudio']} - {data['estado']} {badge}"
            ))

    def mostrar_resumen(self, usuarios):
        """Mostrar resumen de datos creados"""
        self.stdout.write('\n📊 Resumen de datos creados:')
        self.stdout.write(f"\n👥 Usuarios:")
        self.stdout.write(f"  - {len(usuarios.get('residentes', []))} residentes")
        self.stdout.write(f"  - {len(usuarios.get('jefes', []))} jefes de residentes")
        self.stdout.write(f"  - {len(usuarios.get('instructores', []))} instructores")
        self.stdout.write(f"  - {len(usuarios.get('staff', []))} staff")
        
        self.stdout.write(f"\n📝 Preinformes:")
        self.stdout.write(f"  - {Preinforme.objects.filter(numero_estudio__startswith='TEST-').count()} preinformes de prueba")
        self.stdout.write(f"  - {Preinforme.objects.filter(asignacion_compartida=True).count()} en pool compartido")
        self.stdout.write(f"  - {Preinforme.objects.filter(estado='pendiente_revision').count()} pendientes de revisión")
        self.stdout.write(f"  - {Preinforme.objects.filter(estado='en_revision').count()} en revisión")
        self.stdout.write(f"  - {Preinforme.objects.filter(estado='finalizado', numero_estudio__startswith='TEST-').count()} finalizados")
        
        self.stdout.write(f"\n🔐 Credenciales de acceso:")
        self.stdout.write(self.style.WARNING(f"  Usuario: test_residente1 / test_jefe1 / test_instructor1 / test_staff1"))
        self.stdout.write(self.style.WARNING(f"  Contraseña: test123"))
        
        self.stdout.write(f"\n💡 Próximos pasos:")
        self.stdout.write(f"  1. Inicia sesión como 'test_residente1' para crear preinformes")
        self.stdout.write(f"  2. Inicia sesión como 'test_jefe1' para ver el pool compartido")
        self.stdout.write(f"  3. Prueba tomar estudios del pool compartido")
        self.stdout.write(f"  4. Verifica que otros jefes ya no ven los estudios tomados")
