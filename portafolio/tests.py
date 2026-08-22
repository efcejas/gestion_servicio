import hashlib
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from accounts.context_processors import navbar_links
from accounts.models import CustomUser
from clases_residentes.models import ClaseResidente
from control_guardias.models import AsignacionGuardia, ConfiguracionTipoGuardia, Feriado
from liquidacion.models import Estudios, RegistroEstudio, RegistroEstudiosPorMedico
from preinformes.models import Preinforme, Region, TipoEstudio

from .models import ActividadCurricular, DocumentoActividadCurricular
from .selectors import (
    evolucion_actividad,
    fin_datos_exclusivo,
    periodo_ciclo_lectivo,
    periodo_ciclo_lectivo_por_anio,
    resumen_guardias,
)
from .services import construir_resumen_portafolio


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PORTAFOLIO_SOLO_SUPERUSER=False,
)
class PortafolioTests(TestCase):
    def setUp(self):
        self.residente = CustomUser.objects.create_user(
            username='residente_portafolio',
            password='testpass123',
            first_name='Ana',
            last_name='Residente',
            rol='medico_residente',
            perfil_completo=True,
            anio_residencia='R2',
            estado_residencia='ACTIVO',
        )
        self.otro_residente = CustomUser.objects.create_user(
            username='otro_residente_portafolio',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
            anio_residencia='R1',
            estado_residencia='ACTIVO',
        )
        self.instructor = CustomUser.objects.create_user(
            username='instructor_portafolio',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.staff = CustomUser.objects.create_user(
            username='staff_portafolio',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )

    def _crear_actividad(self):
        tipo_guardia = ConfiguracionTipoGuardia.objects.create(
            nombre='Guardia nocturna portafolio',
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0),
            dias_semana='L,M,X,J,V,S,D',
            creado_por=self.instructor,
        )
        fecha_pasada = timezone.localdate() - timedelta(days=2)
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo_guardia,
            fecha=fecha_pasada,
            estado='PUBLICADA',
            creada_por=self.instructor,
        )
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo_guardia,
            fecha=timezone.localdate() + timedelta(days=2),
            estado='PUBLICADA',
            creada_por=self.instructor,
        )
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo_guardia,
            fecha=fecha_pasada - timedelta(days=1),
            estado='REASIGNADA',
            creada_por=self.instructor,
        )

        estudio = Estudios.objects.create(
            codigo='ECO-PORT',
            nombre='Ecografia abdominal portafolio',
            tipo='ECO',
            conteo_regiones=2,
            conteo_regiones_default=2,
            precio_cober=Decimal('9999.99'),
            precio_otras_os=Decimal('9999.99'),
        )
        registro = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='PACIENTE-SECRETO',
            apellido_paciente='APELLIDO-SECRETO',
            dni_paciente='99888777',
            fecha_del_informe=fecha_pasada,
            cantidad_regiones=4,
            monto_calculado=Decimal('9999.99'),
        )
        RegistroEstudio.objects.create(
            registro=registro,
            estudio=estudio,
            cantidad=2,
        )

        tipo_preinforme = TipoEstudio.objects.create(nombre='TC Portafolio')
        region = Region.objects.create(nombre='Torax Portafolio')
        Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='PORT-001',
            tipo_estudio=tipo_preinforme,
            region=region,
            apellido_paciente='PREINFORME-SECRETO',
            nombre_paciente='NOMBRE-SECRETO',
            estado='finalizado',
        )

        ClaseResidente.objects.create(
            titulo='Clase del ciclo',
            categoria='tc',
            anios_dirigidos=['R1', 'R2'],
            autor=self.residente,
            fecha_clase=fecha_pasada,
        )

    def test_resumen_cuenta_solo_guardias_publicadas_con_fecha_transcurrida(self):
        self._crear_actividad()

        resumen = construir_resumen_portafolio(self.residente)

        self.assertEqual(resumen['guardias']['total'], 1)

    def test_resumen_clasifica_guardias_segun_fecha_y_unifica_slots(self):
        periodo = periodo_ciclo_lectivo_por_anio(2025)
        tipo_original = ConfiguracionTipoGuardia.objects.create(
            nombre='Día de semana',
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0),
            dias_semana='L,M,X,J,V',
            creado_por=self.instructor,
        )
        tipo_duplicado = ConfiguracionTipoGuardia.objects.create(
            nombre='Día de semana (2)',
            hora_inicio=time(20, 0),
            hora_fin=time(8, 0),
            dias_semana='L,M,X,J,V',
            creado_por=self.instructor,
        )
        fecha_habil = periodo['inicio']
        for tipo in (tipo_original, tipo_duplicado):
            AsignacionGuardia.objects.create(
                residente=self.residente,
                tipo_guardia=tipo,
                fecha=fecha_habil,
                estado='PUBLICADA',
                creada_por=self.instructor,
            )

        fecha_fin_semana = fecha_habil + timedelta(days=1)
        while fecha_fin_semana.weekday() < 5:
            fecha_fin_semana += timedelta(days=1)
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo_original,
            fecha=fecha_fin_semana,
            estado='PUBLICADA',
            creada_por=self.instructor,
        )

        fecha_feriado = fecha_fin_semana + timedelta(days=1)
        while fecha_feriado.weekday() >= 5:
            fecha_feriado += timedelta(days=1)
        Feriado.objects.create(
            fecha=fecha_feriado,
            descripcion='Feriado para portafolio',
        )
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo_duplicado,
            fecha=fecha_feriado,
            estado='PUBLICADA',
            creada_por=self.instructor,
        )

        resumen = resumen_guardias(
            self.residente,
            periodo,
            hoy=fecha_feriado + timedelta(days=1),
        )

        self.assertEqual(resumen['total'], 4)
        self.assertEqual(
            resumen['por_tipo'],
            [
                {'tipo_guardia__nombre': 'Lunes a viernes', 'cantidad': 2},
                {
                    'tipo_guardia__nombre': 'Sábados, domingos y feriados',
                    'cantidad': 2,
                },
            ],
        )

    def test_evolucion_mensual_distingue_mes_actual_y_meses_futuros(self):
        periodo = periodo_ciclo_lectivo_por_anio(2025)
        ClaseResidente.objects.create(
            titulo='Clase de agosto',
            categoria='tc',
            anios_dirigidos=['R1'],
            autor=self.residente,
            fecha_clase=date(2025, 8, 5),
        )
        ClaseResidente.objects.create(
            titulo='Clase de octubre',
            categoria='rm',
            anios_dirigidos=['R2'],
            autor=self.residente,
            fecha_clase=date(2025, 10, 10),
        )

        evolucion = evolucion_actividad(
            self.residente,
            periodo,
            hoy=date(2025, 10, 15),
        )
        clases = next(
            serie for serie in evolucion['series'] if serie['clave'] == 'clases'
        )

        self.assertEqual(evolucion['mes_actual'], 2)
        self.assertEqual(clases['mensual'][:3], [1, 0, 1])
        self.assertEqual(clases['acumulada'][:3], [1, 1, 2])
        self.assertTrue(all(valor is None for valor in clases['mensual'][3:]))
        self.assertTrue(all(valor is None for valor in clases['acumulada'][3:]))

    def test_evolucion_coincide_con_totales_y_se_renderiza(self):
        self._crear_actividad()
        resumen = construir_resumen_portafolio(self.residente)
        series = {
            serie['clave']: serie for serie in resumen['evolucion']['series']
        }

        def total_registrado(clave):
            return sum(
                valor
                for valor in series[clave]['mensual']
                if valor is not None
            )

        self.assertEqual(
            total_registrado('estudios'),
            resumen['estudios']['total_practicas'],
        )
        self.assertEqual(
            total_registrado('preinformes'),
            resumen['preinformes']['total'],
        )
        self.assertEqual(total_registrado('guardias'), resumen['guardias']['total'])
        self.assertEqual(total_registrado('clases'), resumen['clases']['total'])

        self.client.login(username=self.instructor.username, password='testpass123')
        response = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Evolución de la actividad')
        self.assertContains(response, 'portafolio-evolucion-chart')
        self.assertContains(response, 'data-evolucion-modo="acumulada"')

    def test_dashboard_renderiza_distribuciones_y_valores_exactos(self):
        self._crear_actividad()
        self.client.login(username=self.instructor.username, password='testpass123')

        response = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'portafolio-modalidades-chart')
        self.assertContains(response, 'portafolio-guardias-chart')
        self.assertContains(response, 'portafolio-modalidades-data')
        self.assertContains(response, 'portafolio-guardias-data')
        self.assertContains(response, 'Ver valores exactos', count=2)
        self.assertContains(response, 'portafolio-practicas-chart')
        self.assertContains(response, 'portafolio-preinformes-chart')
        self.assertContains(response, 'portafolio-practicas-data')
        self.assertContains(response, 'portafolio-preinformes-data')
        self.assertContains(response, 'Ver detalle completo', count=2)
        self.assertContains(response, 'Ecografía')
        self.assertContains(response, 'Lunes a viernes')
        self.assertContains(response, 'Sábados, domingos y feriados')

    def test_resumen_liquidacion_expone_cantidades_sin_paciente_ni_montos(self):
        self._crear_actividad()

        resumen = construir_resumen_portafolio(self.residente)
        estudios = resumen['estudios']

        self.assertEqual(estudios['total_registros'], 1)
        self.assertEqual(estudios['total_practicas'], 2)
        self.assertEqual(estudios['total_regiones'], 4)
        self.assertEqual(estudios['practicas_asociadas'][0]['estudio__nombre'], 'Ecografia abdominal portafolio')
        serializado = str(estudios)
        self.assertNotIn('PACIENTE-SECRETO', serializado)
        self.assertNotIn('99888777', serializado)
        self.assertNotIn('9999.99', serializado)
        self.assertNotIn('monto_calculado', serializado)

    def test_dashboard_personal_no_renderiza_datos_sensibles(self):
        self._crear_actividad()
        self.client.login(username=self.residente.username, password='testpass123')

        response = self.client.get(reverse('portafolio:mi_portafolio'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ecografia abdominal portafolio')
        self.assertNotContains(response, 'PACIENTE-SECRETO')
        self.assertNotContains(response, 'PREINFORME-SECRETO')
        self.assertNotContains(response, '99888777')
        self.assertNotContains(response, '9999.99')

    def test_dashboard_lista_clases_con_enlace_y_miniatura_disponible(self):
        periodo = periodo_ciclo_lectivo()
        clase = ClaseResidente.objects.create(
            titulo='Clase ilustrada del portafolio',
            categoria='patologia',
            anios_dirigidos=['R1', 'R2'],
            autor=self.residente,
            fecha_clase=periodo['inicio'],
            archivo_thumbnail='image/upload/portafolio/clase-ilustrada.jpg',
        )
        self.client.login(username=self.instructor.username, password='testpass123')

        response = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, clase.titulo)
        self.assertContains(response, clase.get_categoria_display())
        self.assertContains(response, clase.fecha_clase.strftime('%d/%m/%Y'))
        self.assertContains(
            response,
            reverse('clases_residentes:detalle', args=[clase.pk]),
        )
        self.assertContains(response, f'Miniatura de {clase.titulo}')

    def test_superusuario_puede_abrir_clase_desde_el_portafolio(self):
        clase = ClaseResidente.objects.create(
            titulo='Clase accesible para superusuario',
            categoria='revision',
            anios_dirigidos=['R1'],
            autor=self.residente,
            fecha_clase=timezone.localdate(),
        )
        superusuario = CustomUser.objects.create_user(
            username='superusuario_portafolio',
            password='testpass123',
            is_staff=True,
            is_superuser=True,
            perfil_completo=True,
        )
        self.client.login(username=superusuario.username, password='testpass123')

        response = self.client.get(
            reverse('clases_residentes:detalle', args=[clase.pk])
        )

        self.assertEqual(response.status_code, 200)

    def test_dashboard_no_confunde_residente_sin_anio_con_egresado(self):
        self.residente.anio_residencia = None
        self.residente.estado_residencia = 'ACTIVO'
        self.residente.save(update_fields=['anio_residencia', 'estado_residencia'])
        self.client.login(username=self.residente.username, password='testpass123')

        response = self.client.get(reverse('portafolio:mi_portafolio'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Médico residente · Año no informado')
        self.assertNotContains(response, 'Egresado')

    def test_residente_no_puede_ver_portafolio_ajeno(self):
        self.client.login(username=self.residente.username, password='testpass123')

        response = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.otro_residente.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_instructor_puede_ver_todos_y_abrir_detalle(self):
        self.client.login(username=self.instructor.username, password='testpass123')

        listado = self.client.get(reverse('portafolio:seguimiento'))
        detalle = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )

        self.assertEqual(listado.status_code, 200)
        self.assertContains(listado, self.residente.get_full_name())
        self.assertContains(listado, self.otro_residente.username)
        self.assertEqual(detalle.status_code, 200)

    def test_jefe_residentes_puede_ver_seguimiento_y_detalle(self):
        jefe_residentes = CustomUser.objects.create_user(
            username='jefe_residentes_portafolio',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.client.login(
            username=jefe_residentes.username,
            password='testpass123',
        )

        listado = self.client.get(reverse('portafolio:seguimiento'))
        detalle = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )

        self.assertEqual(listado.status_code, 200)
        self.assertEqual(detalle.status_code, 200)

    def test_staff_sin_rol_docente_no_puede_ver_seguimiento(self):
        self.client.login(username=self.staff.username, password='testpass123')

        response = self.client.get(reverse('portafolio:seguimiento'))

        self.assertEqual(response.status_code, 403)

    def test_administrativo_docencia_no_puede_ver_seguimiento(self):
        grupo = Group.objects.create(name='Administrativo - Docencia')
        administrativo = CustomUser.objects.create_user(
            username='administrativo_portafolio',
            password='testpass123',
            rol='administrativo',
            perfil_completo=True,
        )
        administrativo.groups.add(grupo)
        self.client.login(username=administrativo.username, password='testpass123')

        listado = self.client.get(reverse('portafolio:seguimiento'))
        detalle = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )

        self.assertEqual(listado.status_code, 403)
        self.assertEqual(detalle.status_code, 403)

    def test_jefe_servicio_sin_superusuario_no_puede_ver_seguimiento(self):
        jefe_servicio = CustomUser.objects.create_user(
            username='jefe_servicio_portafolio',
            password='testpass123',
            rol='jefe_servicio',
            perfil_completo=True,
        )
        self.client.login(
            username=jefe_servicio.username,
            password='testpass123',
        )

        response = self.client.get(reverse('portafolio:seguimiento'))

        self.assertEqual(response.status_code, 403)

    def test_navbar_expone_portafolio_solo_a_roles_de_la_etapa(self):
        request_factory = RequestFactory()
        jefe_residentes = CustomUser.objects.create_user(
            username='jefe_navbar_portafolio',
            password='testpass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        usuarios = {
            'residente': self.residente,
            'instructor': self.instructor,
            'jefe_residentes': jefe_residentes,
            'staff': self.staff,
        }
        labels_por_usuario = {}
        for nombre, usuario in usuarios.items():
            request = request_factory.get('/')
            request.user = usuario
            request.resolver_match = resolve('/')
            labels_por_usuario[nombre] = {
                item['label']
                for grupo in navbar_links(request)['nav_groups']
                for item in grupo['items']
            }

        self.assertIn('Mi portafolio', labels_por_usuario['residente'])
        self.assertIn('Mis actividades', labels_por_usuario['residente'])
        self.assertIn(
            'Seguimiento de residentes',
            labels_por_usuario['instructor'],
        )
        self.assertIn(
            'Actividades por revisar',
            labels_por_usuario['instructor'],
        )
        self.assertIn(
            'Seguimiento de residentes',
            labels_por_usuario['jefe_residentes'],
        )
        self.assertIn(
            'Actividades por revisar',
            labels_por_usuario['jefe_residentes'],
        )
        self.assertNotIn(
            'Seguimiento de residentes',
            labels_por_usuario['staff'],
        )
        self.assertNotIn('Actividades por revisar', labels_por_usuario['staff'])

    def test_docente_consulta_ciclo_anterior_y_trayectoria_acumulada(self):
        periodo_actual = periodo_ciclo_lectivo()
        periodo_anterior = periodo_ciclo_lectivo_por_anio(
            periodo_actual['anio_inicio'] - 1
        )
        self.residente.fecha_ingreso_residencia = periodo_anterior['inicio']
        self.residente.save(update_fields=['fecha_ingreso_residencia'])

        estudio = Estudios.objects.create(
            codigo='ECO-HIST-PORT',
            nombre='Ecografia historica portafolio',
            tipo='ECO',
            conteo_regiones=1,
            conteo_regiones_default=1,
            precio_cober=Decimal('9999.99'),
            precio_otras_os=Decimal('9999.99'),
        )
        registro_anterior = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='PACIENTE-HISTORICO',
            apellido_paciente='PRIVADO',
            dni_paciente='11111111',
            fecha_del_informe=periodo_anterior['fin_inclusivo'],
            cantidad_regiones=2,
            monto_calculado=Decimal('9999.99'),
        )
        RegistroEstudio.objects.create(
            registro=registro_anterior,
            estudio=estudio,
            cantidad=2,
        )
        registro_actual = RegistroEstudiosPorMedico.objects.create(
            medico=self.residente,
            nombre_paciente='PACIENTE-ACTUAL',
            apellido_paciente='PRIVADO',
            dni_paciente='22222222',
            fecha_del_informe=timezone.localdate(),
            cantidad_regiones=3,
            monto_calculado=Decimal('9999.99'),
        )
        RegistroEstudio.objects.create(
            registro=registro_actual,
            estudio=estudio,
            cantidad=3,
        )
        self.client.login(username=self.instructor.username, password='testpass123')

        detalle = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk]),
            {'ciclo': periodo_anterior['anio_inicio']},
        )
        trayectoria = self.client.get(
            reverse('portafolio:trayectoria_residente', args=[self.residente.pk])
        )

        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(
            detalle.context['resumen']['periodo']['anio_inicio'],
            periodo_anterior['anio_inicio'],
        )
        self.assertEqual(detalle.context['resumen']['estudios']['total_practicas'], 2)
        self.assertEqual(trayectoria.status_code, 200)
        self.assertEqual(trayectoria.context['trayectoria']['acumulado']['estudios'], 5)
        self.assertEqual(len(trayectoria.context['trayectoria']['ciclos']), 2)
        self.assertNotContains(trayectoria, 'PACIENTE-HISTORICO')
        self.assertNotContains(trayectoria, '9999.99')

    def test_ciclo_fuera_de_la_trayectoria_devuelve_404(self):
        self.client.login(username=self.instructor.username, password='testpass123')

        response = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk]),
            {'ciclo': 1900},
        )

        self.assertEqual(response.status_code, 404)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PORTAFOLIO_SOLO_SUPERUSER=False,
)
class ActividadCurricularTests(TestCase):
    def setUp(self):
        self.residente = CustomUser.objects.create_user(
            username='residente_actividad',
            password='testpass123',
            first_name='Ana',
            last_name='Actividad',
            rol='medico_residente',
            perfil_completo=True,
            anio_residencia='R2',
            estado_residencia='ACTIVO',
        )
        self.otro_residente = CustomUser.objects.create_user(
            username='otro_residente_actividad',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
            anio_residencia='R1',
            estado_residencia='ACTIVO',
        )
        self.instructor = CustomUser.objects.create_user(
            username='instructor_actividad',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.staff = CustomUser.objects.create_user(
            username='staff_actividad',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )

    def _crear_actividad(self, estado='BORRADOR', **kwargs):
        datos = {
            'residente': self.residente,
            'tipo': 'CURSO',
            'titulo': 'Curso de imágenes abdominales',
            'institucion': 'Institución de prueba',
            'fecha_inicio': timezone.localdate(),
            'estado': estado,
        }
        datos.update(kwargs)
        return ActividadCurricular.objects.create(**datos)

    def test_modelo_rechaza_fecha_fin_anterior_al_inicio(self):
        actividad = self._crear_actividad(
            fecha_inicio=date(2026, 8, 20),
            fecha_fin=date(2026, 8, 19),
        )

        with self.assertRaises(ValidationError):
            actividad.full_clean()

    def test_residente_crea_borrador_y_lo_envia(self):
        self.client.login(username=self.residente.username, password='testpass123')
        response = self.client.post(
            reverse('portafolio:actividad_crear'),
            {
                'tipo': 'CONGRESO_JORNADA',
                'titulo': 'Jornada de diagnóstico por imágenes',
                'institucion': 'UBA',
                'fecha_inicio': timezone.localdate().isoformat(),
                'fecha_fin': '',
                'descripcion': 'Participación presencial.',
                'enlace': '',
                'accion': 'enviar',
            },
        )

        actividad = ActividadCurricular.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(actividad.residente, self.residente)
        self.assertEqual(actividad.estado, 'ENVIADA')
        self.assertIsNotNone(actividad.enviada_en)

    def test_editar_borrador_precarga_fechas_en_formato_html(self):
        actividad = self._crear_actividad(
            fecha_inicio=date(2026, 8, 20),
            fecha_fin=date(2026, 8, 22),
        )
        self.client.login(username=self.residente.username, password='testpass123')

        response = self.client.get(
            reverse('portafolio:actividad_editar', args=[actividad.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-08-20"')
        self.assertContains(response, 'value="2026-08-22"')

    def test_carga_documento_registra_metadatos_y_hash(self):
        self.client.login(username=self.residente.username, password='testpass123')
        contenido = b'certificado curricular de prueba'
        archivo = SimpleUploadedFile(
            'certificado.pdf',
            contenido,
            content_type='application/pdf',
        )
        storage = DocumentoActividadCurricular._meta.get_field('archivo').storage
        with patch.object(
            storage,
            'save',
            return_value='portafolio/actividades/1/1/certificado.pdf',
        ):
            response = self.client.post(
                reverse('portafolio:actividad_crear'),
                {
                    'tipo': 'CURSO',
                    'titulo': 'Curso con certificado',
                    'institucion': '',
                    'fecha_inicio': timezone.localdate().isoformat(),
                    'fecha_fin': '',
                    'descripcion': '',
                    'enlace': '',
                    'documentos': archivo,
                    'accion': 'guardar',
                },
            )

        documento = DocumentoActividadCurricular.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(documento.nombre_original, 'certificado.pdf')
        self.assertEqual(documento.tipo_mime, 'application/pdf')
        self.assertEqual(documento.tamanio_bytes, len(contenido))
        self.assertEqual(documento.sha256, hashlib.sha256(contenido).hexdigest())

    def test_instructor_valida_y_la_actividad_suma_al_resumen(self):
        actividad = self._crear_actividad(estado='ENVIADA', enviada_en=timezone.now())
        self.client.login(username=self.instructor.username, password='testpass123')

        response = self.client.post(
            reverse('portafolio:actividad_revisar', args=[actividad.pk]),
            {'accion': 'VALIDAR', 'observacion': ''},
        )

        actividad.refresh_from_db()
        resumen = construir_resumen_portafolio(self.residente)
        dashboard = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(actividad.estado, 'VALIDADA')
        self.assertEqual(actividad.revisada_por, self.instructor)
        self.assertEqual(resumen['actividades']['total_validadas'], 1)
        self.assertContains(dashboard, actividad.titulo)

    def test_residente_ve_seguimiento_mientras_espera_revision(self):
        actividad = self._crear_actividad(
            estado='ENVIADA',
            enviada_en=timezone.now(),
        )
        self.client.login(username=self.residente.username, password='testpass123')

        response = self.client.get(
            reverse('portafolio:actividad_detalle', args=[actividad.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pendiente de revisión')
        self.assertContains(response, 'La actividad fue enviada correctamente')
        self.assertNotContains(response, 'Revisión docente')

    def test_observar_requiere_devolucion_docente(self):
        actividad = self._crear_actividad(estado='ENVIADA', enviada_en=timezone.now())
        self.client.login(username=self.instructor.username, password='testpass123')

        response = self.client.post(
            reverse('portafolio:actividad_revisar', args=[actividad.pk]),
            {'accion': 'OBSERVAR', 'observacion': ''},
        )

        actividad.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(actividad.estado, 'ENVIADA')
        self.assertContains(
            response,
            'Indicá qué debe corregir o completar el residente.',
            status_code=400,
        )

    def test_otro_residente_y_staff_no_pueden_ver_actividad(self):
        actividad = self._crear_actividad()
        detalle_url = reverse('portafolio:actividad_detalle', args=[actividad.pk])

        self.client.login(
            username=self.otro_residente.username,
            password='testpass123',
        )
        respuesta_otro = self.client.get(detalle_url)
        self.client.logout()
        self.client.login(username=self.staff.username, password='testpass123')
        respuesta_staff = self.client.get(detalle_url)

        self.assertEqual(respuesta_otro.status_code, 403)
        self.assertEqual(respuesta_staff.status_code, 403)

    def test_descarga_documento_exige_propietario_o_docente(self):
        actividad = self._crear_actividad()
        documento = DocumentoActividadCurricular.objects.create(
            actividad=actividad,
            archivo='portafolio/actividades/certificado.pdf',
            nombre_original='certificado.pdf',
            subido_por=self.residente,
        )
        storage = DocumentoActividadCurricular._meta.get_field('archivo').storage
        url = reverse(
            'portafolio:documento_actividad_descargar',
            args=[documento.pk],
        )

        self.client.login(username=self.residente.username, password='testpass123')
        with patch.object(storage, 'url', return_value='https://s3.example/firmado'):
            respuesta_propietario = self.client.get(url)
        self.client.logout()
        self.client.login(
            username=self.otro_residente.username,
            password='testpass123',
        )
        respuesta_otro = self.client.get(url)

        self.assertRedirects(
            respuesta_propietario,
            'https://s3.example/firmado',
            fetch_redirect_response=False,
        )
        self.assertEqual(respuesta_otro.status_code, 403)

    def test_egresado_conserva_listado_sin_poder_crear(self):
        self.residente.estado_residencia = 'EGRESADO'
        self.residente.save(update_fields=['estado_residencia'])
        self.client.login(username=self.residente.username, password='testpass123')

        listado = self.client.get(reverse('portafolio:actividades_propias'))
        crear = self.client.get(reverse('portafolio:actividad_crear'))

        self.assertEqual(listado.status_code, 200)
        self.assertFalse(listado.context['puede_registrar'])
        self.assertEqual(crear.status_code, 403)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    PORTAFOLIO_SOLO_SUPERUSER=True,
)
class PortafolioRolloutTests(TestCase):
    def setUp(self):
        self.residente = CustomUser.objects.create_user(
            username='residente_rollout_portafolio',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
            anio_residencia='R1',
        )
        self.instructor = CustomUser.objects.create_user(
            username='instructor_rollout_portafolio',
            password='testpass123',
            rol='instructor_residentes',
            perfil_completo=True,
        )
        self.superuser = CustomUser.objects.create_superuser(
            username='superuser_rollout_portafolio',
            password='testpass123',
            email='superuser@example.com',
        )

    def test_superuser_puede_abrir_seguimiento_y_detalle(self):
        self.client.login(username=self.superuser.username, password='testpass123')

        listado = self.client.get(reverse('portafolio:seguimiento'))
        detalle = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )
        trayectoria = self.client.get(
            reverse('portafolio:trayectoria_residente', args=[self.residente.pk])
        )

        self.assertEqual(listado.status_code, 200)
        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(trayectoria.status_code, 200)

    def test_residente_e_instructor_no_pueden_acceder_durante_rollout(self):
        self.client.login(username=self.residente.username, password='testpass123')
        propio = self.client.get(reverse('portafolio:mi_portafolio'))

        self.client.logout()
        self.client.login(username=self.instructor.username, password='testpass123')
        listado = self.client.get(reverse('portafolio:seguimiento'))
        detalle = self.client.get(
            reverse('portafolio:detalle_residente', args=[self.residente.pk])
        )
        trayectoria = self.client.get(
            reverse('portafolio:trayectoria_residente', args=[self.residente.pk])
        )

        self.assertEqual(propio.status_code, 403)
        self.assertEqual(listado.status_code, 403)
        self.assertEqual(detalle.status_code, 403)
        self.assertEqual(trayectoria.status_code, 403)

    def test_navbar_muestra_portafolio_solo_al_superuser(self):
        request_factory = RequestFactory()
        labels_por_usuario = {}

        for nombre, usuario in (
            ('residente', self.residente),
            ('instructor', self.instructor),
            ('superuser', self.superuser),
        ):
            request = request_factory.get('/')
            request.user = usuario
            request.resolver_match = resolve('/')
            grupos = navbar_links(request)['nav_groups']
            labels_por_usuario[nombre] = {
                item['label']
                for grupo in grupos
                for item in grupo['items']
            }

        self.assertNotIn('Mi portafolio', labels_por_usuario['residente'])
        self.assertNotIn(
            'Seguimiento de residentes',
            labels_por_usuario['instructor'],
        )
        self.assertIn(
            'Seguimiento de residentes',
            labels_por_usuario['superuser'],
        )


class CicloLectivoTests(TestCase):
    def test_comienza_el_primer_dia_habil_de_agosto(self):
        periodo = periodo_ciclo_lectivo(date(2026, 8, 17))

        self.assertEqual(periodo['inicio'], date(2026, 8, 3))
        self.assertEqual(periodo['fin_exclusivo'], date(2027, 8, 2))

    def test_omite_feriado_registrado(self):
        Feriado.objects.create(fecha=date(2026, 8, 3), descripcion='Feriado de prueba')

        periodo = periodo_ciclo_lectivo(date(2026, 8, 17))

        self.assertEqual(periodo['inicio'], date(2026, 8, 4))

    def test_fuentes_fechadas_se_limitan_hasta_hoy_en_ciclo_actual(self):
        periodo = periodo_ciclo_lectivo_por_anio(2026)

        limite_actual = fin_datos_exclusivo(periodo, hoy=date(2026, 8, 17))
        limite_cumplido = fin_datos_exclusivo(periodo, hoy=date(2027, 8, 17))

        self.assertEqual(limite_actual, date(2026, 8, 18))
        self.assertEqual(limite_cumplido, periodo['fin_exclusivo'])
