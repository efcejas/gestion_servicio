from django import forms
from .models import EventoServicio, NotaEvento


class EventoServicioForm(forms.ModelForm):
    class Meta:
        model = EventoServicio
        fields = [
            'tipo_evento',
            'descripcion',
            'sector_de_pedido',
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
            'sector_de_pedido': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'dni_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'estudio_relacionado': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'tipo_evento': 'Tipo de evento',
            'descripcion': 'Descripción del evento',
            'sector_de_pedido': 'Sector de pedido',
            'nombre_paciente': 'Nombre y apellido del paciente',
            'dni_paciente': 'DNI del paciente',
            'estudio_relacionado': 'Estudio relacionado',
        }
        help_texts = {
            'descripcion': (
                'Proporcione una descripción detallada del evento, incluyendo, '
                'si aplica, el nombre y apellido de la persona con quien se habló.'
            ),
            'sector_de_pedido': (
                'Si aplica, indique desde donde se generó el pedido y/o donde se localiza el paciente. ejemplo: Guardia, habitación 123, etc.'
            ),
        }

class NotaEventoForm(forms.ModelForm):
    class Meta:
        model = NotaEvento
        fields = ['comentario']
        widgets = {
            'comentario': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Agregar una nota sobre este evento...'
            })
        }
        labels = {
            'comentario': 'Comentario'
        }

class ActualizarEstadoEventoForm(forms.ModelForm):
    class Meta:
        model = EventoServicio
        fields = ['estado']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'})
        }
        labels = {
            'estado': 'Actualizar estado del evento'
        }

    def save(self, commit=True, usuario=None):
        instance = super().save(commit=False)
        if commit:
            instance.save(usuario=usuario)
        return instance

class ActualizarTipoEventoForm(forms.ModelForm):
    class Meta:
        model = EventoServicio
        fields = ['tipo_evento']
        widgets = {
            'tipo_evento': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }
        labels = {
            'tipo_evento': 'Tipo de evento',
        }

    def save(self, commit=True, usuario=None):
        instance = super().save(commit=False)
        if commit:
            instance.save(usuario=usuario)
        return instance