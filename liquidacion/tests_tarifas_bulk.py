from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ConfiguracionGuardiaPasiva, GrupoTarifario, GuardiaPasiva, TarifaGrupoTarifario


User = get_user_model()


class TarifasGrupoBulkUpdateTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_tarifas',
            email='admin@example.com',
            password='testpass123',
        )
        self.client.force_login(self.user)
        self.grupo = GrupoTarifario.objects.create(
            codigo='ECO_BULK',
            nombre='Ecografia Bulk',
            modalidad='ECO',
            activo=True,
        )
        self.tarifa_anterior = TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 1, 1),
            precio_cober=Decimal('5000.00'),
            precio_otras_os=Decimal('7000.00'),
            motivo_actualizacion='Inicial',
            actualizado_por=self.user,
        )
        self.url = reverse('liquidacion:grupo_tarifario_tarifa_bulk_update')

    def _post_data(self, confirmar='1', precio_cober='6500.00', precio_otras='8500.00'):
        return {
            'vigencia_desde': '2026-07-01',
            'motivo_actualizacion': 'Actualizacion julio 2026',
            f'incluir_{self.grupo.pk}': 'on',
            f'precio_cober_{self.grupo.pk}': precio_cober,
            f'precio_otras_os_{self.grupo.pk}': precio_otras,
            'confirmar': confirmar,
        }

    def test_preview_no_crea_tarifa(self):
        response = self.client.post(self.url, self._post_data(confirmar='0'), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Previsualizacion')
        self.assertEqual(TarifaGrupoTarifario.objects.filter(grupo_tarifario=self.grupo).count(), 1)

    def test_confirmar_crea_nueva_tarifa_y_cierra_anterior(self):
        response = self.client.post(self.url, self._post_data(), secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        self.tarifa_anterior.refresh_from_db()
        self.assertEqual(self.tarifa_anterior.vigencia_hasta, date(2026, 6, 30))
        nueva = TarifaGrupoTarifario.objects.get(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 7, 1),
        )
        self.assertEqual(nueva.precio_cober, Decimal('6500.00'))
        self.assertEqual(nueva.precio_otras_os, Decimal('8500.00'))
        self.assertEqual(nueva.actualizado_por, self.user)

    def test_bloquea_vigencia_duplicada(self):
        TarifaGrupoTarifario.objects.create(
            grupo_tarifario=self.grupo,
            vigencia_desde=date(2026, 7, 1),
            precio_cober=Decimal('6500.00'),
            precio_otras_os=Decimal('8500.00'),
            actualizado_por=self.user,
        )

        response = self.client.post(self.url, self._post_data(), secure=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ya existe una tarifa con vigencia')

    def test_confirmar_crea_nueva_tarifa_guardia_pasiva_y_cierra_anterior(self):
        tarifa_guardia = ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('36500.00'),
            vigente_desde=date(2026, 1, 1),
            motivo_actualizacion='Inicial guardia',
            actualizado_por=self.user,
        )
        data = self._post_data()
        data.pop(f'incluir_{self.grupo.pk}')
        data['incluir_guardia_pasiva'] = 'on'
        data['monto_guardia_pasiva'] = '42000.00'

        response = self.client.post(self.url, data, secure=True, follow=True)

        self.assertEqual(response.status_code, 200)
        tarifa_guardia.refresh_from_db()
        self.assertEqual(tarifa_guardia.vigente_hasta, date(2026, 6, 30))
        nueva = ConfiguracionGuardiaPasiva.objects.get(vigente_desde=date(2026, 7, 1))
        self.assertEqual(nueva.monto_vigente, Decimal('42000.00'))
        self.assertIsNone(nueva.vigente_hasta)

    def test_guardia_pasiva_toma_tarifa_por_fecha_guardia(self):
        ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('36500.00'),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 6, 30),
        )
        ConfiguracionGuardiaPasiva.objects.create(
            monto_vigente=Decimal('42000.00'),
            vigente_desde=date(2026, 7, 1),
        )

        guardia_junio = GuardiaPasiva.objects.create(
            medico=self.user,
            fecha_guardia=date(2026, 6, 30),
        )
        guardia_julio = GuardiaPasiva.objects.create(
            medico=self.user,
            fecha_guardia=date(2026, 7, 1),
        )

        self.assertEqual(guardia_junio.monto, Decimal('36500.00'))
        self.assertEqual(guardia_julio.monto, Decimal('42000.00'))
