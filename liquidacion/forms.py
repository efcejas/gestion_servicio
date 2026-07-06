from django import forms
from django.db.models import Q
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import (
    Estudios,
    RegistroEstudiosPorMedico,
    GuardiaPasiva,
    ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA,
    SesionContable,
    SolicitudRevisionHorarioRegistro,
)
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from decimal import Decimal
from .grupo_tarifario_mapping import es_estudio_cardiologico

# [ELIMINADO - 16 de febrero 2026]
# Import de RegistroProcedimientosIntervensionismo eliminado
# Import de DiaSinPacientes eliminado (deprecado para Colegiales)
# Razón: En Colegiales se registra todo como Estudios

# Clases Tailwind reutilizables para campos de formulario
TAILWIND_INPUT_CLASSES = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all'
TAILWIND_SELECT_CLASSES = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all bg-white'
TAILWIND_CHECKBOX_CLASSES = 'h-5 w-5 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500'
TAILWIND_RADIO_CLASSES = 'h-4 w-4 text-indigo-600 border-gray-300 focus:ring-indigo-500'


def _parse_email_list(value):
    if not value:
        return []
    raw_items = []
    for chunk in str(value).replace('\n', ',').split(','):
        email = chunk.strip()
        if email:
            raw_items.append(email)
    for email in raw_items:
        try:
            validate_email(email)
        except ValidationError:
            raise forms.ValidationError(f'Email invalido: {email}')
    return raw_items


class PreparacionLiquidacionRRHHForm(forms.Form):
    destinatarios = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': TAILWIND_INPUT_CLASSES,
            'rows': 2,
            'placeholder': 'rrhh@ejemplo.com, liquidaciones@ejemplo.com',
        }),
        label='Destinatarios',
        help_text='Separar multiples emails con coma o salto de linea.',
    )
    cc = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': TAILWIND_INPUT_CLASSES,
            'rows': 2,
            'placeholder': 'copia@ejemplo.com',
        }),
        label='CC',
        help_text='Opcional. Separar multiples emails con coma o salto de linea.',
    )
    asunto = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': TAILWIND_INPUT_CLASSES}),
        label='Asunto',
    )
    cuerpo = forms.CharField(
        widget=forms.Textarea(attrs={'class': TAILWIND_INPUT_CLASSES, 'rows': 8}),
        label='Cuerpo',
    )

    def clean_destinatarios(self):
        return _parse_email_list(self.cleaned_data.get('destinatarios'))

    def clean_cc(self):
        return _parse_email_list(self.cleaned_data.get('cc'))


class EstudiosAdminForm(forms.ModelForm):
    """Formulario administrativo mínimo para alta/edición de estudios."""

    class Meta:
        model = Estudios
        fields = ['nombre', 'tipo', 'grupo_tarifario', 'activo', 'conteo_regiones']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'placeholder': 'Nombre del estudio',
            }),
            'tipo': forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
            'grupo_tarifario': forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
            'activo': forms.CheckboxInput(attrs={'class': TAILWIND_CHECKBOX_CLASSES}),
            'conteo_regiones': forms.NumberInput(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'min': 1,
            }),
        }
        labels = {
            'nombre': 'Nombre',
            'tipo': 'Tipo de estudio',
            'grupo_tarifario': 'Grupo tarifario',
            'activo': 'Activo',
            'conteo_regiones': 'Cantidad de regiones',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grupo_tarifario'].queryset = self.fields['grupo_tarifario'].queryset.order_by('codigo')


class SolicitudRevisionHorarioRegistroForm(forms.ModelForm):
    """Formulario médico para solicitar revisión de horario de un registro."""

    class Meta:
        model = SolicitudRevisionHorarioRegistro
        fields = ['horario_solicitado', 'fecha_hora_real_declarada', 'motivo_solicitud']
        widgets = {
            'horario_solicitado': forms.Select(attrs={'class': TAILWIND_SELECT_CLASSES}),
            'fecha_hora_real_declarada': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': TAILWIND_INPUT_CLASSES,
                }
            ),
            'motivo_solicitud': forms.Textarea(
                attrs={
                    'class': TAILWIND_INPUT_CLASSES,
                    'rows': 4,
                    'placeholder': 'Describa brevemente el motivo de la revisión solicitada',
                }
            ),
        }
        labels = {
            'horario_solicitado': 'Horario solicitado',
            'fecha_hora_real_declarada': 'Fecha/Hora real declarada',
            'motivo_solicitud': 'Motivo de solicitud',
        }


