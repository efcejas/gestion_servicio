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
            'tipo_estudio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'sector_solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'medico_solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'prioridad': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_paciente': 'Nombre y apellido del paciente',
            'dni_paciente': 'DNI del paciente',
            'modalidad': 'Modalidad',
            'tipo_estudio': 'Estudio solicitado',
            'sector_solicitante': 'Área de pertenencia del paciente',
            'medico_solicitante': 'Médico solicitante',
            'prioridad': 'Prioridad',
        }
        help_texts = {
            'nombre_paciente': 'Ingrese el nombre y apellido del paciente.',
            'dni_paciente': 'Ingrese el DNI del paciente (opcional).',
            'modalidad': 'Seleccione la modalidad del estudio.',
            'tipo_estudio': 'Ingrese el estudio solicitado. Por ejemplo: TC de abdomen, TC de tórax, etc. De ser posible, incluir el diagnóstico o el motivo de la solicitud.',
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
    
# filtro para el listado de pedidos

class FiltroPedidoEstudioForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por nombre o DNI'
        })
    )
    estado = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos')] + PedidoEstudio.ESTADO_CHOICES,
        label="Estado",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    prioridad = forms.ChoiceField(
        required=False,
        choices=[('', 'Todas')] + PedidoEstudio.PRIORIDAD_CHOICES,
        label="Prioridad",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    modalidad = forms.ChoiceField(
        required=False,
        choices=[('', 'Todas')] + PedidoEstudio.MODALIDAD_CHOICES,
        label="Modalidad",
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )