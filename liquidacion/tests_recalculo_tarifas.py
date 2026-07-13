from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    ConfiguracionGuardiaPasiva,
    Estudios,
    GrupoTarifario,
    GuardiaPasiva,
    HistorialRecalculoTarifaGuardiaPasiva,
    HistorialRecalculoTarifaRegistro,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    SesionContable,
    TarifaGrupoTarifario,
)


User = get_user_model()


class RecalculoTarifasSesionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_recalculo_tarifa',
            email='admin@example.com',
            password='testpass123',
        )
        self.medico = User.objects.create_user(
            username='medico_tarifa',
            password='testpass123',
            rol='medico_staff',
        )
        self.client.force_login(self.user)
        self.sesion = SesionContable.objects.create(mes=7, año=2026, estado='REVISION')
        self.grupo = GrupoTarifario.objects.create(
            codigo='ECO_RT',
            nombre='Eco Recalculo Tarifa',
            modalidad='ECO',
            activo=True,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 1, 1),
            vigencia_hasta=date(2026, 6, 30),
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            actualizado_por=self.user,
        )
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 7, 1),
            precio_cober=Decimal('6500.00'),
            precio_otras_os=Decimal('8500.00'),
            actualizado_por=self.user,
        )
        self.estudio = Estudios.objects.create(
            codigo='ECO-RT',
            nombre='Eco tarifa recalculo',
            tipo='ECO',
            grupo_tarifario=self.grupo,
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            activo=True,
        )
        self.registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.medico,
            sesion_contable=self.sesion,
            nombre_paciente='Paciente',
            apellido_paciente='Tarifa',
            dni_paciente='12345678',
            fecha_del_informe=date(2026, 7, 3),
            tipo_obra_social='COBER',
            horario='NA',
            monto_calculado=Decimal('5000.00'),
        )
        RegistroEstudio.objects.create(
            registro=self.registro,
            estudio=self.estudio,
            cantidad=1,
            contexto='SERVICIO',
        )
        RegistroEstudiosPorMedico.objects.filter(pk=self.registro.pk).update(
            monto_calculado=Decimal('5000.00'),
            modificado_por=None,
            fecha_modificacion=None,
            motivo_modificacion='',
        )
        self.registro.refresh_from_db()
        self.url = reverse('liquidacion:sesion_recalculo_tarifas', kwargs={'pk': self.sesion.pk})

        ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('36500.00'),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 6, 30),
        )
        ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('42000.00'),
            vigente_desde=date(2026, 7, 1),
        )
        self.guardia = GuardiaPasiva.objects.create(
            medico=self.medico,
            sesion_contable=self.sesion,
            fecha_guardia=date(2026, 7, 5),
            monto=Decimal('36500.00'),
        )
        GuardiaPasiva.objects.filter(pk=self.guardia.pk).update(monto=Decimal('36500.00'))
        self.guardia.refresh_from_db()

    def _post_data(self, confirmar='0'):
        return {
            'fecha_desde': '2026-07-01',
            'fecha_hasta': '2026-07-31',
            'motivo': 'Actualizacion tarifas julio',
            'confirmar': confirmar,
        }

    def test_preview_muestra_diferencia_sin_modificar_registro(self):
        response = self.client.post(self.url, self._post_data(confirmar='0'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Previsualizacion')
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.monto_calculado, Decimal('5000.00'))
        self.assertEqual(HistorialRecalculoTarifaRegistro.objects.count(), 0)
        self.assertEqual(HistorialRecalculoTarifaGuardiaPasiva.objects.count(), 0)

    def test_confirmar_actualiza_monto_y_crea_historial(self):
        response = self.client.post(self.url, self._post_data(confirmar='1'), secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.monto_calculado, Decimal('6500.00'))
        self.assertEqual(self.registro.modificado_por, self.user)
        self.assertIn('Recalculo por tarifas vigentes', self.registro.motivo_modificacion)
        historial = HistorialRecalculoTarifaRegistro.objects.get(registro=self.registro)
        self.assertEqual(historial.monto_anterior, Decimal('5000.00'))
        self.assertEqual(historial.monto_nuevo, Decimal('6500.00'))
        self.assertEqual(historial.diferencia, Decimal('1500.00'))

    def test_confirmar_actualiza_guardia_pasiva_y_crea_historial(self):
        response = self.client.post(self.url, self._post_data(confirmar='1'), secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        self.guardia.refresh_from_db()
        self.assertEqual(self.guardia.monto, Decimal('42000.00'))
        self.assertIn('Recalculo por tarifas vigentes de guardia pasiva', self.guardia.observaciones)
        historial = HistorialRecalculoTarifaGuardiaPasiva.objects.get(guardia=self.guardia)
        self.assertEqual(historial.monto_anterior, Decimal('36500.00'))
        self.assertEqual(historial.monto_nuevo, Decimal('42000.00'))
        self.assertEqual(historial.diferencia, Decimal('5500.00'))

    def test_preview_permite_rango_solo_con_guardias_pasivas(self):
        self.registro.fecha_del_informe = date(2026, 6, 30)
        self.registro.save(update_fields=['fecha_del_informe'])

        response = self.client.post(self.url, self._post_data(confirmar='0'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Previsualizacion de guardias pasivas')
        self.assertContains(response, '42000')

    def test_bloquea_sesion_facturada(self):
        self.sesion.estado = 'FACTURADA'
        self.sesion.save(update_fields=['estado'])

        response = self.client.get(self.url, secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.monto_calculado, Decimal('5000.00'))
