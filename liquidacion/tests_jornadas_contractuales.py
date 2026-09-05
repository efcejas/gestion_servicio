from copy import deepcopy
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from eges_import.models import ImportBatch
from .forms_jornadas import JornadaContractualForm
from .models import (ControlEgesSesion, JornadaContractual, RegistroEstudiosPorMedico,
                     ResultadoControlEgesRegistro, RevisionCruceEgesRegistro, SesionContable)
from .services_jornadas import crear_jornada_contractual, jornada_para_fecha


@override_settings(SECURE_SSL_REDIRECT=False)
class JornadasContractualesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.jefe = User.objects.create_user(username='jefatura_jornadas', rol='jefe_servicio', perfil_completo=True)
        cls.camilo = User.objects.create_user(username='camilo_jornadas', rol='jefe_residentes', perfil_completo=True)
        cls.instructora = User.objects.create_user(username='instructora_jornadas', rol='instructor_residentes', perfil_completo=True)
        cls.admin = User.objects.create_user(username='admin_jornadas', rol='administrativo', perfil_completo=True)
        cls.residente = User.objects.create_user(username='residente_jornadas', rol='medico_residente', perfil_completo=True)
        cls.semana = {str(d): [] for d in range(7)}
        cls.semana.update({'2': [['08:00', '18:00']], '3': [['08:00', '13:00']], '4': [['08:00', '13:00']]})

    def crear(self, **kwargs):
        valores = dict(profesional=self.camilo, vigencia_desde=date(2026, 8, 1),
                       semana=deepcopy(self.semana), observacion='Agenda autorizada por RRHH.', user=self.jefe)
        valores.update(kwargs)
        return crear_jornada_contractual(**valores)

    def payload(self):
        data = {'profesional': self.camilo.pk, 'vigencia_desde': '2026-08-01', 'observacion': 'RRHH agosto'}
        for dia, tramos in self.semana.items():
            data[f'dia_{dia}'] = 'con' if tramos else 'sin'
            for indice, (inicio, fin) in enumerate(tramos):
                data[f'{dia}_{indice}_desde'] = inicio
                data[f'{dia}_{indice}_hasta'] = fin
        return data

    def test_vigencia_agosto_y_sin_jornada_no_es_sin_configuracion(self):
        jornada = self.crear()
        self.assertIsNone(jornada_para_fecha(self.camilo, date(2026, 7, 31)))
        self.assertEqual(jornada_para_fecha(self.camilo, date(2026, 8, 3)).semana['0'], [])
        self.assertIsNone(jornada_para_fecha(self.instructora, date(2026, 8, 3)))
        self.assertEqual(jornada.creado_por, self.jefe)

    def test_nueva_version_conserva_agosto_y_cierra_vigencia_anterior(self):
        agosto = self.crear()
        semana_nueva = deepcopy(self.semana)
        semana_nueva['2'] = [['08:00', '12:00'], ['14:00', '18:00']]
        septiembre = self.crear(vigencia_desde=date(2026, 9, 1), semana=semana_nueva)
        agosto.refresh_from_db()
        self.assertEqual(agosto.vigencia_hasta, date(2026, 8, 31))
        self.assertEqual(agosto.semana, self.semana)
        self.assertEqual(agosto.cerrado_por, self.jefe)
        self.assertIsNotNone(agosto.fecha_cierre)
        self.assertEqual(jornada_para_fecha(self.camilo, date(2026, 8, 31)), agosto)
        self.assertEqual(jornada_para_fecha(self.camilo, date(2026, 9, 1)), septiembre)

    def test_rechaza_misma_fecha_y_versiones_anteriores(self):
        self.crear()
        for inicio in (date(2026, 8, 1), date(2026, 7, 1)):
            with self.subTest(inicio=inicio), self.assertRaises(ValidationError):
                self.crear(vigencia_desde=inicio)
        self.assertEqual(JornadaContractual.objects.count(), 1)

    def test_rechaza_dias_faltantes_solapes_e_inversiones(self):
        for semana in ({'0': []}, {**self.semana, '2': [['18:00', '08:00']]},
                       {**self.semana, '2': [['08:00', '13:00'], ['12:00', '18:00']]}):
            with self.subTest(semana=semana), self.assertRaises(ValidationError):
                self.crear(semana=semana)
        self.assertFalse(JornadaContractual.objects.exists())

    def test_no_cierra_version_anterior_si_nueva_es_invalida(self):
        original = self.crear()
        with self.assertRaises(ValidationError):
            self.crear(vigencia_desde=date(2026, 9, 1), semana={})
        original.refresh_from_db()
        self.assertIsNone(original.vigencia_hasta)

    def test_rollback_si_falla_guardado_nueva_version(self):
        original = self.crear()
        save = JornadaContractual.save
        def fallar_nueva(instance, *args, **kwargs):
            if not instance.pk:
                raise RuntimeError('Fallo simulado')
            return save(instance, *args, **kwargs)
        with patch.object(JornadaContractual, 'save', fallar_nueva), self.assertRaises(RuntimeError):
            self.crear(vigencia_desde=date(2026, 9, 1))
        original.refresh_from_db()
        self.assertIsNone(original.vigencia_hasta)
        self.assertEqual(JornadaContractual.objects.count(), 1)

    def test_administrativo_requiere_permiso_explicito_y_profesional_no_edita(self):
        for usuario in (self.admin, self.camilo, self.residente):
            with self.subTest(usuario=usuario), self.assertRaises(PermissionDenied):
                self.crear(user=usuario)
        self.admin.user_permissions.add(Permission.objects.get(codename='gestionar_jornadas_contractuales'))
        admin = get_user_model().objects.get(pk=self.admin.pk)
        self.assertEqual(self.crear(user=admin).creado_por, admin)

    def test_solo_roles_destinatarios_y_superuser_puede_crear(self):
        with self.assertRaises(ValidationError):
            self.crear(profesional=self.residente)
        self.admin.is_superuser = True
        self.assertEqual(self.crear(user=self.admin, profesional=self.instructora).profesional, self.instructora)

    def test_formulario_exige_declaracion_por_dia_y_admite_turno_partido(self):
        data = self.payload()
        data['2_0_hasta'] = '12:00'
        data['2_1_desde'] = '14:00'
        data['2_1_hasta'] = '18:00'
        form = JornadaContractualForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['semana']['2']), 2)
        del data['dia_0']
        self.assertFalse(JornadaContractualForm(data).is_valid())

    def test_post_y_errores_conservan_datos_y_no_permiten_edicion_ajena(self):
        url = reverse('liquidacion:jornada_contractual_nueva')
        self.client.force_login(self.jefe)
        self.assertEqual(self.client.get(url).status_code, 200)
        data = self.payload()
        data['2_0_hasta'] = '07:00'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '07:00')
        self.assertFalse(JornadaContractual.objects.exists())
        response = self.client.post(url, self.payload())
        self.assertRedirects(response, reverse('liquidacion:jornadas_contractuales'))
        self.client.force_login(self.camilo)
        self.assertEqual(self.client.post(url, self.payload()).status_code, 403)

    def test_profesional_ve_solo_sus_versiones_incluso_con_parametro_ajeno(self):
        self.crear(observacion='Agenda propia Camilo')
        self.crear(profesional=self.instructora, observacion='Agenda privada instructora')
        self.client.force_login(self.camilo)
        response = self.client.get(reverse('liquidacion:jornadas_contractuales'), {'profesional': self.instructora.pk})
        self.assertContains(response, 'Agenda propia Camilo')
        self.assertNotContains(response, 'Agenda privada instructora')
        self.assertNotContains(response, 'Nueva jornada')
        self.client.force_login(self.residente)
        self.assertEqual(self.client.get(reverse('liquidacion:jornadas_contractuales')).status_code, 403)

    def test_guardar_agenda_preserva_control_revision_y_registro_economico(self):
        sesion = SesionContable.objects.create(mes=8, **{'a\u00f1o': 2026}, estado='REVISION')
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion, medico=self.camilo, nombre_paciente='Prueba', apellido_paciente='Test',
            dni_paciente='12345678', fecha_del_informe=date(2026, 8, 5), horario='EXTRA',
            tipo_obra_social='COBER', monto_calculado=1200)
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='prueba.xls')
        control = ControlEgesSesion.objects.create(sesion_contable=sesion, batch_eges=batch, version=1, procesado_por=self.jefe)
        ResultadoControlEgesRegistro.objects.create(control=control, registro=registro, estado='ADVERTENCIA', snapshot_json={'previo': True})
        RevisionCruceEgesRegistro.objects.create(sesion_contable=sesion, registro=registro, batch_eges=batch,
                                                estado='VALIDADO', revisado_por=self.jefe, observacion='Ya revisado', snapshot_json={'previo': True})
        modelos = (RegistroEstudiosPorMedico, ControlEgesSesion, ResultadoControlEgesRegistro, RevisionCruceEgesRegistro)
        antes = [list(modelo.objects.values()) for modelo in modelos]
        with patch.object(RegistroEstudiosPorMedico, 'calcular_monto', side_effect=AssertionError('No recalcular')):
            self.crear()
        self.assertEqual(antes, [list(modelo.objects.values()) for modelo in modelos])
