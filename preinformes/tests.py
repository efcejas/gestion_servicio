from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .models import TipoEstudio, Region, PlantillaPreinforme, Preinforme, RevisionPreinforme, HistorialEstudios

User = get_user_model()


class PreinformeModelTest(TestCase):
    def setUp(self):
        # Crear usuarios de prueba
        self.residente = User.objects.create_user(
            username='residente1',
            email='residente1@test.com',
            password='testpass123',
            rol='medico_residente',
            first_name='Juan',
            last_name='Pérez'
        )
        
        self.staff = User.objects.create_user(
            username='staff1',
            email='staff1@test.com',
            password='testpass123',
            rol='medico_staff',
            first_name='Dr.',
            last_name='García'
        )
        
        # Crear tipo de estudio y región
        self.tipo_estudio = TipoEstudio.objects.create(
            nombre='Radiografía de Tórax',
            descripcion='Radiografía simple de tórax'
        )
        
        self.region = Region.objects.create(
            nombre='Tórax',
            descripcion='Región torácica'
        )
        
        # Crear plantilla
        self.plantilla = PlantillaPreinforme.objects.create(
            nombre='RX Tórax Normal',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            contenido='TÉCNICA: Radiografía de tórax PA y lateral.\n\n{HALLAZGOS}\n\nCONCLUSIÓN: Sin hallazgos patológicos.',
            creada_por=self.staff
        )

    def test_crear_preinforme(self):
        """Test crear preinforme"""
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2024-001234',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            plantilla_utilizada=self.plantilla,
            apellido_paciente='González',
            nombre_paciente='María',
            edad_paciente=45,
            sexo_paciente='F',
            tecnica='Radiografía de tórax PA y lateral en inspiración.',
            hallazgos='Pulmones bien expandidos, sin infiltrados ni consolidaciones.',
            conclusion='Radiografía de tórax normal.'
        )
        
        self.assertEqual(preinforme.estado, 'borrador')
        self.assertEqual(str(preinforme), '2024-001234 - González, María (residente1)')
        
    def test_enviar_a_revision(self):
        """Test enviar preinforme a revisión"""
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2024-001234',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='González',
            nombre_paciente='María',
            edad_paciente=45,
            sexo_paciente='F',
            tecnica='Test',
            hallazgos='Test',
            conclusion='Test'
        )
        
        preinforme.enviar_a_revision()
        
        self.assertEqual(preinforme.estado, 'pendiente_revision')
        self.assertIsNotNone(preinforme.fecha_envio_revision)
        
    def test_iniciar_revision(self):
        """Test iniciar revisión por staff"""
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2024-001234',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='González',
            nombre_paciente='María',
            edad_paciente=45,
            sexo_paciente='F',
            tecnica='Test',
            hallazgos='Test',
            conclusion='Test'
        )
        
        preinforme.enviar_a_revision()
        preinforme.iniciar_revision(self.staff)
        
        self.assertEqual(preinforme.estado, 'en_revision')
        self.assertEqual(preinforme.revisor, self.staff)
        self.assertIsNotNone(preinforme.fecha_inicio_revision)

    def test_historial_estadisticas(self):
        """Test actualización de estadísticas del historial"""
        # Crear algunos preinformes
        for i in range(3):
            preinforme = Preinforme.objects.create(
                residente=self.residente,
                numero_estudio=f'2024-00123{i}',
                tipo_estudio=self.tipo_estudio,
                region=self.region,
                apellido_paciente='Test',
                nombre_paciente='Test',
                edad_paciente=30,
                sexo_paciente='M',
                tecnica='Test',
                hallazgos='Test',
                conclusion='Test'
            )
            
            if i < 2:  # Finalizar 2 de 3
                preinforme.enviar_a_revision()
                preinforme.iniciar_revision(self.staff)
                preinforme.finalizar_revision()
                
                # Crear revisión con puntuación
                RevisionPreinforme.objects.create(
                    preinforme=preinforme,
                    revisor=self.staff,
                    informe_final='Informe final test',
                    puntuacion=8 + i  # 8 y 9
                )
        
        # Actualizar historial
        historial, created = HistorialEstudios.objects.get_or_create(residente=self.residente)
        historial.actualizar_estadisticas()
        
        self.assertEqual(historial.total_preinformes, 3)
        self.assertEqual(historial.preinformes_finalizados, 2)
        self.assertEqual(historial.promedio_puntuacion, 8.5)


class PreinformeViewTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='residente1',
            email='residente1@test.com',
            password='testpass123',
            rol='medico_residente'
        )
        
        self.staff = User.objects.create_user(
            username='staff1',
            email='staff1@test.com',
            password='testpass123',
            rol='medico_staff'
        )
        
        self.tipo_estudio = TipoEstudio.objects.create(nombre='RX Tórax')
        self.region = Region.objects.create(nombre='Tórax')

    def test_dashboard_residente_login_required(self):
        """Test que el dashboard requiere login"""
        response = self.client.get(reverse('preinformes:dashboard_residente'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_residente_access(self):
        """Test acceso al dashboard de residente"""
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('preinformes:dashboard_residente'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard de Preinformes')

    def test_crear_preinforme_get(self):
        """Test GET del formulario de creación"""
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('preinformes:crear_preinforme'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nuevo Preinforme')

    def test_crear_preinforme_post(self):
        """Test POST del formulario de creación"""
        self.client.login(username='residente1', password='testpass123')
        
        data = {
            'numero_estudio': '2024-001234',
            'tipo_estudio': self.tipo_estudio.id,
            'region': self.region.id,
            'apellido_paciente': 'González',
            'nombre_paciente': 'María',
            'edad_paciente': 45,
            'sexo_paciente': 'F',
            'tecnica': 'Radiografía de tórax PA y lateral.',
            'hallazgos': 'Sin hallazgos patológicos.',
            'conclusion': 'Radiografía normal.'
        }
        
        response = self.client.post(reverse('preinformes:crear_preinforme'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verificar que se creó el preinforme
        self.assertTrue(Preinforme.objects.filter(numero_estudio='2024-001234').exists())

    def test_staff_dashboard_access(self):
        """Test acceso al dashboard de staff"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('preinformes:dashboard_staff'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard Staff')

    def test_residente_no_access_staff_dashboard(self):
        """Test que residente no puede acceder al dashboard de staff"""
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('preinformes:dashboard_staff'))
        # Debería redirigir o mostrar error de permisos
        self.assertNotEqual(response.status_code, 200)