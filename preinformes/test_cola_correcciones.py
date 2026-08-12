from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Preinforme, Region, RevisionPreinforme, TipoEstudio


User = get_user_model()


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ColaCorreccionesResidenteTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_cola', password='pass123', rol='medico_residente', perfil_completo=True
        )
        self.otro = User.objects.create_user(
            username='res_otro_cola', password='pass123', rol='medico_residente', perfil_completo=True
        )
        self.staff = User.objects.create_user(
            username='staff_cola', password='pass123', rol='medico_staff', perfil_completo=True
        )
        self.tipo = TipoEstudio.objects.create(nombre='TC cola')
        self.region = Region.objects.create(nombre='Tórax cola')
        self.primero = self._crear_finalizado('COLA-001')
        self.segundo = self._crear_finalizado('COLA-002')
        self.client.login(username='res_cola', password='pass123')

    def _crear_finalizado(self, numero, residente=None):
        preinforme = Preinforme.objects.create(
            residente=residente or self.residente,
            numero_estudio=numero,
            tipo_estudio=self.tipo,
            region=self.region,
            estado='finalizado',
            fecha_finalizacion=timezone.now(),
        )
        RevisionPreinforme.objects.create(
            preinforme=preinforme,
            revisor=self.staff,
            informe_final_html='<p>Informe corregido.</p>',
        )
        return preinforme

    def test_listado_ofrece_comenzar_revision_y_marca_nuevas(self):
        response = self.client.get(reverse('preinformes:mis_preinformes'))

        self.assertContains(response, 'Tenés 2 correcciones nuevas')
        self.assertContains(response, 'Comenzar revisión')
        self.assertContains(response, 'Corrección nueva', count=2)

    def test_confirmar_lectura_avanza_a_siguiente_pendiente(self):
        response = self.client.post(
            reverse('preinformes:marcar_correccion_vista', args=[self.primero.pk]),
            {'cola': 'correcciones'},
        )

        self.primero.refresh_from_db()
        self.assertIsNotNone(self.primero.fecha_correccion_vista)
        self.assertRedirects(
            response,
            f"{reverse('preinformes:ver_preinforme', args=[self.segundo.pk])}?cola=correcciones",
            fetch_redirect_response=False,
        )

    def test_no_permite_marcar_correccion_ajena(self):
        ajeno = self._crear_finalizado('COLA-AJENO', residente=self.otro)

        response = self.client.post(
            reverse('preinformes:marcar_correccion_vista', args=[ajeno.pk])
        )

        self.assertEqual(response.status_code, 404)
        ajeno.refresh_from_db()
        self.assertIsNone(ajeno.fecha_correccion_vista)

    def test_detalle_vuelve_al_listado_con_filtros_fechas_y_pagina(self):
        listado = (
            reverse('preinformes:mis_preinformes')
            + '?estado=finalizado&fecha_desde=2026-08-01&fecha_hasta=2026-08-12&page=2'
        )

        response = self.client.get(
            reverse('preinformes:ver_preinforme', args=[self.primero.pk]),
            {'next': listado},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{listado.replace("&", "&amp;")}"', html=False)

    def test_marcar_fuera_de_cola_regresa_a_filtros(self):
        listado = reverse('preinformes:mis_preinformes') + '?estado=finalizado&page=2'

        response = self.client.post(
            reverse('preinformes:marcar_correccion_vista', args=[self.primero.pk]),
            {'next': listado},
        )

        self.assertRedirects(response, listado, fetch_redirect_response=False)

    def test_retorno_externo_es_rechazado(self):
        response = self.client.get(
            reverse('preinformes:ver_preinforme', args=[self.primero.pk]),
            {'next': 'https://sitio-malicioso.example/robo'},
        )

        self.assertEqual(response.context['volver_url'], reverse('preinformes:mis_preinformes'))

    def test_finalizar_nuevamente_reabre_la_novedad(self):
        self.primero.fecha_correccion_vista = timezone.now()
        self.primero.save(update_fields=['fecha_correccion_vista'])

        self.primero.finalizar_revision()

        self.primero.refresh_from_db()
        self.assertIsNone(self.primero.fecha_correccion_vista)
