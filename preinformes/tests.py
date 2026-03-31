from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .models import TipoEstudio, Region, PlantillaPreinforme, Preinforme, RevisionPreinforme, HistorialEstudios

User = get_user_model()


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
