from django import forms
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group


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
    class Meta:
        model = RegistroEstudiosPorMedico
        fields = ['nombre_paciente', 'apellido_paciente', 'dni_paciente', 'fecha_del_informe', 'estudio']
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
            'estudio': forms.SelectMultiple(attrs={
                'class': 'form-control form-control-sm',
                'size': 3,
            }),
            'fecha_del_informe': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control form-control-sm',
            }),
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
            }),
            'notas': forms.Textarea(attrs={
                'class': 'form-control form-control-sm',
                'rows': 3,
            }),
        }

User = get_user_model()

class FiltroProcedimientosIntervensionismoForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=User.objects.filter(groups__name='Médicos de staff').order_by('first_name', 'last_name'),
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
        required=False,
        label="Médico"
    )
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
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