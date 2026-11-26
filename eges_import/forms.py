from django import forms
from django.core.exceptions import ValidationError
import openpyxl

from .services import leer_encabezados_eges
from .services_netterm import MAX_BYTES_NETTERM, preparar_preview_netterm
from .models import ConciliacionRevision, ImportBatch, NettermLote
from .services_conciliacion import MAX_LOTES_NETTERM_CRUCE, ESTADOS_CRUCE


CLASE_ARCHIVO_EXCEL = (
    'block w-full text-sm text-gray-900 dark:text-gray-100 '
    'bg-gray-50 dark:bg-gray-800 border border-gray-300 dark:border-gray-600 '
    'rounded-lg cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500'
)


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
            'class': CLASE_ARCHIVO_EXCEL,
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


class PreviewNettermForm(forms.Form):
    archivo = forms.FileField(
        label='Libro Netterm',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx',
            'class': CLASE_ARCHIVO_EXCEL,
        }),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if archivo.size > MAX_BYTES_NETTERM:
            raise ValidationError('El archivo Netterm supera el limite de 10 MB.')
        try:
            self.resultado_preview = preparar_preview_netterm(archivo)
        except ValidationError:
            raise
        except Exception:
            raise ValidationError('No se pudo interpretar el libro Netterm; revisa el formato de la exportacion.') from None
        return archivo


class GuardarNettermForm(forms.Form):
    archivo = forms.FileField(
        label='Mismo libro Netterm del preview',
        widget=forms.FileInput(attrs={'accept': '.xlsx', 'class': CLASE_ARCHIVO_EXCEL}),
    )
    preview_token = forms.CharField(widget=forms.HiddenInput())
    motivo = forms.CharField(
        max_length=2000, strip=True, label='Motivo de carga',
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'w-full rounded-md border border-gray-500 bg-gray-800 p-2 text-white'}),
    )
    confirmar = forms.BooleanField(label='Confirmo guardar estas filas de origen, sin consolidar ni liquidar')

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        if not archivo.name.lower().endswith('.xlsx') or archivo.size > MAX_BYTES_NETTERM:
            raise ValidationError('Selecciona el XLSX Netterm del preview, hasta 10 MB.')
        return archivo


class PreviewConciliacionForm(forms.Form):
    batch_eges = forms.ModelChoiceField(queryset=ImportBatch.objects.none(), label='Lote EGES', required=False)
    lotes_eges = forms.ModelMultipleChoiceField(
        queryset=ImportBatch.objects.none(), label='Lotes EGES', widget=forms.CheckboxSelectMultiple(),
    )
    fecha_desde = forms.DateField(required=False, label='Desde', widget=forms.DateInput(attrs={'type': 'date'}))
    fecha_hasta = forms.DateField(required=False, label='Hasta', widget=forms.DateInput(attrs={'type': 'date'}))
    lotes_netterm = forms.ModelMultipleChoiceField(
        queryset=NettermLote.objects.none(), label='Lotes Netterm',
        widget=forms.CheckboxSelectMultiple(),
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todas las categorías'), ('EXCEPCIONES', 'Sólo excepciones de producción'),
                 ('ALERTAS_ESTADO', 'Correspondencia única con alerta de estado')] + [(estado, estado) for estado in ESTADOS_CRUCE],
        required=False, label='Resultado del cruce',
    )

    def __init__(self, *args, **kwargs):
        data = args[0] if args else kwargs.get('data')
        if data and data.get('batch_eges') and not data.get('lotes_eges'):
            data = data.copy()
            if hasattr(data, 'setlist'):
                data.setlist('lotes_eges', [data['batch_eges']])
            else:
                data['lotes_eges'] = [data['batch_eges']]
            data.pop('batch_eges', None)
            if args:
                args = (data, *args[1:])
            else:
                kwargs['data'] = data
        super().__init__(*args, **kwargs)
        self.fields['batch_eges'].queryset = ImportBatch.objects.order_by('-fecha_importacion', '-pk')
        self.fields['batch_eges'].label_from_instance = lambda lote: f'EGES #{lote.pk} - {lote.archivo_nombre}'
        self.fields['batch_eges'].widget.attrs['class'] = 'w-full rounded-md border border-gray-500 bg-gray-800 p-2 text-white'
        self.fields['lotes_eges'].queryset = ImportBatch.objects.order_by('-fecha_importacion', '-pk')
        self.fields['lotes_eges'].label_from_instance = lambda lote: f'EGES #{lote.pk} - {lote.archivo_nombre}'
        self.fields['lotes_netterm'].queryset = NettermLote.objects.order_by('-fecha_importacion', '-pk')
        self.fields['lotes_netterm'].label_from_instance = lambda lote: f'Netterm #{lote.pk} - {lote.archivo_nombre}'
        self.fields['estado'].widget.attrs['class'] = 'w-full rounded-md border border-gray-500 bg-gray-800 p-2 text-white'
        for campo in ('fecha_desde', 'fecha_hasta'):
            self.fields[campo].widget.attrs['class'] = 'w-full rounded-md border border-gray-500 bg-gray-800 p-2 text-white'

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get('fecha_desde'), datos.get('fecha_hasta')
        if desde and hasta and desde > hasta:
            self.add_error('fecha_hasta', 'La fecha final debe ser igual o posterior a la inicial.')
        if datos.get('batch_eges'):
            self.add_error(None, 'Usa una sola seleccion de lotes EGES.')
        return datos


class RevisionConciliacionForm(forms.Form):
    batch_eges_id = forms.IntegerField(widget=forms.HiddenInput())
    lote_netterm_ids = forms.CharField(widget=forms.HiddenInput())
    fila_netterm_id = forms.IntegerField(widget=forms.HiddenInput())
    fila_eges_id = forms.IntegerField(widget=forms.HiddenInput())
    firma_snapshot = forms.CharField(min_length=64, max_length=64, widget=forms.HiddenInput())
    decision = forms.ChoiceField(
        choices=ConciliacionRevision.DECISION_CHOICES,
        label='Decision humana',
        widget=forms.Select(attrs={'class': 'rounded-md border border-gray-500 bg-gray-800 p-2 text-white'}),
    )
    motivo = forms.CharField(
        min_length=8, max_length=2000, label='Motivo de revision',
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'w-full rounded-md border border-gray-500 bg-gray-800 p-2 text-white',
            'required': True,
        }),
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todas las categorias'), ('EXCEPCIONES', 'Solo excepciones de produccion'),
                 ('ALERTAS_ESTADO', 'Correspondencia unica con alerta de estado')] + [(estado, estado) for estado in ESTADOS_CRUCE],
        required=False, widget=forms.HiddenInput(),
    )

    def clean_lote_netterm_ids(self):
        try:
            ids = [int(valor) for valor in self.cleaned_data['lote_netterm_ids'].split(',')]
        except ValueError:
            raise ValidationError('La seleccion Netterm no es valida.') from None
        if not ids or len(ids) > MAX_LOTES_NETTERM_CRUCE or len(ids) != len(set(ids)):
            raise ValidationError('La seleccion debe incluir entre 1 y 10 lotes Netterm distintos.')
        return ids
