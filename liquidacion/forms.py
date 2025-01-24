from django import forms
from .models import Medico, Estudios, RegistroEstudiosPorMedico

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
            'estudio': forms.SelectMultiple(attrs={  # Cambiado a SelectMultiple
                'class': 'form-control form-control-sm',
                'size': 3,  # Tamaño del selector para facilitar la selección de múltiples estudios
            }),
            'fecha_del_informe': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control form-control-sm',
            }),
        }
