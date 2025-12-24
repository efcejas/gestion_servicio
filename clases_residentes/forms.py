from django import forms
from .models import ClaseResidente, ComentarioClase


class ClaseResidenteForm(forms.ModelForm):
    """
    Formulario para crear y editar clases de residentes.
    """
    # Campo personalizado para selección múltiple de años
    anios_dirigidos = forms.MultipleChoiceField(
        choices=ClaseResidente.ANIO_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        }),
        required=False,
        help_text='Selecciona los años de residencia a los que va dirigida (deja vacío para "Todos")'
    )
    
    class Meta:
        model = ClaseResidente
        fields = ['titulo', 'descripcion', 'categoria', 'anios_dirigidos', 
                  'archivo', 'fecha_clase', 'tags', 'es_destacada']
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'Ej: Protocolo de TC de Tórax para Neumonía'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'rows': 4,
                'placeholder': 'Describe el contenido de la clase...'
            }),
            'categoria': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
            }),
            'archivo': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none',
                'accept': '.ppt,.pptx,.pdf,.key'
            }),
            'fecha_clase': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'type': 'date'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'tórax, covid, neumonía (separados por comas)'
            }),
            'es_destacada': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.usuario = kwargs.pop('usuario', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario NO es jefe o instructor, ocultar campo es_destacada
        if self.usuario and self.usuario.rol not in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']:
            self.fields['es_destacada'].widget = forms.HiddenInput()
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Convertir MultipleChoiceField a lista para JSONField
        anios = self.cleaned_data.get('anios_dirigidos', [])
        instance.anios_dirigidos = list(anios) if anios else []
        
        if commit:
            instance.save()
        return instance


class ComentarioClaseForm(forms.ModelForm):
    """
    Formulario para agregar comentarios a las clases.
    """
    class Meta:
        model = ComentarioClase
        fields = ['contenido']
        widgets = {
            'contenido': forms.Textarea(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'rows': 3,
                'placeholder': 'Escribe tu comentario o feedback sobre esta clase...'
            }),
        }


class BuscarClaseForm(forms.Form):
    """
    Formulario para buscar y filtrar clases.
    """
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
            'placeholder': 'Buscar por título, tags o descripción...'
        })
    )
    categoria = forms.ChoiceField(
        required=False,
        choices=[('', 'Todas las categorías')] + ClaseResidente.CATEGORIA_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
        })
    )
    anio = forms.ChoiceField(
        required=False,
        choices=[('', 'Todos los años')] + ClaseResidente.ANIO_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
        })
    )
    solo_destacadas = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
        })
    )
