from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import time, timedelta

from control_guardias.models import (
    AsignacionGuardia,
    ConfiguracionTipoGuardia,
    SolicitudSlotVacante,
)
from .forms import DEMO_PATIENT_SENTINEL, FiltroPreinformesForm, PreinformeForm
from .models import Preinforme, Region, RevisionPreinforme, TipoEstudio


User = get_user_model()

TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGES)
class DemoPrivacyTests(TestCase):
    def setUp(self):
        self.demo = User.objects.create_user(
            username='demo_jefe',
            password='test-pass',
            rol='jefe_residentes',
            is_demo_user=True,
            first_name='Demo',
            last_name='Docencia',
            perfil_completo=True,
        )
        self.jefe = User.objects.create_user(
            username='jefe_normal',
            password='test-pass',
            rol='jefe_residentes',
            first_name='Jefe',
            last_name='Normal',
            perfil_completo=True,
        )
        self.residente = User.objects.create_user(
            username='residente_demo_test',
            password='test-pass',
            rol='medico_residente',
            first_name='Residente',
            last_name='Visible',
            perfil_completo=True,
        )
        tipo = TipoEstudio.objects.create(nombre='RM Demo')
        region = Region.objects.create(nombre='Rodilla Demo')
        self.preinforme = Preinforme.objects.create(
            residente=self.residente,
            revisor=self.demo,
            numero_estudio='EGES-DEMO-7788',
            tipo_estudio=tipo,
            region=region,
            apellido_paciente='APELLIDOSECRETO',
            nombre_paciente='NOMBRESECRETO',
            dni_paciente='DNI-99887766',
            edad_paciente=47,
            sexo_paciente='F',
            informe_html='<p>CUERPO PROFESIONAL PERMITIDO</p>',
            estado='finalizado',
            fecha_finalizacion=timezone.now(),
        )
        RevisionPreinforme.objects.create(
            preinforme=self.preinforme,
            revisor=self.demo,
            informe_residente_snapshot='<p>VERSIÓN RESIDENTE PERMITIDA</p>',
            informe_final_html='<p>VERSIÓN FINAL PERMITIDA</p>',
            puntuacion=9,
            resumen_ia_revision={'resumen': 'Disponible'},
        )

    def assert_no_patient_identity(self, response):
        self.assertNotContains(response, 'APELLIDOSECRETO', status_code=response.status_code)
        self.assertNotContains(response, 'NOMBRESECRETO', status_code=response.status_code)
        self.assertNotContains(response, 'DNI-99887766', status_code=response.status_code)
        self.assertNotContains(response, '47 años', status_code=response.status_code)
        self.assertNotContains(response, 'Femenino', status_code=response.status_code)

    def test_normal_jefe_keeps_patient_filters_and_duplicate_payload(self):
        form = FiltroPreinformesForm(user=self.jefe)
        self.assertIn('apellido_paciente', form.fields)
        self.assertIn('nombre_paciente', form.fields)
        self.client.force_login(self.jefe)
        response = self.client.get(
            reverse('preinformes:verificar_duplicado'),
            {'numero_estudio': self.preinforme.numero_estudio},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'APELLIDOSECRETO')
        self.assertContains(response, 'DNI-99887766')

        create_response = self.client.get(reverse('preinformes:crear_preinforme'))
        for field_name in ('apellido_paciente', 'nombre_paciente', 'dni_paciente', 'edad_paciente', 'sexo_paciente'):
            self.assertContains(create_response, field_name)

        form = PreinformeForm(
            data={
                'numero_estudio': 'NORMAL-SIN-PACIENTE',
                'tipo_estudio': self.preinforme.tipo_estudio_id,
                'region': self.preinforme.region_id,
                'sistema_destino': 'eges',
                'informe_html': '<p>Informe</p>',
            },
            user=self.jefe,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('apellido_paciente', form.errors)
        self.assertIn('nombre_paciente', form.errors)

    def test_demo_navbar_and_home_are_restricted(self):
        self.client.force_login(self.demo)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        groups = response.context['nav_groups']
        labels = {item['label'] for group in groups for item in group['items']}
        self.assertIn('Protocolos', labels)
        self.assertIn('Clases', labels)
        self.assertIn('Preinformes', labels)
        self.assertIn('Portal de Guardias', labels)
        self.assertNotIn('Liquidaciones', labels)
        self.assertNotContains(response, 'Registrar Estudios')
        self.assertContains(response, 'fa-file-medical')
        self.assertContains(response, 'fa-graduation-cap')
        self.assertContains(response, 'fa-book-medical')
        self.assertContains(response, 'fa-chart-line')
        self.assertContains(response, 'fa-calendar-alt')

    def test_demo_revision_list_keeps_study_data_without_identity(self):
        self.client.force_login(self.demo)
        response = self.client.get(
            reverse('preinformes:lista_revision'),
            {'mostrar': 'finalizados', 'apellido_paciente': 'APELLIDOSECRETO'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'EGES-DEMO-7788')
        self.assertContains(response, 'RM Demo')
        self.assert_no_patient_identity(response)
        self.assertNotContains(response, 'Apellido del Paciente')

    def test_demo_can_open_detail_review_and_comparison_without_identity(self):
        self.client.force_login(self.demo)
        urls = [
            reverse('preinformes:ver_preinforme', args=[self.preinforme.pk]),
            reverse('preinformes:revisar_preinforme', args=[self.preinforme.pk]),
            reverse('preinformes:comparacion_revision', args=[self.preinforme.pk]),
            reverse('preinformes:ver_banco_preinforme', args=[self.preinforme.pk]),
        ]
        responses = [self.client.get(url) for url in urls]
        for response in responses:
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'EGES-DEMO-7788')
            self.assert_no_patient_identity(response)
        self.assertContains(responses[0], 'CUERPO PROFESIONAL PERMITIDO')
        self.assertContains(responses[1], 'VERSIÓN FINAL PERMITIDA')
        self.assertContains(responses[2], 'VERSIÓN FINAL PERMITIDA')

    def test_demo_patient_filters_and_duplicate_endpoint_are_disabled(self):
        form = FiltroPreinformesForm(user=self.demo)
        self.assertNotIn('apellido_paciente', form.fields)
        self.assertNotIn('nombre_paciente', form.fields)
        self.client.force_login(self.demo)
        response = self.client.get(
            reverse('preinformes:verificar_duplicado'),
            {'numero_estudio': self.preinforme.numero_estudio, 'dni_paciente': 'DNI-99887766'},
        )
        self.assertEqual(response.status_code, 403)
        self.assert_no_patient_identity(response)

    def test_demo_can_create_and_edit_without_patient_fields(self):
        self.client.force_login(self.demo)
        create_url = reverse('preinformes:crear_preinforme')
        get_response = self.client.get(create_url)
        self.assertEqual(get_response.status_code, 200)
        for field_name in (
            'apellido_paciente',
            'nombre_paciente',
            'dni_paciente',
            'edad_paciente',
            'sexo_paciente',
        ):
            self.assertNotContains(get_response, field_name)
        self.assertNotContains(get_response, DEMO_PATIENT_SENTINEL)

        post_response = self.client.post(create_url, {
            'numero_estudio': 'EGES-CREADO-DEMO',
            'tipo_estudio': self.preinforme.tipo_estudio_id,
            'region': self.preinforme.region_id,
            'sistema_destino': 'eges',
            'contexto_clinico': 'Contexto profesional sin identidad',
            'informe_html': '<p>INFORME CREADO EN DEMO</p>',
            'guardar_y_continuar': '1',
        })
        creado = Preinforme.objects.get(numero_estudio='EGES-CREADO-DEMO')
        self.assertRedirects(
            post_response,
            reverse('preinformes:editar_preinforme', args=[creado.pk]),
            fetch_redirect_response=False,
        )
        self.assertTrue(creado.es_registro_demo)
        self.assertEqual(creado.residente, self.demo)
        self.assertEqual(creado.apellido_paciente, DEMO_PATIENT_SENTINEL)
        self.assertEqual(creado.nombre_paciente, DEMO_PATIENT_SENTINEL)
        self.assertEqual(creado.dni_paciente, '')
        self.assertIsNone(creado.edad_paciente)
        self.assertIsNone(creado.sexo_paciente)

        edit_response = self.client.get(
            reverse('preinformes:editar_preinforme', args=[creado.pk])
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertContains(edit_response, 'INFORME CREADO EN DEMO')
        self.assertNotContains(edit_response, DEMO_PATIENT_SENTINEL)

        send_response = self.client.post(
            reverse('preinformes:editar_preinforme', args=[creado.pk]),
            {
                'numero_estudio': creado.numero_estudio,
                'tipo_estudio': creado.tipo_estudio_id,
                'region': creado.region_id,
                'sistema_destino': 'eges',
                'asignacion_compartida': 'on',
                'contexto_clinico': creado.contexto_clinico,
                'informe_html': creado.informe_html,
                'guardar_y_enviar': '1',
            },
        )
        self.assertRedirects(
            send_response,
            reverse('preinformes:dashboard_residente'),
            fetch_redirect_response=False,
        )
        creado.refresh_from_db()
        self.assertEqual(creado.estado, 'pendiente_revision')
        revision_list = self.client.get(
            reverse('preinformes:lista_revision'),
            {'mostrar': 'compartidos'},
        )
        self.assertContains(revision_list, creado.numero_estudio)
        take_response = self.client.post(
            reverse('preinformes:tomar_estudio', args=[creado.pk])
        )
        self.assertEqual(take_response.status_code, 302)
        RevisionPreinforme.objects.create(
            preinforme=creado,
            revisor=self.demo,
            informe_residente_snapshot=creado.informe_html,
            informe_final_html=creado.informe_html,
            resumen_ia_revision={'resumen': 'Disponible'},
        )
        review_response = self.client.get(
            reverse('preinformes:revisar_preinforme', args=[creado.pk])
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, 'INFORME CREADO EN DEMO')
        self.assertNotContains(review_response, DEMO_PATIENT_SENTINEL)

        self.client.force_login(self.jefe)
        normal_list = self.client.get(
            reverse('preinformes:lista_revision'),
            {'mostrar': 'todos'},
        )
        self.assertNotContains(normal_list, creado.numero_estudio)

        # La eliminación continúa bloqueada para evitar acciones destructivas.
        self.client.force_login(self.demo)
        self.assertEqual(
            self.client.post(reverse('preinformes:eliminar_preinforme', args=[creado.pk])).status_code,
            403,
        )

    def test_demo_statistics_remain_available(self):
        self.client.force_login(self.demo)
        before = self.client.get(reverse('preinformes:estadisticas'))
        Preinforme.objects.create(
            residente=self.demo,
            numero_estudio='NO-CONTAR-DEMO',
            tipo_estudio=self.preinforme.tipo_estudio,
            region=self.preinforme.region,
            apellido_paciente=DEMO_PATIENT_SENTINEL,
            nombre_paciente=DEMO_PATIENT_SENTINEL,
            es_registro_demo=True,
        )
        after = self.client.get(reverse('preinformes:estadisticas'))
        self.assertEqual(after.status_code, 200)
        self.assertEqual(
            before.context['preinformes_mes_actual'],
            after.context['preinformes_mes_actual'],
        )
        self.assert_no_patient_identity(after)

    def test_demo_guardia_management_posts_are_read_only(self):
        self.client.force_login(self.demo)
        index_response = self.client.get(reverse('control_guardias:index'))
        self.assertEqual(index_response.status_code, 200)
        self.assertContains(index_response, 'Calendario')
        self.assertNotContains(index_response, 'Distribución automática')
        self.assertNotContains(index_response, 'Configuración')
        response = self.client.post(reverse('control_guardias:configuracion'))
        self.assertEqual(response.status_code, 403)

    def test_demo_slot_requests_render_read_only_without_broken_action_form(self):
        tipo_guardia = ConfiguracionTipoGuardia.objects.create(
            nombre='Guardia demo',
            hora_inicio=time(8, 0),
            hora_fin=time(20, 0),
            dias_semana='L,M,X,J,V,S,D',
            creado_por=self.jefe,
        )
        guardia = AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo_guardia,
            fecha=timezone.localdate() + timedelta(days=1),
            estado='PUBLICADA',
            creada_por=self.jefe,
        )
        SolicitudSlotVacante.objects.create(
            solicitante=self.residente,
            guardia_ceder=guardia,
            slot_fecha=guardia.fecha + timedelta(days=2),
            slot_tipo_guardia=tipo_guardia,
            notas_solicitante='Solicitud visible',
        )

        self.client.force_login(self.demo)
        demo_response = self.client.get(reverse('control_guardias:solicitudes_slot_vacante'))
        self.assertEqual(demo_response.status_code, 200)
        self.assertContains(demo_response, 'Solicitud visible')
        self.assertNotContains(demo_response, 'name="notas_jefe"')
        self.assertNotContains(demo_response, 'value="aprobar"')
        self.assertNotContains(demo_response, 'value="rechazar"')

        self.client.force_login(self.jefe)
        normal_response = self.client.get(reverse('control_guardias:solicitudes_slot_vacante'))
        self.assertContains(normal_response, 'name="notas_jefe"')
        self.assertContains(normal_response, 'value="aprobar"')

    def test_demo_guardia_read_only_pages_all_render(self):
        self.client.force_login(self.demo)
        url_names = [
            'control_guardias:index',
            'control_guardias:calendario',
            'control_guardias:cambios',
            'control_guardias:solicitudes_slot_vacante',
            'control_guardias:ausencias',
            'control_guardias:notificaciones',
        ]
        for url_name in url_names:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
