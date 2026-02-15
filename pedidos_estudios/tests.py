"""
Tests básicos para pedidos_estudios.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import PacienteEstudio, TipoEstudio, PedidoEstudio
from .services.email_parser import EmailParser

User = get_user_model()


class PacienteEstudioTestCase(TestCase):
    """Tests para modelo PacienteEstudio."""
    
    def setUp(self):
        self.paciente = PacienteEstudio.objects.create(
            nombre_completo='Juan Pérez',
            dni='12345678',
            historia_clinica='HC001',
            habitacion='302A',
            cama='1'
        )
    
    def test_crear_paciente(self):
        """Test creación de paciente."""
        self.assertEqual(self.paciente.nombre_completo, 'Juan Pérez')
        self.assertEqual(self.paciente.dni, '12345678')
    
    def test_str_paciente(self):
        """Test representación string de paciente."""
        self.assertIn('Juan Pérez', str(self.paciente))
        self.assertIn('302A', str(self.paciente))


class PedidoEstudioTestCase(TestCase):
    """Tests para modelo PedidoEstudio."""
    
    def setUp(self):
        self.paciente = PacienteEstudio.objects.create(
            nombre_completo='María García',
            historia_clinica='HC002'
        )
        
        self.tipo_estudio = TipoEstudio.objects.create(
            nombre='Radiografía de Tórax',
            modalidad='RX'
        )
        
        self.pedido = PedidoEstudio.objects.create(
            paciente=self.paciente,
            tipo_estudio=self.tipo_estudio,
            descripcion_estudio='Radiografía de tórax frente y perfil',
            medico_solicitante='Dr. González',
            prioridad='URGENTE'
        )
    
    def test_crear_pedido(self):
        """Test creación de pedido."""
        self.assertEqual(self.pedido.estado, 'PENDIENTE')
        self.assertEqual(self.pedido.prioridad, 'URGENTE')
    
    def test_marcar_como_procesado(self):
        """Test marcar pedido como procesado."""
        self.pedido.marcar_como_procesado()
        self.assertEqual(self.pedido.estado, 'PROCESANDO')
        self.assertFalse(self.pedido.requiere_revision)
    
    def test_str_pedido(self):
        """Test representación string de pedido."""
        self.assertIn('María García', str(self.pedido))


class EmailParserTestCase(TestCase):
    """Tests para EmailParser."""
    
    def setUp(self):
        self.parser = EmailParser()
    
    def test_extraer_nombre(self):
        """Test extracción de nombre de paciente."""
        texto = "Paciente: Juan Pérez\nDNI: 12345678"
        datos = self.parser._extraer_datos_paciente(texto)
        self.assertIsNotNone(datos['nombre_completo'])
    
    def test_detectar_urgencia(self):
        """Test detección de prioridad urgente."""
        texto = "Estudio URGENTE para paciente"
        email_data = {'asunto': 'Pedido urgente', 'adjuntos': []}
        prioridad = self.parser._detectar_prioridad(texto, email_data)
        self.assertEqual(prioridad, 'URGENTE')
    
    def test_clasificar_tipo_estudio(self):
        """Test clasificación de tipo de estudio."""
        tipo = self.parser._clasificar_tipo_estudio('Ecocardiograma transtorácico')
        self.assertEqual(tipo, 'ecografía')
        
        tipo = self.parser._clasificar_tipo_estudio('Ecodoppler de MMII')
        self.assertEqual(tipo, 'ecografía')
        
        tipo = self.parser._clasificar_tipo_estudio('Doppler carotídeo')
        self.assertEqual(tipo, 'ecografía')
