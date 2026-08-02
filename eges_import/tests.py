from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from .forms import ImportarEGESForm
from .models import EgesRow, ImportBatch
from .services import procesar_excel_eges


def _archivo_eges_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Atendidos'
    ws.append([
        'Dni',
        'Numero  Afiliado',
        'Centro',
        'Fecha Turno',
        'Hora Desde',
        'Hora Hasta',
        'Tipo Atencion',
        'Medico Informante',
        'Medico Actuante',
        'Paciente',
        'Codigo OS',
        'Obra Social',
        'Equipo',
        'Estado Turno',
        'Código Practica',
        'Practica',
        'Cantidad',
        'Servicio',
        'Estado Informe',
        'Tipo de turno',
        'Tipo de paciente',
        'Region del informe',
    ])
    ws.append([
        '37933118',
        '2052113',
        'Sanatorio Colegiales',
        '01/05/2026',
        '09:45',
        '10:00',
        'Ambulatorio',
        'Médico No Especificado',
        'TOMALA BERNABE FABIAN HOLGER',
        'NIZ MICAELA YANINA',
        '1967',
        'SANCOR SALUD (C)',
        'P - Ecografo - AFFINITI 30',
        'Informado',
        '180112/0',
        'ECOGRAFIA COMPLETA DE ABDOMEN',
        1,
        'Ecografia',
        '-',
        'Normal',
        'Adulto',
        '-',
    ])
    ws.append([
        '37933118',
        '2052113',
        'Sanatorio Colegiales',
        '01/05/2026',
        '09:45',
        '10:00',
        'Ambulatorio',
        'Médico No Especificado',
        'TOMALA BERNABE FABIAN HOLGER',
        'NIZ MICAELA YANINA',
        '1967',
        'SANCOR SALUD (C)',
        'P - Ecografo - AFFINITI 30',
        'Informado',
        '3005554/0',
        'CAMISOLIN',
        1,
        'Ecografia',
        '-',
        'Normal',
        'Adulto',
        '-',
    ])
    contenido = BytesIO()
    wb.save(contenido)
    contenido.seek(0)
    return contenido.getvalue()


class ImportacionEgesAuditoriaPacsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='admin', password='x')

    def test_importa_campos_operativos_y_descarta_insumos(self):
        archivo = SimpleUploadedFile(
            'Turnos-Mayo-ECO.xlsx',
            _archivo_eges_xlsx(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        batch = ImportBatch.objects.create(usuario=self.user, archivo_nombre=archivo.name)

        resultado = procesar_excel_eges(archivo, batch)

        self.assertEqual(resultado['creadas'], 1)
        self.assertEqual(EgesRow.objects.count(), 1)
        fila = EgesRow.objects.get()
        self.assertEqual(fila.dni_paciente, '37933118')
        self.assertEqual(fila.historia_clinica, '37933118')
        self.assertEqual(fila.numero_afiliado, '2052113')
        self.assertEqual(fila.apellido_nombre, 'NIZ MICAELA YANINA')
        self.assertEqual(fila.tipo_atencion, 'Ambulatorio')
        self.assertEqual(fila.hora_turno.strftime('%H:%M'), '09:45')
        self.assertEqual(fila.hora_hasta.strftime('%H:%M'), '10:00')
        self.assertEqual(fila.codigo_practica, '180112/0')
        self.assertEqual(fila.practica, 'ECOGRAFIA COMPLETA DE ABDOMEN')
        self.assertEqual(fila.medico_informante, 'TOMALA BERNABE FABIAN HOLGER')
        self.assertEqual(fila.medico_actuante, 'TOMALA BERNABE FABIAN HOLGER')
        self.assertEqual(fila.estado_informe, '-')
        self.assertEqual(fila.tipo_turno, 'Normal')
        self.assertEqual(fila.tipo_paciente, 'Adulto')
        self.assertEqual(fila.region_informe, '-')

    def test_formulario_acepta_xlsx_eges_real(self):
        archivo = SimpleUploadedFile(
            'Turnos-Mayo-ECO.xlsx',
            _archivo_eges_xlsx(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        form = ImportarEGESForm(files={'archivo': archivo})

        self.assertTrue(form.is_valid(), form.errors)
