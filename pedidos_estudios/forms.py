from django import forms
from .models import PedidoEstudio, PedidoEstudioNota

class PedidoEstudioForm(forms.ModelForm):
    class Meta:
        model = PedidoEstudio
        fields = [
            'nombre_paciente',
            'dni_paciente',
            'modalidad',
            'tipo_estudio',
            'sector_solicitante',
            'medico_solicitante',
            'prioridad',
        ]
        widgets = {
            'nombre_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'dni_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'modalidad': forms.Select(attrs={'class': 'form-select'}),
            'tipo_estudio': forms.TextInput(attrs={'class': 'form-control'}),
            'sector_solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'medico_solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'prioridad': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_paciente': 'Nombre y Apellido del Paciente',
            'dni_paciente': 'DNI del Paciente',
            'modalidad': 'Modalidad',
            'tipo_estudio': 'Estudio Solicitado',
            'sector_solicitante': 'Sector Solicitante',
            'medico_solicitante': 'Médico Solicitante',
            'prioridad': 'Prioridad',
        }
        help_texts = {
            'nombre_paciente': 'Ingrese el nombre y apellido del paciente.',
            'dni_paciente': 'Ingrese el DNI del paciente (opcional).',
            'modalidad': 'Seleccione la modalidad del estudio.',
            'tipo_estudio': 'Ingrese el tipo de estudio solicitado.',
            'sector_solicitante': 'Ingrese a qué sector pertenece la solicitud. Por ejemplo: Habitación 345, UTI 212, Guardia, etc.',
            'medico_solicitante': 'Ingrese el nombre del médico solicitante (opcional).',
            'prioridad': 'Seleccione la prioridad del estudio.',
        }

class PedidoEstudioNotaForm(forms.ModelForm):
    class Meta:
        model = PedidoEstudioNota
        fields = ['comentario']
        widgets = {
            'comentario': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Agregar un comentario...',
                'rows': 3
            }),
        }

class ActualizarEstadoPedidoForm(forms.ModelForm):
    class Meta:
        model = PedidoEstudio
        fields = ['estado']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {'estado': 'Actualizar estado'}

    def save(self, commit=True, usuario=None):
        instance = super().save(commit=False)
        if commit:
            instance.save(usuario=usuario)  # 👈 activa la lógica del modelo
        return instance

