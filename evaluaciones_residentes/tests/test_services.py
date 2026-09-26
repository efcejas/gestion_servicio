from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from evaluaciones_residentes.exceptions import (
    EvaluacionNoDisponibleError,
    RespuestasInvalidasError,
    TransicionEvaluacionError,
)
from evaluaciones_residentes.models import (
    DestinatarioExamen,
    Examen,
    IntentoExamen,
    Opcion,
    Pregunta,
)
from evaluaciones_residentes.services import (
    cerrar_examenes_vencidos,
    corregir_respuesta_desarrollo,
    entregar_intento,
    anular_intento,
    finalizar_correccion_manual,
    finalizar_examen,
    iniciar_examen_manual,
    iniciar_intento,
    publicar_examen,
    publicar_resultado,
    recuperar_intento,
)


class EvaluacionServicesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.docente = user_model.objects.create_user(
            username='docente',
            rol='instructor_residentes',
        )
        self.residente = user_model.objects.create_user(
            username='residente',
            rol='medico_residente',
            anio_residencia='R1',
            estado_residencia='ACTIVO',
        )
        ahora = timezone.now()
        self.examen = Examen.objects.create(
            titulo='Evaluacion de anatomia',
            creador=self.docente,
            ciclo_lectivo='2026',
            modo_destinatarios=Examen.ANIOS,
            anios_destinatarios=['R1'],
            fecha_apertura=ahora - timedelta(minutes=5),
            fecha_vencimiento=ahora + timedelta(hours=1),
        )
        self.pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Pregunta 1',
            orden=1,
            puntaje=Decimal('2.00'),
        )
        self.correcta = Opcion.objects.create(
            pregunta=self.pregunta,
            texto='Correcta',
            orden=1,
            es_correcta=True,
        )
        self.incorrecta = Opcion.objects.create(
            pregunta=self.pregunta,
            texto='Incorrecta',
            orden=2,
        )

    def test_publicar_examen_valida_y_cambia_estado(self):
        self.examen = publicar_examen(self.examen, self.docente)

        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado, Examen.PUBLICADO)
        self.assertIsNotNone(self.examen.fecha_publicacion)

    def test_publicar_examen_congela_preguntas_y_opciones(self):
        self.examen = publicar_examen(self.examen, self.docente)

        self.pregunta.texto = 'Texto cambiado'
        with self.assertRaises(ValidationError):
            self.pregunta.save()

        self.incorrecta.texto = 'Opcion cambiada'
        with self.assertRaises(ValidationError):
            self.incorrecta.save()

    def test_no_publica_examen_sin_preguntas_validas(self):
        self.pregunta.opciones.all().delete()

        with self.assertRaises(TransicionEvaluacionError):
            publicar_examen(self.examen, self.docente)

    def test_cerrar_examenes_vencidos_marca_publicados_vencidos(self):
        self.examen = publicar_examen(self.examen, self.docente)
        ahora = timezone.now()
        self.examen.fecha_vencimiento = ahora - timedelta(minutes=1)
        self.examen.save(update_fields=['fecha_vencimiento'])

        cerrados = cerrar_examenes_vencidos(ahora=ahora)

        self.assertEqual(cerrados, 1)
        self.examen.refresh_from_db()
        self.assertEqual(self.examen.estado, Examen.CERRADO)
        self.assertEqual(self.examen.fecha_cierre, ahora)

    def test_iniciar_y_finalizar_examen_manual(self):
        self.examen.modo_inicio = Examen.INICIO_MANUAL
        self.examen.save(update_fields=['modo_inicio'])
        self.examen = publicar_examen(self.examen, self.docente)

        self.examen = iniciar_examen_manual(self.examen, self.docente)
        self.assertIsNotNone(self.examen.iniciado_en)

        self.examen = finalizar_examen(self.examen, self.docente)
        self.assertEqual(self.examen.estado, Examen.CERRADO)
        self.assertIsNotNone(self.examen.fecha_cierre)

    def test_anular_intento_registra_motivo_usuario_y_fecha_sin_borrar_respuestas(self):
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)
        intento = entregar_intento(intento, {str(self.pregunta.pk): self.correcta.pk})
        motivo = 'Se detectó un problema técnico durante la evaluación.'

        intento = anular_intento(intento, self.docente, motivo)

        intento.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.ANULADO)
        self.assertEqual(intento.motivo_anulacion, motivo)
        self.assertEqual(intento.anulado_por_id, self.docente.pk)
        self.assertIsNotNone(intento.anulado_en)
        self.assertIsNone(intento.resultado_publicado_en)
        self.assertTrue(intento.respuestas.exists())

    def test_no_se_puede_anular_sin_motivo(self):
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)

        with self.assertRaises(RespuestasInvalidasError):
            anular_intento(intento, self.docente, '   ')

    def test_recuperar_intento_anulado_reabre_el_mismo_intento_y_audita(self):
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)
        intento = anular_intento(intento, self.docente, 'Falla técnica durante la entrega.')

        motivo = 'Se restablece el acceso por autorización de jefatura.'
        intento = recuperar_intento(intento, self.docente, motivo)

        intento.refresh_from_db()
        self.assertEqual(intento.estado, IntentoExamen.INICIADO)
        self.assertEqual(intento.motivo_recuperacion, motivo)
        self.assertEqual(intento.recuperado_por_id, self.docente.pk)
        self.assertIsNotNone(intento.recuperado_en)

    def test_no_se_puede_recuperar_si_el_examen_esta_cerrado(self):
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)
        intento = anular_intento(intento, self.docente, 'Falla técnica durante la entrega.')
        self.examen.estado = Examen.CERRADO
        self.examen.save(update_fields=['estado'])

        with self.assertRaises(EvaluacionNoDisponibleError):
            recuperar_intento(intento, self.docente, 'Autorización excepcional suficiente.')

    def test_entregar_intento_calcula_puntaje_porcentaje_y_nota(self):
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)

        intento = entregar_intento(
            intento,
            {str(self.pregunta.pk): self.correcta.pk},
        )

        self.assertEqual(intento.estado, IntentoExamen.CORREGIDO)
        self.assertEqual(intento.puntaje_obtenido, Decimal('2.00'))
        self.assertEqual(intento.porcentaje, Decimal('100.00'))
        self.assertEqual(intento.nota_final, Decimal('10.00'))
        self.assertTrue(intento.respuestas.get().es_correcta)

    def test_no_se_puede_iniciar_despues_del_vencimiento(self):
        self.examen = publicar_examen(self.examen, self.docente)
        ahora = self.examen.fecha_vencimiento

        with self.assertRaises(EvaluacionNoDisponibleError):
            iniciar_intento(self.examen, self.residente, ahora=ahora)

    def test_resultado_no_visible_hasta_publicacion_explicita(self):
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)
        intento = entregar_intento(
            intento,
            {str(self.pregunta.pk): self.incorrecta.pk},
        )

        self.assertIsNone(intento.resultado_publicado_en)
        publicar_resultado(intento, self.docente)
        intento.refresh_from_db()
        self.assertIsNotNone(intento.resultado_publicado_en)

    def test_opcion_multiple_solo_otorga_puntaje_conjunto_completo(self):
        self.pregunta.tipo = Pregunta.OPCION_MULTIPLE
        self.pregunta.save()
        segunda_correcta = Opcion.objects.create(
            pregunta=self.pregunta,
            texto='Tambien correcta',
            orden=3,
            es_correcta=True,
        )
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)

        intento = entregar_intento(
            intento,
            {str(self.pregunta.pk): [self.correcta.pk]},
        )

        self.assertEqual(intento.puntaje_obtenido, Decimal('0'))
        self.assertFalse(intento.respuestas.get().es_correcta)

        self.assertIsNotNone(segunda_correcta.pk)

    def test_desarrollo_queda_pendiente_hasta_correccion_docente(self):
        desarrollo = Pregunta.objects.create(
            examen=self.examen,
            texto='Explique el hallazgo.',
            orden=2,
            puntaje=Decimal('3.00'),
            tipo=Pregunta.DESARROLLO,
        )
        self.examen = publicar_examen(self.examen, self.docente)
        intento = iniciar_intento(self.examen, self.residente)
        intento = entregar_intento(
            intento,
            {
                str(self.pregunta.pk): self.correcta.pk,
                str(desarrollo.pk): 'Respuesta del residente',
            },
        )

        self.assertEqual(intento.estado, IntentoExamen.PENDIENTE_CORRECCION)
        respuesta = intento.respuestas.get(pregunta=desarrollo)
        corregir_respuesta_desarrollo(
            respuesta,
            Decimal('2.00'),
            'Buen razonamiento, falta completar la conclusión.',
            self.docente,
        )
        intento = finalizar_correccion_manual(intento, self.docente)

        self.assertEqual(intento.estado, IntentoExamen.CORREGIDO)
        self.assertEqual(intento.puntaje_obtenido, Decimal('4.00'))
        self.assertEqual(intento.nota_final, Decimal('8.00'))

    def test_publicar_todos_congela_residentes_activos(self):
        r2 = get_user_model().objects.create_user(
            username='residente-r2',
            rol='medico_residente',
            anio_residencia='R2',
            estado_residencia='ACTIVO',
        )
        self.examen.modo_destinatarios = Examen.TODOS
        self.examen.anios_destinatarios = []
        self.examen.save(update_fields=['modo_destinatarios', 'anios_destinatarios'])

        self.examen = publicar_examen(self.examen, self.docente)

        asignaciones = DestinatarioExamen.objects.filter(examen=self.examen)
        self.assertEqual(asignaciones.count(), 2)
        self.assertEqual(
            set(asignaciones.values_list('anio_residencia_al_asignar', flat=True)),
            {'R1', 'R2'},
        )
        self.assertTrue(self.examen.esta_disponible_para(self.residente))
        self.assertTrue(self.examen.esta_disponible_para(r2))

    def test_un_r1_que_pasa_a_r2_conserva_su_asignacion_historica(self):
        self.examen = publicar_examen(self.examen, self.docente)
        self.residente.anio_residencia = 'R2'
        self.residente.save(update_fields=['anio_residencia'])

        asignacion = DestinatarioExamen.objects.get(
            examen=self.examen,
            residente=self.residente,
        )
        self.assertEqual(asignacion.anio_residencia_al_asignar, 'R1')
        self.assertEqual(asignacion.ciclo_lectivo, '2026')
        self.assertTrue(self.examen.esta_disponible_para(self.residente))
