from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import (
    AplicacionPlantillaPreinforme,
    PlantillaPreinforme,
    Preinforme,
    PropuestaPlantillaPreinforme,
    Region,
    TipoEstudio,
    VersionPlantillaPreinforme,
)


User = get_user_model()


class PlantillasInstitucionalesBaseTest(TestCase):
    def setUp(self):
        self.tipo_estudio = TipoEstudio.objects.create(nombre='Resonancia magnética')
        self.region = Region.objects.create(nombre='Miembro superior')
        self.residente = User.objects.create_user(
            username='residente_plantillas',
            password='test',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_plantillas',
            password='test',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.jefe = User.objects.create_user(
            username='jefe_plantillas',
            password='test',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.administrativo = User.objects.create_user(
            username='administrativo_plantillas',
            password='test',
            rol='administrativo',
            perfil_completo=True,
        )

    def crear_propuesta(self, **kwargs):
        datos = {
            'autor': self.residente,
            'tipo_estudio': self.tipo_estudio,
            'region': self.region,
            'estudio_especifico': 'Muñeca',
            'titulo': 'RESONANCIA MAGNÉTICA DE MUÑECA',
            'encabezado': 'Se exploró la muñeca en los diferentes planos.',
            'hallazgos': 'Estructuras óseas y tendinosas sin alteraciones.',
            'variables': [
                {
                    'codigo': 'lateralidad',
                    'tipo': 'opcion',
                    'requerida': True,
                    'opciones': ['derecha', 'izquierda', 'bilateral'],
                }
            ],
        }
        datos.update(kwargs)
        return PropuestaPlantillaPreinforme.objects.create(**datos)


class PermisosPropuestaPlantillaTest(PlantillasInstitucionalesBaseTest):
    def test_solo_perfiles_medicos_pueden_generar(self):
        self.assertTrue(PropuestaPlantillaPreinforme.usuario_puede_generar(self.residente))
        self.assertTrue(PropuestaPlantillaPreinforme.usuario_puede_generar(self.staff))
        self.assertTrue(PropuestaPlantillaPreinforme.usuario_puede_generar(self.jefe))
        self.assertFalse(
            PropuestaPlantillaPreinforme.usuario_puede_generar(self.administrativo)
        )

    def test_residente_egresado_no_puede_generar(self):
        self.residente.estado_residencia = 'EGRESADO'
        self.residente.save(update_fields=['estado_residencia'])

        self.assertFalse(
            PropuestaPlantillaPreinforme.usuario_puede_generar(self.residente)
        )

    def test_solo_jefe_o_superusuario_pueden_validar(self):
        superusuario = User.objects.create_superuser(
            username='super_plantillas',
            password='test',
        )

        self.assertTrue(PropuestaPlantillaPreinforme.usuario_puede_validar(self.jefe))
        self.assertTrue(PropuestaPlantillaPreinforme.usuario_puede_validar(superusuario))
        self.assertFalse(PropuestaPlantillaPreinforme.usuario_puede_validar(self.staff))
        self.assertFalse(
            PropuestaPlantillaPreinforme.usuario_puede_validar(self.residente)
        )


class FlujoPropuestaPlantillaTest(PlantillasInstitucionalesBaseTest):
    def test_flujo_aprobacion_registra_fechas_y_revisor(self):
        propuesta = self.crear_propuesta()

        propuesta.enviar_a_revision()
        self.assertEqual(propuesta.estado, propuesta.ESTADO_PENDIENTE)
        self.assertIsNotNone(propuesta.fecha_envio_revision)

        propuesta.iniciar_revision(self.jefe)
        self.assertEqual(propuesta.estado, propuesta.ESTADO_EN_REVISION)
        self.assertEqual(propuesta.revisor, self.jefe)
        self.assertIsNotNone(propuesta.fecha_inicio_revision)

        propuesta.aprobar(self.jefe, 'Adecuada para el servicio.')
        self.assertEqual(propuesta.estado, propuesta.ESTADO_APROBADA)
        self.assertEqual(propuesta.observacion_revision, 'Adecuada para el servicio.')
        self.assertIsNotNone(propuesta.fecha_resolucion)

    def test_staff_no_puede_aprobar(self):
        propuesta = self.crear_propuesta()
        propuesta.enviar_a_revision()

        with self.assertRaises(ValidationError):
            propuesta.aprobar(self.staff)

    def test_rechazo_exige_observacion(self):
        propuesta = self.crear_propuesta()
        propuesta.enviar_a_revision()

        with self.assertRaises(ValidationError):
            propuesta.rechazar(self.jefe, '')

    def test_modificacion_exige_plantilla_base(self):
        propuesta = self.crear_propuesta(
            tipo_solicitud=PropuestaPlantillaPreinforme.TIPO_MODIFICACION,
        )

        with self.assertRaises(ValidationError):
            propuesta.full_clean()


class VersionPlantillaTest(PlantillasInstitucionalesBaseTest):
    def setUp(self):
        super().setUp()
        self.plantilla = PlantillaPreinforme.objects.create(
            nombre='RM de muñeca',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            estado='publica',
            contenido='<p>Contenido compatible</p>',
            creada_por=self.jefe,
        )

    def crear_version(self, numero=1, vigente=True):
        return VersionPlantillaPreinforme.objects.create(
            plantilla=self.plantilla,
            numero=numero,
            titulo='RESONANCIA MAGNÉTICA DE MUÑECA',
            encabezado='Técnica base.',
            hallazgos='Hallazgos base.',
            variables=[],
            fuentes=[],
            vigente=vigente,
            aprobada_por=self.jefe,
        )

    def test_una_sola_version_puede_estar_vigente(self):
        self.crear_version()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.crear_version(numero=2)

    def test_aprobador_debe_ser_jefe_o_superusuario(self):
        version = VersionPlantillaPreinforme(
            plantilla=self.plantilla,
            numero=1,
            titulo='Título',
            encabezado='Encabezado',
            hallazgos='Hallazgos',
            aprobada_por=self.staff,
        )

        with self.assertRaises(ValidationError):
            version.full_clean()


class AplicacionPlantillaTest(PlantillasInstitucionalesBaseTest):
    def setUp(self):
        super().setUp()
        self.preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='RM-001',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente='Prueba',
        )
        self.propuesta = self.crear_propuesta()

    def test_contraste_ev_exige_volumen(self):
        aplicacion = AplicacionPlantillaPreinforme(
            preinforme=self.preinforme,
            propuesta=self.propuesta,
            contraste_ev=True,
            contenido_renderizado='<p>Informe renderizado</p>',
            aplicada_por=self.residente,
        )

        with self.assertRaises(ValidationError):
            aplicacion.full_clean()

        aplicacion.volumen_contraste_ml = Decimal('80.00')
        aplicacion.marca_contraste = 'Otro'
        aplicacion.full_clean()

    def test_aplicacion_conserva_snapshot_renderizado(self):
        aplicacion = AplicacionPlantillaPreinforme.objects.create(
            preinforme=self.preinforme,
            propuesta=self.propuesta,
            valores_variables={'lateralidad': 'derecha'},
            lateralidad='derecha',
            contraste_ev=False,
            contenido_renderizado='<p>RM DE MUÑECA DERECHA</p>',
            aplicada_por=self.residente,
        )

        self.propuesta.titulo = 'Título modificado posteriormente'
        self.propuesta.save(update_fields=['titulo'])
        aplicacion.refresh_from_db()

        self.assertEqual(
            aplicacion.contenido_renderizado,
            '<p>RM DE MUÑECA DERECHA</p>',
        )
