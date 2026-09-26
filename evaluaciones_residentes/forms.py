from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import Examen, Opcion, Pregunta


User = get_user_model()


FORM_CONTROL = (
    'w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 '
    'text-sm text-gray-900 focus:border-blue-500 focus:outline-none '
    'focus:ring-2 focus:ring-blue-500'
)


class ResidenteDestinatarioField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, residente):
        nombre = residente.get_full_name().strip() or residente.username
        return f'{nombre} · {residente.anio_residencia or "Sin año"}'


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return super().value_from_datadict(data, files, name)


class MultipleImageField(forms.FileField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [super().clean(item, initial) for item in data]


class ExamenForm(forms.ModelForm):
    ciclo_lectivo = forms.CharField(
        label='Ciclo lectivo',
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': FORM_CONTROL,
            'placeholder': 'Ej.: 2026 o 2026-2027',
        }),
        help_text='El ciclo queda asociado históricamente a esta evaluación.',
    )
    modo_destinatarios = forms.ChoiceField(
        label='¿Quiénes rendirán?',
        choices=Examen.MODO_DESTINATARIOS_CHOICES,
        widget=forms.RadioSelect,
    )
    modo_inicio = forms.ChoiceField(
        label='Inicio de la evaluación',
        choices=Examen.MODO_INICIO_CHOICES,
        widget=forms.RadioSelect,
        help_text='Automático habilita por fecha. Manual requiere que un docente toque Iniciar examen.',
    )
    anios_destinatarios = forms.MultipleChoiceField(
        choices=Examen.ANIOS_RESIDENCIA,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    residentes_destinatarios = ResidenteDestinatarioField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'js-residentes-select',
            'data-placeholder': 'Buscar residentes activos...',
        }),
    )

    class Meta:
        model = Examen
        fields = [
            'titulo',
            'descripcion',
            'instrucciones',
            'ciclo_lectivo',
            'modo_destinatarios',
            'modo_inicio',
            'fecha_apertura',
            'fecha_vencimiento',
            'anios_destinatarios',
            'residentes_destinatarios',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={'class': FORM_CONTROL}),
            'descripcion': forms.Textarea(attrs={'class': FORM_CONTROL, 'rows': 4}),
            'instrucciones': forms.Textarea(attrs={'class': FORM_CONTROL, 'rows': 4}),
            'fecha_apertura': forms.DateTimeInput(
                attrs={'class': FORM_CONTROL, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'fecha_vencimiento': forms.DateTimeInput(
                attrs={'class': FORM_CONTROL, 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['residentes_destinatarios'].queryset = User.objects.filter(
            is_active=True,
            rol='medico_residente',
            estado_residencia='ACTIVO',
        ).order_by('last_name', 'first_name', 'username')
        self.fields['anios_destinatarios'].initial = self.instance.anios_destinatarios or []
        if not self.instance.pk:
            self.initial['modo_destinatarios'] = Examen.TODOS
            self.initial['modo_inicio'] = Examen.INICIO_AUTOMATICO
        self.fields['fecha_apertura'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['fecha_vencimiento'].input_formats = ['%Y-%m-%dT%H:%M']
        if self.instance.pk:
            for field_name in ('fecha_apertura', 'fecha_vencimiento'):
                value = getattr(self.instance, field_name)
                if value:
                    self.initial[field_name] = value.strftime('%Y-%m-%dT%H:%M')

    def clean(self):
        cleaned_data = super().clean()
        modo = cleaned_data.get('modo_destinatarios')
        if self.is_bound:
            if hasattr(self.data, 'getlist'):
                anios = self.data.getlist('anios_destinatarios')
            else:
                anios = self.data.get('anios_destinatarios') or []
                if not isinstance(anios, (list, tuple)):
                    anios = [anios]
        else:
            anios = cleaned_data.get('anios_destinatarios') or []
        residentes = cleaned_data.get('residentes_destinatarios')
        if hasattr(self.data, 'getlist'):
            residentes_enviados = self.data.getlist('residentes_destinatarios')
        else:
            residentes_enviados = self.data.get('residentes_destinatarios') or []
            if not isinstance(residentes_enviados, (list, tuple)):
                residentes_enviados = [residentes_enviados]
        # El campo ya valida que las IDs pertenezcan al queryset permitido.
        tiene_residentes = bool(residentes_enviados)
        if modo == Examen.TODOS and (anios or tiene_residentes):
            raise forms.ValidationError('Para Todos, no selecciones años ni residentes específicos.')
        if modo == Examen.ANIOS and (not anios or tiene_residentes):
            raise forms.ValidationError('Seleccioná uno o varios años y no residentes específicos.')
        if modo == Examen.RESIDENTES and (not tiene_residentes or anios):
            raise forms.ValidationError('Seleccioná uno o varios residentes y no años.')
        return cleaned_data

    def save(self, commit=True):
        examen = super().save(commit=False)
        examen.modo_destinatarios = self.cleaned_data['modo_destinatarios']
        examen.modo_inicio = self.cleaned_data['modo_inicio']
        examen.anios_destinatarios = (
            list(self.cleaned_data.get('anios_destinatarios') or [])
            if examen.modo_destinatarios == Examen.ANIOS
            else []
        )
        if commit:
            examen.save()
            self.save_m2m()
        return examen


class PreguntaForm(forms.ModelForm):
    imagenes = MultipleImageField(
        label='Imágenes clínicas',
        required=False,
        widget=MultipleImageInput(attrs={
            'class': 'sr-only',
            'accept': 'image/*',
        }),
        help_text='Podés cargar varias imágenes y ordenarlas o quitarlas antes de guardar.',
    )

    class Meta:
        model = Pregunta
        fields = ['texto', 'orden', 'puntaje', 'tipo']
        widgets = {
            'texto': forms.Textarea(attrs={'class': FORM_CONTROL, 'rows': 4}),
            'orden': forms.NumberInput(attrs={'class': FORM_CONTROL, 'min': 1}),
            'puntaje': forms.NumberInput(attrs={'class': FORM_CONTROL, 'min': '0.01', 'step': '0.01'}),
            'tipo': forms.Select(attrs={'class': FORM_CONTROL}),
        }


class CorreccionRespuestaForm(forms.Form):
    puntaje = forms.DecimalField(
        min_value=0,
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': FORM_CONTROL,
            'step': '0.01',
        }),
    )
    comentario = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': FORM_CONTROL,
            'rows': 3,
        }),
    )


