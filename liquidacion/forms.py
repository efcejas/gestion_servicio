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
                'class': 'form-control',
            }),
            'nombre_paciente': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'apellido_paciente': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'dni_paciente': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'estudio': forms.SelectMultiple(attrs={  # Cambiado a SelectMultiple
                'class': 'form-control',
                'size': 5,  # Tamaño del selector para facilitar la selección de múltiples estudios
            }),
            'fecha_del_informe': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
        }

    def clean_dni_paciente(self):
        """
        Valida el campo DNI para asegurarse de que contenga solo números y tenga 8 dígitos.
        """
        dni = self.cleaned_data.get('dni_paciente')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI debe contener solo números.')
        if len(dni) != 8:
            raise forms.ValidationError('El DNI debe tener 8 dígitos.')
        return dni
