from io import BytesIO
import zipfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from dictado_informes.template_importer import (
    DocxTemplateImportError,
    extraer_parrafos_docx,
    extraer_parrafos_texto,
    importar_plantilla_archivo,
    importar_plantilla_docx,
    importar_plantilla_texto,
)
from dictado_informes.models import PlantillaEstructurada
from dictado_informes.views import _generar_codigo_interno_plantilla


def crear_docx_minimo(parrafos):
    body = ''.join(
        f'<w:p><w:r><w:t>{parrafo}</w:t></w:r></w:p>'
        for parrafo in parrafos
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body>{body}</w:body>'
        '</w:document>'
    )
    archivo = BytesIO()
    with zipfile.ZipFile(archivo, 'w') as zf:
        zf.writestr('word/document.xml', document_xml)
    archivo.seek(0)
    return archivo


class TemplateImporterTests(SimpleTestCase):
    def test_extraer_parrafos_docx(self):
        archivo = crear_docx_minimo(['RM DE RODILLA', 'TECNICA', 'Texto tecnico'])

        parrafos = extraer_parrafos_docx(archivo)

        self.assertEqual(parrafos, ['RM DE RODILLA', 'TECNICA', 'Texto tecnico'])

    def test_importar_plantilla_docx_sin_conclusion(self):
        archivo = crear_docx_minimo([
            'RM DE RODILLA',
            'TECNICA',
            'Se exploro la rodilla con secuencias habituales.',
            'HALLAZGOS',
            'Meniscos de configuracion habitual.',
            'No se observa derrame articular.',
        ])

        data = importar_plantilla_docx(archivo)

        self.assertEqual(data['titulo'], 'RM DE RODILLA')
        self.assertEqual(data['seccion_tecnica'], 'Se exploro la rodilla con secuencias habituales.')
        self.assertEqual(data['comentarios_base'], [
            'Meniscos de configuracion habitual.',
            'No se observa derrame articular.',
        ])
        nombres = [s['nombre'] for s in data['estructura_documento']['secciones']]
        self.assertEqual(nombres, ['TITULO', 'TECNICA', 'HALLAZGOS'])
        self.assertNotIn('CONCLUSION', nombres)

    def test_importar_plantilla_docx_con_comentario_y_conclusion(self):
        archivo = crear_docx_minimo([
            'RM DE HOMBRO',
            'COMENTARIO',
            'Manguito rotador conservado.',
            'CONCLUSION',
            'Estudio dentro de parametros normales.',
        ])

        data = importar_plantilla_docx(archivo)

        nombres = [s['nombre'] for s in data['estructura_documento']['secciones']]
        self.assertEqual(nombres, ['TITULO', 'HALLAZGOS', 'CONCLUSION'])
        self.assertEqual(data['comentarios_base'], ['Manguito rotador conservado.'])

    def test_importar_plantilla_docx_con_headers_inline(self):
        archivo = crear_docx_minimo([
            'RESONANCIA MAGNETICA DE CEREBRO CON DIFUSION',
            'Tecnica: Se realizo estudio de encefalo con secuencias habituales y difusion.',
            'Informe: Sistema ventricular de forma y tamano conservados.',
            'No se observan lesiones con restriccion en difusion.',
        ])

        data = importar_plantilla_docx(archivo)

        self.assertEqual(data['seccion_tecnica'], 'Se realizo estudio de encefalo con secuencias habituales y difusion.')
        self.assertEqual(data['comentarios_base'], [
            'Sistema ventricular de forma y tamano conservados.',
            'No se observan lesiones con restriccion en difusion.',
        ])
        nombres = [s['nombre'] for s in data['estructura_documento']['secciones']]
        self.assertEqual(nombres, ['TITULO', 'TECNICA', 'HALLAZGOS'])

    def test_importar_plantilla_docx_sin_headers_usa_resto_como_hallazgos(self):
        archivo = crear_docx_minimo([
            'RM CEREBRO',
            'Sistema ventricular conservado.',
            'No se reconocen lesiones focales.',
        ])

        data = importar_plantilla_docx(archivo)

        self.assertEqual(data['titulo'], 'RM CEREBRO')
        self.assertEqual(data['comentarios_base'], [
            'Sistema ventricular conservado.',
            'No se reconocen lesiones focales.',
        ])
        nombres = [s['nombre'] for s in data['estructura_documento']['secciones']]
        self.assertEqual(nombres, ['TITULO', 'HALLAZGOS'])

    def test_importar_plantilla_docx_infiere_tecnica_sin_header(self):
        archivo = crear_docx_minimo([
            'RESONANCIA MAGNETICA DE CEREBRO CON DIFUSION',
            'Se exploro la region solicitada con secuencias que ponderan tiempos de relajacion tisulares T1, T2 y FLAIR con registro en planos axial, coronal y sagital. Se adiciono secuencia de difusion.',
            'Sistema ventricular de forma, tamano y posicion conservados.',
            'Espacios subaracnoideos cisternales y corticales dentro de limites normales.',
            'No se observan alteraciones en la senal de la sustancia gris ni blanca encefalicas.',
            'La secuencia de difusion no mostro alteraciones.',
        ])

        data = importar_plantilla_docx(archivo)

        self.assertEqual(
            data['seccion_tecnica'],
            'Se exploro la region solicitada con secuencias que ponderan tiempos de relajacion tisulares T1, T2 y FLAIR con registro en planos axial, coronal y sagital. Se adiciono secuencia de difusion.'
        )
        self.assertEqual(data['comentarios_base'], [
            'Sistema ventricular de forma, tamano y posicion conservados.',
            'Espacios subaracnoideos cisternales y corticales dentro de limites normales.',
            'No se observan alteraciones en la senal de la sustancia gris ni blanca encefalicas.',
            'La secuencia de difusion no mostro alteraciones.',
        ])
        nombres = [s['nombre'] for s in data['estructura_documento']['secciones']]
        self.assertEqual(nombres, ['TITULO', 'TECNICA', 'HALLAZGOS'])

    def test_importar_plantilla_txt(self):
        archivo = BytesIO(
            b'RM DE RODILLA\nTECNICA\nTecnica base\nHALLAZGOS\nMeniscos normales.'
        )
        archivo.name = 'rodilla.txt'

        data = importar_plantilla_archivo(archivo)

        self.assertEqual(data['titulo'], 'RM DE RODILLA')
        self.assertEqual(data['seccion_tecnica'], 'Tecnica base')
        self.assertEqual(data['comentarios_base'], ['Meniscos normales.'])

    def test_importar_plantilla_desde_texto_pegado(self):
        data = importar_plantilla_texto(
            'RM DE CEREBRO\n'
            'Tecnica: Tecnica base\n'
            'Hallazgos: Sistema ventricular conservado.\n'
            'No se observan lesiones focales.'
        )

        self.assertEqual(data['titulo'], 'RM DE CEREBRO')
        self.assertEqual(data['seccion_tecnica'], 'Tecnica base')
        self.assertEqual(data['comentarios_base'], [
            'Sistema ventricular conservado.',
            'No se observan lesiones focales.',
        ])

    def test_importar_plantilla_markdown_limpia_encabezados(self):
        archivo = BytesIO(
            b'# RM DE CEREBRO\n## Tecnica\nSe realizo estudio con difusion.\n## Informe\n- Sistema ventricular conservado.'
        )
        archivo.name = 'cerebro.md'

        data = importar_plantilla_archivo(archivo)

        self.assertEqual(data['titulo'], 'RM DE CEREBRO')
        self.assertEqual(data['seccion_tecnica'], 'Se realizo estudio con difusion.')
        self.assertEqual(data['comentarios_base'], ['Sistema ventricular conservado.'])

    def test_importar_plantilla_html(self):
        archivo = BytesIO(
            b'<h1>RM DE HOMBRO</h1><p>Tecnica: Tecnica base</p><p>Hallazgos: Manguito rotador conservado.</p>'
        )
        archivo.name = 'hombro.html'

        data = importar_plantilla_archivo(archivo)

        self.assertEqual(data['titulo'], 'RM DE HOMBRO')
        self.assertEqual(data['seccion_tecnica'], 'Tecnica base')
        self.assertEqual(data['comentarios_base'], ['Manguito rotador conservado.'])

    def test_importar_plantilla_rtf(self):
        archivo = BytesIO(
            b'{\\rtf1 RM DE TOBILLO\\par TECNICA\\par Tecnica base\\par HALLAZGOS\\par Tendones conservados.}'
        )
        archivo.name = 'tobillo.rtf'

        data = importar_plantilla_archivo(archivo)

        self.assertEqual(data['titulo'], 'RM DE TOBILLO')
        self.assertEqual(data['seccion_tecnica'], 'Tecnica base')
        self.assertEqual(data['comentarios_base'], ['Tendones conservados.'])

    def test_importar_doc_basado_en_rtf(self):
        archivo = BytesIO(
            b'{\\rtf1 RM DE CODO\\par TECNICA\\par Tecnica base\\par HALLAZGOS\\par Tendones conservados.}'
        )
        archivo.name = 'codo.doc'

        data = importar_plantilla_archivo(archivo)

        self.assertEqual(data['titulo'], 'RM DE CODO')
        self.assertEqual(data['seccion_tecnica'], 'Tecnica base')
        self.assertEqual(data['comentarios_base'], ['Tendones conservados.'])

    def test_rechaza_doc_binario_legacy(self):
        archivo = BytesIO(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1contenido binario word')
        archivo.name = 'legacy.doc'

        with self.assertRaises(DocxTemplateImportError):
            importar_plantilla_archivo(archivo)

    def test_rechaza_archivo_no_docx(self):
        with self.assertRaises(DocxTemplateImportError):
            extraer_parrafos_docx(BytesIO(b'no es zip'))

    def test_rechaza_formato_no_soportado(self):
        archivo = BytesIO(b'contenido')
        archivo.name = 'plantilla.pdf'

        with self.assertRaises(DocxTemplateImportError):
            importar_plantilla_archivo(archivo)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver', 'localhost'])
class ImportarPlantillaDocxViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='importador_docx',
            email='importador@example.com',
            password='testpass123',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_importador_renderiza(self):
        response = self.client.get(reverse('dictado_informes:plantilla_estructurada_import_docx'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Importar Plantilla')

    def test_importador_genera_preview_desde_docx(self):
        archivo = SimpleUploadedFile(
            'rodilla.docx',
            crear_docx_minimo([
                'RM DE RODILLA',
                'TECNICA',
                'Tecnica base',
                'HALLAZGOS',
                'Meniscos normales.',
            ]).getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

        response = self.client.post(
            reverse('dictado_informes:plantilla_estructurada_import_docx'),
            data={'accion': 'preview', 'archivo_docx': archivo},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista previa editable')
        self.assertContains(response, 'Codigo interno automatico')
        self.assertContains(response, 'name="codigo"')
        self.assertContains(response, 'value="100000"')
        self.assertContains(response, 'RM DE RODILLA')
        self.assertContains(response, 'Meniscos normales.')
        self.assertContains(response, 'HALLAZGOS')

    def test_importador_genera_preview_desde_txt(self):
        archivo = SimpleUploadedFile(
            'cerebro.txt',
            b'RM CEREBRO\nTecnica: Tecnica base\nHallazgos: Sistema ventricular conservado.',
            content_type='text/plain',
        )

        response = self.client.post(
            reverse('dictado_informes:plantilla_estructurada_import_docx'),
            data={'accion': 'preview', 'archivo_docx': archivo},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista previa editable')
        self.assertContains(response, 'RM CEREBRO')
        self.assertContains(response, 'Sistema ventricular conservado.')

    def test_importador_genera_preview_desde_texto_pegado(self):
        response = self.client.post(
            reverse('dictado_informes:plantilla_estructurada_import_docx'),
            data={
                'accion': 'preview',
                'texto_plantilla': (
                    'RM CEREBRO\n'
                    'Tecnica: Tecnica base\n'
                    'Hallazgos: Sistema ventricular conservado.'
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vista previa editable')
        self.assertContains(response, 'RM CEREBRO')
        self.assertContains(response, 'Sistema ventricular conservado.')

    def test_importador_requiere_archivo_o_texto(self):
        response = self.client.post(
            reverse('dictado_informes:plantilla_estructurada_import_docx'),
            data={'accion': 'preview'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sube un archivo o pega el texto de la plantilla')

    def test_generador_codigo_interno_ignora_codigos_textuales(self):
        PlantillaEstructurada.objects.create(
            codigo='RODILLA_NORMAL',
            nombre='Rodilla normal',
            titulo='RM DE RODILLA',
            seccion_tecnica='Tecnica base',
            comentarios_base=[],
            creada_por=self.user,
            origen='user',
        )

        self.assertEqual(_generar_codigo_interno_plantilla(), '100000')

        PlantillaEstructurada.objects.create(
            codigo='100000',
            nombre='Codigo numerico',
            titulo='RM DE RODILLA',
            seccion_tecnica='Tecnica base',
            comentarios_base=[],
            creada_por=self.user,
            origen='user',
        )

        self.assertEqual(_generar_codigo_interno_plantilla(), '100001')

    def test_importador_guarda_preview_confirmado(self):
        response = self.client.post(
            reverse('dictado_informes:plantilla_estructurada_import_docx'),
            data={
                'accion': 'guardar',
                'codigo': '100000',
                'nombre': 'RM Rodilla guardada',
                'titulo': 'RM DE RODILLA',
                'seccion_tecnica': 'Tecnica base',
                'comentarios_base_texto': 'Meniscos normales.',
                'guia_estilo': '',
                'modo_estructura': PlantillaEstructurada.MODO_ESTRUCTURA_ESTRICTA,
                'permitir_secciones_nuevas': '',
                'estructura_documento_texto': (
                    '{"secciones": ['
                    '{"nombre": "TITULO", "tipo": "titulo", "contenido": "RM DE RODILLA"},'
                    '{"nombre": "HALLAZGOS", "tipo": "hallazgos", "lineas_base": ["Meniscos normales."]}'
                    ']}'
                ),
                'activa': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        plantilla = PlantillaEstructurada.objects.get(codigo='100000')
        self.assertEqual(plantilla.creada_por, self.user)
        self.assertEqual(plantilla.origen, 'user')
        self.assertEqual(plantilla.comentarios_base, ['Meniscos normales.'])
        self.assertFalse(plantilla.tiene_seccion('CONCLUSION'))
