from pathlib import Path

from django import forms

from .models import ActividadCurricular, DocumentoActividadCurricular


INPUT_CLASS = (
    'mt-1 block w-full rounded-lg border-gray-300 bg-white text-sm '
    'focus:border-medical-primary focus:ring-medical-primary'
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        limpiar_archivo = super().clean
        if isinstance(data, (list, tuple)):
            return [limpiar_archivo(archivo, initial) for archivo in data]
        return [limpiar_archivo(data, initial)] if data else []


class ActividadCurricularForm(forms.ModelForm):
    documentos = MultipleFileField(
        required=False,
        label='Certificados o evidencias',
        widget=MultipleFileInput(
            attrs={
                'class': 'sr-only',
                'multiple': True,
                'accept': (
                    '.jpg,.jpeg,.png,.webp,.heic,.heif,.pdf,.doc,.docx,'
                    '.ppt,.pptx,.xls,.xlsx'
                ),
            }
        ),
        help_text='Podés adjuntar varios archivos. Se almacenan de forma privada.',
    )

    class Meta:
        model = ActividadCurricular
        fields = [
            'tipo',
            'titulo',
            'institucion',
            'fecha_inicio',
            'fecha_fin',
            'descripcion',
            'enlace',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': INPUT_CLASS}),
            'titulo': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'institucion': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'fecha_inicio': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': INPUT_CLASS, 'type': 'date'},
            ),
            'fecha_fin': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': INPUT_CLASS, 'type': 'date'},
            ),
            'descripcion': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4}),
            'enlace': forms.URLInput(attrs={'class': INPUT_CLASS}),
        }
        labels = {
            'titulo': 'Título de la actividad',
            'institucion': 'Institución o ámbito',
            'fecha_inicio': 'Fecha de realización o inicio',
            'fecha_fin': 'Fecha de finalización',
            'descripcion': 'Descripción breve',
            'enlace': 'Enlace relacionado',
        }
        help_texts = {
            'tipo': (
                'Las rotaciones externas se registran por ahora como antecedente '
                'curricular y todavía no modifican el sorteo de guardias.'
            ),
        }

    def clean_documentos(self):
        archivos = self.files.getlist('documentos')
        permitidas = set(DocumentoActividadCurricular.EXTENSIONES_PERMITIDAS)
        for archivo in archivos:
            extension = Path(archivo.name).suffix.lower().lstrip('.')
            if extension not in permitidas:
                raise forms.ValidationError(
                    f'El archivo {archivo.name} tiene una extensión no permitida.'
                )
        return archivos


class RevisionActividadForm(forms.Form):
    accion = forms.ChoiceField(
        choices=(('VALIDAR', 'Validar'), ('OBSERVAR', 'Observar')),
        widget=forms.HiddenInput,
    )
    observacion = forms.CharField(
        required=False,
        label='Devolución al residente',
        widget=forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 4}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('accion') == 'OBSERVAR' and not cleaned.get('observacion', '').strip():
            self.add_error(
                'observacion',
                'Indicá qué debe corregir o completar el residente.',
            )
        return cleaned
