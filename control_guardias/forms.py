from django import forms

from .models import (
    AsignacionGuardia,
        AjusteCuotaGuardia,
    AusenciaResidente,
    ConfiguracionTipoGuardia,
    CuotaMensualGuardia,
    Feriado,
    RotacionExterna,
    SolicitudCambioGuardia,
    SolicitudSlotVacante,
)

INPUT_CLASS = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg'
CHECKBOX_CLASS = 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded'
EXTENSIONES_PERMITIDAS_CERT = {'jpg', 'jpeg', 'png', 'webp', 'pdf', 'doc', 'docx', 'heic', 'heif'}


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ConfiguracionTipoGuardiaForm(forms.ModelForm):
    DIAS_CHOICES = [
        ('L', 'Lunes'),
        ('M', 'Martes'),
        ('X', 'Miércoles'),
        ('J', 'Jueves'),
        ('V', 'Viernes'),
        ('S', 'Sábado'),
        ('D', 'Domingo'),
    ]
    dias = forms.MultipleChoiceField(
        choices=DIAS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Días de la semana',
        help_text='Seleccioná los días en que aplica este tipo de guardia.',
    )

    class Meta:
        model = ConfiguracionTipoGuardia
        fields = ['nombre', 'hora_inicio', 'hora_fin', 'aplica_feriados', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': INPUT_CLASS}),
            'hora_fin': forms.TimeInput(attrs={'type': 'time', 'class': INPUT_CLASS}),
            'aplica_feriados': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'activo': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.dias_semana:
            self.initial['dias'] = self.instance.dias_semana.split(',')

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.dias_semana = ','.join(self.cleaned_data['dias'])
        if commit:
            instance.save()
        return instance


class CuotaMensualGuardiaForm(forms.ModelForm):
    class Meta:
        model = CuotaMensualGuardia
        fields = ['guardias_por_mes', 'atenuante_porcentaje']
        widgets = {
            'guardias_por_mes': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 0}),
            'atenuante_porcentaje': forms.NumberInput(
                attrs={'class': INPUT_CLASS, 'min': 0, 'max': 100, 'step': '0.01'}
            ),
        }


class AjustePenalizacionForm(forms.ModelForm):
    class Meta:
        model = AjusteCuotaGuardia
        fields = ['residente', 'mes', 'anio', 'cantidad', 'motivo']
        widgets = {
            'residente': forms.Select(attrs={'class': INPUT_CLASS}),
            'mes': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 1, 'max': 12}),
            'anio': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 2025, 'max': 2099}),
            'cantidad': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 1}),
            'motivo': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3, 'placeholder': 'Motivo de la penalizacion'}),
        }
        labels = {
            'cantidad': 'Guardias adicionales',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['residente'].queryset = User.objects.filter(
            rol='medico_residente',
            perfil_completo=True,
            is_active=True,
        ).order_by('last_name', 'first_name')

        import datetime
        hoy = datetime.date.today()
        if not self.initial.get('mes'):
            self.initial['mes'] = hoy.month
        if not self.initial.get('anio'):
            self.initial['anio'] = hoy.year
        if not self.initial.get('cantidad'):
            self.initial['cantidad'] = 1

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is None or cantidad < 1:
            raise forms.ValidationError('La penalizacion debe ser al menos 1 guardia adicional.')
        return cantidad


class FeriadoForm(forms.ModelForm):
    class Meta:
        model = Feriado
        fields = ['fecha', 'descripcion']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': INPUT_CLASS}),
            'descripcion': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Día del Trabajo'}),
        }


