from datetime import date, time
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from .tests_produccion import FuentesSinteticasMixin
from .services_validacion_produccion import preparar_validacion_produccion, construir_resultado_validado
from .services_revision_parcial import guardar_revision_parcial, decisiones_guardadas
from .models import EgesRow, NettermFila, ProduccionValidada


class RepeticionesEcoTest(FuentesSinteticasMixin, TestCase):
    def preparar(self):
        return preparar_validacion_produccion(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
            fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31))

    def repetidas(self, codigo='180112', practica='ECOGRAFIA COMPLETA DE ABDOMEN'):
        for indice in (10, 11):
            self.eges(hora_turno=time(indice), codigo_practica=codigo, practica=practica)
            fila = self.netterm(pedido=str(indice), codigo=codigo, practica=practica,
                hora_realizacion=f'{indice}:30:00', hora_pedido=f'{indice}:00:00')

    def test_unico_retira_tambien_copia_eges_y_conserva_otras_regiones(self):
        self.repetidas()
        self.eges(codigo_practica='180116', practica='ECOGRAFIA TIROIDEA')
        p = self.preparar()
        self.assertEqual(len(p['grupos_repeticiones']), 1)
        resultado = construir_resultado_validado(p, {p['grupos_repeticiones'][0]['id']: {'accion': 'UNICO'}})
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(EgesRow.objects.count(), 3)
        self.assertEqual(NettermFila.objects.count(), 2)
        self.assertEqual(resultado['agrupaciones_repeticiones'][0]['practicas_despues'], 1)

    def test_independientes_vincula_por_hora_sin_eliminar_realizaciones(self):
        self.repetidas()
        p = self.preparar()
        resultado = construir_resultado_validado(p, {p['grupos_repeticiones'][0]['id']: {'accion': 'INDEPENDIENTES'}})
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(resultado['aporte_netterm'], 0)

    def test_grupo_pendiente_bloquea_confirmacion_pero_permite_guardado_parcial(self):
        self.repetidas()
        p = self.preparar()
        with self.assertRaises(ValidationError):
            construir_resultado_validado(p, {})
        grupo = p['grupos_repeticiones'][0]['id']
        guardar_revision_parcial(preparacion=p, firma_esperada=p['firma'],
            decisiones={grupo: {'accion': 'UNICO'}}, usuario=self.usuario, motivo='Verificado en fuente externa')
        guardadas = decisiones_guardadas(p)
        self.assertEqual(guardadas[grupo]['accion'], 'UNICO')
        self.assertEqual(construir_resultado_validado(p, guardadas)['total_produccion'], 1)
        self.assertFalse(ProduccionValidada.objects.exists())

    def test_distintas_practicas_no_forman_grupo(self):
        self.eges()
        self.eges(codigo_practica='180116', practica='ECOGRAFIA TIROIDEA')
        self.netterm()
        self.assertEqual(self.preparar()['grupos_repeticiones'], [])

    def test_doppler_mmii_unico_retira_copia_eges_sin_afectar_venoso(self):
        self.repetidas(codigo='900046', practica='ECODOPPLER ARTERIAL MM INF')
        self.eges(codigo_practica='900048', practica='ECODOPPLER VENOSO MM INF')
        p = self.preparar()
        self.assertEqual(p['grupos_repeticiones'], [])
        grupo = p['grupos_bilaterales'][0]['id']
        resultado = construir_resultado_validado(p, {grupo: {'accion': 'UNICO'}})
        self.assertEqual(resultado['total_produccion'], 2)
        self.assertEqual(EgesRow.objects.count(), 3)

    def test_nombre_distinto_con_lc_solo_ofrece_candidata_manual(self):
        fila_eges = self.eges(apellido_nombre='PRUEBA ANA MARIA')
        fila_nt = self.netterm(tipo_documento='LC', paciente='PRUEBA ANA')
        p = self.preparar()
        caso = next(item for item in p['excepciones'] if item['id'] == str(fila_nt.pk))
        self.assertEqual(caso['candidatas'][0]['id'], fila_eges.pk)
        self.assertFalse(next(item for item in p['preview']['resultados'] if item['netterm'])['identidad_coincidente'])
        with self.assertRaises(ValidationError):
            construir_resultado_validado(p, {})
        resultado = construir_resultado_validado(p, {str(fila_nt.pk): {'accion': f'VINCULAR:{fila_eges.pk}', 'modalidad': 'ECO'}})
        self.assertEqual(resultado['total_produccion'], 1)

    def test_realizado_sin_informe_se_puede_revisar_sin_inventar_informe(self):
        self.eges()
        self.eges(hora_turno=time(11))
        fila = self.netterm(estado='PENDIENTE', hora_realizacion='11:30:00')
        p = self.preparar()
        self.assertIn(str(fila.pk), {e['id'] for e in p['excepciones']})
        grupo = p['grupos_repeticiones'][0]['id']
        resultado = construir_resultado_validado(p, {grupo: {'accion': 'UNICO'}})
        self.assertEqual(resultado['total_produccion'], 1)
        fila.refresh_from_db()
        self.assertEqual(fila.estado_informe, 'PENDIENTE')

    @override_settings(SECURE_SSL_REDIRECT=False, SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_pantalla_recupera_grupo_generico_guardado(self):
        self.repetidas()
        p = self.preparar()
        grupo = p['grupos_repeticiones'][0]['id']
        guardar_revision_parcial(preparacion=p, firma_esperada=p['firma'],
            decisiones={grupo: {'accion': 'UNICO'}}, usuario=self.usuario, motivo='Prueba de recuperación')
        self.client.force_login(self.usuario)
        pagina = self.client.get(reverse('eges_import:validar_produccion'), {
            'lotes_eges': [self.batch.pk], 'lotes_netterm': [self.lote.pk],
            'fecha_desde': '2026-10-01', 'fecha_hasta': '2026-10-31'})
        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'Carga duplicada: una práctica')
        self.assertContains(pagina, 'Se recuperaron')
        self.assertEqual(pagina.context['preparacion']['grupos_repeticiones'][0]['accion_seleccionada'], 'UNICO')
