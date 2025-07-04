from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import EventoServicio, NotaEvento

class EventoServicioForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Opciones base (todas menos guardia/internado)
        base_choices = [
            ('cancelado', 'Estudio cancelado'),
            ('demorado', 'Estudio demorado'),
            ('pendiente', 'Estudio pendiente'),
            ('tecnico', 'Problema técnico'),
            ('conflicto', 'Conflicto o situación interpersonal'),
            ('otro', 'Otro'),
        ]
        # Si es técnico de resonancia, agrega las opciones extra
        if user and user.groups.filter(name="Técnicos de resonancia").exists():
            base_choices += [
                ('guardia', 'Estudio de guardia realizado'),
                ('internado', 'Estudio de paciente internado realizado'),
            ]
        self.fields['tipo_evento'].choices = base_choices

    class Meta:
        model = EventoServicio
        fields = [
            'tipo_evento',
            'descripcion',
            'sector_de_pedido',
            'nombre_paciente',
            'dni_paciente',
            'estudio_relacionado',
            'servicio_origen_evento',
        ]
        widgets = {
            'tipo_evento': forms.Select(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'cols': 40
            }),
            'servicio_origen_evento': forms.Select(attrs={'class': 'form-select'}),
            'sector_de_pedido': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'dni_paciente': forms.TextInput(attrs={'class': 'form-control'}),
            'estudio_relacionado': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'tipo_evento': 'Tipo de evento',
            'descripcion': 'Descripción del evento',
            'servicio_origen_evento': 'Servicio',
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
            'servicio_origen_evento': (
                'Seleccione el servicio desde donde se generó el evento. '
                'Por ejemplo: si el evento es sobre un paciente de ecografía, seleccione "Ecografía".'
            ),
            'sector_de_pedido': (
                'Si aplica, indique desde donde se generó el pedido y/o donde se localiza el paciente. ejemplo: Guardia, habitación 123, etc.'
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        # Solo validar si tenemos los datos mínimos necesarios
        if not cleaned_data.get('tipo_evento') or not cleaned_data.get('descripcion'):
            return cleaned_data
        
        # Verificar duplicados en los últimos 5 minutos
        hace_5_minutos = timezone.now() - timedelta(minutes=5)
        
        # Obtener el usuario desde la vista (si está disponible)
        user = getattr(self, '_user', None)
        if not user:
            return cleaned_data
            
        duplicados = EventoServicio.objects.filter(
            creado_por=user,
            tipo_evento=cleaned_data['tipo_evento'],
            descripcion=cleaned_data['descripcion'],
            dni_paciente=cleaned_data.get('dni_paciente', ''),
            fecha_creacion__gte=hace_5_minutos
        )
        
        if duplicados.exists():
            raise forms.ValidationError(
                "Ya has registrado un evento similar en los últimos 5 minutos. "
                "Por favor, revisa la lista de eventos antes de crear uno nuevo."
            )
        
        return cleaned_data

    def save(self, commit=True):
        # Almacenar el usuario para la validación
        if hasattr(self, '_user'):
            instance = super().save(commit=False)
            if commit:
                instance.save()
            return instance
        return super().save(commit=commit)

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
        if usuario:
            instance.save(usuario=usuario)  # Pasa el usuario al método save del modelo
        elif commit:
            instance.save()  # Guarda normalmente si no se pasa usuario
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
        if usuario:
            instance.save(usuario=usuario)  # Pasa el usuario al método save del modelo
        elif commit:
            instance.save()  # Guarda normalmente si no se pasa usuario
        return instance

class FiltroEventoForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por paciente o DNI'
        })
    )
    tipo_evento = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos')] + EventoServicio.TIPO_EVENTO_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    fecha_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )
    fecha_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-sm',
            'type': 'date'
        })
    )