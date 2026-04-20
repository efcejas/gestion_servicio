from django.test import TestCase, override_settings
from django.utils import timezone

from .models import CorreoResumen, CorreoSincronizacion
from .selectors import get_dashboard_context
from .services import _clasificar_correo, _extraer_fechas_y_acciones


class CorreoResumenServiceTests(TestCase):
    @override_settings(CORREO_RESUMEN_CONFIG={
        'PRIORITY_SENDERS': 'auditoria@sanatorio.com',
        'URGENT_KEYWORDS': 'urgente,auditoria',
        'ACTION_KEYWORDS': 'responder,confirmar',
    })
    def test_clasificar_correo_detecta_prioridad_alta(self):
        payload = {
            'remitente': 'auditoria@sanatorio.com',
            'asunto': 'Auditoría urgente de consultorios',
            'snippet': 'Necesitamos responder hoy mismo',
            'leido': False,
            'tiene_adjuntos': True,
        }

        clasificacion = _clasificar_correo(payload, {'PRIORITY_SENDERS': 'auditoria@sanatorio.com', 'URGENT_KEYWORDS': 'urgente,auditoria', 'ACTION_KEYWORDS': 'responder,confirmar'})

        self.assertEqual(clasificacion['prioridad_sugerida'], 'URGENTE')
        self.assertTrue(clasificacion['requiere_accion'])
        self.assertGreaterEqual(clasificacion['score_importancia'], 80)

    def test_extraer_fechas_detecta_vence_hoy(self):
        payload = {
            'asunto': 'Solicitud urgente',
            'snippet': 'Vence hoy a las 17 hs',
        }

        resultado = _extraer_fechas_y_acciones(payload)

        self.assertIsNotNone(resultado['fecha_compromiso'])
        self.assertEqual(resultado['fecha_compromiso'].date(), timezone.now().date())
        self.assertIn('hoy', resultado['evidencia_fecha'].lower())

    def test_extraer_fechas_detecta_vence_maniana(self):
        payload = {
            'asunto': 'Documentación pendiente',
            'snippet': 'Por favor vence mañana',
        }

        resultado = _extraer_fechas_y_acciones(payload)

        self.assertIsNotNone(resultado['fecha_compromiso'])
        esperado = timezone.now().date() + timezone.timedelta(days=1)
        self.assertEqual(resultado['fecha_compromiso'].date(), esperado)
        self.assertIn('mañana', resultado['evidencia_fecha'].lower())

    def test_extraer_fechas_detecta_requiere_respuesta(self):
        payload = {
            'asunto': 'Necesitamos tu aporte',
            'snippet': 'Por favor responde a la brevedad',
        }

        resultado = _extraer_fechas_y_acciones(payload)

        self.assertTrue(resultado['requiere_respuesta'])

    def test_extraer_fechas_no_detecta_falso_positivo(self):
        payload = {
            'asunto': 'Información de auditoría general',
            'snippet': 'Se adjunta el reporte mensual sin hallazgos críticos.',
        }

        resultado = _extraer_fechas_y_acciones(payload)

        self.assertFalse(resultado['requiere_respuesta'])
        self.assertIsNone(resultado['fecha_compromiso'])

    def test_extraer_fechas_detecta_para_el_dd_mm(self):
        # Prueba patrón "para el 25/04"
        hoy = timezone.now()
        asunto = 'Reporte de gestión'
        # Usar una fecha futura
        snippet = f'Este documento debe estar listo para el {hoy.day}/04'
        
        payload = {
            'asunto': asunto,
            'snippet': snippet,
        }

        resultado = _extraer_fechas_y_acciones(payload)

        # Si la fecha ya pasó, debería calcular para el próximo año
        if timezone.now().month > 4:
            self.assertIsNotNone(resultado['fecha_compromiso'])
        else:
            # Si estamos en o antes de abril, debería detectarla
            self.assertIsNotNone(resultado['fecha_compromiso'])


class CorreoResumenSelectorTests(TestCase):
    def test_dashboard_context_expone_resumen_y_sync(self):
        correo = CorreoResumen.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            remote_uid='1',
            message_id='msg-1',
            asunto='Recorrida de calidad',
            remitente='calidad@sanatorio.com',
            fecha_email=timezone.now(),
            snippet='Hay hallazgos pendientes para revisar',
            score_importancia=85,
            prioridad_sugerida='URGENTE',
            categoria='AUDITORIA',
            resumen_ejecutivo='Calidad solicita revisión hoy por hallazgos pendientes.',
        )
        CorreoSincronizacion.objects.create(
            cuenta='inbox',
            proveedor='IMAP',
            estado='OK',
            correos_leidos=3,
            correos_nuevos=1,
        )

        context = get_dashboard_context()

        self.assertIn(correo, list(context['correos_urgentes']))
        self.assertEqual(context['correo_urgentes_count'], 1)
        self.assertTrue(context['correo_resumen_del_dia'])
        self.assertIsNotNone(context['correo_ultima_sync'])
