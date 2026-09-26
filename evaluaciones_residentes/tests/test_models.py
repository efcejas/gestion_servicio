from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from evaluaciones_residentes.models import (
    Examen,
    IntentoExamen,
    Opcion,
    Pregunta,
    Respuesta,
    RespuestaOpcion,
    DestinatarioExamen,
    PreguntaImagen,
)


class ExamenModelTests(TestCase):
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
        self.residente_inactivo = user_model.objects.create_user(
            username='egresado',
            rol='medico_residente',
            anio_residencia='R1',
            estado_residencia='EGRESADO',
        )
        ahora = timezone.now()
        self.examen = Examen.objects.create(
            titulo='Evaluacion R1',
            creador=self.docente,
            ciclo_lectivo='2026',
            modo_destinatarios=Examen.ANIOS,
            anios_destinatarios=['R1'],
            estado=Examen.PUBLICADO,
            fecha_apertura=ahora - timedelta(minutes=5),
            fecha_vencimiento=ahora + timedelta(hours=1),
        )
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
            anio_residencia_al_asignar='R1',
            ciclo_lectivo='2026',
            criterio_origen=Examen.ANIOS,
        )

    def test_examen_disponible_solo_para_residente_activo_destinatario(self):
        self.assertTrue(self.examen.esta_disponible_para(self.residente))
        self.assertFalse(self.examen.esta_disponible_para(self.residente_inactivo))

    def test_examen_manual_requiere_inicio_docente(self):
        self.examen.modo_inicio = Examen.INICIO_MANUAL
        self.examen.iniciado_en = None
        self.examen.save(update_fields=['modo_inicio', 'iniciado_en'])

        self.assertFalse(self.examen.esta_disponible_para(self.residente))

        self.examen.iniciado_en = timezone.now()
        self.examen.save(update_fields=['iniciado_en'])
        self.assertTrue(self.examen.esta_disponible_para(self.residente))

    def test_residente_individual_puede_ser_destinatario(self):
        otro = get_user_model().objects.create_user(
            username='residente-r2',
            rol='medico_residente',
            anio_residencia='R2',
            estado_residencia='ACTIVO',
        )
        self.examen.anios_destinatarios = []
        self.examen.save(update_fields=['anios_destinatarios'])
        self.examen.destinatarios_asignados.all().delete()
        self.examen.residentes_destinatarios.add(otro)
        DestinatarioExamen.objects.create(
            examen=self.examen,
            residente=otro,
            anio_residencia_al_asignar='R2',
            ciclo_lectivo='2026',
            criterio_origen=Examen.RESIDENTES,
        )

        self.assertFalse(self.examen.esta_disponible_para(self.residente))
        self.assertTrue(self.examen.esta_disponible_para(otro))

    def test_no_se_puede_validar_vencimiento_anterior_a_apertura(self):
        ahora = timezone.now()
        examen = Examen(
            titulo='Fechas invalidas',
            creador=self.docente,
            ciclo_lectivo='2026',
            fecha_apertura=ahora,
            fecha_vencimiento=ahora,
        )

        with self.assertRaises(ValidationError):
            examen.full_clean()


class IntentoYRespuestaModelTests(TestCase):
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
            titulo='Evaluacion',
            creador=self.docente,
            ciclo_lectivo='2026',
            modo_destinatarios=Examen.ANIOS,
            fecha_apertura=ahora - timedelta(minutes=5),
            fecha_vencimiento=ahora + timedelta(hours=1),
        )
        self.pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Pregunta 1',
            orden=1,
            puntaje=Decimal('2.00'),
        )
        self.opcion_correcta = Opcion.objects.create(
            pregunta=self.pregunta,
            texto='Correcta',
            orden=1,
            es_correcta=True,
        )
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])

    def test_no_se_permiten_dos_intentos_para_el_mismo_residente(self):
        IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

        with self.assertRaises(IntegrityError):
            IntentoExamen.objects.create(examen=self.examen, residente=self.residente)

    def test_respuesta_debe_pertenecer_a_la_pregunta_del_intento(self):
        otro_examen = Examen.objects.create(
            titulo='Otro examen',
            creador=self.docente,
            ciclo_lectivo='2026',
            fecha_apertura=timezone.now(),
            fecha_vencimiento=timezone.now() + timedelta(hours=1),
        )
        otra_pregunta = Pregunta.objects.create(
            examen=otro_examen,
            texto='Otra pregunta',
            orden=1,
        )
        intento = IntentoExamen.objects.create(
            examen=self.examen,
            residente=self.residente,
        )
        respuesta = Respuesta(
            intento=intento,
            pregunta=otra_pregunta,
        )

        with self.assertRaises(ValidationError):
            respuesta.full_clean()

    def test_respuesta_opcion_debe_pertenecer_a_la_pregunta(self):
        self.examen.estado = Examen.BORRADOR
        self.examen.save(update_fields=['estado'])
        respuesta = Respuesta.objects.create(
            intento=IntentoExamen.objects.create(
                examen=self.examen,
                residente=self.residente,
            ),
            pregunta=self.pregunta,
        )
        otra_pregunta = Pregunta.objects.create(
            examen=self.examen,
            texto='Pregunta 2',
            orden=2,
        )
        otra_opcion = Opcion.objects.create(
            pregunta=otra_pregunta,
            texto='Opción ajena',
            orden=1,
        )
        vinculacion = RespuestaOpcion(respuesta=respuesta, opcion=otra_opcion)

        with self.assertRaises(ValidationError):
            vinculacion.full_clean()

    def test_pregunta_multiple_puede_tener_varias_opciones_correctas(self):
        self.examen.estado = Examen.BORRADOR
        self.examen.save(update_fields=['estado'])
        self.pregunta.tipo = Pregunta.OPCION_MULTIPLE
        self.pregunta.save()

        Opcion.objects.create(
            pregunta=self.pregunta,
            texto='Otra correcta',
            orden=2,
            es_correcta=True,
        )

        self.assertEqual(self.pregunta.opciones.filter(es_correcta=True).count(), 2)

    def test_opcion_unica_no_requiere_restriccion_de_bd_para_correctas(self):
        self.examen.estado = Examen.BORRADOR
        self.examen.save(update_fields=['estado'])

        segunda = Opcion.objects.create(
            pregunta=self.pregunta,
            texto='Tambien correcta',
            orden=2,
            es_correcta=True,
        )

        self.assertTrue(segunda.es_correcta)

    def test_imagen_de_pregunta_publicada_queda_congelada(self):
        self.examen.estado = Examen.BORRADOR
        self.examen.save(update_fields=['estado'])
        imagen = PreguntaImagen.objects.create(
            pregunta=self.pregunta,
            archivo='preguntas/galeria/imagen.jpg',
            orden=1,
        )
        self.examen.estado = Examen.PUBLICADO
        self.examen.save(update_fields=['estado'])

        imagen.texto_alternativo = 'Cambio no permitido'
        with self.assertRaises(ValidationError):
            imagen.save()

        with self.assertRaises(ValidationError):
            imagen.delete()
