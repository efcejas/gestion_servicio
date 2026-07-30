from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from unittest.mock import patch
from io import StringIO

from .models import TipoEstudio, Region, PlantillaPreinforme, Preinforme, RevisionPreinforme, HistorialEstudios, AdjuntoPreinforme

User = get_user_model()

TEST_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


class PreinformeModelTest(TestCase):
    def setUp(self):
        # Crear usuarios de prueba
        self.residente = User.objects.create_user(
            username='residente1',
            email='residente1@test.com',
            password='testpass123',
            rol='medico_residente',
            first_name='Juan',
            last_name='Pérez',
            perfil_completo=True
        )
        
        self.staff = User.objects.create_user(
            username='staff1',
            email='staff1@test.com',
            password='testpass123',
            rol='medico_staff',
            first_name='Dr.',
            last_name='García',
            perfil_completo=True
        )
        
        # Crear tipo de estudio y región
        self.tipo_estudio = TipoEstudio.objects.create(
            nombre='Radiografía de Tórax',
            descripcion='Radiografía simple de tórax'
        )
        
        self.region = Region.objects.create(
            nombre='Tórax',
            descripcion='Región torácica'
        )
        
        # Crear plantilla
        self.plantilla = PlantillaPreinforme.objects.create(
            nombre='RX Tórax Normal',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            contenido='TÉCNICA: Radiografía de tórax PA y lateral.\n\n{HALLAZGOS}\n\nCONCLUSIÓN: Sin hallazgos patológicos.',
            creada_por=self.staff
        )

    def test_crear_preinforme(self):
        """Test crear preinforme"""
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2024-001234',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            plantilla_utilizada=self.plantilla,
            apellido_paciente='González',
            nombre_paciente='María',
            edad_paciente=45,
            sexo_paciente='F',
            tecnica='Radiografía de tórax PA y lateral en inspiración.',
            hallazgos='Pulmones bien expandidos, sin infiltrados ni consolidaciones.',
            conclusion='Radiografía de tórax normal.'
        )
        
        self.assertEqual(preinforme.estado, 'borrador')
        self.assertEqual(str(preinforme), '2024-001234 - González, María (residente1)')
        
    def test_enviar_a_revision(self):
        """Test enviar preinforme a revisión"""
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2024-001234',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='González',
            nombre_paciente='María',
            edad_paciente=45,
            sexo_paciente='F',
            tecnica='Test',
            hallazgos='Test',
            conclusion='Test'
        )
        
        preinforme.enviar_a_revision()
        
        self.assertEqual(preinforme.estado, 'pendiente_revision')
        self.assertIsNotNone(preinforme.fecha_envio_revision)
        
    def test_iniciar_revision(self):
        """Test iniciar revisión por staff"""
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2024-001234',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='González',
            nombre_paciente='María',
            edad_paciente=45,
            sexo_paciente='F',
            tecnica='Test',
            hallazgos='Test',
            conclusion='Test'
        )
        
        preinforme.enviar_a_revision()
        preinforme.iniciar_revision(self.staff)
        
        self.assertEqual(preinforme.estado, 'en_revision')
        self.assertEqual(preinforme.revisor, self.staff)
        self.assertIsNotNone(preinforme.fecha_inicio_revision)

    def test_historial_estadisticas(self):
        """Test actualización de estadísticas del historial"""
        # Crear algunos preinformes
        for i in range(3):
            preinforme = Preinforme.objects.create(
                residente=self.residente,
                numero_estudio=f'2024-00123{i}',
                tipo_estudio=self.tipo_estudio,
                region=self.region,
                apellido_paciente='Test',
                nombre_paciente='Test',
                edad_paciente=30,
                sexo_paciente='M',
                tecnica='Test',
                hallazgos='Test',
                conclusion='Test'
            )
            
            if i < 2:  # Finalizar 2 de 3
                preinforme.enviar_a_revision()
                preinforme.iniciar_revision(self.staff)
                preinforme.finalizar_revision()
                
                # Crear revisión con puntuación
                RevisionPreinforme.objects.create(
                    preinforme=preinforme,
                    revisor=self.staff,
                    informe_final_html='<p>Informe final test</p>',
                    puntuacion=8 + i  # 8 y 9
                )
        
        # Actualizar historial
        historial, created = HistorialEstudios.objects.get_or_create(residente=self.residente)
        historial.actualizar_estadisticas()
        
        self.assertEqual(historial.total_preinformes, 3)
        self.assertEqual(historial.preinformes_finalizados, 2)
        self.assertEqual(historial.promedio_puntuacion, 8.5)


@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES=TEST_STORAGES,
    PREINFORMES_RESUMEN_IA_REVISION_AUTO_GENERAR=False,
)
class RevisionStaffWorkflowRefactorTest(TestCase):
    """Tests de reglas reutilizables del circuito staff."""

    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_staff_flow',
            email='res_staff_flow@test.com',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_flow',
            email='staff_flow@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.jefe = User.objects.create_user(
            username='jefe_flow',
            email='jefe_flow@test.com',
            password='pass123',
            rol='jefe_residentes',
            perfil_completo=True,
        )
        self.otro_staff = User.objects.create_user(
            username='otro_staff_flow',
            email='otro_staff_flow@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo_estudio = TipoEstudio.objects.create(nombre='TC Staff Flow')
        self.region = Region.objects.create(nombre='Abdomen Staff Flow')

    def _preinforme(self, numero, estado='pendiente_revision', revisor=None, compartido=False):
        return Preinforme.objects.create(
            residente=self.residente,
            numero_estudio=numero,
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente=numero,
            informe_html=f'<p>Original {numero}</p>',
            estado=estado,
            revisor=revisor,
            asignacion_compartida=compartido,
            fecha_envio_revision=timezone.now(),
        )

    def test_revision_queryset_staff_no_ve_pool_compartido_en_sin_asignar(self):
        from .selectors import get_revision_queryset

        normal = self._preinforme('FLOW-001')
        compartido = self._preinforme('FLOW-002', compartido=True)

        qs = get_revision_queryset(self.staff, 'sin_asignar')

        self.assertIn(normal, qs)
        self.assertNotIn(compartido, qs)

    def test_revision_queryset_jefe_ve_pool_compartido(self):
        from .selectors import get_revision_queryset

        compartido = self._preinforme('FLOW-003', compartido=True)

        qs = get_revision_queryset(self.jefe, 'compartidos')

        self.assertIn(compartido, qs)

    def test_revision_queryset_muestra_asignados_a_otros(self):
        from .selectors import get_revision_queryset

        propio = self._preinforme('FLOW-004', revisor=self.staff)
        ajeno = self._preinforme('FLOW-005', revisor=self.otro_staff)

        qs = get_revision_queryset(self.staff, 'asignados_otros')

        self.assertIn(ajeno, qs)
        self.assertNotIn(propio, qs)

    def test_obtener_o_preparar_revision_crea_snapshot_y_precarga_editor(self):
        from .services import obtener_o_preparar_revision

        preinforme = self._preinforme('FLOW-006')

        revision, created = obtener_o_preparar_revision(preinforme, self.staff)

        self.assertTrue(created)
        self.assertEqual(revision.revisor, self.staff)
        self.assertEqual(revision.informe_residente_snapshot, '<p>Original FLOW-006</p>')
        self.assertEqual(revision.informe_final_html, '<p>Original FLOW-006</p>')

    def test_preinforme_form_guarda_contexto_clinico_opcional(self):
        from .forms import PreinformeForm

        form = PreinformeForm(data={
            'numero_estudio': 'FLOW-CONTEXTO-001',
            'tipo_estudio': self.tipo_estudio.pk,
            'region': self.region.pk,
            'sistema_destino': 'eges',
            'apellido_paciente': 'Paciente',
            'nombre_paciente': 'Contexto',
            'contexto_clinico': 'Dolor toracico y control evolutivo.',
            'informe_html': '<p>Informe de prueba.</p>',
        }, user=self.residente)

        self.assertTrue(form.is_valid(), form.errors)
        preinforme = form.save(commit=False)
        preinforme.residente = self.residente
        preinforme.save()
        self.assertEqual(preinforme.contexto_clinico, 'Dolor toracico y control evolutivo.')

    @override_settings(PREINFORMES_RESUMEN_IA_REVISION_AUTO_GENERAR=True)
    def test_revisar_preinforme_genera_y_muestra_resumen_ia(self):
        preinforme = self._preinforme('FLOW-IA-001', estado='en_revision', revisor=self.staff)

        with patch('preinformes.asistente_service.AsistenteRadiologicoBot') as bot_mock:
            bot_mock.return_value.generar_resumen_pre_revision.return_value = {
                'success': True,
                'resumen': {
                    'resumen': 'Preinforme con hallazgos principales presentes.',
                    'puntos_clave': ['Revisar que el cierre diagnóstico priorice los hallazgos relevantes.'],
                    'posibles_fricciones': ['El cierre del informe podría quedar poco específico.'],
                    'prioridad': 'media',
                },
                'error': None,
            }

            self.client.login(username='staff_flow', password='pass123')
            response = self.client.get(reverse('preinformes:revisar_preinforme', kwargs={'pk': preinforme.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resumen IA para revisar')
        self.assertContains(response, 'cierre diagnóstico')

        revision = RevisionPreinforme.objects.get(preinforme=preinforme)
        self.assertEqual(revision.resumen_ia_revision['prioridad'], 'media')

    def test_resumen_ia_pre_revision_filtra_recomendaciones_demograficas(self):
        from .asistente_service import limpiar_resumen_pre_revision

        resumen = limpiar_resumen_pre_revision({
            'resumen': 'El preinforme describe los hallazgos principales.',
            'puntos_clave': ['Verificar que el cierre diagnostico priorice los hallazgos relevantes.'],
            'posibles_fricciones': [
                'No se menciona la edad y el sexo del paciente, lo que podria ser relevante.',
                'La descripcion podria ordenar mejor la prioridad de los hallazgos.',
            ],
            'prioridad': 'media',
        })

        fricciones = ' '.join(resumen['posibles_fricciones']).lower()
        self.assertNotIn('edad', fricciones)
        self.assertNotIn('sexo', fricciones)
        self.assertIn('La descripcion podria ordenar mejor la prioridad de los hallazgos.', resumen['posibles_fricciones'])

    def test_finalizar_revision_genera_evaluacion_ia_formativa(self):
        preinforme = self._preinforme('FLOW-IA-FINAL-001', estado='en_revision', revisor=self.staff)

        evaluacion = {
            'puntaje_global': 8,
            'dimensiones': {
                'interpretacion_diagnostica': {'puntaje': 8, 'comentario': 'Reconoce el hallazgo principal.'},
                'priorizacion_clinica': {'puntaje': 7, 'comentario': 'Puede jerarquizar mejor.'},
                'redaccion_radiologica': {'puntaje': 8, 'comentario': 'Redaccion clara.'},
                'estructura_informe': {'puntaje': 8, 'comentario': 'Orden adecuado.'},
                'precision_terminologica': {'puntaje': 7, 'comentario': 'Terminologia aceptable.'},
                'autonomia': {'puntaje': 7, 'comentario': 'Requirio correccion moderada.'},
            },
            'fortalezas': ['Describe el hallazgo principal.'],
            'aspectos_a_mejorar': ['Mejorar la priorizacion.'],
            'tipo_correccion_predominante': 'jerarquizacion',
            'impacto_correccion_staff': 'La correccion fue moderada.',
            'uso_mentor': 'Sin uso registrado.',
            'devolucion_docente': 'Buen avance, con foco pendiente en jerarquizacion.',
        }

        with patch('preinformes.asistente_service.AsistenteRadiologicoBot') as bot_mock:
            bot_mock.return_value.generar_evaluacion_final_revision.return_value = {
                'success': True,
                'evaluacion': evaluacion,
                'error': None,
            }

            self.client.login(username='staff_flow', password='pass123')
            response = self.client.post(
                reverse('preinformes:revisar_preinforme', kwargs={'pk': preinforme.pk}),
                {
                    'informe_final_html': '<p>Informe final corregido.</p>',
                    'comentarios_generales': 'Revisar jerarquizacion de hallazgos.',
                    'puntuacion': '8',
                    'finalizar_revision': '1',
                },
            )

        self.assertEqual(response.status_code, 302)
        preinforme.refresh_from_db()
        revision = RevisionPreinforme.objects.get(preinforme=preinforme)
        self.assertEqual(preinforme.estado, 'finalizado')
        self.assertEqual(revision.evaluacion_ia_final['puntaje_global'], 8)
        self.assertEqual(revision.evaluacion_ia_final['tipo_correccion_predominante'], 'jerarquizacion')

    def test_evaluacion_ia_aceptada_sin_cambios_tiene_piso_justo(self):
        from .asistente_service import normalizar_evaluacion_ia_final

        evaluacion = normalizar_evaluacion_ia_final({
            'puntaje_global': 4,
            'dimensiones': {
                'interpretacion_diagnostica': {
                    'puntaje': 3,
                    'comentario': 'La redaccion es clara. Falta contexto clinico.',
                },
                'priorizacion_clinica': {'puntaje': 5},
            },
            'aspectos_a_mejorar': [
                'Incluir contexto clinico.',
                'Mejorar la jerarquizacion del hallazgo principal.',
            ],
            'devolucion_docente': (
                'Buen trabajo en la redaccion. '
                'Considera incluir mas datos clinicos en futuros informes.'
            ),
        }, aceptado_sin_cambios=True)

        self.assertEqual(evaluacion['puntaje_global'], 8)
        self.assertEqual(
            evaluacion['dimensiones']['interpretacion_diagnostica']['puntaje'],
            8,
        )
        self.assertEqual(evaluacion['criterio_puntaje'], 'aceptado_sin_cambios')
        self.assertEqual(evaluacion['version_rubrica'], 2)
        self.assertNotIn('Incluir contexto clinico.', evaluacion['aspectos_a_mejorar'])
        self.assertIn(
            'Mejorar la jerarquizacion del hallazgo principal.',
            evaluacion['aspectos_a_mejorar'],
        )
        self.assertEqual(
            evaluacion['dimensiones']['interpretacion_diagnostica']['comentario'],
            'La redaccion es clara.',
        )
        self.assertEqual(evaluacion['devolucion_docente'], 'Buen trabajo en la redaccion.')

    def test_evaluacion_ia_respeta_margen_de_nota_staff(self):
        from .asistente_service import normalizar_evaluacion_ia_final

        evaluacion_baja = normalizar_evaluacion_ia_final(
            {'puntaje_global': 3},
            puntuacion_staff=8,
        )
        evaluacion_alta = normalizar_evaluacion_ia_final(
            {'puntaje_global': 10},
            puntuacion_staff=6,
        )

        self.assertEqual(evaluacion_baja['puntaje_global'], 7)
        self.assertEqual(evaluacion_alta['puntaje_global'], 7)
        self.assertEqual(evaluacion_baja['criterio_puntaje'], 'anclado_nota_staff')
        self.assertEqual(evaluacion_baja['confianza_evaluacion'], 'alta')

    def test_comando_reevalua_solo_puntajes_historicos_bajos(self):
        preinforme_bajo = self._preinforme('FLOW-IA-BAJA-001', estado='finalizado', revisor=self.staff)
        revision_baja = RevisionPreinforme.objects.create(
            preinforme=preinforme_bajo,
            revisor=self.staff,
            informe_residente_snapshot='<p>Informe aceptado.</p>',
            informe_final_html='<p>Informe aceptado.</p>',
            evaluacion_ia_final={'puntaje_global': 4, 'devolucion_docente': 'Evaluacion anterior.'},
        )
        preinforme_alto = self._preinforme('FLOW-IA-ALTA-001', estado='finalizado', revisor=self.staff)
        revision_alta = RevisionPreinforme.objects.create(
            preinforme=preinforme_alto,
            revisor=self.staff,
            evaluacion_ia_final={'puntaje_global': 7},
        )
        evaluacion_nueva = {
            'puntaje_global': 9,
            'dimensiones': {},
            'version_rubrica': 2,
            'devolucion_docente': 'Aceptado sin cambios por el staff.',
        }

        with patch(
            'preinformes.management.commands.reevaluar_evaluaciones_ia_bajas.AsistenteRadiologicoBot'
        ) as bot_mock:
            bot_mock.return_value.client = object()
            bot_mock.return_value.generar_evaluacion_final_revision.return_value = {
                'success': True,
                'evaluacion': evaluacion_nueva,
                'error': None,
            }
            salida = StringIO()
            call_command(
                'reevaluar_evaluaciones_ia_bajas',
                '--apply',
                stdout=salida,
            )

        revision_baja.refresh_from_db()
        revision_alta.refresh_from_db()
        self.assertEqual(revision_baja.evaluacion_ia_final['puntaje_global'], 9)
        self.assertEqual(
            revision_baja.evaluacion_ia_final['auditoria_reevaluacion']['puntaje_anterior'],
            4,
        )
        self.assertEqual(revision_alta.evaluacion_ia_final['puntaje_global'], 7)
        bot_mock.return_value.generar_evaluacion_final_revision.assert_called_once_with(
            revision_baja
        )

    def test_staff_puede_tomar_preinforme_asignado_a_otro(self):
        preinforme = self._preinforme('FLOW-007', revisor=self.otro_staff)

        self.client.login(username='staff_flow', password='pass123')
        response = self.client.post(
            reverse('preinformes:asignar_revisor', kwargs={'pk': preinforme.pk}) + '?mostrar=asignados_otros',
            {'action': 'asignarme'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('mostrar=asignados_otros', response['Location'])
        preinforme.refresh_from_db()
        self.assertEqual(preinforme.revisor, self.staff)

    def test_staff_no_puede_tomar_preinforme_en_revision_de_otro(self):
        preinforme = self._preinforme('FLOW-008', estado='en_revision', revisor=self.otro_staff)

        self.client.login(username='staff_flow', password='pass123')
        response = self.client.post(
            reverse('preinformes:asignar_revisor', kwargs={'pk': preinforme.pk}) + '?mostrar=asignados_otros',
            {'action': 'asignarme'},
        )

        self.assertEqual(response.status_code, 302)
        preinforme.refresh_from_db()
        self.assertEqual(preinforme.revisor, self.otro_staff)

    def test_staff_puede_liberar_revision_accidental(self):
        preinforme = self._preinforme('FLOW-009', estado='en_revision', revisor=self.staff)

        self.client.login(username='staff_flow', password='pass123')
        response = self.client.post(
            reverse('preinformes:revisar_preinforme', kwargs={'pk': preinforme.pk}),
            {'liberar_revision': '1'},
        )

        self.assertEqual(response.status_code, 302)
        preinforme.refresh_from_db()
        self.assertEqual(preinforme.estado, 'pendiente_revision')
        self.assertIsNone(preinforme.revisor)


class PreinformeViewTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='residente1',
            email='residente1@test.com',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True
        )
        
        self.staff = User.objects.create_user(
            username='staff1',
            email='staff1@test.com',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True
        )
        
        self.tipo_estudio = TipoEstudio.objects.create(nombre='RX Tórax')
        self.region = Region.objects.create(nombre='Tórax')

    def test_dashboard_residente_login_required(self):
        """Test que el dashboard requiere login"""
        response = self.client.get(reverse('preinformes:dashboard_residente'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_residente_access(self):
        """Test acceso al dashboard de residente"""
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('preinformes:dashboard_residente'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard - Preinformes')

    def test_crear_preinforme_get(self):
        """Test GET del formulario de creación"""
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('preinformes:crear_preinforme'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nuevo Preinforme')

    def test_crear_preinforme_post(self):
        """Test POST del formulario de creación"""
        self.client.login(username='residente1', password='testpass123')
        
        data = {
            'numero_estudio': '2024-001234',
            'tipo_estudio': self.tipo_estudio.id,
            'region': self.region.id,
            'sistema_destino': 'eges',
            'apellido_paciente': 'González',
            'nombre_paciente': 'María',
            'informe_html': '<p>TÉCNICA: Radiografía de tórax PA y lateral.</p><p>HALLAZGOS: Sin hallazgos patológicos.</p>',
        }
        
        response = self.client.post(reverse('preinformes:crear_preinforme'), data)
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Verificar que se creó el preinforme
        self.assertTrue(Preinforme.objects.filter(numero_estudio='2024-001234').exists())

    def test_staff_dashboard_access(self):
        """Test acceso al dashboard de staff"""
        self.client.login(username='staff1', password='testpass123')
        response = self.client.get(reverse('preinformes:dashboard_staff'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard Staff')

    def test_residente_no_access_staff_dashboard(self):
        """Test que residente no puede acceder al dashboard de staff"""
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('preinformes:dashboard_staff'))
        # Debería redirigir o mostrar error de permisos
        self.assertNotEqual(response.status_code, 200)


class NormalizeHTMLContentSoftTest(TestCase):
    """
    Tests para normalize_html_content_soft() - versión respetuosa de normalización HTML.
    
    Esta versión preserva la estructura original del usuario y solo normaliza
    cuando detecta "pegado sucio" (muchos <br> en un solo <p>).
    """
    
    def test_caso1_preservar_tecnica_narrativa(self):
        """
        Caso 1: Técnica narrativa con pocos <br> - NO debe convertir
        
        Escenario: Usuario tiene plantilla bien formada con 1-2 <br> intencionales
        Ejemplo: Sección TÉCNICA con descripción en 2 líneas
        Esperado: Preservar <br>, NO convertir a nuevos <p>
        """
        from preinformes.models import normalize_html_content_soft
        
        html_input = '<p><strong>TÉCNICA:</strong></p><p>Línea 1<br>Línea 2</p>'
        result = normalize_html_content_soft(html_input)
        
        # Debe preservar la estructura original (2 <p> con 1 <br> interno)
        self.assertIn('<p><strong>TÉCNICA:</strong></p>', result)
        self.assertIn('<p>Línea 1<br>Línea 2</p>', result, 
                      "NO debe convertir <br> a <p> cuando hay pocos <br>")
        
        # No debe crear párrafos adicionales
        self.assertEqual(result.count('<p>'), 2,
                        "Debe mantener exactamente 2 <p> (no agregar más)")
    
    def test_caso2_convertir_pegado_sucio(self):
        """
        Caso 2: Pegado sucio con muchos <br> - SÍ debe convertir
        
        Escenario: Usuario pegó desde Word y el HTML tiene 1 <p> con 4+ <br>
        Ejemplo: <p>L1<br>L2<br>L3<br>L4</p>
        Esperado: Convertir cada línea en <p> separado
        """
        from preinformes.models import normalize_html_content_soft
        
        # Por defecto, br_threshold=3, así que 4 <br> debe convertir
        html_input = '<p>Línea 1<br>Línea 2<br>Línea 3<br>Línea 4</p>'
        result = normalize_html_content_soft(html_input)
        
        # Debe crear 4 párrafos separados
        self.assertEqual(result.count('<p>'), 4, 
                        "Debe crear 4 <p> cuando hay >= br_threshold <br>")
        
        self.assertIn('<p>Línea 1</p>', result)
        self.assertIn('<p>Línea 2</p>', result)
        self.assertIn('<p>Línea 3</p>', result)
        self.assertIn('<p>Línea 4</p>', result)
        
        # NO debe tener <br> en el resultado
        self.assertNotIn('<br>', result, 
                        "No debe quedar <br> después de conversión")
    
    def test_caso3_multiples_parrafos_bien_estructurados(self):
        """
        Caso 3: HTML con 2+ <p> ya bien formado - NO reestructurar
        
        Escenario: Usuario tiene contenido bien estructurado con múltiples párrafos
        Ejemplo: <p>A</p><p>B</p>
        Esperado: Preservar tal cual (solo limpiar párrafos vacíos si hay)
        """
        from preinformes.models import normalize_html_content_soft
        
        html_input = '<p>Párrafo A</p><p>Párrafo B</p>'
        result = normalize_html_content_soft(html_input)
        
        # Debe preservar estructura exacta
        self.assertEqual(result, html_input, 
                        "Estructura con 2+ <p> debe preservarse sin cambios")
        
        # Caso con <br> dentro pero múltiples <p>: NO convertir
        html_input_con_br = '<p>A<br>A2</p><p>B<br>B2</p>'
        result_br = normalize_html_content_soft(html_input_con_br)
        
        # Debe respetar los <br> internos (NO convertir a más <p>)
        self.assertIn('<br>', result_br, 
                     "Con 2+ <p>, debe preservar <br> internos")
        self.assertEqual(result_br.count('<p>'), 2, 
                        "No debe crear <p> adicionales")
    
    def test_caso4_eliminar_parrafos_vacios(self):
        """
        Caso 4: Párrafos vacíos - deben eliminarse
        
        Escenario: HTML tiene <p>&nbsp;</p>, <p> </p>, <p><br></p>
        Esperado: Eliminar párrafos vacíos, preservar solo los con contenido
        """
        from preinformes.models import normalize_html_content_soft
        
        html_input = '<p>A</p><p>&nbsp;</p><p> </p><p><br></p><p>B</p>'
        result = normalize_html_content_soft(html_input)
        
        # Solo deben quedar 2 párrafos con contenido
        self.assertEqual(result.count('<p>'), 2, 
                        "Debe eliminar párrafos vacíos")
        
        self.assertIn('<p>A</p>', result)
        self.assertIn('<p>B</p>', result)
        
        # No debe contener párrafos vacíos
        self.assertNotIn('&nbsp;', result)
        self.assertNotIn('<p></p>', result)
        self.assertNotIn('<p> </p>', result)
    
    def test_caso5_texto_plano_con_saltos(self):
        """
        Caso 5: Texto plano con saltos de línea - convertir a <p>
        
        Escenario: HTML sin <p>, solo texto con \n
        Ejemplo: "Uno\nDos\nTres"
        Esperado: Crear <p> por cada línea
        """
        from preinformes.models import normalize_html_content_soft
        
        html_input = "Uno\nDos\nTres"
        result = normalize_html_content_soft(html_input)
        
        # Debe crear 3 párrafos
        self.assertEqual(result.count('<p>'), 3)
        
        self.assertIn('<p>Uno</p>', result)
        self.assertIn('<p>Dos</p>', result)
        self.assertIn('<p>Tres</p>', result)
    
    def test_caso6_br_threshold_custom(self):
        """
        Caso 6: Threshold customizado - probar br_threshold=2
        
        Escenario: Ajustar sensibilidad de "pegado sucio"
        Esperado: Con threshold=2, solo 2 <br> ya convierte
        """
        from preinformes.models import normalize_html_content_soft
        
        # Con threshold por defecto (3), NO debe convertir
        html_2br = '<p>A<br>B</p>'
        result_default = normalize_html_content_soft(html_2br)
        self.assertIn('<br>', result_default, 
                     "Con 1 <br> y threshold=3, debe preservar")
        
        # Con threshold=2, SÍ debe convertir
        html_2br = '<p>A<br>B<br>C</p>'
        result_threshold2 = normalize_html_content_soft(html_2br, br_threshold=2)
        self.assertNotIn('<br>', result_threshold2, 
                        "Con 2 <br> y threshold=2, debe convertir")
        self.assertEqual(result_threshold2.count('<p>'), 3)
    
    def test_caso7_contenido_vacio_o_none(self):
        """
        Caso 7: Edge cases - None, '', espacios
        
        Escenario: Validar robustez con entradas vacías
        Esperado: Retornar '' sin errores
        """
        from preinformes.models import normalize_html_content_soft
        
        self.assertEqual(normalize_html_content_soft(None), '')
        self.assertEqual(normalize_html_content_soft(''), '')
        self.assertEqual(normalize_html_content_soft('   '), '')
        self.assertEqual(normalize_html_content_soft('\n\n'), '')
    
    def test_caso8_html_con_atributos(self):
        """
        Caso 8: <p> con atributos (class, style, etc.)
        
        Escenario: HTML real de CKEditor tiene atributos en <p>
        Ejemplo: <p class="...">...</p>
        Esperado: Respetar atributos, aplicar lógica igual
        """
        from preinformes.models import normalize_html_content_soft
        
        # Múltiples <p> con atributos: preservar
        html_input = '<p class="destacado">A</p><p style="color:red">B</p>'
        result = normalize_html_content_soft(html_input)
        
        self.assertIn('class="destacado"', result)
        self.assertIn('style="color:red"', result)
        self.assertEqual(result.count('<p'), 2)
    
    def test_caso9_br_en_tabla_no_convierte(self):
        """
        Caso 9: <br> dentro de tabla - NO debe convertir
        
        Escenario: Tabla con <br> interno (uso legítimo)
        Ejemplo: <table><tr><td>A<br>B</td></tr></table>
        Esperado: NO contar esos <br> para threshold (preservar)
        
        TODO: Implementar detección más sofisticada si este caso falla
        """
        from preinformes.models import normalize_html_content_soft
        
        # Tabla con varios <br> internos
        html_tabla = '<p><table><tr><td>A<br>B<br>C<br>D</td></tr></table></p>'
        result = normalize_html_content_soft(html_tabla)
        
        # Debe preservar tabla intacta (no reestructurar)
        self.assertIn('<table>', result)
        self.assertIn('<br>', result, 
                     "<br> en tabla debe preservarse")
        
        # TODO: Si este test falla, mejorar lógica de filtrado de <table>
    
    def test_caso10_comparacion_con_normalize_original(self):
        """
        Caso 10: Comparación con normalize_html_content (versión agresiva)
        
        Escenario: Documentar diferencia entre versión soft vs original
        Esperado: normalize_html_content convierte TODO, soft preserva
        """
        from preinformes.models import normalize_html_content, normalize_html_content_soft
        
        # HTML con técnica narrativa (pocos <br>)
        html = '<p>TÉCNICA:</p><p>Línea 1<br>Línea 2</p>'
        
        # Versión agresiva (original): convierte TODO
        result_agresivo = normalize_html_content(html)
        # Contaría más <p> porque convierte <br>
        
        # Versión soft: preserva
        result_soft = normalize_html_content_soft(html)
        self.assertIn('<br>', result_soft, 
                     "Versión soft debe preservar <br> intencionales")
        
        # Número de <p> debe ser menor en soft (no crea adicionales)
        self.assertLessEqual(result_soft.count('<p>'), 
                            html.count('<p>') + 2,  # tolerancia mínima
                            "Soft no debe crear muchos <p> adicionales")


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGES)
class AdjuntoPreinformeTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='residente_adjuntos',
            email='residente_adjuntos@test.com',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_adjuntos',
            email='staff_adjuntos@test.com',
            password='testpass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo_estudio = TipoEstudio.objects.create(nombre='RM Cerebro')
        self.region = Region.objects.create(nombre='Cráneo')

    def _png_file(self, name='captura.png'):
        # PNG mínimo de 1x1 pixel
        return SimpleUploadedFile(
            name,
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
            content_type='image/png',
        )

    def test_adjuntar_imagen_residente_al_crear_preinforme(self):
        self.client.login(username='residente_adjuntos', password='testpass123')

        response = self.client.post(
            reverse('preinformes:crear_preinforme'),
            {
                'numero_estudio': '2026-9001',
                'tipo_estudio': self.tipo_estudio.id,
                'region': self.region.id,
                'sistema_destino': 'eges',
                'apellido_paciente': 'Paciente',
                'nombre_paciente': 'Uno',
                'informe_html': '<p>Hallazgo test</p>',
                'imagenes_residente': self._png_file(),
            },
        )

        self.assertEqual(response.status_code, 302)
        preinforme = Preinforme.objects.get(numero_estudio='2026-9001')
        self.assertTrue(
            AdjuntoPreinforme.objects.filter(
                preinforme=preinforme,
                origen='residente',
                subido_por=self.residente,
            ).exists()
        )

    def test_revisor_puede_adjuntar_feedback_visual(self):
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-9002',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente='Dos',
            informe_html='<p>Original</p>',
        )
        preinforme.enviar_a_revision()

        self.client.login(username='staff_adjuntos', password='testpass123')
        response = self.client.post(
            reverse('preinformes:revisar_preinforme', kwargs={'pk': preinforme.pk}),
            {
                'informe_final_html': '<p>Informe corregido</p>',
                'comentarios_generales': 'Buen trabajo.',
                'imagenes_revisor': self._png_file('feedback.png'),
                'guardar_y_continuar': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AdjuntoPreinforme.objects.filter(
                preinforme=preinforme,
                origen='revisor',
                subido_por=self.staff,
            ).exists()
        )

    def test_residente_no_puede_ver_preinforme_ajeno_con_adjuntos(self):
        otro_residente = User.objects.create_user(
            username='residente_otro',
            email='residente_otro@test.com',
            password='testpass123',
            rol='medico_residente',
            perfil_completo=True,
        )

        preinforme = Preinforme.objects.create(
            residente=otro_residente,
            numero_estudio='2026-9003',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente='Tres',
            informe_html='<p>Texto</p>',
        )

        AdjuntoPreinforme.objects.create(
            preinforme=preinforme,
            imagen=self._png_file('ajeno.png'),
            subido_por=otro_residente,
            origen='residente',
        )

        self.client.login(username='residente_adjuntos', password='testpass123')
        response = self.client.get(reverse('preinformes:ver_preinforme', kwargs={'pk': preinforme.pk}))
        self.assertEqual(response.status_code, 404)

    def test_residente_puede_eliminar_adjunto_propio_en_edicion(self):
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-9004',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente='Cuatro',
            informe_html='<p>Texto inicial</p>',
        )
        preinforme.enviar_a_revision()  # pendiente_revision sigue siendo editable por residente

        adjunto = AdjuntoPreinforme.objects.create(
            preinforme=preinforme,
            imagen=self._png_file('borrar.png'),
            subido_por=self.residente,
            origen='residente',
        )

        self.client.login(username='residente_adjuntos', password='testpass123')
        response = self.client.post(
            reverse('preinformes:editar_preinforme', kwargs={'pk': preinforme.pk}),
            {
                'numero_estudio': preinforme.numero_estudio,
                'tipo_estudio': self.tipo_estudio.id,
                'region': self.region.id,
                'sistema_destino': 'eges',
                'apellido_paciente': preinforme.apellido_paciente,
                'nombre_paciente': preinforme.nombre_paciente,
                'informe_html': '<p>Texto actualizado</p>',
                'eliminar_adjuntos_residente': str(adjunto.id),
                'guardar_y_continuar': '1',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(AdjuntoPreinforme.objects.filter(id=adjunto.id).exists())

    def test_residente_puede_eliminar_preinforme_propio_pendiente(self):
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-9005',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente='Cinco',
            informe_html='<p>Texto inicial</p>',
        )
        preinforme.enviar_a_revision()

        self.client.login(username='residente_adjuntos', password='testpass123')
        response = self.client.post(reverse('preinformes:eliminar_preinforme', kwargs={'pk': preinforme.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Preinforme.objects.filter(pk=preinforme.pk).exists())

    def test_eliminar_preinforme_preserva_filtros_de_retorno(self):
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-9006',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Paciente',
            nombre_paciente='Seis',
            informe_html='<p>Texto inicial</p>',
        )
        preinforme.enviar_a_revision()
        next_url = f"{reverse('preinformes:mis_preinformes')}?estado=pendiente_revision&page=2"

        self.client.login(username='residente_adjuntos', password='testpass123')
        response = self.client.post(
            reverse('preinformes:eliminar_preinforme', kwargs={'pk': preinforme.pk}),
            {'next': next_url},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], next_url)
        self.assertFalse(Preinforme.objects.filter(pk=preinforme.pk).exists())


# ---------------------------------------------------------------------------
# Smoke tests: autosave residente + revisor, copiar_informe_final, cargar_plantillas
# ---------------------------------------------------------------------------

@override_settings(
    SECURE_SSL_REDIRECT=False,
    STORAGES=TEST_STORAGES,
    PREINFORMES_RESUMEN_IA_REVISION_AUTO_GENERAR=False,
)
class RevisionFinalizadaEditTest(TestCase):
    """Permite corregir una revision ya finalizada solo al revisor asignado."""

    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_final_edit',
            email='res_final_edit@test.com',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.revisor = User.objects.create_user(
            username='rev_final_edit',
            email='rev_final_edit@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.otro_revisor = User.objects.create_user(
            username='otro_final_edit',
            email='otro_final_edit@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo_estudio = TipoEstudio.objects.create(nombre='RM Rodilla')
        self.region = Region.objects.create(nombre='Rodilla')
        self.preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-FIN001',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Final',
            nombre_paciente='Editar',
            informe_html='<p>Original residente</p>',
        )
        self.preinforme.iniciar_revision(self.revisor)
        self.revision = RevisionPreinforme.objects.create(
            preinforme=self.preinforme,
            revisor=self.revisor,
            informe_residente_snapshot='<p>Original residente</p>',
            informe_final_html='<p>Informe final inicial</p>',
        )
        self.preinforme.finalizar_revision()

    def _url(self):
        return reverse('preinformes:revisar_preinforme', kwargs={'pk': self.preinforme.pk})

    def test_revisor_asignado_puede_abrir_finalizado_para_editar(self):
        self.client.login(username='rev_final_edit', password='pass123')
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Editar Revisi')

    def test_revisor_asignado_puede_guardar_finalizado(self):
        self.client.login(username='rev_final_edit', password='pass123')
        response = self.client.post(
            self._url(),
            {
                'informe_final_html': '<p>Informe corregido luego de finalizado</p>',
                'comentarios_generales': 'Agrego comentario tardio.',
                'puntuacion': '8',
                'finalizar_revision': '1',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('mostrar=finalizados', response['Location'])

        self.revision.refresh_from_db()
        self.preinforme.refresh_from_db()
        self.assertEqual(self.preinforme.estado, 'finalizado')
        self.assertEqual(self.revision.informe_final_html, '<p>Informe corregido luego de finalizado</p>')
        self.assertEqual(self.revision.comentarios_generales, 'Agrego comentario tardio.')

    def test_otro_revisor_no_puede_editar_finalizado(self):
        self.client.login(username='otro_final_edit', password='pass123')
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('preinformes:lista_revision'))


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGES)
class AutosaveRevisionSmokeTest(TestCase):
    """Tests del endpoint autosave_revision (POST /preinformes/revision/<pk>/autosave/)."""

    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_autosave',
            email='res_autosave@test.com',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.revisor = User.objects.create_user(
            username='rev_autosave',
            email='rev_autosave@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo_estudio = TipoEstudio.objects.create(nombre='TC Abdomen')
        self.region = Region.objects.create(nombre='Abdomen')

        self.preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-AS001',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Prueba',
            nombre_paciente='Autosave',
            informe_html='<p>Contenido inicial</p>',
        )
        self.preinforme.iniciar_revision(self.revisor)
        # Crear el objeto RevisionPreinforme que crearía la vista revisar_preinforme
        from .models import RevisionPreinforme
        self.revision = RevisionPreinforme.objects.create(
            preinforme=self.preinforme,
            revisor=self.revisor,
            informe_final_html='<p>Inicial del revisor</p>',
        )

    def _url(self):
        return reverse('preinformes:autosave_revision', kwargs={'pk': self.preinforme.pk})

    def test_autosave_revision_sin_login_devuelve_302(self):
        """Sin autenticación debe redirigir al login."""
        import json
        response = self.client.post(
            self._url(),
            data=json.dumps({'informe_final_html': '<p>X</p>'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)

    def test_autosave_revision_revisor_correcto_ok(self):
        """Revisor asignado puede guardar: devuelve JSON success=True."""
        import json
        self.client.login(username='rev_autosave', password='pass123')
        payload = '<p>Contenido guardado por autosave</p>'
        response = self.client.post(
            self._url(),
            data=json.dumps({'informe_final_html': payload}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertIn('timestamp', data)

        # Verificar que se persistió en BD
        from .models import RevisionPreinforme
        revision = RevisionPreinforme.objects.get(preinforme=self.preinforme)
        self.assertEqual(revision.informe_final_html, payload)

    def test_autosave_revision_finalizado_revisor_correcto_ok(self):
        """El revisor asignado puede usar autosave aunque el preinforme ya este finalizado."""
        import json
        self.preinforme.finalizar_revision()
        self.client.login(username='rev_autosave', password='pass123')
        payload = '<p>Contenido finalizado guardado por autosave</p>'
        response = self.client.post(
            self._url(),
            data=json.dumps({'informe_final_html': payload}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))

        self.revision.refresh_from_db()
        self.assertEqual(self.revision.informe_final_html, payload)

    def test_autosave_revision_contenido_vacio_devuelve_400(self):
        """Contenido vacío debe devolver HTTP 400."""
        import json
        self.client.login(username='rev_autosave', password='pass123')
        response = self.client.post(
            self._url(),
            data=json.dumps({'informe_final_html': ''}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json().get('success'))

    def test_autosave_revision_revisor_incorrecto_devuelve_404(self):
        """Un revisor distinto al asignado debe recibir 404."""
        import json
        otro_staff = User.objects.create_user(
            username='otro_staff',
            email='otro@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.client.login(username='otro_staff', password='pass123')
        response = self.client.post(
            self._url(),
            data=json.dumps({'informe_final_html': '<p>Intento</p>'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)


class CopiarInformeFinalSmokeTest(TestCase):
    """Tests del endpoint copiar_informe_final (GET /preinformes/copiar-informe/<pk>/)."""

    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_copiar',
            email='res_copiar@test.com',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.revisor = User.objects.create_user(
            username='rev_copiar',
            email='rev_copiar@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.otro_residente = User.objects.create_user(
            username='res_copiar_otro',
            email='res_copiar_otro@test.com',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.tipo_estudio = TipoEstudio.objects.create(nombre='RM Rodilla')
        self.region = Region.objects.create(nombre='Rodilla')

    def _crear_preinforme(self, sistema='eges'):
        return Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-CP001',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Copiar',
            nombre_paciente='Test',
            informe_html='<p>Hallazgos de prueba.</p>',
            sistema_destino=sistema,
        )

    def _url(self, pk):
        return reverse('preinformes:copiar_informe_final', kwargs={'pk': pk})

    def test_copiar_sin_login_redirige(self):
        p = self._crear_preinforme()
        response = self.client.get(self._url(p.pk))
        self.assertEqual(response.status_code, 302)

    def test_copiar_propio_residente_devuelve_json(self):
        """El propio residente puede copiar su informe."""
        p = self._crear_preinforme()
        self.client.login(username='res_copiar', password='pass123')
        response = self.client.get(self._url(p.pk))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('informe_html', data)
        self.assertIn('informe_texto', data)
        self.assertIn('sistema_destino', data)
        self.assertEqual(data['sistema_destino'], 'eges')

    def test_copiar_revisor_asignado_devuelve_json(self):
        """El revisor asignado puede copiar."""
        p = self._crear_preinforme()
        p.iniciar_revision(self.revisor)
        self.client.login(username='rev_copiar', password='pass123')
        response = self.client.get(self._url(p.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn('informe_html', response.json())

    def test_copiar_residente_ajeno_no_finalizado_devuelve_403(self):
        """Un residente distinto no puede copiar un informe no finalizado."""
        p = self._crear_preinforme()
        self.client.login(username='res_copiar_otro', password='pass123')
        response = self.client.get(self._url(p.pk))
        self.assertEqual(response.status_code, 403)

    def test_copiar_informe_finalizado_cualquier_residente_ok(self):
        """Cualquier residente puede copiar un informe ya finalizado (banco de informes)."""
        p = self._crear_preinforme()
        p.iniciar_revision(self.revisor)
        p.finalizar_revision()
        self.client.login(username='res_copiar_otro', password='pass123')
        response = self.client.get(self._url(p.pk))
        self.assertEqual(response.status_code, 200)

    def test_copiar_sistema_netterm_devuelve_texto_sin_acentos(self):
        """Sistema NetTerm: informe_texto no debe contener vocales con tilde."""
        p = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-CP002',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Acción',
            nombre_paciente='Revisión',
            informe_html='<p>Conclusión: hallazgos normales. Corazón sin alteraciones.</p>',
            sistema_destino='netterm',
        )
        self.client.login(username='res_copiar', password='pass123')
        response = self.client.get(self._url(p.pk))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['sistema_destino'], 'netterm')
        # El texto plano para NetTerm no debe tener acentos
        texto = data['informe_texto']
        for acento in ['á', 'é', 'í', 'ó', 'ú', 'Á', 'É', 'Í', 'Ó', 'Ú']:
            self.assertNotIn(acento, texto, f"NetTerm texto no debe contener '{acento}'")

    def test_copiar_sistema_netterm_no_trunca_informe_largo(self):
        """El endpoint entrega completo un informe NetTerm extenso."""
        parrafos = [
            f'<p>Hallazgo {numero:04d}: descripcion extensa sin alteraciones.</p>'
            for numero in range(1500)
        ]
        p = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='2026-CP003',
            tipo_estudio=self.tipo_estudio,
            region=self.region,
            apellido_paciente='Extenso',
            nombre_paciente='NetTerm',
            informe_html=''.join(parrafos),
            sistema_destino='netterm',
        )
        self.client.login(username='res_copiar', password='pass123')

        response = self.client.get(self._url(p.pk))

        self.assertEqual(response.status_code, 200)
        texto = response.json()['informe_texto']
        self.assertIn('Hallazgo 0000', texto)
        self.assertIn('Hallazgo 1499', texto)
        self.assertEqual(texto.count('Hallazgo'), 1500)


class CargarPlantillasSmokeTest(TestCase):
    """Tests del endpoint cargar_plantillas (GET /preinformes/cargar-plantillas/)."""

    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_plantilla',
            email='res_plantilla@test.com',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.staff = User.objects.create_user(
            username='staff_plantilla',
            email='staff_plantilla@test.com',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo = TipoEstudio.objects.create(nombre='RX Columna')
        self.region = Region.objects.create(nombre='Columna')

        self.plantilla_publica = PlantillaPreinforme.objects.create(
            nombre='Columna Normal',
            tipo_estudio=self.tipo,
            region=self.region,
            contenido='<p>TÉCNICA: columna lumbar.</p>',
            creada_por=self.staff,
            estado='publica',
            sistema_destino='eges',
        )
        self.plantilla_borrador = PlantillaPreinforme.objects.create(
            nombre='Borrador privado',
            tipo_estudio=self.tipo,
            region=self.region,
            contenido='<p>Borrador</p>',
            creada_por=self.staff,
            estado='borrador',
            sistema_destino='eges',
        )

    def _url(self):
        return reverse('preinformes:cargar_plantillas')

    def test_cargar_sin_login_redirige(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)

    def test_cargar_plantillas_publicas_devuelve_lista(self):
        """Residente ve plantillas públicas."""
        self.client.login(username='res_plantilla', password='pass123')
        response = self.client.get(self._url(), {'tipo_estudio_id': self.tipo.id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        nombres = [p['nombre'] for p in data['plantillas']]
        self.assertIn('Columna Normal', nombres)
        # Borrador de otro usuario NO debe aparecer para el residente
        self.assertNotIn('Borrador privado', nombres)

    def test_cargar_plantillas_borrador_visible_para_su_creador(self):
        """El creador de un borrador lo ve en su lista."""
        self.client.login(username='staff_plantilla', password='pass123')
        response = self.client.get(self._url(), {'tipo_estudio_id': self.tipo.id})
        self.assertEqual(response.status_code, 200)
        nombres = [p['nombre'] for p in response.json()['plantillas']]
        self.assertIn('Borrador privado', nombres)

    def test_cargar_plantillas_contenido_normalizado(self):
        """El contenido devuelto no debe tener fondos de color ni estilos sucios."""
        from preinformes.models import PlantillaPreinforme
        # Plantilla con fondo rojo (background-color sucio)
        p = PlantillaPreinforme.objects.create(
            nombre='Con fondo',
            tipo_estudio=self.tipo,
            region=self.region,
            contenido='<p style="background-color: red;">Texto</p>',
            creada_por=self.staff,
            estado='publica',
            sistema_destino='eges',
        )
        self.client.login(username='res_plantilla', password='pass123')
        response = self.client.get(self._url(), {'tipo_estudio_id': self.tipo.id})
        datos = response.json()['plantillas']
        plantilla_con_fondo = next((x for x in datos if x['nombre'] == 'Con fondo'), None)
        self.assertIsNotNone(plantilla_con_fondo)
        self.assertNotIn('background-color', plantilla_con_fondo['contenido'])


class PerfilResidenteDocentePaginacionTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin_evaluaciones',
            email='admin@test.com',
            password='pass123',
        )
        self.residente = User.objects.create_user(
            username='residente_evaluaciones',
            password='pass123',
            rol='medico_residente',
            perfil_completo=True,
        )
        self.revisor = User.objects.create_user(
            username='staff_evaluaciones',
            password='pass123',
            rol='medico_staff',
            perfil_completo=True,
        )
        self.tipo = TipoEstudio.objects.create(nombre='TC evaluaciones')
        self.region = Region.objects.create(nombre='Region evaluaciones')

        for indice in range(11):
            preinforme = Preinforme.objects.create(
                residente=self.residente,
                numero_estudio=f'EVAL-{indice:03d}',
                tipo_estudio=self.tipo,
                region=self.region,
                apellido_paciente='Paciente',
                nombre_paciente=str(indice),
            )
            RevisionPreinforme.objects.create(
                preinforme=preinforme,
                revisor=self.revisor,
                evaluacion_ia_final={'puntaje_global': indice + 1},
            )

    def test_evaluaciones_finales_se_paginan_sin_alterar_promedio(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse(
            'preinformes:perfil_residente_docente',
            args=[self.residente.pk],
        ), follow=True)

        self.assertEqual(response.status_code, 200)
        pagina = response.context['revisiones_evaluadas']
        self.assertEqual(len(pagina), 10)
        self.assertEqual(pagina.paginator.count, 11)
        self.assertEqual(response.context['promedio_evaluacion_final'], 6.0)

        segunda_pagina = self.client.get(
            reverse('preinformes:perfil_residente_docente', args=[self.residente.pk]),
            {'evaluaciones_page': 2},
            follow=True,
        ).context['revisiones_evaluadas']
        self.assertEqual(len(segunda_pagina), 1)