class AnulacionIntentoForm(forms.Form):
    motivo = forms.CharField(
        label='Motivo de anulación',
        min_length=10,
        widget=forms.Textarea(attrs={
            'class': FORM_CONTROL,
            'rows': 4,
            'placeholder': 'Describí por qué debe anularse este intento.',
        }),
        help_text='El motivo queda registrado junto con tu usuario y la fecha.',
    )


class RecuperacionIntentoForm(forms.Form):
    motivo = forms.CharField(
        label='Motivo de recuperación',
        min_length=10,
        widget=forms.Textarea(attrs={
            'class': FORM_CONTROL,
            'rows': 4,
            'placeholder': 'Describí por qué corresponde habilitar nuevamente este intento.',
        }),
        help_text='El motivo queda registrado junto con tu usuario y la fecha.',
    )


class OpcionForm(forms.ModelForm):
    class Meta:
        model = Opcion
        fields = ['texto', 'orden', 'es_correcta']
        widgets = {
            'texto': forms.TextInput(attrs={'class': FORM_CONTROL}),
            'orden': forms.NumberInput(attrs={'class': FORM_CONTROL, 'min': 1}),
            'es_correcta': forms.CheckboxInput(attrs={'class': 'h-4 w-4 rounded border-gray-300 text-blue-600'}),
        }


class BaseOpcionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        filas = [
            form.cleaned_data for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE')
        ]
        tipo = self.instance.tipo
        if tipo == Pregunta.DESARROLLO:
            if filas:
                raise ValidationError('Una pregunta desarrollada no puede tener opciones.')
            return
        if len(filas) < 2:
            raise ValidationError('La pregunta debe tener al menos dos opciones.')

        correctas = sum(1 for fila in filas if fila.get('es_correcta'))
        if tipo in {Pregunta.OPCION_UNICA, Pregunta.VERDADERO_FALSO} and correctas != 1:
            raise ValidationError('Debe existir exactamente una opción correcta.')
        if tipo == Pregunta.OPCION_MULTIPLE and correctas < 1:
            raise ValidationError('Debe existir al menos una opción correcta.')


OpcionFormSet = inlineformset_factory(
    Pregunta,
    Opcion,
    form=OpcionForm,
    formset=BaseOpcionFormSet,
    fields=['texto', 'orden', 'es_correcta'],
    extra=2,
    can_delete=True,
)
