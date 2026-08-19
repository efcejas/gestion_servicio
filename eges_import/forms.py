from django import forms
from django.core.exceptions import ValidationError
import openpyxl

from .services import leer_encabezados_eges


class ImportarEGESForm(forms.Form):
    """
    Formulario para subir un archivo Excel EGES.
    Valida archivos .xls/.xlsx y columnas mínimas del formato real.
    """
    archivo = forms.FileField(
        label='Archivo Excel EGES',
        help_text='Suba un archivo .xls o .xlsx exportado desde EGES',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'
        })
    )

    COLUMNAS_ESPERADAS = [
        'Dni',
        'Fecha Turno',
        'Hora Desde',
        'Centro',
        'Paciente',
        'Medico Informante',
        'Medico Actuante',
        'Estado Turno',
        'Código Practica',
        'Practica',
        'Cantidad',
        'Servicio',
    ]

    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')

        if not archivo:
            raise ValidationError('Debe seleccionar un archivo.')

        nombre = archivo.name.lower()
        if not (nombre.endswith('.xlsx') or nombre.endswith('.xls')):
            raise ValidationError('El archivo debe ser un Excel en formato .xls o .xlsx.')

        max_size = 10 * 1024 * 1024
        if archivo.size > max_size:
            raise ValidationError('El archivo es demasiado grande. Máximo permitido: 10 MB')

        try:
            headers = leer_encabezados_eges(archivo)
            headers_normalizados = {str(col).strip().lower() for col in headers}

            tiene_fecha = 'fecha turno' in headers_normalizados or 'fecha' in headers_normalizados
            tiene_estado = 'estado turno' in headers_normalizados or 'estado' in headers_normalizados
            tiene_practica = 'practica' in headers_normalizados or 'práctica' in headers_normalizados
            tiene_paciente = 'paciente' in headers_normalizados or 'apellido y nombre' in headers_normalizados
            tiene_documento = (
                'dni' in headers_normalizados
                or 'historia clínica' in headers_normalizados
                or 'historia clinica' in headers_normalizados
            )

            if not (tiene_fecha and tiene_estado and tiene_practica and tiene_paciente and tiene_documento):
                raise ValidationError(
                    'El Excel no tiene las columnas esperadas. '
                    f'Se esperaban columnas como: {", ".join(self.COLUMNAS_ESPERADAS)}'
                )

            archivo.seek(0)
        except openpyxl.utils.exceptions.InvalidFileException:
            raise ValidationError('El archivo no es un Excel válido. Use un archivo .xls o .xlsx exportado desde EGES.')
        except Exception as exc:
            error_msg = str(exc).lower()
            if 'zip' in error_msg:
                raise ValidationError('El archivo no tiene el formato correcto. Debe ser un archivo .xls o .xlsx exportado desde EGES.')
            raise ValidationError(f'Error al leer el archivo: {exc}')

        return archivo
