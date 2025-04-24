from django import forms
from .models import EventoServicio


class EventoServicioForm(forms.ModelForm):
    class Meta:
        model = EventoServicio
        fields = [
            'tipo_evento',
            'descripcion',
            'nombre_paciente',
            'dni_paciente',
            'estudio_relacionado'
        ]
        widgets = {
            'tipo_evento': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'cols': 40
            }),
            'nombre_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'dni_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'estudio_relacionado': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'tipo_evento': 'Tipo de evento',
            'descripcion': 'Descripción del evento',
            'nombre_paciente': 'Nombre y apellido del paciente',
            'dni_paciente': 'DNI del paciente',
            'estudio_relacionado': 'Estudio relacionado',
        }
        help_texts = {
            'descripcion': (
                'Proporcione una descripción detallada del evento, incluyendo, '
                'si aplica, el nombre y apellido de la persona con quien se habló.'
            ),
        }
