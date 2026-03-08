"""
Tests del Diccionario Médico y Comandos de Voz
==============================================
Tests para TerminoMedico.aplicar_correcciones() y procesar_comandos_voz()

Fecha: 2026-03-08
Cobertura esperada: ~80% del código de TerminoMedico
"""

from django.test import TestCase
from dictado_informes.models import TerminoMedico, CategoriaTerminoMedico


class TestTerminoMedico(TestCase):
    """Tests para el diccionario médico y correcciones automáticas"""
    
    def setUp(self):
        """Crear términos de prueba"""
        self.termino1 = TerminoMedico.objects.create(
            termino_incorrecto='gonartrosis trick compartimental',
            termino_correcto='gonartrosis tricompartimental',
            categoria=CategoriaTerminoMedico.ORTOPEDIA,
            activo=True
        )
        
        self.termino2 = TerminoMedico.objects.create(
            termino_incorrecto='meniscos normales',
            termino_correcto='meniscos de configuración habitual',
            categoria=CategoriaTerminoMedico.RADIOLOGIA,
            activo=True
        )
        
        self.termino_inactivo = TerminoMedico.objects.create(
            termino_incorrecto='viejo término',
            termino_correcto='nuevo término',
            activo=False
        )
    
    def test_aplicar_correcciones_basico(self):
        """Prueba corrección básica de un término"""
        texto = "Paciente con gonartrosis trick compartimental."
        resultado, correcciones = TerminoMedico.aplicar_correcciones(texto)
        
        self.assertIn('gonartrosis tricompartimental', resultado)
        self.assertEqual(len(correcciones), 1)
        self.assertEqual(correcciones[0]['de'], 'gonartrosis trick compartimental')
        self.assertEqual(correcciones[0]['a'], 'gonartrosis tricompartimental')
    
    def test_aplicar_correcciones_case_insensitive(self):
        """Prueba que funciona sin importar mayúsculas/minúsculas"""
        texto = "GONARTROSIS TRICK COMPARTIMENTAL grado III"
        resultado, correcciones = TerminoMedico.aplicar_correcciones(texto)
        
        self.assertIn('tricompartimental', resultado.lower())
    
    def test_aplicar_correcciones_multiples(self):
        """Prueba múltiples correcciones en un texto"""
        texto = "gonartrosis trick compartimental, meniscos normales"
        resultado, correcciones = TerminoMedico.aplicar_correcciones(texto)
        
        self.assertEqual(len(correcciones), 2)
        self.assertIn('tricompartimental', resultado)
        self.assertIn('configuración habitual', resultado)
    
    def test_terminos_inactivos_no_aplican(self):
        """Términos inactivos no deben aplicarse"""
        texto = "viejo término"
        resultado, correcciones = TerminoMedico.aplicar_correcciones(texto)
        
        self.assertEqual(resultado, texto)
        self.assertEqual(len(correcciones), 0)
    
    def test_incrementa_frecuencia_uso(self):
        """Verifica que se incrementa frecuencia al usar un término"""
        frecuencia_inicial = self.termino1.frecuencia_uso
        
        texto = "gonartrosis trick compartimental"
        TerminoMedico.aplicar_correcciones(texto)
        
        self.termino1.refresh_from_db()
        self.assertEqual(self.termino1.frecuencia_uso, frecuencia_inicial + 1)
    
    def test_procesar_comandos_voz_punto(self):
        """Prueba comando 'punto'"""
        texto = "Hallazgo uno punto Hallazgo dos"
        resultado = TerminoMedico.procesar_comandos_voz(texto)
        
        # Verifica que hay un punto (puede tener espacio antes o no)
        self.assertIn('.', resultado)
        # El resultado puede variar según implementación
        self.assertIn('Hallazgo dos', resultado)
    
    def test_procesar_comandos_voz_nueva_linea(self):
        """Prueba comando 'nueva línea'"""
        texto = "Línea uno nueva línea Línea dos"
        resultado = TerminoMedico.procesar_comandos_voz(texto)
        
        self.assertIn('\n', resultado)
    
    def test_procesar_comandos_voz_punto_seguido(self):
        """Prueba que 'punto seguido' no agrega salto de línea"""
        texto = "Frase uno punto seguido frase dos"
        resultado = TerminoMedico.procesar_comandos_voz(texto)
        
        self.assertIn('. ', resultado)
        self.assertNotIn('\n', resultado)
    
    def test_procesar_comandos_voz_grado_romano(self):
        """Prueba conversión automática grado 1/2/3/4 a I/II/III/IV"""
        texto = "gonartrosis grado 3"
        resultado = TerminoMedico.procesar_comandos_voz(texto)
        
        self.assertIn('grado III', resultado)
        self.assertNotIn('grado 3', resultado)
    
    def test_procesar_comandos_voz_limpiar_artefactos(self):
        """Prueba limpieza de artefactos de Whisper"""
        texto = "Hallazgo uno., Hallazgo dos"
        resultado = TerminoMedico.procesar_comandos_voz(texto)
        
        # Debe limpiar "., " → ".\n"
        self.assertNotIn('.,', resultado)
    
    def test_procesar_comandos_voz_varios_comandos(self):
        """Prueba múltiples comandos en un mismo texto"""
        texto = "Título nueva línea Párrafo punto Siguiente frase"
        resultado = TerminoMedico.procesar_comandos_voz(texto)
        
        # Debe tener salto de línea y punto
        self.assertIn('\n', resultado)
        self.assertIn('.', resultado)


class TestTerminoMedicoAdmin(TestCase):
    """Tests para funcionalidad administrativa"""
    
    def test_str_representation(self):
        """Prueba representación en string"""
        termino = TerminoMedico.objects.create(
            termino_incorrecto='test_inc',
            termino_correcto='test_corr'
        )
        
        self.assertEqual(str(termino), 'test_inc → test_corr')
    
    def test_creacion_con_categoria(self):
        """Prueba que se puede crear con categoría"""
        termino = TerminoMedico.objects.create(
            termino_incorrecto='test',
            termino_correcto='test correcto',
            categoria=CategoriaTerminoMedico.ANATOMIA
        )
        
        self.assertEqual(termino.categoria, CategoriaTerminoMedico.ANATOMIA)
    
    def test_frecuencia_uso_default(self):
        """Prueba que frecuencia_uso empieza en 0"""
        termino = TerminoMedico.objects.create(
            termino_incorrecto='test',
            termino_correcto='test corr'
        )
        
        self.assertEqual(termino.frecuencia_uso, 0)