class SolicitudRevisionHorarioResolucionForm(forms.Form):
    """Formulario administrativo para resolver solicitudes de revisión de horario."""

    DECISION_APROBAR = 'APROBAR'
    DECISION_RECHAZAR = 'RECHAZAR'
    DECISION_CHOICES = [
        (DECISION_APROBAR, 'Aprobar'),
        (DECISION_RECHAZAR, 'Rechazar'),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect,
        label='Decision administrativa',
    )
    observacion_revision = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'Observacion administrativa (opcional)',
            }
        ),
        label='Observacion de revision',
    )


class SolicitudRevisionHorarioAplicarForm(forms.Form):
    """Formulario administrativo para aplicar corrección económica B2."""

    observacion_aplicacion = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'Observacion de aplicación (opcional)',
            }
        ),
        label='Observacion de aplicacion',
    )


class SolicitudRevisionHorarioRecalcularAplicacionForm(forms.Form):
    """Formulario administrativo para recalculo puntual B3."""

    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'Observacion del recalculo (opcional)',
            }
        ),
        label='Observacion del recalculo',
    )


class SolicitudRevisionHorarioBulkActionForm(forms.Form):
    """Acciones masivas B4 para superusuario sobre solicitudes seleccionadas."""

    ACCION_APROBAR = 'APROBAR'
    ACCION_APLICAR = 'APLICAR'
    ACCION_CHOICES = [
        (ACCION_APROBAR, 'Aprobar seleccionadas'),
        (ACCION_APLICAR, 'Aplicar aprobadas seleccionadas'),
    ]

    solicitudes = forms.MultipleChoiceField(required=True)
    accion = forms.ChoiceField(choices=ACCION_CHOICES)
    observacion = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': TAILWIND_INPUT_CLASSES,
            'rows': 2,
            'placeholder': 'Observacion para registrar en la accion masiva',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['solicitudes'].choices = [
            (str(pk), str(pk))
            for pk in SolicitudRevisionHorarioRegistro.objects.values_list('pk', flat=True)
        ]


# ============================================================================
# FORMULARIO PRINCIPAL: REGISTRO DE PRÁCTICAS (v2.0)
# ============================================================================

class RevisionAuditoriaEcoRegistroForm(forms.Form):
    """Resolucion administrativa de una alerta ECO sin modificar el registro."""

    ESTADO_VALIDADO = 'VALIDADO'
    ESTADO_REQUIERE_CORRECCION = 'REQUIERE_CORRECCION'
    ESTADO_DESCARTADO = 'DESCARTADO'
    ESTADO_CHOICES = [
        (ESTADO_VALIDADO, 'Validado contra PACS'),
        (ESTADO_REQUIERE_CORRECCION, 'Requiere correccion'),
        (ESTADO_DESCARTADO, 'Descartado / no corresponde'),
    ]

    estado = forms.ChoiceField(choices=ESTADO_CHOICES)
    observacion = forms.CharField(
        max_length=1000,
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Observacion de revision administrativa',
        }),
    )


class CorreccionPacsRegistroForm(forms.Form):
    """Correccion economica puntual posterior a control PACS."""

    TIPO_HORARIO_RECALCULADO = 'HORARIO_RECALCULADO'
    TIPO_MONTO_MANUAL = 'MONTO_MANUAL'
    TIPO_CHOICES = [
        (TIPO_HORARIO_RECALCULADO, 'Recalcular por horario corregido'),
        (TIPO_MONTO_MANUAL, 'Cargar monto manual'),
    ]

    tipo_correccion = forms.ChoiceField(
        choices=TIPO_CHOICES,
        required=False,
        initial=TIPO_MONTO_MANUAL,
    )
    horario_corregido = forms.ChoiceField(
        choices=RegistroEstudiosPorMedico.HORARIO_CHOICES,
        required=False,
    )
    hora_pacs = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={
            'type': 'time',
        }),
    )
    monto_nuevo = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'placeholder': 'Monto corregido',
        }),
    )
    observacion = forms.CharField(
        max_length=1000,
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Motivo del ajuste segun control PACS',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_correccion') or self.TIPO_MONTO_MANUAL
        cleaned['tipo_correccion'] = tipo

        if tipo == self.TIPO_HORARIO_RECALCULADO and not cleaned.get('horario_corregido'):
            self.add_error('horario_corregido', 'Debes indicar el horario corregido.')
        if tipo == self.TIPO_HORARIO_RECALCULADO and not cleaned.get('hora_pacs'):
            self.add_error('hora_pacs', 'Debes indicar la hora vista en PACS.')
        if tipo == self.TIPO_MONTO_MANUAL and cleaned.get('monto_nuevo') is None:
            self.add_error('monto_nuevo', 'Debes indicar el monto corregido.')

        return cleaned


