from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from evaluaciones_residentes.models import Examen, IntentoExamen, Opcion, Pregunta, PreguntaImagen


class EvaluacionViewsTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.docente = user_model.objects.create_user(
            username='docente-web',
            password='test-pass',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.residente = user_model.objects.create_user(
            username='residente-web',
            password='test-pass',
            rol='medico_residente',
            anio_residencia='R1',
            estado_residencia='ACTIVO',
            perfil_completo=True,
        )
        self.examen = Examen.objects.create(
            titulo='Evaluacion web',
            creador=self.docente,
            ciclo_lectivo='2026',
            modo_destinatarios=Examen.ANIOS,
            anios_destinatarios=['R1'],
            fecha_apertura=timezone.now(),
            fecha_vencimiento=timezone.now() + timedelta(hours=1),
        )

    def test_docente_puede_ver_sus_evaluaciones(self):
        self.client.force_login(self.docente)

        response = self.client.get(reverse('evaluaciones_residentes:lista'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Evaluacion web')

    def test_residente_no_puede_entrar_al_editor_docente(self):
        self.client.force_login(self.residente)

        response = self.client.get(reverse('evaluaciones_residentes:lista'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_bandeja_docente_cierra_evaluaciones_vencidas(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.fecha_vencimiento = timezone.now() - timedelta(minutes=1)
        self.examen.save(update_fields=['estado', 'fecha_vencimiento'])

        response = self.client.get(reverse('evaluaciones_residentes:lista'))

        self.assertEqual(response.status_code, 200)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado, Examen.CERRADO)
        self.assertContains(response, 'Cerradas')

    def test_residente_no_puede_iniciar_evaluacion_cerrada_automaticamente(self):
        self.client.force_login(self.residente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.fecha_apertura = timezone.now() - timedelta(hours=2)
        self.examen.fecha_vencimiento = timezone.now() - timedelta(minutes=1)
        self.examen.save(update_fields=['estado', 'fecha_apertura', 'fecha_vencimiento'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )

        response = self.client.get(reverse('evaluaciones_residentes:detalle_residente', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 200)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado, Examen.CERRADO)
        self.assertContains(response, 'La evaluación ya cerró')
        self.assertNotContains(response, 'Iniciar evaluación')

    def test_residente_puede_iniciar_intento_de_evaluacion_asignada(self):
        self.client.force_login(self.residente)
        Pregunta.objects.create(examen=self.examen, texto='Pregunta de prueba', orden=1)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        response = self.client.post(reverse('evaluaciones_residentes:iniciar_residente', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 302)
        intento = IntentoExamen.objects.get(examen=self.examen, residente=self.residente)
        self.assertEqual(response.url, reverse('evaluaciones_residentes:intento_residente', args=[intento.pk]))

    def test_residente_puede_guardar_respuesta_y_avanzar(self):
        self.client.force_login(self.residente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta de prueba', orden=1)
        correcta = Opcion.objects.create(pregunta=pregunta, texto='Respuesta', orden=1, es_correcta=True)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(examen=self.examen, residente=self.residente, anio_residencia_al_asignar='R1', ciclo_lectivo='2026', criterio_origen=Examen.ANIOS)
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.post(reverse('evaluaciones_residentes:intento_residente', args=[intento.pk]), {f'pregunta_{pregunta.pk}': str(correcta.pk)})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(intento.respuestas.filter(pregunta=pregunta).exists())

    def test_residente_puede_volver_a_pregunta_anterior_guardando(self):
        self.client.force_login(self.residente)
        primera = Pregunta.objects.create(examen=self.examen, texto='Primera', orden=1)
        Opcion.objects.create(pregunta=primera, texto='A', orden=1, es_correcta=True)
        segunda = Pregunta.objects.create(examen=self.examen, texto='Segunda', orden=2)
        opcion_segunda = Opcion.objects.create(pregunta=segunda, texto='B', orden=1, es_correcta=True)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.post(
            f"{reverse('evaluaciones_residentes:intento_residente', args=[intento.pk])}?pregunta=1",
            {
                f'pregunta_{segunda.pk}': str(opcion_segunda.pk),
                'accion': 'anterior',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('pregunta=0', response.url)
        self.assertTrue(intento.respuestas.filter(pregunta=segunda).exists())

    def test_residente_puede_entregar_desde_ultima_pregunta(self):
        self.client.force_login(self.residente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta final', orden=1, puntaje='2.00')
        correcta = Opcion.objects.create(pregunta=pregunta, texto='Correcta', orden=1, es_correcta=True)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.post(
            reverse('evaluaciones_residentes:intento_residente', args=[intento.pk]),
            {
                f'pregunta_{pregunta.pk}': str(correcta.pk),
                'accion': 'entregar',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('evaluaciones_residentes:confirmar_entrega', args=[intento.pk]))
        self.assertEqual(intento.estado, IntentoExamen.INICIADO)

        response = self.client.get(response.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confirmar y entregar')
        intento.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.INICIADO)

        response = self.client.post(
            reverse('evaluaciones_residentes:confirmar_entrega', args=[intento.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('evaluaciones_residentes:detalle_residente', args=[self.examen.pk]))
        intento.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.CORREGIDO)
        self.assertIsNotNone(intento.entregado_en)

    def test_docente_puede_ver_bandeja_de_intentos(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.get(
            reverse('evaluaciones_residentes:intentos', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.residente.username)
        self.assertContains(response, reverse('evaluaciones_residentes:revisar_intento', args=[intento.pk]))

    def test_bandeja_docente_filtra_intentos_por_estado(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        iniciado = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)
        otro_residente = get_user_model().objects.create_user(
            username='residente-filtrado',
            rol='medico_residente',
            anio_residencia='R1',
            estado_residencia='ACTIVO',
        )
        corregido = IntentoExamen.objects.create(
            examen=self.examen,
            residente=otro_residente,
            estado=IntentoExamen.CORREGIDO,
        )

        response = self.client.get(
            reverse('evaluaciones_residentes:intentos', args=[self.examen.pk]),
            {'estado': IntentoExamen.CORREGIDO},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, iniciado.residente.username)
        self.assertContains(response, corregido.residente.username)
        self.assertEqual(response.context['total_entregados'], 1)

    def test_docente_puede_corregir_y_publicar_respuesta_desarrollada(self):
        self.client.force_login(self.docente)
        pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Explique el hallazgo',
            orden=1,
            tipo=Pregunta.DESARROLLO,
            puntaje='3.00',
        )
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            estado=IntentoExamen.PENDIENTE_CORRECCION,
        )
        from evaluaciones_residentes.models import Respuesta
        respuesta = Respuesta.objects.create(
            intento=intento,
            pregunta=pregunta,
            texto_desarrollo='Respuesta del residente',
            requiere_correccion=True,
        )

        response = self.client.post(
            reverse('evaluaciones_residentes:revisar_intento', args=[intento.pk]),
            {
                'accion': 'corregir',
                f'respuesta_{respuesta.pk}-puntaje': '2.50',
                f'respuesta_{respuesta.pk}-comentario': 'Buen análisis.',
            },
        )

        self.assertEqual(response.status_code, 302)
        intento.refresh_from_db()
        respuesta.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.CORREGIDO)
        self.assertEqual(respuesta.puntaje_obtenido, 2.5)
        self.assertFalse(respuesta.requiere_correccion)

        response = self.client.post(
            reverse('evaluaciones_residentes:revisar_intento', args=[intento.pk]),
            {'accion': 'publicar'},
        )

        self.assertEqual(response.status_code, 302)
        intento.refresh_from_db()
        self.assertIsNotNone(intento.resultado_publicado_en)

    def test_docente_puede_anular_intento_con_motivo(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.post(
            reverse('evaluaciones_residentes:revisar_intento', args=[intento.pk]),
            {
                'accion': 'anular',
                'anulacion-motivo': 'El residente tuvo una falla de conexión.',
            },
        )

        self.assertEqual(response.status_code, 302)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.ANULADO)
        self.assertEqual(intento.anulado_por_id, self.docente.pk)

        response = self.client.get(
            reverse('evaluaciones_residentes:revisar_intento', args=[intento.pk]),
        )

        self.assertContains(response, 'Intento anulado')
        self.assertContains(response, 'falla de conexión')

    def test_docente_puede_recuperar_intento_anulado(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            estado=IntentoExamen.ANULADO,
            motivo_anulacion='Se anuló por una incidencia técnica.',
        )

        response = self.client.post(
            reverse('evaluaciones_residentes:revisar_intento', args=[intento.pk]),
            {
                'accion': 'recuperar',
                'recuperacion-motivo': 'Jefatura autorizó una nueva oportunidad.',
            },
        )

        self.assertEqual(response.status_code, 302)
        intento.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.INICIADO)
        self.assertEqual(intento.recuperado_por_id, self.docente.pk)

    def test_residente_no_puede_ver_bandeja_docente_de_intentos(self):
        self.client.force_login(self.residente)

        response = self.client.get(
            reverse('evaluaciones_residentes:intentos', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('home'))

    def test_residente_no_ve_resultado_hasta_que_se_publique(self):
        self.client.force_login(self.residente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            estado=IntentoExamen.CORREGIDO,
            nota_final='8.00',
            porcentaje='80.00',
        )

        response = self.client.get(
            reverse('evaluaciones_residentes:resultado_residente', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('evaluaciones_residentes:detalle_residente', args=[self.examen.pk]))
        intento.resultado_publicado_en = timezone.now()
        intento.save(update_fields=['resultado_publicado_en'])

        response = self.client.get(
            reverse('evaluaciones_residentes:resultado_residente', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '8,00')
        self.assertContains(response, '80,00%')

    def test_residente_no_puede_consultar_resultado_de_evaluacion_no_asignada(self):
        self.client.force_login(self.residente)

        response = self.client.get(
            reverse('evaluaciones_residentes:resultado_residente', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_residente_no_ve_resultado_de_intento_anulado(self):
        self.client.force_login(self.residente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            estado=IntentoExamen.ANULADO,
            motivo_anulacion='Se anuló por una incidencia técnica.',
            resultado_publicado_en=timezone.now(),
        )

        response = self.client.get(
            reverse('evaluaciones_residentes:resultado_residente', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('evaluaciones_residentes:detalle_residente', args=[self.examen.pk]))

    def test_reanudar_intento_recupera_respuesta_guardada(self):
        self.client.force_login(self.residente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta guardada', orden=1)
        opcion = Opcion.objects.create(pregunta=pregunta, texto='Elegida', orden=1)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen, Respuesta, RespuestaOpcion
        DestinatarioExamen.objects.create(examen=self.examen, residente=self.residente, anio_residencia_al_asignar='R1', ciclo_lectivo='2026', criterio_origen=Examen.ANIOS)
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)
        respuesta = Respuesta.objects.create(intento=intento, pregunta=pregunta)
        RespuestaOpcion.objects.create(respuesta=respuesta, opcion=opcion)

        response = self.client.get(reverse('evaluaciones_residentes:intento_residente', args=[intento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn(opcion.pk, response.context['opciones_seleccionadas'])

    def test_intento_renderiza_visor_para_imagenes(self):
        self.client.force_login(self.residente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta con imagen', orden=1)
        Opcion.objects.create(pregunta=pregunta, texto='Elegida', orden=1, es_correcta=True)
        PreguntaImagen.objects.create(
            pregunta=pregunta,
            archivo='preguntas/galeria/imagen.jpg',
            orden=1,
        )
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.get(reverse('evaluaciones_residentes:intento_residente', args=[intento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-abrir-imagen')
        self.assertContains(response, 'visor-imagen-pregunta')
        self.assertContains(response, 'mover-visor-imagen')

    def test_revision_docente_renderiza_visor_para_imagenes(self):
        self.client.force_login(self.docente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta con imagen', orden=1)
        Opcion.objects.create(pregunta=pregunta, texto='Elegida', orden=1, es_correcta=True)
        PreguntaImagen.objects.create(
            pregunta=pregunta,
            archivo='preguntas/galeria/imagen.jpg',
            orden=1,
        )

        response = self.client.get(reverse('evaluaciones_residentes:revision', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-abrir-imagen')
        self.assertContains(response, 'visor-imagen-pregunta')

    def test_resultado_residente_renderiza_visor_para_imagenes_publicadas(self):
        self.client.force_login(self.residente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta con imagen', orden=1)
        Opcion.objects.create(pregunta=pregunta, texto='Elegida', orden=1, es_correcta=True)
        PreguntaImagen.objects.create(
            pregunta=pregunta,
            archivo='preguntas/galeria/imagen.jpg',
            orden=1,
        )
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])
        from evaluaciones_residentes.models import DestinatarioExamen, Respuesta
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            estado=IntentoExamen.CORREGIDO,
            nota_final='8.00',
            porcentaje='80.00',
            resultado_publicado_en=timezone.now(),
        )
        Respuesta.objects.create(intento=intento, pregunta=pregunta, puntaje_obtenido='1.00')

        response = self.client.get(reverse('evaluaciones_residentes:resultado_residente', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js-abrir-imagen')
        self.assertContains(response, 'visor-imagen-pregunta')

    def test_residente_no_puede_guardar_respuesta_fuera_de_periodo(self):
        self.client.force_login(self.residente)
        pregunta = Pregunta.objects.create(examen=self.examen, texto='Pregunta vencida', orden=1)
        opcion = Opcion.objects.create(pregunta=pregunta, texto='Respuesta', orden=1)
        self.examen.estado = Examen.PUBLICADO
        self.examen.fecha_apertura = timezone.now() - timedelta(hours=2)
        self.examen.fecha_vencimiento = timezone.now() - timedelta(minutes=1)
        self.examen.save(update_fields=['estado', 'fecha_apertura', 'fecha_vencimiento'])
        from evaluaciones_residentes.models import DestinatarioExamen
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )
        intento = IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        response = self.client.post(
            reverse('evaluaciones_residentes:intento_residente', args=[intento.pk]),
            {f'pregunta_{pregunta.pk}': str(opcion.pk)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('evaluaciones_residentes:detalle_residente', args=[self.examen.pk]))
        self.assertFalse(intento.respuestas.exists())

    def test_residente_no_puede_iniciar_evaluacion_no_asignada(self):
        self.client.force_login(self.residente)

        response = self.client.post(reverse('evaluaciones_residentes:iniciar_residente', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 404)

    def test_docente_puede_eliminar_borrador_por_post(self):
        self.client.force_login(self.docente)

        response = self.client.post(
            reverse('evaluaciones_residentes:eliminar', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Examen.objects.filter(pk=self.examen.pk).exists())

    def test_no_se_puede_eliminar_un_examen_publicado(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])

        response = self.client.post(
            reverse('evaluaciones_residentes:eliminar', args=[self.examen.pk]),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Examen.objects.filter(pk=self.examen.pk).exists())

    def test_docente_puede_crear_borrador(self):
        self.client.force_login(self.docente)
        datos = {
            'titulo': 'Nueva evaluacion',
            'descripcion': 'Descripcion',
            'instrucciones': 'Leer cada consigna.',
            'ciclo_lectivo': '2026',
            'modo_destinatarios': 'ANIOS',
            'modo_inicio': 'AUTOMATICO',
            'fecha_apertura': '2026-09-20T08:00',
            'fecha_vencimiento': '2026-09-21T08:00',
            'anios_destinatarios': ['R1'],
            'residentes_destinatarios': [],
        }

        response = self.client.post(reverse('evaluaciones_residentes:crear'), datos)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Examen.objects.filter(titulo='Nueva evaluacion', estado=Examen.BORRADOR).exists())

    def test_docente_puede_editar_destinatario_individual(self):
        self.client.force_login(self.docente)
        datos = {
            'titulo': self.examen.titulo,
            'descripcion': '',
            'instrucciones': '',
            'ciclo_lectivo': '2026',
            'modo_destinatarios': 'RESIDENTES',
            'modo_inicio': 'AUTOMATICO',
            'fecha_apertura': '2026-09-20T08:00',
            'fecha_vencimiento': '2026-09-21T08:00',
            'residentes_destinatarios': [str(self.residente.pk)],
        }

        response = self.client.post(
            reverse('evaluaciones_residentes:editar', args=[self.examen.pk]),
            datos,
        )

        self.assertEqual(response.status_code, 302)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.modo_destinatarios, Examen.RESIDENTES)
        self.assertEqual(list(self.examen.residentes_destinatarios.values_list('pk', flat=True)), [self.residente.pk])

    def test_docente_puede_editar_modo_todos_sin_residentes_especificos(self):
        self.client.force_login(self.docente)
        datos = {
            'titulo': self.examen.titulo,
            'descripcion': '',
            'instrucciones': '',
            'ciclo_lectivo': '2026',
            'modo_destinatarios': 'TODOS',
            'modo_inicio': 'AUTOMATICO',
            'fecha_apertura': '2026-09-20T08:00',
            'fecha_vencimiento': '2026-09-21T08:00',
            'residentes_destinatarios': [],
        }

        response = self.client.post(
            reverse('evaluaciones_residentes:editar', args=[self.examen.pk]),
            datos,
        )

        self.assertEqual(response.status_code, 302)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.modo_destinatarios, Examen.TODOS)
        self.assertFalse(self.examen.residentes_destinatarios.exists())

    def test_docente_puede_iniciar_examen_manual(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.modo_inicio = Examen.INICIO_MANUAL
        self.examen.save(update_fields=['estado', 'modo_inicio'])

        response = self.client.post(reverse('evaluaciones_residentes:iniciar_examen', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 302)
        self.examen.refresh_from_db()
        self.assertIsNotNone(self.examen.iniciado_en)

    def test_docente_puede_finalizar_examen_en_curso(self):
        self.client.force_login(self.docente)
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])

        response = self.client.post(reverse('evaluaciones_residentes:finalizar', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 302)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado, Examen.CERRADO)
        self.assertIsNotNone(self.examen.fecha_cierre)

    def test_publicar_solo_acepta_post(self):
        self.client.force_login(self.docente)
        pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Pregunta',
            orden=1,
        )
        Opcion.objects.create(pregunta=pregunta, texto='Correcta', orden=1, es_correcta=True)
        Opcion.objects.create(pregunta=pregunta, texto='Incorrecta', orden=2)

        response = self.client.get(reverse('evaluaciones_residentes:publicar', args=[self.examen.pk]))

        self.assertEqual(response.status_code, 403)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado, Examen.BORRADOR)

    def test_docente_puede_crear_pregunta_con_opciones(self):
        self.client.force_login(self.docente)
        datos = {
            'texto': '¿Cuál es la respuesta?',
            'orden': '1',
            'puntaje': '2.00',
            'tipo': 'OPCION_UNICA',
            'opciones-TOTAL_FORMS': '2',
            'opciones-INITIAL_FORMS': '0',
            'opciones-MIN_NUM_FORMS': '0',
            'opciones-MAX_NUM_FORMS': '1000',
            'opciones-0-texto': 'Correcta',
            'opciones-0-orden': '1',
            'opciones-0-es_correcta': 'on',
            'opciones-1-texto': 'Incorrecta',
            'opciones-1-orden': '2',
        }

        response = self.client.post(
            reverse('evaluaciones_residentes:crear_pregunta', args=[self.examen.pk]),
            datos,
        )

        self.assertEqual(response.status_code, 302, response.context)
        pregunta = self.examen.preguntas.get()
        self.assertEqual(pregunta.opciones.count(), 2)
        self.assertEqual(pregunta.opciones.filter(es_correcta=True).count(), 1)

    def test_docente_puede_guardar_opcion_unica_con_imagen(self):
        self.client.force_login(self.docente)
        datos = {
            'texto': '¿Cuál es la respuesta?',
            'orden': '1',
            'puntaje': '2.00',
            'tipo': 'OPCION_UNICA',
            'opciones-TOTAL_FORMS': '2',
            'opciones-INITIAL_FORMS': '0',
            'opciones-MIN_NUM_FORMS': '0',
            'opciones-MAX_NUM_FORMS': '1000',
            'opciones-0-texto': 'Correcta',
            'opciones-0-orden': '1',
            'opciones-0-es_correcta': 'on',
            'opciones-1-texto': 'Incorrecta',
            'opciones-1-orden': '2',
        }
        imagen = SimpleUploadedFile(
            'hallazgo.png',
            (
                b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
                b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
                b'\x00\x00\x00\x0dIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00'
                b'\x05\x00\x01\xff\x89\x99\x3d\x1d\x00\x00\x00\x00IEND\xaeB`\x82'
            ),
            content_type='image/png',
        )

        with TemporaryDirectory() as media_root:
            storage = FileSystemStorage(location=media_root)
            with patch.object(PreguntaImagen._meta.get_field('archivo'), 'storage', storage):
                response = self.client.post(
                    reverse('evaluaciones_residentes:crear_pregunta', args=[self.examen.pk]),
                    data={**datos, 'imagenes': [imagen]},
                )

        self.assertEqual(response.status_code, 302, response.context)
        pregunta = self.examen.preguntas.get()
        self.assertEqual(pregunta.imagenes.count(), 1)

    def test_docente_puede_reordenar_imagenes_guardadas(self):
        self.client.force_login(self.docente)
        pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Pregunta con imágenes',
            orden=1,
        )
        Opcion.objects.create(pregunta=pregunta, texto='Correcta', orden=1, es_correcta=True)
        Opcion.objects.create(pregunta=pregunta, texto='Incorrecta', orden=2)
        primera = PreguntaImagen.objects.create(
            pregunta=pregunta,
            archivo='preguntas/galeria/primera.jpg',
            orden=1,
        )
        segunda = PreguntaImagen.objects.create(
            pregunta=pregunta,
            archivo='preguntas/galeria/segunda.jpg',
            orden=2,
        )

        datos = {
            'texto': pregunta.texto,
            'orden': '1',
            'puntaje': '1.00',
            'tipo': 'OPCION_UNICA',
            'opciones-TOTAL_FORMS': '2',
            'opciones-INITIAL_FORMS': '2',
            'opciones-MIN_NUM_FORMS': '0',
            'opciones-MAX_NUM_FORMS': '1000',
            'opciones-0-id': str(pregunta.opciones.order_by('orden')[0].pk),
            'opciones-0-pregunta': str(pregunta.pk),
            'opciones-0-texto': 'Correcta',
            'opciones-0-orden': '1',
            'opciones-0-es_correcta': 'on',
            'opciones-1-id': str(pregunta.opciones.order_by('orden')[1].pk),
            'opciones-1-pregunta': str(pregunta.pk),
            'opciones-1-texto': 'Incorrecta',
            'opciones-1-orden': '2',
            f'orden_imagen_{primera.pk}': '2',
            f'orden_imagen_{segunda.pk}': '1',
        }

        response = self.client.post(
            reverse('evaluaciones_residentes:editar_pregunta', args=[self.examen.pk, pregunta.pk]),
            datos,
        )

        self.assertEqual(response.status_code, 302)
        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(primera.orden, 2)
        self.assertEqual(segunda.orden, 1)

    def test_desarrollo_elimina_opciones_existentes_sin_error_de_formset(self):
        self.client.force_login(self.docente)
        pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Pregunta de desarrollo',
            orden=1,
            tipo=Pregunta.OPCION_UNICA,
        )
        Opcion.objects.create(pregunta=pregunta, texto='Opción A', orden=1, es_correcta=True)
        Opcion.objects.create(pregunta=pregunta, texto='Opción B', orden=2)

        response = self.client.post(
            reverse('evaluaciones_residentes:editar_pregunta', args=[self.examen.pk, pregunta.pk]),
            {
                'texto': pregunta.texto,
                'orden': '1',
                'puntaje': '2.00',
                'tipo': 'DESARROLLO',
                'opciones-TOTAL_FORMS': '2',
                'opciones-INITIAL_FORMS': '2',
                'opciones-MIN_NUM_FORMS': '0',
                'opciones-MAX_NUM_FORMS': '1000',
            },
        )

        self.assertEqual(response.status_code, 302)
        pregunta.refresh_from_db()
        self.assertEqual(pregunta.tipo, Pregunta.DESARROLLO)
        self.assertEqual(pregunta.opciones.count(), 0)
