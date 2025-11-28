from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import EventoServicio, NotaEvento, HistorialEvento

User = get_user_model()


class EventoServicioModelTest(TestCase):
    """Pruebas para el modelo EventoServicio"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='drtest',
            password='testpass123',
            first_name='Test',
            last_name='Doctor'
        )

    def test_crear_evento(self):
        """Verifica que se puede crear un evento"""
        evento = EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='tecnico',
            descripcion='Problema con el tomógrafo',
            servicio_origen_evento='tomografia'
        )
        self.assertEqual(evento.tipo_evento, 'tecnico')
        self.assertEqual(evento.estado, 'abierto')  # Estado por defecto
        self.assertEqual(evento.creado_por, self.user)

    def test_evento_str(self):
        """Verifica la representación en string del evento"""
        evento = EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='cancelado',
            descripcion='Estudio cancelado por el paciente debido a problemas personales'
        )
        str_evento = str(evento)
        self.assertIn('Estudio cancelado', str_evento)

    def test_opciones_tipo_evento(self):
        """Verifica que todos los tipos de evento están disponibles"""
        tipos = [choice[0] for choice in EventoServicio.TIPO_EVENTO_CHOICES]
        self.assertIn('cancelado', tipos)
        self.assertIn('tecnico', tipos)
        self.assertIn('conflicto', tipos)

    def test_opciones_estado(self):
        """Verifica que todos los estados están disponibles"""
        estados = [choice[0] for choice in EventoServicio.ESTADO_CHOICES]
        self.assertIn('abierto', estados)
        self.assertIn('en_revision', estados)
        self.assertIn('resuelto', estados)

    def test_evento_con_paciente(self):
        """Verifica que se puede crear un evento con datos de paciente"""
        evento = EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='demorado',
            descripcion='Estudio demorado',
            nombre_paciente='Juan Pérez',
            dni_paciente='12345678',
            estudio_relacionado='Tomografía de tórax'
        )
        self.assertEqual(evento.nombre_paciente, 'Juan Pérez')
        self.assertEqual(evento.dni_paciente, '12345678')

    def test_cambio_estado_crea_historial(self):
        """Verifica que al cambiar el estado se crea un registro en el historial"""
        evento = EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='tecnico',
            descripcion='Problema técnico'
        )
        
        # Cambiar estado
        evento.estado = 'en_revision'
        evento.save(usuario=self.user)
        
        # Verificar que se creó el historial
        historial = HistorialEvento.objects.filter(evento=evento, cambio='estado')
        self.assertTrue(historial.exists())
        self.assertEqual(historial.first().valor_anterior, 'abierto')
        self.assertEqual(historial.first().valor_nuevo, 'en_revision')


class NotaEventoModelTest(TestCase):
    """Pruebas para el modelo NotaEvento"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.user = User.objects.create_user(
            username='drtest',
            password='testpass123'
        )
        self.evento = EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='tecnico',
            descripcion='Problema técnico'
        )

    def test_crear_nota(self):
        """Verifica que se puede crear una nota para un evento"""
        nota = NotaEvento.objects.create(
            evento=self.evento,
            creado_por=self.user,
            comentario='Se está revisando el equipo'
        )
        self.assertEqual(nota.evento, self.evento)
        self.assertEqual(nota.creado_por, self.user)
        self.assertEqual(nota.comentario, 'Se está revisando el equipo')

    def test_evento_ultima_nota(self):
        """Verifica que se puede obtener la última nota de un evento"""
        # Crear varias notas
        NotaEvento.objects.create(
            evento=self.evento,
            creado_por=self.user,
            comentario='Primera nota'
        )
        nota_reciente = NotaEvento.objects.create(
            evento=self.evento,
            creado_por=self.user,
            comentario='Segunda nota más reciente'
        )
        
        ultima_nota = self.evento.ultima_nota
        self.assertEqual(ultima_nota, nota_reciente)

    def test_evento_sin_notas(self):
        """Verifica que un evento sin notas devuelve None"""
        self.assertIsNone(self.evento.ultima_nota)


class EventoViewsTest(TestCase):
    """Pruebas para las vistas de gestión de eventos"""

    def setUp(self):
        """Configuración inicial para cada prueba"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='drtest',
            password='testpass123',
            is_staff=True
        )
        self.client.login(username='drtest', password='testpass123')

    def test_lista_eventos_requiere_autenticacion(self):
        """Verifica que la lista de eventos requiere autenticación"""
        self.client.logout()
        response = self.client.get(reverse('gestion_eventos:lista_eventos'))
        self.assertEqual(response.status_code, 302)  # Redirige al login

    def test_lista_eventos_autenticado(self):
        """Verifica que un usuario autenticado puede ver la lista de eventos"""
        response = self.client.get(reverse('gestion_eventos:lista_eventos'))
        self.assertEqual(response.status_code, 200)

    def test_crear_evento_get(self):
        """Verifica que se puede acceder al formulario de creación"""
        response = self.client.get(reverse('gestion_eventos:crear_evento'))
        self.assertEqual(response.status_code, 200)

    def test_crear_evento_post(self):
        """Verifica que se puede crear un evento mediante POST"""
        data = {
            'tipo_evento': 'tecnico',
            'descripcion': 'Problema con el equipo de resonancia',
            'servicio_origen_evento': 'resonancia',
        }
        response = self.client.post(reverse('gestion_eventos:crear_evento'), data)
        
        # Verifica que se creó el evento
        self.assertEqual(EventoServicio.objects.count(), 1)
        evento = EventoServicio.objects.first()
        self.assertEqual(evento.tipo_evento, 'tecnico')
        self.assertEqual(evento.creado_por, self.user)

    def test_filtrar_eventos_por_estado(self):
        """Verifica que se pueden filtrar eventos por estado"""
        # Crear eventos con diferentes estados
        EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='tecnico',
            descripcion='Evento abierto',
            estado='abierto'
        )
        EventoServicio.objects.create(
            creado_por=self.user,
            tipo_evento='cancelado',
            descripcion='Evento resuelto',
            estado='resuelto'
        )
        
        # Verificar que existen ambos
        self.assertEqual(EventoServicio.objects.filter(estado='abierto').count(), 1)
        self.assertEqual(EventoServicio.objects.filter(estado='resuelto').count(), 1)
