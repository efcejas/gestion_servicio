from django import forms
from .models import Estudios, RegistroEstudiosPorMedico, GuardiaPasiva, SesionContable
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from decimal import Decimal

# [ELIMINADO - 16 de febrero 2026]
# Import de RegistroProcedimientosIntervensionismo eliminado
# Import de DiaSinPacientes eliminado (deprecado para Colegiales)
# Razón: En Colegiales se registra todo como Estudios

# Clases Tailwind reutilizables para campos de formulario
TAILWIND_INPUT_CLASSES = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all'
TAILWIND_SELECT_CLASSES = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all bg-white'
TAILWIND_CHECKBOX_CLASSES = 'h-5 w-5 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'
TAILWIND_RADIO_CLASSES = 'h-4 w-4 text-indigo-600 border-gray-300 focus:ring-indigo-500'


# ============================================================================
# FORMULARIO PRINCIPAL: REGISTRO DE PRÁCTICAS (v2.0)
# ============================================================================

class PracticaForm(forms.ModelForm):
    """
    Formulario para registro de prácticas médicas - Liquidación v2.0
    Incluye campos para facturación, bonus urgencia, y auditoría
    """
    tipo_estudio = forms.ChoiceField(
        choices=[('', 'Seleccione modalidad')] + list(Estudios.TIPO_ESTUDIO_CHOICES),
        required=True,
        label="Modalidad",
        widget=forms.Select(attrs={'class': 'hidden', 'id': 'id_tipo_estudio'}),
    )

    class Meta:
        model = RegistroEstudiosPorMedico
        fields = [
            'fecha_del_informe',
            'nombre_paciente',
            'apellido_paciente',
            'dni_paciente',
            'estudio',
            'cantidad_estudio',
            'cantidad_regiones',
            'tipo_obra_social',
            'paciente_internado',
            'fecha_hora_solicitud',
            'fecha_hora_informe',
        ]
        widgets = {
            'fecha_del_informe': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': TAILWIND_INPUT_CLASSES,
                    'id': 'id_fecha_del_informe'
                },
                format='%Y-%m-%d'
            ),
            'nombre_paciente': forms.TextInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'placeholder': 'Nombre del paciente'
            }),
            'apellido_paciente': forms.TextInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'placeholder': 'Apellido del paciente'
            }),
            'dni_paciente': forms.TextInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'maxlength': 8,
                'placeholder': 'DNI sin puntos'
            }),
            'estudio': forms.SelectMultiple(attrs={
                'class': 'hidden',
                'id': 'id_estudio',
                'size': '5'
            }),
            'cantidad_estudio': forms.NumberInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'min': 1,
                'value': 1
            }),
            'cantidad_regiones': forms.NumberInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'min': 1,
                'value': 1,
                'id': 'id_cantidad_regiones'
            }),
            'tipo_obra_social': forms.RadioSelect(attrs={
                'class': TAILWIND_RADIO_CLASSES,
            }),
            'paciente_internado': forms.CheckboxInput(attrs={
                'class': TAILWIND_CHECKBOX_CLASSES,
                'id': 'id_paciente_internado'
            }),
            'fecha_hora_solicitud': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': TAILWIND_INPUT_CLASSES,
                'id': 'id_fecha_hora_solicitud'
            }),
            'fecha_hora_informe': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': TAILWIND_INPUT_CLASSES,
                'id': 'id_fecha_hora_informe'
            }),
        }
        labels = {
            'fecha_del_informe': 'Fecha del Informe',
            'nombre_paciente': 'Nombre',
            'apellido_paciente': 'Apellido',
            'dni_paciente': 'DNI',
            'estudio': 'Estudio',
            'cantidad_estudio': 'Cantidad',
            'cantidad_regiones': 'Regiones',
            'tipo_obra_social': 'Obra Social',
            'paciente_internado': '¿Paciente internado? (para bonus urgencia RM)',
            'fecha_hora_solicitud': 'Fecha/Hora Solicitud',
            'fecha_hora_informe': 'Fecha/Hora Informe',
        }
        help_texts = {
            'cantidad_regiones': 'Número entero (1, 2, 3...). No se permiten fracciones.',
            'paciente_internado': 'Solo para estudios de Resonancia Magnética (RM) con médicos remotos. Bonus +20% si informe <24hs.',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Inicializar choices de estudio vacío (se carga con JavaScript según modalidad)
        self.fields['estudio'].choices = []

        # Precargar fecha actual si es nuevo registro
        if not self.instance.pk and not self.initial.get('fecha_del_informe'):
            self.fields['fecha_del_informe'].initial = timezone.now().date()

        # Formato de fecha
        self.fields['fecha_del_informe'].input_formats = ['%Y-%m-%d']

        # Horario se asigna automáticamente en models.RegistroEstudiosPorMedico.save()

    def clean_cantidad_regiones(self):
        cantidad = self.cleaned_data.get('cantidad_regiones')
        if cantidad and cantidad <= 0:
            raise forms.ValidationError('La cantidad de regiones debe ser mayor a 0.')
        if cantidad and not isinstance(cantidad, int):
            raise forms.ValidationError('La cantidad de regiones debe ser un número entero (sin decimales).')
        return cantidad

    def clean(self):
        cleaned_data = super().clean()
        paciente_internado = cleaned_data.get('paciente_internado')
        fecha_hora_solicitud = cleaned_data.get('fecha_hora_solicitud')
        fecha_hora_informe = cleaned_data.get('fecha_hora_informe')

        # Validar fechas de urgencia si paciente está internado
        if paciente_internado:
            if not fecha_hora_solicitud:
                self.add_error('fecha_hora_solicitud', 'Requerido para calcular bonus urgencia.')
            if not fecha_hora_informe:
                self.add_error('fecha_hora_informe', 'Requerido para calcular bonus urgencia.')
            
            # Validar que fecha_hora_informe > fecha_hora_solicitud
            if fecha_hora_solicitud and fecha_hora_informe:
                if fecha_hora_informe <= fecha_hora_solicitud:
                    self.add_error('fecha_hora_informe', 'La fecha del informe debe ser posterior a la solicitud.')

        return cleaned_data


# ============================================================================
# FORMULARIO: GUARDIAS PASIVAS
# ============================================================================

class GuardiaPasivaForm(forms.ModelForm):
    """
    Formulario para registro de guardias pasivas ($36.500 por día)
    """
    class Meta:
        model = GuardiaPasiva
        fields = [
            'fecha_guardia',
            'tipo_guardia',
            'monto',
            'observaciones',
        ]
        widgets = {
            'fecha_guardia': forms.DateInput(attrs={
                'type': 'date',
                'class': TAILWIND_INPUT_CLASSES,
            }),
            'tipo_guardia': forms.RadioSelect(attrs={
                'class': TAILWIND_RADIO_CLASSES,
            }),
            'monto': forms.NumberInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'step': '0.01',
            }),
            'observaciones': forms.Textarea(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
        labels = {
            'fecha_guardia': 'Fecha de la Guardia',
            'tipo_guardia': 'Tipo de Guardia',
            'monto': 'Monto',
            'observaciones': 'Observaciones',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Valor por defecto: $36.500
        if not self.instance.pk and not self.initial.get('monto'):
            self.fields['monto'].initial = Decimal('36500.00')


# ============================================================================
# FORMULARIOS DE FILTRADO Y REPORTES
# ============================================================================

# ============================================================================
# FORMULARIOS DE FILTRADO Y REPORTES
# ============================================================================

User = get_user_model()

class FiltroMedicoMesForm(forms.Form):
    """Formulario para filtrar reportes por médico y período"""
    medico = forms.ModelChoiceField(
        queryset=User.objects.filter(
            rol__in=['jefe_residentes', 'instructor_residentes', 'medico_residente', 
                    'medico_staff', 'jefe_servicio', 'cardiologo']
        ).order_by('last_name', 'first_name'),
        required=False,
        label="Médico",
        widget=forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
        empty_label="Todos los médicos"
    )
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        required=False,
        label="Mes",
        initial=datetime.now().month,
        widget=forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2020, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: f"{obj.last_name}, {obj.first_name}"


class FiltroEstudiosPorMedicoForm(forms.Form):
    """Formulario para filtrar estudios por médico (para dashboard personal)"""
    fecha_actual = datetime.now()
    
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        required=False,
        label="Mes",
        initial=fecha_actual.month,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2020, 2031)],
        required=False,
        label="Año",
        initial=fecha_actual.year,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    orden = forms.ChoiceField(
        choices=[
            ('fecha_desc', 'Más recientes primero'),
            ('fecha_asc', 'Más antiguos primero'),
            ('paciente_asc', 'Paciente (A-Z)'),
            ('paciente_desc', 'Paciente (Z-A)'),
        ],
        required=False,
        initial='fecha_desc',
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por nombre, apellido o DNI...',
        }),
    )


class CargaExcelForm(forms.Form):
    """Formulario para carga masiva de estudios desde Excel"""
    archivo_excel = forms.FileField(
        label="Subí el archivo Excel",
        help_text="Formato: .xlsx con columnas: Fecha, Paciente, DNI, Estudio, OS, Horario, Regiones"
    )


class FiltroSesionContableForm(forms.Form):
    """Formulario para filtrar sesiones contables en admin"""
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2020, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
    )
    estado = forms.ChoiceField(
        choices=[('', 'Todos los estados')] + list(SesionContable.ESTADO_CHOICES),
        required=False,
        label="Estado",
        widget=forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
    )


# ============================================================================
# ALIAS PARA COMPATIBILIDAD CON CÓDIGO LEGACY
# ============================================================================

# Mantener alias para evitar romper código existente
RegistroEstudiosPorMedicoCreateViewForm = PracticaForm

    