from django import forms
from django.core.exceptions import ValidationError
import openpyxl
from datetime import datetime


class ImportarEGESForm(forms.Form):
    """
    Formulario para subir un archivo Excel EGES.
    Valida que sea un Excel válido y que tenga las columnas esperadas.
    """
    archivo = forms.FileField(
        label='Archivo Excel EGES',
        help_text='Suba un archivo .xlsx con datos EGES',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'
        })
    )
    
    # Columnas esperadas en el Excel (ajustar según el formato real)
    COLUMNAS_ESPERADAS = [
        'Nro. Turno',
        'Fecha Turno',
        'Hora Turno',
        'Centro de Atención',
        'Historia Clínica',
        'Apellido y Nombre',
        'Servicio',
        'Equipo',
        'Estado Turno',
    ]
    
    def clean_archivo(self):
        archivo = self.cleaned_data.get('archivo')
        
        if not archivo:
            raise ValidationError('Debe seleccionar un archivo.')
        
        # Validar extensión
        nombre = archivo.name.lower()
        if not nombre.endswith('.xlsx'):
            raise ValidationError(
                'El archivo debe ser un Excel en formato .xlsx (Excel 2007 o posterior). '
                'Si tiene un archivo .xls antiguo, ábralo en Excel y guárdelo como .xlsx'
            )
        
        # Validar tamaño (máximo 10MB)
        max_size = 10 * 1024 * 1024  # 10 MB
        if archivo.size > max_size:
            raise ValidationError(f'El archivo es demasiado grande. Máximo permitido: 10 MB')
        
        # Validar que sea un Excel válido y tenga las columnas esperadas
        try:
            wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
            ws = wb.active
            
            # Leer primera fila (encabezados)
            headers = []
            for cell in ws[1]:
                headers.append(str(cell.value).strip() if cell.value else '')
            
            # Verificar que tenga al menos algunas columnas críticas
            columnas_criticas = ['Historia Clínica', 'Servicio', 'Estado Turno']
            columnas_encontradas = [col for col in columnas_criticas if col in headers]
            
            if len(columnas_encontradas) < 2:
                raise ValidationError(
                    f'El Excel no tiene las columnas esperadas. '
                    f'Se esperaban columnas como: {", ".join(self.COLUMNAS_ESPERADAS)}'
                )
            
            wb.close()
            
            # Resetear el puntero del archivo para que se pueda leer de nuevo
            archivo.seek(0)
            
        except openpyxl.utils.exceptions.InvalidFileException as e:
            raise ValidationError(
                'El archivo no es un Excel válido en formato .xlsx. '
                'Asegúrese de usar Excel 2007 o posterior y guardar como .xlsx (no .xls)'
            )
        except Exception as e:
            error_msg = str(e).lower()
            if 'zip' in error_msg:
                raise ValidationError(
                    'El archivo no tiene el formato correcto. '
                    'Debe ser un archivo .xlsx (Excel 2007+). '
                    'Si tiene un .xls, ábralo en Excel y use "Guardar como" → "Excel (.xlsx)"'
                )
            raise ValidationError(f'Error al leer el archivo: {str(e)}')
        
        return archivo
