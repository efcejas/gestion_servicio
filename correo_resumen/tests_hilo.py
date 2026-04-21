"""Tests para Phase 2: agrupacion de correos en hilos."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CorreoHilo, CorreoResumen
from .selectors import get_agenda_seguimiento_hilos, get_dashboard_context, get_atencion_hoy_por_hilo
from .services import (
    _agrupar_correos_en_hilos,
    _normalizar_asunto,
    actualizar_estado_hilo,
    actualizar_seguimiento_hilo,
)


class CorreoHiloNormalizacionTests(TestCase):
    def test_normalizar_asunto_prefijo_re(self):
        self.assertEqual(_normalizar_asunto('Re: Tema'), 'tema')

    def test_normalizar_asunto_prefijo_fw(self):
        self.assertEqual(_normalizar_asunto('FW: Tema'), 'tema')

    def test_normalizar_asunto_tildes(self):
        self.assertEqual(_normalizar_asunto('Auditoria de Imagenes'), 'auditoria de imagenes')

    def test_normalizar_asunto_vacio(self):
        self.assertEqual(_normalizar_asunto(''), '')
        self.assertEqual(_normalizar_asunto(None), '')


class CorreoHiloAgrupacionTests(TestCase):
    def test_crea_hilo_nuevo(self):
        CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='1',
            message_id='msg-1',
            asunto='Tema Calidad',
            remitente='user1@test.com',
            remitente_nombre='User 1',
            fecha_email=timezone.now(),
            snippet='Mensaje 1',
            prioridad_sugerida='NORMAL',
        )

        _agrupar_correos_en_hilos({'IMAP_USERNAME': 'inbox', 'THREAD_WINDOW_DAYS': 3})

        hilo = CorreoHilo.objects.first()
        self.assertIsNotNone(hilo)
        self.assertEqual(hilo.cantidad_correos, 1)

    def test_agrupa_replies_mismo_asunto(self):
        CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='1',
            message_id='msg-1',
            asunto='Tema Calidad',
            remitente='user1@test.com',
            remitente_nombre='User 1',
            fecha_email=timezone.now(),
            snippet='Mensaje 1',
            prioridad_sugerida='NORMAL',
        )
        CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='2',
            message_id='msg-2',
            asunto='Re: Tema Calidad',
            remitente='user2@test.com',
            remitente_nombre='User 2',
            fecha_email=timezone.now() + timezone.timedelta(hours=1),
            snippet='Mensaje 2',
            prioridad_sugerida='ALTA',
            requiere_respuesta=True,
        )

        _agrupar_correos_en_hilos({'IMAP_USERNAME': 'inbox', 'THREAD_WINDOW_DAYS': 3})

        hilos = CorreoHilo.objects.all()
        self.assertEqual(hilos.count(), 1)
        self.assertEqual(hilos.first().cantidad_correos, 2)
        self.assertEqual(hilos.first().prioridad_hilo, 'ALTA')


class CorreoHiloSelectorTests(TestCase):
    def test_selector_retorna_pendientes(self):
        hilo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema pendiente',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
            requiere_respuesta=True,
        )

        resultado = get_atencion_hoy_por_hilo()

        self.assertEqual(resultado.count(), 1)
        self.assertEqual(resultado.first().id, hilo.id)

    def test_selector_incluye_fecha_seguimiento_vencida(self):
        hilo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema seguimiento',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='en_curso',
            fecha_seguimiento=timezone.now() - timezone.timedelta(hours=2),
        )

        resultado = get_atencion_hoy_por_hilo()

        self.assertEqual(resultado.count(), 1)
        self.assertEqual(resultado.first().id, hilo.id)

    def test_selector_filtra_hilos_urgentes(self):
        urgente = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema urgente',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='URGENTE',
            estado_hilo='pendiente',
            requiere_respuesta=True,
        )
        CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema normal',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
            requiere_respuesta=True,
        )

        resultado = get_atencion_hoy_por_hilo(filtro='urgentes')

        self.assertEqual(resultado.count(), 1)
        self.assertEqual(resultado.first().id, urgente.id)

    def test_selector_excluye_resueltos(self):
        CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema resuelto',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='resuelto',
        )

        resultado = get_atencion_hoy_por_hilo()

        self.assertEqual(resultado.count(), 0)

    def test_agenda_seguimiento_separa_vencidos_y_proximos(self):
        vencido = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema vencido',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
            fecha_seguimiento=timezone.now() - timezone.timedelta(hours=3),
        )
        proximo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema proximo',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='en_curso',
            fecha_seguimiento=timezone.now() + timezone.timedelta(hours=6),
        )
        CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema resuelto agenda',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='resuelto',
            fecha_seguimiento=timezone.now() + timezone.timedelta(hours=2),
        )

        agenda = get_agenda_seguimiento_hilos()

        self.assertEqual(agenda['vencidos_count'], 1)
        self.assertEqual(agenda['proximos_count'], 1)
        self.assertEqual(agenda['vencidos'][0].id, vencido.id)
        self.assertEqual(agenda['proximos'][0].id, proximo.id)

    def test_dashboard_context_incluye_agenda_seguimiento(self):
        CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema dashboard agenda',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
            fecha_seguimiento=timezone.now() + timezone.timedelta(hours=1),
        )

        context = get_dashboard_context()

        self.assertEqual(context['correo_hilos_seguimiento_vencidos_count'], 0)
        self.assertEqual(context['correo_hilos_seguimiento_proximos_count'], 1)
        self.assertEqual(len(context['correo_hilos_seguimiento_proximos']), 1)


class CorreoHiloGestionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_actualizar_estado_hilo_propagado_a_correos(self):
        correo = CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='1',
            message_id='msg-1',
            asunto='Tema Calidad',
            remitente='user1@test.com',
            remitente_nombre='User 1',
            fecha_email=timezone.now(),
            snippet='Mensaje 1',
            prioridad_sugerida='NORMAL',
            estado_atencion='pendiente',
        )
        hilo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema calidad',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
        )
        hilo.correos.add(correo)

        resultado = actualizar_estado_hilo(hilo, 'resuelto')

        hilo.refresh_from_db()
        correo.refresh_from_db()
        self.assertTrue(resultado['exito'])
        self.assertEqual(hilo.estado_hilo, 'resuelto')
        self.assertEqual(correo.estado_atencion, 'resuelto')

    def test_cambio_rapido_desde_dashboard_actualiza_y_redirige(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123',
        )
        self.client.force_login(usuario)

        correo = CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='2',
            message_id='msg-2',
            asunto='Tema Dashboard',
            remitente='user2@test.com',
            remitente_nombre='User 2',
            fecha_email=timezone.now(),
            snippet='Mensaje 2',
            prioridad_sugerida='NORMAL',
            estado_atencion='pendiente',
        )
        hilo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema dashboard',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
        )
        hilo.correos.add(correo)

        response = self.client.post(
            reverse('correo_hilo_cambiar_estado', args=[hilo.id]),
            {'estado_hilo': 'en_curso', 'return_to': 'admin_dashboard'},
        )

        hilo.refresh_from_db()
        correo.refresh_from_db()
        self.assertRedirects(response, reverse('admin_dashboard'))
        self.assertEqual(hilo.estado_hilo, 'en_curso')
        self.assertEqual(correo.estado_atencion, 'en_curso')

    def test_actualizar_seguimiento_reabre_hilo_resuelto(self):
        correo = CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='3',
            message_id='msg-3',
            asunto='Tema Seguimiento',
            remitente='user3@test.com',
            remitente_nombre='User 3',
            fecha_email=timezone.now(),
            snippet='Mensaje 3',
            prioridad_sugerida='NORMAL',
            estado_atencion='resuelto',
        )
        hilo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema seguimiento',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='resuelto',
        )
        hilo.correos.add(correo)

        resultado = actualizar_seguimiento_hilo(hilo, timezone.now() + timezone.timedelta(hours=4))

        hilo.refresh_from_db()
        correo.refresh_from_db()
        self.assertTrue(resultado['estado_reabierto'])
        self.assertEqual(hilo.estado_hilo, 'pendiente')
        self.assertEqual(correo.estado_atencion, 'pendiente')
        self.assertIsNotNone(hilo.fecha_seguimiento)

    def test_post_seguimiento_desde_detalle_redirige_y_guarda_fecha(self):
        usuario = get_user_model().objects.create_superuser(
            username='admin2',
            email='admin2@test.com',
            password='testpass123',
        )
        self.client.force_login(usuario)

        hilo = CorreoHilo.objects.create(
            cuenta='inbox',
            asunto_normalizado='tema agenda',
            fecha_primer_email=timezone.now(),
            fecha_ultimo_email=timezone.now(),
            prioridad_hilo='NORMAL',
            estado_hilo='pendiente',
            requiere_respuesta=True,
        )

        response = self.client.post(
            reverse('correo_hilo_cambiar_estado', args=[hilo.id]),
            {
                'accion': 'seguimiento',
                'fecha_seguimiento': '2026-04-22T09:30',
                'return_to': '/dashboard/correos/hilo/{}/?return_to=%2Fadmin-dashboard%2F%3Fhilo_filtro%3Dpendiente'.format(hilo.id),
            },
        )

        hilo.refresh_from_db()
        self.assertRedirects(
            response,
            '/dashboard/correos/hilo/{}/?return_to=%2Fadmin-dashboard%2F%3Fhilo_filtro%3Dpendiente'.format(hilo.id),
            fetch_redirect_response=False,
        )
        self.assertIsNotNone(hilo.fecha_seguimiento)
        self.assertEqual(timezone.localtime(hilo.fecha_seguimiento).strftime('%Y-%m-%dT%H:%M'), '2026-04-22T09:30')
