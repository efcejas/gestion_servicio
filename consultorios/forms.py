"""
Formularios para gestión operativa de consultorios.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import (
    BloqueHorario,
    Consultorio,
    MotivoAusencia,
    ProfesionalExterno,
    SolicitudAgendaExtra,
    TipoActividad,
    TipoTitularBloque,
)
from .utils import ConflictDetector

User = get_user_model()


class BloqueHorarioForm(forms.ModelForm):
    """Formulario principal para alta/edición de bloques horarios."""

    class Meta:
        model = BloqueHorario
        fields = [
            'consultorio',
            'tipo_titular',
            'profesional_asignado_temporal',
            'profesional_interno',
            'profesional_externo',
            'equipo',
            'dia_semana',
            'hora_inicio',
            'hora_fin',
            'fecha_inicio_vigencia',
            'fecha_fin_vigencia',
            'tipo_actividad',
            'tipo_lista',
            'permite_cobertura_residente',
            'prioridad_cobertura',
            'competencia_requerida',
            'estado',
            'observaciones',
        ]
        widgets = {
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
            'fecha_inicio_vigencia': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_vigencia': forms.DateInput(attrs={'type': 'date'}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
            'competencia_requerida': forms.TextInput(attrs={'placeholder': 'Ej: Puncion mamaria, Elastografia'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = (
            'consultorios-form-control w-full rounded border border-gray-300 '
            'bg-white text-gray-900 px-3 py-2 focus:border-blue-500 '
            'focus:outline-none focus:ring-1 focus:ring-blue-500'
        )
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500')
            else:
                field.widget.attrs.setdefault('class', base_class)
                if isinstance(field.widget, (forms.TimeInput, forms.DateInput)):
                    style = field.widget.attrs.get('style', '')
                    if 'color-scheme' not in style:
                        field.widget.attrs['style'] = (style + '; color-scheme: light;').strip('; ')

        self.fields['profesional_interno'].queryset = User.objects.filter(
            is_active=True,
            rol__in=[
                'medico_staff',
                'jefe_residentes',
                'instructor_residentes',
                'medico_residente',
                'jefe_servicio',
            ]
        ).order_by('last_name', 'first_name', 'username')

        self.fields['profesional_asignado_temporal'].queryset = User.objects.filter(
            is_active=True,
            rol__in=['medico_residente', 'jefe_residentes', 'instructor_residentes']
        ).order_by('last_name', 'first_name', 'username')
        self.fields['profesional_asignado_temporal'].required = False

    def clean(self):
        cleaned_data = super().clean()

        consultorio = cleaned_data.get('consultorio')
        tipo_titular = cleaned_data.get('tipo_titular')
        profesional_asignado_temporal = cleaned_data.get('profesional_asignado_temporal')
        profesional_interno = cleaned_data.get('profesional_interno')
        profesional_externo = cleaned_data.get('profesional_externo')
        dia_semana = cleaned_data.get('dia_semana')
        hora_inicio = cleaned_data.get('hora_inicio')
        hora_fin = cleaned_data.get('hora_fin')

        if tipo_titular == TipoTitularBloque.NOMINAL:
            if not profesional_interno and not profesional_externo:
                raise ValidationError('Para titular nominal debe seleccionar profesional interno o externo.')
            if profesional_interno and profesional_externo:
                raise ValidationError('Especificar un profesional: interno O externo, no ambos.')
        else:
            if profesional_interno or profesional_externo:
                raise ValidationError(
                    'En bloques genéricos no completar profesional interno/externo. Use solo Nombre asignado (opcional).'
                )

            if profesional_asignado_temporal:
                rol_asignado = getattr(profesional_asignado_temporal, 'rol', None)
                if tipo_titular in (
                    TipoTitularBloque.RESIDENTE_R1,
                    TipoTitularBloque.RESIDENTE_R2,
                    TipoTitularBloque.RESIDENTE_R3,
                    TipoTitularBloque.RESIDENTE_R4,
                ):
                    if rol_asignado != 'medico_residente':
                        raise ValidationError('Para bloques R1-R4, el nombre asignado debe ser un medico_residente.')
                if tipo_titular == TipoTitularBloque.JEFES_RESIDENTES:
                    if rol_asignado not in {'jefe_residentes', 'instructor_residentes'}:
                        raise ValidationError('Para jefes, el nombre asignado debe ser jefe_residentes o instructor_residentes.')

        if not all([consultorio, dia_semana is not None, hora_inicio, hora_fin]):
            return cleaned_data

        conflictos = ConflictDetector.verificar_conflictos(
            consultorio=consultorio,
            profesional_interno=profesional_interno,
            profesional_externo=profesional_externo,
            dia_semana=dia_semana,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            excluir_id=self.instance.id if self.instance and self.instance.id else None,
        )

        if conflictos['tiene_conflictos']:
            raise ValidationError(conflictos['mensajes'])

        return cleaned_data


class AusenciaCoberturaForm(forms.Form):
    """
    Formulario para reportar la ausencia de un profesional en un bloque horario.
    El profesional ausente se infiere del bloque; aquí solo se captura la fecha y el motivo.
    """

    _input_class = (
        'consultorios-form-control w-full rounded border border-gray-300 bg-white text-gray-900 px-3 py-2 '
        'focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500'
    )

    fecha_ausencia = forms.DateField(
        label='Fecha de inicio',
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Para una ausencia puntual, dejá la fecha de fin vacía.',
    )

    fecha_fin_ausencia = forms.DateField(
        label='Fecha de fin (opcional)',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Solo si la ausencia dura varios días (ej: vacaciones). El sistema generará un registro por cada ocurrencia del día del bloque dentro del rango.',
    )

    motivo = forms.ChoiceField(
        label='Motivo',
        choices=MotivoAusencia.choices,
    )

    detalle_motivo = forms.CharField(
        label='Detalle (opcional)',
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Información adicional sobre la ausencia...'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', self._input_class)
            if isinstance(field.widget, (forms.TimeInput, forms.DateInput)):
                style = field.widget.attrs.get('style', '')
                if 'color-scheme' not in style:
                    field.widget.attrs['style'] = (style + '; color-scheme: light;').strip('; ')

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_ausencia')
        fecha_fin = cleaned_data.get('fecha_fin_ausencia')
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            self.add_error('fecha_fin_ausencia', 'La fecha de fin no puede ser anterior a la fecha de inicio.')
        return cleaned_data


# ---------------------------------------------------------------------------
# Formularios de gestión de salas y profesionales
# ---------------------------------------------------------------------------

_FIELD_CLASS = (
    'consultorios-form-control w-full rounded border border-gray-300 bg-white text-gray-900 px-3 py-2 text-sm '
    'focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500'
)
_CHECKBOX_CLASS = 'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500'


class ConsultorioForm(forms.ModelForm):
    """Alta y edición de salas/consultorios."""

    class Meta:
        model = Consultorio
        fields = ['nombre', 'ubicacion', 'capacidad_pacientes_hora', 'esta_activo', 'observaciones']
        widgets = {
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', _CHECKBOX_CLASS)
            else:
                field.widget.attrs.setdefault('class', _FIELD_CLASS)
                if isinstance(field.widget, (forms.TimeInput, forms.DateInput)):
                    style = field.widget.attrs.get('style', '')
                    if 'color-scheme' not in style:
                        field.widget.attrs['style'] = (style + '; color-scheme: light;').strip('; ')
                if isinstance(field.widget, (forms.TimeInput, forms.DateInput)):
                    style = field.widget.attrs.get('style', '')
                    if 'color-scheme' not in style:
                        field.widget.attrs['style'] = (style + '; color-scheme: light;').strip('; ')


class ProfesionalExternoForm(forms.ModelForm):
    """Alta y edición de profesionales externos."""

    class Meta:
        model = ProfesionalExterno
        fields = [
            'nombre', 'apellido', 'matricula', 'especialidad',
            'categoria', 'telefono', 'email', 'esta_activo', 'observaciones',
        ]
        widgets = {
            'observaciones': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', _CHECKBOX_CLASS)
            else:
                field.widget.attrs.setdefault('class', _FIELD_CLASS)
                if isinstance(field.widget, (forms.TimeInput, forms.DateInput)):
                    style = field.widget.attrs.get('style', '')
                    if 'color-scheme' not in style:
                        field.widget.attrs['style'] = (style + '; color-scheme: light;').strip('; ')


class SolicitudAgendaExtraForm(forms.ModelForm):
    """Formulario para solicitar una agenda extra fuera del horario habitual."""

    class Meta:
        model = SolicitudAgendaExtra
        fields = [
            'consultorio',
            'profesional_interno',
            'profesional_externo',
            'fecha_solicitada',
            'hora_inicio',
            'hora_fin',
            'tipo_actividad',
            'motivo',
        ]
        widgets = {
            'fecha_solicitada': forms.DateInput(attrs={'type': 'date'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time'}),
            'motivo': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        self.fields['consultorio'].queryset = Consultorio.objects.activos()
        self.fields['profesional_externo'].queryset = ProfesionalExterno.objects.activos()
        self.fields['profesional_externo'].required = False
        self.fields['profesional_interno'].required = False

        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', _CHECKBOX_CLASS)
            else:
                field.widget.attrs.setdefault('class', _FIELD_CLASS)

    def clean(self):
        cleaned_data = super().clean()
        interno = cleaned_data.get('profesional_interno')
        externo = cleaned_data.get('profesional_externo')

        if interno and externo:
            raise ValidationError('Especificar un profesional: interno O externo, no ambos.')

        hora_inicio = cleaned_data.get('hora_inicio')
        hora_fin = cleaned_data.get('hora_fin')
        if hora_inicio and hora_fin and hora_inicio >= hora_fin:
            raise ValidationError({'hora_fin': 'La hora de fin debe ser posterior a la hora de inicio.'})

        return cleaned_data
