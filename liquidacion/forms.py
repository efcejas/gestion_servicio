from django import forms
from django.forms.models import inlineformset_factory
from .models import RegistroDiario, DetalleRegistro

class RegistroDiarioForm(forms.ModelForm):
    class Meta:
        model = RegistroDiario
        fields = ['medico', 'paciente', 'fecha']  # Campos principales
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'})
        }

DetalleRegistroFormSet = inlineformset_factory(
    RegistroDiario,  # Modelo principal
    DetalleRegistro,  # Modelo relacionado
    fields=('estudio', 'cantidad'),  # Campos que se incluirán
    extra=1,  # Número de formularios extra para agregar más registros
    can_delete=True  # Permitir eliminar detalles existentes
)