class CorreccionPacsAplicadaBulkForm(forms.Form):
    """Nueva correccion auditada sobre ajustes PACS ya aplicados."""

    registros = forms.MultipleChoiceField(required=True)
    horario_corregido = forms.ChoiceField(
        choices=RegistroEstudiosPorMedico.HORARIO_CHOICES,
        required=True,
    )
    observacion = forms.CharField(
        max_length=1000,
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Motivo de la nueva correccion sobre ajustes PACS aplicados',
        }),
    )

    def __init__(self, *args, registro_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['registros'].choices = registro_choices or []


class PracticaForm(forms.ModelForm):
    """
    Formulario para registro de prácticas médicas - Liquidación v3.1
    MULTI-ESTUDIO: 1 registro (paciente) = N estudios, cada uno con su precio
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
            'cantidad_regiones',
            'tipo_obra_social',
            'liquidar_como_extra_residencia',
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
                'class': TAILWIND_SELECT_CLASSES,
                'id': 'id_estudio',
            }),
            'cantidad_regiones': forms.NumberInput(attrs={
                'class': TAILWIND_INPUT_CLASSES + ' h-12',
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
            'liquidar_como_extra_residencia': forms.CheckboxInput(attrs={
                'class': TAILWIND_CHECKBOX_CLASSES,
                'id': 'id_liquidar_como_extra_residencia'
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
            'estudio': 'Estudios Realizados',
            'cantidad_regiones': 'Cantidad de Regiones',
            'tipo_obra_social': 'Obra Social',
            'liquidar_como_extra_residencia': 'Actividad asistencial fuera de rol docente / liquidar como Extra Residencia',
            'paciente_internado': '¿Paciente internado? (para bonus urgencia RM)',
            'fecha_hora_solicitud': 'Fecha/Hora Solicitud',
            'fecha_hora_informe': 'Fecha/Hora Informe',
        }
        help_texts = {
            'estudio': 'Selecciona todos los estudios realizados a este paciente',
            'cantidad_regiones': 'Se calcula automáticamente sumando las regiones de cada estudio',
            'liquidar_como_extra_residencia': 'Usar cuando la práctica corresponde a una lista asistencial fuera de la actividad docente habitual. El registro se liquidará como Extra Residencia.',
            'paciente_internado': 'Solo para estudios de Resonancia Magnética (RM) con médicos remotos. Bonus +20% si informe <24hs.',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Cargar estudios activos filtrados por rol
        estudios_qs = Estudios.objects.filter(activo=True).order_by('tipo', 'nombre')
        if self.user and not self.user.is_superuser and self.user.rol != 'cardiologo':
            estudios_permitidos_ids = [
                est.id
                for est in estudios_qs
                if not es_estudio_cardiologico(est.tipo, est.nombre, est.codigo)
            ]
            estudios_qs = Estudios.objects.filter(id__in=estudios_permitidos_ids).order_by('tipo', 'nombre')

        self.fields['estudio'].queryset = estudios_qs
        
        # Precargar fecha actual si es nuevo registro
        if not self.instance.pk and not self.initial.get('fecha_del_informe'):
            self.fields['fecha_del_informe'].initial = timezone.now().date()

        # Formato de fecha
        self.fields['fecha_del_informe'].input_formats = ['%Y-%m-%d']

        # FIX: Pre-seleccionar Obra Social para evitar opción vacía "-----"
        if self.instance.pk:
            # Edición: usar valor actual o default si está vacío
            self.fields['tipo_obra_social'].initial = (
                self.instance.tipo_obra_social or 'OTRAS_OS'
            )
        else:
            # Creación: usar default
            self.fields['tipo_obra_social'].initial = 'OTRAS_OS'
        
        # Hacer campo required para evitar envío vacío
        self.fields['tipo_obra_social'].required = True

        if (
            not self.user
            or self.user.rol not in ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA
        ):
            self.fields.pop('liquidar_como_extra_residencia', None)

        # Horario: clasificación canónica post-M2M en services.py; save() deja fallback legacy.

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
    Formulario para registro de guardias pasivas.
    """
    class Meta:
        model = GuardiaPasiva
        fields = [
            'fecha_guardia',
            'observaciones',
        ]
        widgets = {
            'fecha_guardia': forms.DateInput(attrs={
                'type': 'date',
                'class': TAILWIND_INPUT_CLASSES,
            }),
            'observaciones': forms.Textarea(attrs={
                'class': TAILWIND_INPUT_CLASSES,
                'rows': 3,
                'placeholder': 'Observaciones adicionales (opcional)'
            }),
        }
        labels = {
            'fecha_guardia': 'Fecha de la Guardia',
            'observaciones': 'Observaciones',
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('user', None)
        super().__init__(*args, **kwargs)


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


class TarifaGrupoTarifarioAdminForm(forms.ModelForm):
    """Alta administrativa de nueva tarifa para un grupo tarifario existente."""

    class Meta:
        from .models import TarifaGrupoTarifario

        model = TarifaGrupoTarifario
        fields = [
            'vigencia_desde',
            'vigencia_hasta',
            'precio_cober',
            'precio_otras_os',
            'motivo_actualizacion',
        ]
        widgets = {
            'vigencia_desde': forms.DateInput(attrs={'type': 'date', 'class': TAILWIND_INPUT_CLASSES}),
            'vigencia_hasta': forms.DateInput(attrs={'type': 'date', 'class': TAILWIND_INPUT_CLASSES}),
            'precio_cober': forms.NumberInput(attrs={'class': TAILWIND_INPUT_CLASSES, 'step': '0.01', 'min': '0.01'}),
            'precio_otras_os': forms.NumberInput(attrs={'class': TAILWIND_INPUT_CLASSES, 'step': '0.01', 'min': '0.01'}),
            'motivo_actualizacion': forms.Textarea(
                attrs={
                    'class': TAILWIND_INPUT_CLASSES,
                    'rows': 3,
                    'placeholder': 'Motivo u observaciones de la actualización',
                }
            ),
        }
        labels = {
            'motivo_actualizacion': 'Motivo / observaciones',
        }

    def __init__(self, *args, **kwargs):
        self.grupo_tarifario = kwargs.pop('grupo_tarifario', None)
        super().__init__(*args, **kwargs)

    def clean_precio_cober(self):
        precio_cober = self.cleaned_data.get('precio_cober')
        if precio_cober is None or precio_cober <= 0:
            raise forms.ValidationError('El precio COBER debe ser mayor a 0.')
        return precio_cober

    def clean_precio_otras_os(self):
        precio_otras_os = self.cleaned_data.get('precio_otras_os')
        if precio_otras_os is None or precio_otras_os <= 0:
            raise forms.ValidationError('El precio OTRAS OS debe ser mayor a 0.')
        return precio_otras_os

    def clean(self):
        cleaned_data = super().clean()
        vigencia_desde = cleaned_data.get('vigencia_desde')
        vigencia_hasta = cleaned_data.get('vigencia_hasta')

        if vigencia_desde and vigencia_hasta and vigencia_hasta < vigencia_desde:
            self.add_error('vigencia_hasta', 'La vigencia hasta no puede ser anterior a vigencia desde.')

        if not self.grupo_tarifario or not vigencia_desde:
            return cleaned_data

        # Solapamiento de vigencias para el mismo grupo (null = rango abierto)
        tarifas_qs = (
            self._meta.model.objects
            .filter(grupo_tarifario=self.grupo_tarifario)
            .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=vigencia_desde))
        )
        if vigencia_hasta:
            tarifas_qs = tarifas_qs.filter(vigencia_desde__lte=vigencia_hasta)

        if tarifas_qs.exists():
            raise forms.ValidationError(
                'Ya existe una tarifa con vigencia que se solapa para este grupo tarifario.'
            )

        return cleaned_data


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

    
