from django import forms
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo
from datetime import datetime

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
        fields = ['medico', 'nombre_paciente', 'apellido_paciente', 'dni_paciente', 'fecha_del_informe', 'estudio']
        widgets = {
            'medico': forms.Select(attrs={
                'class': 'form-control form-control-sm',
            }),
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
            'estudio': forms.SelectMultiple(attrs={  # SelectMultiple con tooltips
                'class': 'form-control form-control-sm',
                'size': 3,
            }),
            'fecha_del_informe': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control form-control-sm',
            }),
        }

class FiltroMedicoMesForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=Medico.objects.all(), 
        required=False, 
        label="Médico",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
        empty_label="Todos los médicos",
        help_text="Seleccione el médico del cual desea obtener la información."
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

class FiltroProcedimientosIntervensionismoForm(forms.Form):
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