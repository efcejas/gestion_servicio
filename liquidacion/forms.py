from django import forms
from .models import Estudios, RegistroEstudiosPorMedico, DiaSinPacientes
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

# [ELIMINADO - 16 de febrero 2026]
# Import de RegistroProcedimientosIntervensionismo eliminado
# Razón: En Colegiales se registra todo como Estudios

# Clases Tailwind reutilizables para campos de formulario
TAILWIND_INPUT_CLASSES = 'w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all'

class RegistroEstudiosPorMedicoCreateViewForm(forms.ModelForm):
    tipo_estudio = forms.ChoiceField(
        choices=[('', 'Seleccione')] + list(Estudios.TIPO_ESTUDIO_CHOICES),
        required=True,
        label="Tipo de estudio",
        widget=forms.Select(attrs={'class': 'hidden', 'id': 'id_tipo_estudio'}),  # Oculto por defecto
    )

    class Meta:
        model = RegistroEstudiosPorMedico
        fields = [
            'nombre_paciente',
            'apellido_paciente',
            'dni_paciente',
            'fecha_del_informe',
            'estudio',
            'cantidad_estudio',
        ]
        widgets = {
            'nombre_paciente': forms.TextInput(attrs={'class': TAILWIND_INPUT_CLASSES}),
            'apellido_paciente': forms.TextInput(attrs={'class': TAILWIND_INPUT_CLASSES}),
            'dni_paciente': forms.TextInput(attrs={'class': TAILWIND_INPUT_CLASSES, 'maxlength': 8}),
            'estudio': forms.SelectMultiple(attrs={'class': 'hidden', 'size': '5'}),  # Oculto, manejado por Select2
            'cantidad_estudio': forms.NumberInput(attrs={'class': TAILWIND_INPUT_CLASSES, 'min': 1}),
            'fecha_del_informe': forms.DateInput(
                attrs={'type': 'date', 'class': TAILWIND_INPUT_CLASSES},
                format='%Y-%m-%d'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['estudio'].choices = []  # vacío al inicio

        # Solo precargar la fecha si se está creando el registro
        if not self.instance.pk and not self.initial.get('fecha_del_informe'):
            self.fields['fecha_del_informe'].initial = timezone.now().date()

        # Asegurar el formato correcto incluso cuando ya hay valor
        self.fields['fecha_del_informe'].input_formats = ['%Y-%m-%d']

class DiaSinPacientesForm(forms.ModelForm):
    class Meta:
        model = DiaSinPacientes
        fields = ['fecha', 'observacion']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'observacion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

User = get_user_model()

class FiltroMedicoMesForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Médicos de staff - informes').order_by('last_name', 'first_name'),
        required=False,
        label="Médico",
        widget=forms.Select(attrs={}),
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
        widget=forms.Select(attrs={}),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"

# [ANULADO - 16 de febrero 2026]
# Formularios RegistroProcedimientosIntervensionismoCreateViewForm y 
# FiltroProcedimientosIntervensionismoForm eliminados
# Razón: En Colegiales, procedimientos se registran como Estudios
# Ver liquidacion_backup_completo_2026-02-16.json para datos históricos

User = get_user_model()

class FiltroEstudiosPorMedicoForm(forms.Form):
    fecha_actual = datetime.now()
    
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        required=False,
        label="Mes",
        initial=fecha_actual.month,  # Inicializar con el mes actual
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=fecha_actual.year,  # Inicializar con el año actual
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    # Nuevos campos para mejorar interactividad
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

    # filtro_rapido se elimina del formulario; se maneja con botones en la UI

    busqueda = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por nombre, apellido o DNI...',
        }),
    )

# A continuación, se agrega el formulario para carga masiva de estudios
class CargaExcelForm(forms.Form):
    archivo_excel = forms.FileField(label="Subí el archivo Excel")
    