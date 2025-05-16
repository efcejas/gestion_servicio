from django import forms
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo, DiaSinPacientes
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

class MedicoCreateViewForm(forms.ModelForm):
    class Meta:
        model = Medico
        fields = ['nombre', 'apellido', 'matricula']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'matricula': forms.TextInput(attrs={'class': 'form-control'}),
        }

class RegistroEstudiosPorMedicoCreateViewForm(forms.ModelForm):
    tipo_estudio = forms.ChoiceField(
        choices=[('', 'Seleccione')] + list(Estudios.TIPO_ESTUDIO_CHOICES),
        required=True,
        label="Tipo de estudio",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'id': 'id_tipo_estudio'}),
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
            'nombre_paciente': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'apellido_paciente': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'dni_paciente': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'maxlength': 8}),
            'estudio': forms.SelectMultiple(attrs={'class': 'form-control form-control-sm', 'size': '5'}),
            'cantidad_estudio': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 1}),
            'fecha_del_informe': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control form-control-sm'},
                format='%Y-%m-%d'  # 👈 este formato es CLAVE
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
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
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
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"

class RegistroProcedimientosIntervensionismoCreateViewForm(forms.ModelForm):
    class Meta:
        model = RegistroProcedimientosIntervensionismo
        fields = ['nombre_paciente', 'apellido_paciente', 'dni_paciente', 'fecha_del_procedimiento', 'procedimiento', 'notas', 'conteo_regiones']
        widgets = {
            'nombre_paciente': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
            }),
            'apellido_paciente': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
            }),
            'dni_paciente': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'maxlength': 8,
            }),
            'procedimiento': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'row' : 3,
            }),
            'fecha_del_procedimiento': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control form-control-sm',
            }),
            'conteo_regiones': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'min': 0,
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 3,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('fecha_del_procedimiento'):
            self.fields['fecha_del_procedimiento'].initial = timezone.now().date()

User = get_user_model()

class FiltroProcedimientosIntervensionismoForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Médicos de staff').order_by('first_name', 'last_name'),
        required=False,
        label="Médico",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
        empty_label="Todos los médicos"
    )
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        initial=datetime.now().month,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
        required=False, 
        label="Mes"
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
        required=False, 
        label="Año",
        initial=datetime.now().year  # Establecer el año actual como valor inicial
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"

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