class AusenciaResidenteForm(forms.ModelForm):
    certificados_adicionales = forms.Field(
        required=False,
        widget=MultipleFileInput(
            attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg',
                'multiple': True,
                'accept': '.jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.heic,.heif',
            }
        ),
        label='Documentos adicionales',
    )

    class Meta:
        model = AusenciaResidente
        fields = ['fecha_inicio', 'fecha_fin', 'motivo', 'descripcion']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg'}),
            'motivo': forms.Select(attrs={'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-lg'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get('fecha_inicio')
        fin = cleaned_data.get('fecha_fin')
        if inicio and fin and fin < inicio:
            raise forms.ValidationError('La fecha de fin no puede ser anterior a la fecha de inicio.')
        return cleaned_data

    def clean_certificados_adicionales(self):
        archivos = self.files.getlist('certificados_adicionales')
        if not archivos:
            return []
        if len(archivos) > 5:
            raise forms.ValidationError('Podés adjuntar hasta 5 documentos adicionales por ausencia.')

        max_size = 10 * 1024 * 1024  # 10 MB por archivo
        for archivo in archivos:
            if archivo.size > max_size:
                raise forms.ValidationError(
                    f'El archivo {archivo.name} supera los 10 MB permitidos.'
                )
            extension = archivo.name.rsplit('.', 1)[-1].lower() if '.' in archivo.name else ''
            if extension not in EXTENSIONES_PERMITIDAS_CERT:
                raise forms.ValidationError(
                    f'El archivo {archivo.name} tiene una extensión no permitida.'
                )
        return archivos


class SolicitudCambioGuardiaForm(forms.ModelForm):
    """
    Formulario para solicitar un cambio de guardia.
    Filtra guardia_receptor a guardias PUBLICADAS que NO pertenezcan al solicitante.
    """
    class Meta:
        model = SolicitudCambioGuardia
        fields = ['guardia_receptor', 'notas_solicitante']
        widgets = {
            'notas_solicitante': forms.Textarea(
                attrs={'rows': 3, 'class': INPUT_CLASS, 'placeholder': 'Motivo del cambio (opcional)'}
            ),
        }
        labels = {
            'guardia_receptor': 'Guardia a intercambiar (del otro residente)',
            'notas_solicitante': 'Notas para el receptor (opcional)',
        }

    def __init__(self, *args, solicitante=None, **kwargs):
        super().__init__(*args, **kwargs)
        if solicitante is not None:
            self.fields['guardia_receptor'].queryset = (
                AsignacionGuardia.objects
                .filter(estado='PUBLICADA')
                .exclude(residente=solicitante)
                .select_related('residente', 'tipo_guardia')
                .order_by('fecha')
            )
        self.fields['guardia_receptor'].widget.attrs['class'] = INPUT_CLASS
        self.fields['guardia_receptor'].label_from_instance = lambda obj: (
            f"{obj.fecha.strftime('%d/%m/%Y')} — {obj.tipo_guardia.nombre} "
            f"({obj.residente.get_full_name()})"
        )


class NotasRechazoForm(forms.Form):
    """Formulario minimal para que el jefe ingrese motivo al rechazar un cambio."""
    notas = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'rows': 3, 'class': INPUT_CLASS, 'placeholder': 'Motivo del rechazo (opcional)'}
        ),
        label='Notas / motivo del rechazo',
    )


# ---------------------------------------------------------------------------
# Fase 3: Distribución automática
# ---------------------------------------------------------------------------

class GenerarDistribucionForm(forms.Form):
    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    mes = forms.ChoiceField(
        choices=MESES,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
        label='Mes',
    )
    anio = forms.IntegerField(
        min_value=2025,
        max_value=2099,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS}),
        label='Año',
    )
    tipos_guardia = forms.ModelMultipleChoiceField(
        queryset=ConfiguracionTipoGuardia.objects.filter(activo=True),
        widget=forms.CheckboxSelectMultiple,
        label='Tipos de guardia a distribuir',
        help_text='Seleccioná al menos un tipo de guardia activo.',
    )
    reemplazar_borradores = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        label='Reemplazar borrador existente si ya hay uno para ese mes',
    )
    restricciones_anio = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        label='Aplicar guardias condicionales por año',
        help_text='R1: Viernes, Domingos y Feriados · R2: Sábados · R3/R4: Lunes a Jueves',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        import datetime
        hoy = datetime.date.today()
        self.fields['mes'].initial = hoy.month
        self.fields['anio'].initial = hoy.year


class RotacionExternaForm(forms.ModelForm):
    class Meta:
        model = RotacionExterna
        fields = ['residente', 'fecha_inicio', 'fecha_fin', 'descripcion', 'activo']
        widgets = {
            'residente': forms.Select(attrs={'class': INPUT_CLASS}),
            'fecha_inicio': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'descripcion': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'Ej: Rotación Clínica Médica HIBA'}),
            'activo': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        residentes_qs = User.objects.filter(
            rol__in=['medico_residente', 'jefe_residentes', 'instructor_residentes']
        ).order_by('last_name', 'first_name')
        self.fields['residente'].queryset = residentes_qs

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get('fecha_inicio')
        fin = cleaned.get('fecha_fin')
        if inicio and fin and fin < inicio:
            raise forms.ValidationError('La fecha de fin no puede ser anterior a la de inicio.')
        return cleaned


class SolicitudSlotVacanteForm(forms.ModelForm):
    class Meta:
        model = SolicitudSlotVacante
        fields = ['notas_solicitante']
        widgets = {
            'notas_solicitante': forms.Textarea(attrs={
                'class': INPUT_CLASS,
                'rows': 3,
                'placeholder': 'Motivo del pedido (opcional)...',
            }),
        }
