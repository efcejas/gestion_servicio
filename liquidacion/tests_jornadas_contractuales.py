from copy import deepcopy
from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from eges_import.models import EgesRow, ImportBatch
from .forms_jornadas import JornadaContractualForm
from .models import (ControlEgesSesion, Estudios, JornadaContractual, RegistroEstudio,
                     RegistroEstudiosPorMedico, ResultadoControlEgesRegistro,
                     RevisionCruceEgesRegistro, SesionContable)
from .services_eges import (
    MOTOR_HORARIO_GENERAL,
    MOTOR_HORARIO_JORNADA,
    construir_preview_cruce_liquidacion_eges,
    procesar_control_eges_sesion,
)
from .services_jornadas import (
    ESTADO_DENTRO_JORNADA,
    ESTADO_FUERA_JORNADA,
    ESTADO_JORNADA_MANUAL,
    ESTADO_JORNADA_NO_APLICA,
    ESTADO_JORNADA_SIN_CONFIGURACION,
    crear_jornada_contractual,
    evaluar_horario_en_jornada,
    jornada_para_fecha,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class JornadasContractualesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.jefe = User.objects.create_user(username='jefatura_jornadas', first_name='Jefe', last_name='Servicio', rol='jefe_servicio', perfil_completo=True)
        cls.camilo = User.objects.create_user(username='camilo_jornadas', first_name='Camilo', last_name='Gavilanes', rol='jefe_residentes', perfil_completo=True)
        cls.instructora = User.objects.create_user(username='instructora_jornadas', first_name='Alejandra', last_name='Maldonado', rol='instructor_residentes', perfil_completo=True)
        cls.admin = User.objects.create_user(username='admin_jornadas', first_name='Admin', last_name='Sistema', rol='administrativo', perfil_completo=True)
        cls.residente = User.objects.create_user(username='residente_jornadas', first_name='Residente', last_name='Medico', rol='medico_residente', perfil_completo=True)
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

    def test_j1_intervalo_dentro_de_jornada(self):
        jornada = self.crear()
        resultado = evaluar_horario_en_jornada(
            profesional=self.camilo,
            fecha=date(2026, 8, 6),
            hora_inicio=time(10, 0),
            hora_fin=time(10, 20),
        )
        self.assertEqual(resultado['estado'], ESTADO_DENTRO_JORNADA)
        self.assertEqual(resultado['jornada_id'], jornada.pk)
        self.assertEqual(resultado['tramos'], [['08:00', '13:00']])

    def test_j1_intervalo_fuera_de_jornada(self):
        self.crear()
        resultado = evaluar_horario_en_jornada(
            profesional=self.camilo,
            fecha=date(2026, 8, 6),
            hora_inicio=time(15, 0),
            hora_fin=time(15, 20),
        )
        self.assertEqual(resultado['estado'], ESTADO_FUERA_JORNADA)
        self.assertIn('fuera', resultado['motivo'].lower())

    def test_j1_fin_de_tramo_es_fuera_de_jornada(self):
        self.crear()
        resultado = evaluar_horario_en_jornada(
            profesional=self.camilo,
            fecha=date(2026, 8, 6),
            hora_inicio=time(13, 0),
        )
        self.assertEqual(resultado['estado'], ESTADO_FUERA_JORNADA)

    def test_j1_intervalo_que_cruza_limite_requiere_revision_manual(self):
        self.crear()
        resultado = evaluar_horario_en_jornada(
            profesional=self.camilo,
            fecha=date(2026, 8, 6),
            hora_inicio=time(12, 50),
            hora_fin=time(13, 10),
        )
        self.assertEqual(resultado['estado'], ESTADO_JORNADA_MANUAL)
        self.assertIn('cruza', resultado['motivo'].lower())

    def test_j1_dia_declarado_sin_jornada_es_fuera(self):
        self.crear()
        resultado = evaluar_horario_en_jornada(
            profesional=self.camilo,
            fecha=date(2026, 8, 3),
            hora_inicio=time(10, 0),
        )
        self.assertEqual(resultado['estado'], ESTADO_FUERA_JORNADA)
        self.assertEqual(resultado['tramos'], [])

    def test_j1_distingue_sin_configuracion_y_rol_no_aplicable(self):
        sin_configuracion = evaluar_horario_en_jornada(
            profesional=self.instructora,
            fecha=date(2026, 8, 6),
            hora_inicio=time(10, 0),
        )
        no_aplica = evaluar_horario_en_jornada(
            profesional=self.residente,
            fecha=date(2026, 8, 6),
            hora_inicio=time(10, 0),
        )
        self.assertEqual(sin_configuracion['estado'], ESTADO_JORNADA_SIN_CONFIGURACION)
        self.assertTrue(sin_configuracion['aplica'])
        self.assertEqual(no_aplica['estado'], ESTADO_JORNADA_NO_APLICA)
        self.assertFalse(no_aplica['aplica'])

    def test_j1_falta_hora_o_cruce_de_medianoche_es_manual(self):
        self.crear()
        casos = (
            {'hora_inicio': None, 'hora_fin': None},
            {'hora_inicio': time(23, 50), 'hora_fin': time(0, 10)},
        )
        for horas in casos:
            with self.subTest(horas=horas):
                resultado = evaluar_horario_en_jornada(
                    profesional=self.camilo,
                    fecha=date(2026, 8, 6),
                    **horas,
                )
                self.assertEqual(resultado['estado'], ESTADO_JORNADA_MANUAL)

    def test_j1_es_solo_lectura_y_no_recalcula(self):
        jornada = self.crear()
        antes = list(JornadaContractual.objects.values())
        with patch.object(RegistroEstudiosPorMedico, 'calcular_monto', side_effect=AssertionError('No recalcular')):
            resultado = evaluar_horario_en_jornada(
                profesional=self.camilo,
                fecha=date(2026, 8, 5),
                hora_inicio=time(19, 0),
                hora_fin=time(19, 20),
            )
        self.assertEqual(resultado['jornada_id'], jornada.pk)
        self.assertEqual(antes, list(JornadaContractual.objects.values()))

    def test_j2_eco_general_fuera_de_jornada_justifica_extra(self):
        self.crear()
        sesion = SesionContable.objects.create(mes=8, **{'año': 2026}, estado='REVISION')
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='batch_j2.xls')
        estudio_eco = Estudios.objects.create(
            nombre='ECOGRAFIA ABDOMINAL COMPLETA',
            tipo='ECO',
            conteo_regiones=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion,
            medico=self.camilo,
            nombre_paciente='Carlos',
            apellido_paciente='Gomez',
            dni_paciente='30111222',
            fecha_del_informe=date(2026, 8, 6),  # Jueves (jornada 08:00-13:00)
            tipo_obra_social='COBER',
            horario='EXTRA',
            liquidar_como_extra_residencia=True,
            cantidad_regiones=1,
            monto_calculado=Decimal('1000.00'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio_eco, cantidad=1)

        EgesRow.objects.create(
            batch=batch,
            fecha_turno=date(2026, 8, 6),
            hora_turno=time(15, 0),
            hora_hasta=time(15, 20),
            dni_paciente='30111222',
            apellido_nombre='Gomez, Carlos',
            practica='ECOGRAFIA ABDOMINAL COMPLETA',
            codigo_practica='180112',
            modalidad='ECO',
            es_insumo=False,
            medico_informante='Camilo Gavilanes Ibarra',
            cantidad=1,
        )

        # Sin jornadas: hora 15:00 en día de semana espera INTRA -> advertencia
        preview_sin = construir_preview_cruce_liquidacion_eges(sesion, batch, usar_jornadas=False)
        item_sin = preview_sin['resultados'][0]
        self.assertEqual(item_sin['estado'], 'advertencia')
        self.assertEqual(item_sin['motor_horario'], MOTOR_HORARIO_GENERAL)

        # Con jornadas: 15:00 fuera de 08:00-13:00 espera EXTRA -> OK justificado
        preview_con = construir_preview_cruce_liquidacion_eges(sesion, batch, usar_jornadas=True)
        item_con = preview_con['resultados'][0]
        self.assertEqual(item_con['estado'], 'ok')
        self.assertEqual(item_con['motor_horario'], MOTOR_HORARIO_JORNADA)
        self.assertEqual(item_con['evaluacion_jornada']['estado'], ESTADO_FUERA_JORNADA)

    def test_j2_eco_general_dentro_de_jornada_mantiene_advertencia(self):
        self.crear()
        sesion = SesionContable.objects.create(mes=8, **{'año': 2026}, estado='REVISION')
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='batch_j2_dentro.xls')
        estudio_eco = Estudios.objects.create(
            nombre='ECOGRAFIA HEPATOBILIAR',
            tipo='ECO',
            conteo_regiones=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion,
            medico=self.camilo,
            nombre_paciente='Ana',
            apellido_paciente='Lopez',
            dni_paciente='30333444',
            fecha_del_informe=date(2026, 8, 6),  # Jueves (jornada 08:00-13:00)
            tipo_obra_social='COBER',
            horario='EXTRA',
            liquidar_como_extra_residencia=True,
            cantidad_regiones=1,
            monto_calculado=Decimal('1000.00'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio_eco, cantidad=1)

        EgesRow.objects.create(
            batch=batch,
            fecha_turno=date(2026, 8, 6),
            hora_turno=time(10, 0),
            hora_hasta=time(10, 20),
            dni_paciente='30333444',
            apellido_nombre='Lopez, Ana',
            practica='ECOGRAFIA HEPATOBILIAR',
            codigo_practica='180113',
            modalidad='ECO',
            es_insumo=False,
            medico_informante='Camilo Gavilanes Ibarra',
            cantidad=1,
        )

        preview_con = construir_preview_cruce_liquidacion_eges(sesion, batch, usar_jornadas=True)
        item = preview_con['resultados'][0]
        self.assertEqual(item['estado'], 'advertencia')
        self.assertEqual(item['evaluacion_jornada']['estado'], ESTADO_DENTRO_JORNADA)

    def test_j2_doppler_no_se_usa_jornada_y_liquida_al_100(self):
        self.crear()
        sesion = SesionContable.objects.create(mes=8, **{'año': 2026}, estado='REVISION')
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='batch_j2_dop.xls')
        estudio_dop = Estudios.objects.create(
            nombre='ECOGRAFIA DOPPLER DE VASOS DE CUELLO',
            tipo='DOP',
            conteo_regiones=1,
            precio_cober=Decimal('2000.00'),
            precio_otras_os=Decimal('2000.00'),
            activo=True,
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion,
            medico=self.camilo,
            nombre_paciente='Pedro',
            apellido_paciente='Diaz',
            dni_paciente='30555666',
            fecha_del_informe=date(2026, 8, 6),  # Jueves 10:00 (dentro de tramo)
            tipo_obra_social='COBER',
            horario='INTRA',
            liquidar_como_extra_residencia=False,
            cantidad_regiones=1,
            monto_calculado=Decimal('2000.00'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio_dop, cantidad=1)

        EgesRow.objects.create(
            batch=batch,
            fecha_turno=date(2026, 8, 6),
            hora_turno=time(10, 0),
            hora_hasta=time(10, 20),
            dni_paciente='30555666',
            apellido_nombre='Diaz, Pedro',
            practica='ECOGRAFIA DOPPLER DE VASOS DE CUELLO',
            codigo_practica='180120',
            modalidad='ECO',
            es_insumo=False,
            medico_informante='Camilo Gavilanes Ibarra',
            cantidad=1,
        )

        preview = construir_preview_cruce_liquidacion_eges(sesion, batch, usar_jornadas=True)
        item = preview['resultados'][0]
        self.assertEqual(item['estado'], 'ok')
        self.assertEqual(item['evaluacion_jornada']['estado'], ESTADO_JORNADA_NO_APLICA)

    def test_j3_reanalizar_jornadas_crea_nueva_version_y_preserva_revisiones(self):
        self.crear()
        sesion = SesionContable.objects.create(mes=8, **{'año': 2026}, estado='REVISION')
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='batch_j3.xls')
        estudio_eco = Estudios.objects.create(
            nombre='ECOGRAFIA RENAL',
            tipo='ECO',
            conteo_regiones=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion,
            medico=self.camilo,
            nombre_paciente='Marta',
            apellido_paciente='Rios',
            dni_paciente='30777888',
            fecha_del_informe=date(2026, 8, 6),
            tipo_obra_social='COBER',
            horario='EXTRA',
            liquidar_como_extra_residencia=True,
            cantidad_regiones=1,
            monto_calculado=Decimal('1000.00'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio_eco, cantidad=1)

        EgesRow.objects.create(
            batch=batch,
            fecha_turno=date(2026, 8, 6),
            hora_turno=time(15, 0),
            hora_hasta=time(15, 20),
            dni_paciente='30777888',
            apellido_nombre='Rios, Marta',
            practica='ECOGRAFIA RENAL',
            codigo_practica='180114',
            modalidad='ECO',
            es_insumo=False,
            medico_informante='Camilo Gavilanes Ibarra',
            cantidad=1,
        )

        # Primer control v1 sin jornadas
        control_v1 = procesar_control_eges_sesion(sesion, batch, self.jefe, usar_jornadas=False)
        self.assertEqual(control_v1.version, 1)
        self.assertEqual(control_v1.total_advertencias, 1)

        # Se registra una revisión manual previa
        revision = RevisionCruceEgesRegistro.objects.create(
            sesion_contable=sesion,
            registro=registro,
            batch_eges=batch,
            estado=RevisionCruceEgesRegistro.ESTADO_VALIDADO,
            observacion='Revisión manual previa preservada',
            revisado_por=self.jefe,
        )

        # Reanálisis con jornadas
        self.client.force_login(self.jefe)
        url_reanalizar = reverse('liquidacion:cruce_eges_reanalizar_jornadas', kwargs={'pk': sesion.pk})
        response = self.client.post(url_reanalizar, {'batch': batch.pk})
        self.assertRedirects(
            response,
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': sesion.pk}) + f'?batch={batch.pk}',
        )

        control_v2 = ControlEgesSesion.objects.filter(sesion_contable=sesion).order_by('-version').first()
        self.assertEqual(control_v2.version, 2)
        resultado_v2 = control_v2.resultados.get(registro=registro)
        self.assertTrue(resultado_v2.snapshot_json.get('preservado_por_revision_previa'))

        # Verificación de que no se alteró monto ni liquidación
        registro.refresh_from_db()
        self.assertEqual(registro.monto_calculado, Decimal('1000.00'))
        self.assertEqual(registro.horario, 'EXTRA')

    def test_j3_reanalizar_jornadas_rechaza_sesiones_no_elegibles(self):
        self.crear()
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='batch_j3_invalido.xls')

        # Sesion ABIERTA (debe rechazar)
        sesion_abierta = SesionContable.objects.create(mes=8, **{'año': 2026}, estado='ABIERTA')
        self.client.force_login(self.jefe)
        url_abierta = reverse('liquidacion:cruce_eges_reanalizar_jornadas', kwargs={'pk': sesion_abierta.pk})
        response = self.client.post(url_abierta, {'batch': batch.pk})
        self.assertRedirects(
            response,
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': sesion_abierta.pk}) + f'?batch={batch.pk}',
        )

        # Sesion previa a agosto 2026 (debe rechazar)
        sesion_julio = SesionContable.objects.create(mes=7, **{'año': 2026}, estado='REVISION')
        url_julio = reverse('liquidacion:cruce_eges_reanalizar_jornadas', kwargs={'pk': sesion_julio.pk})
        response_julio = self.client.post(url_julio, {'batch': batch.pk})
        self.assertRedirects(
            response_julio,
            reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': sesion_julio.pk}) + f'?batch={batch.pk}',
        )

    def test_j4_filtros_y_comparacion_visual_en_preview(self):
        self.crear()
        sesion = SesionContable.objects.create(mes=8, **{'año': 2026}, estado='REVISION')
        batch = ImportBatch.objects.create(usuario=self.jefe, archivo_nombre='batch_j4.xls')
        estudio_eco = Estudios.objects.create(
            nombre='ECOGRAFIA ABDOMINAL',
            tipo='ECO',
            conteo_regiones=1,
            precio_cober=Decimal('1000.00'),
            precio_otras_os=Decimal('1000.00'),
            activo=True,
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            sesion_contable=sesion,
            medico=self.camilo,
            nombre_paciente='Laura',
            apellido_paciente='Vargas',
            dni_paciente='30999000',
            fecha_del_informe=date(2026, 8, 6),
            tipo_obra_social='COBER',
            horario='EXTRA',
            liquidar_como_extra_residencia=True,
            cantidad_regiones=1,
            monto_calculado=Decimal('1000.00'),
        )
        RegistroEstudio.objects.create(registro=registro, estudio=estudio_eco, cantidad=1)

        EgesRow.objects.create(
            batch=batch,
            fecha_turno=date(2026, 8, 6),
            hora_turno=time(15, 0),
            hora_hasta=time(15, 20),
            dni_paciente='30999000',
            apellido_nombre='Vargas, Laura',
            practica='ECOGRAFIA ABDOMINAL',
            codigo_practica='180112',
            modalidad='ECO',
            es_insumo=False,
            medico_informante='Camilo Gavilanes Ibarra',
            cantidad=1,
        )

        # Procesar v1 sin jornadas y luego v2 con jornadas
        procesar_control_eges_sesion(sesion, batch, self.jefe, usar_jornadas=False)
        procesar_control_eges_sesion(sesion, batch, self.jefe, usar_jornadas=True)

        self.client.force_login(self.jefe)
        url_preview = reverse('liquidacion:cruce_eges_liquidacion_preview', kwargs={'pk': sesion.pk})

        # Filtrar por estado_jornada=FUERA
        response = self.client.get(url_preview, {'batch': batch.pk, 'estado_jornada': 'FUERA'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reanalisis por jornada')
        self.assertContains(response, 'Control v1: ADVERTENCIA')
        self.assertContains(response, 'actual: OK')
