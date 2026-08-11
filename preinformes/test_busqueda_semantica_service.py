from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .busqueda_semantica_service import BusquedaSemanticaInformes
from .models import Preinforme, Region, RevisionPreinforme, TipoEstudio


User = get_user_model()


class BusquedaSemanticaServiceTest(TestCase):
    def setUp(self):
        self.residente = User.objects.create_user(
            username='res_embedding', password='pass123', rol='medico_residente'
        )
        self.revisor = User.objects.create_user(
            username='staff_embedding', password='pass123', rol='medico_staff'
        )
        tipo = TipoEstudio.objects.create(nombre='TC embedding')
        region = Region.objects.create(nombre='Cráneo embedding')
        preinforme = Preinforme.objects.create(
            residente=self.residente,
            numero_estudio='EMB-001',
            tipo_estudio=tipo,
            region=region,
            nombre_paciente='NombrePrivado',
            apellido_paciente='ApellidoPrivado',
            dni_paciente='12345678',
            estado='finalizado',
        )
        self.revision = RevisionPreinforme.objects.create(
            preinforme=preinforme,
            revisor=self.revisor,
            informe_final_html=(
                '<p>NombrePrivado ApellidoPrivado presenta una lesión expansiva cerebral.</p>'
            ),
        )

    @patch('preinformes.busqueda_semantica_service.OpenAI')
    @patch('preinformes.busqueda_semantica_service.config', return_value='fake-key')
    def test_anonimiza_e_indexa_en_formato_binario(self, _config, openai_mock):
        cliente = MagicMock()
        openai_mock.return_value = cliente
        cliente.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[1.0, 0.0, 0.0])]
        )
        servicio = BusquedaSemanticaInformes()

        cantidad = servicio.indexar_revisiones([self.revision])

        self.assertEqual(cantidad, 1)
        texto_enviado = cliente.embeddings.create.call_args.kwargs['input'][0]
        self.assertNotIn('NombrePrivado', texto_enviado)
        self.assertNotIn('ApellidoPrivado', texto_enviado)
        self.assertNotIn('12345678', texto_enviado)
        self.revision.refresh_from_db()
        self.assertEqual(
            servicio.desempaquetar(self.revision.embedding_busqueda),
            (1.0, 0.0, 0.0),
        )

    @patch('preinformes.busqueda_semantica_service.OpenAI')
    @patch('preinformes.busqueda_semantica_service.config', return_value='fake-key')
    def test_recupera_por_similitud_sin_coincidencia_literal(self, _config, openai_mock):
        cliente = MagicMock()
        openai_mock.return_value = cliente
        servicio = BusquedaSemanticaInformes()
        self.revision.embedding_busqueda = servicio.empaquetar([0.9, 0.1, 0.0])
        self.revision.embedding_modelo = servicio.modelo
        self.revision.embedding_fuente_hash = servicio._fuente_hash(
            self.revision.informe_final_texto
        )
        self.revision.save(update_fields=[
            'embedding_busqueda', 'embedding_modelo', 'embedding_fuente_hash'
        ])
        cliente.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(index=0, embedding=[1.0, 0.0, 0.0])]
        )

        resultado = servicio.buscar(
            'tumor cerebral',
            RevisionPreinforme.objects.filter(pk=self.revision.pk),
        )

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['resultados'][0]['preinforme_id'], self.revision.preinforme_id)
        self.assertGreater(resultado['resultados'][0]['similitud'], 0.9)
