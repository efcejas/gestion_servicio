"""
Formularios para gestión de pedidos de estudios.
"""
from django import forms
from .models import PedidoEstudio, PacienteEstudio, TipoEstudio


class PedidoEstudioForm(forms.ModelForm):
    """
    Formulario para crear/editar pedidos de estudio manualmente.
    """
    class Meta:
        model = PedidoEstudio
        fields = [
            'paciente', 'tipo_estudio', 'descripcion_estudio',
            'indicacion_clinica', 'medico_solicitante',
            'medico_asignado', 'estado', 'prioridad',
            'fecha_programada', 'observaciones'
        ]
        widgets = {
            'descripcion_estudio': forms.Textarea(attrs={'rows': 3}),
            'indicacion_clinica': forms.Textarea(attrs={'rows': 2}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
            'fecha_programada': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class PacienteEstudioForm(forms.ModelForm):
    """
    Formulario para crear/editar pacientes.
    """
    class Meta:
        model = PacienteEstudio
        fields = [
            'nombre_completo', 'dni', 'historia_clinica',
            'telefono', 'email', 'fecha_nacimiento',
            'obra_social', 'numero_afiliado',
            'piso', 'habitacion', 'cama'
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
        }


class FiltroPedidosForm(forms.Form):
    """
    Formulario para filtrar pedidos.
    """
    ESTADOS = PedidoEstudio.ESTADOS + [('', 'Todos')]
    PRIORIDADES = PedidoEstudio.PRIORIDADES + [('', 'Todas')]
    
    estado = forms.ChoiceField(
        choices=ESTADOS,
        required=False,
        label='Estado'
    )
    prioridad = forms.ChoiceField(
        choices=PRIORIDADES,
        required=False,
        label='Prioridad'
    )
    tipo_estudio = forms.ModelChoiceField(
        queryset=TipoEstudio.objects.filter(activo=True),
        required=False,
        empty_label='Todos los tipos',
        label='Tipo de Estudio'
    )
    requiere_revision = forms.BooleanField(
        required=False,
        label='Solo pendientes de revisión'
    )
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Desde'
    )
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Hasta'
    )
    buscar = forms.CharField(
        required=False,
        max_length=200,
        label='Buscar',
        widget=forms.TextInput(attrs={
            'placeholder': 'Nombre paciente, médico, descripción...'
        })
    )


class RevisarPedidoForm(forms.ModelForm):
    """
    Formulario simplificado para revisión de pedidos.
    """
    class Meta:
        model = PedidoEstudio
        fields = [
            'paciente', 'tipo_estudio', 'descripcion_estudio',
            'indicacion_clinica', 'medico_solicitante',
            'medico_asignado', 'prioridad', 'observaciones'
        ]
        widgets = {
            'descripcion_estudio': forms.Textarea(attrs={'rows': 3}),
            'indicacion_clinica': forms.Textarea(attrs={'rows': 2}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }
