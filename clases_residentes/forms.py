from django import forms
from .models import ClaseResidente, ComentarioClase


# Límites de tamaño de archivo (en bytes)
MAX_ARCHIVO_SIZE = 20 * 1024 * 1024  # 20 MB (límite de Cloudinary free)
MAX_THUMBNAIL_SIZE = 5 * 1024 * 1024  # 5 MB para imágenes


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
                  'archivo', 'archivo_thumbnail', 'fecha_clase', 'tags', 'es_destacada']
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
            'archivo_thumbnail': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none',
                'accept': 'image/*'
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
    
    def clean_archivo(self):
        """Validar tamaño del archivo principal"""
        archivo = self.cleaned_data.get('archivo')
        
        if archivo:
            # Si es un archivo nuevo (no una ruta existente)
            if hasattr(archivo, 'size'):
                if archivo.size > MAX_ARCHIVO_SIZE:
                    size_mb = archivo.size / (1024 * 1024)
                    raise forms.ValidationError(
                        f'El archivo es demasiado grande ({size_mb:.1f} MB). '
                        f'El tamaño máximo permitido es 20 MB. '
                        f'Por favor, comprime el archivo o sube una versión más liviana.'
                    )
        
        return archivo
    
    def clean_archivo_thumbnail(self):
        """Validar tamaño de la imagen de portada"""
        thumbnail = self.cleaned_data.get('archivo_thumbnail')
        
        if thumbnail:
            if hasattr(thumbnail, 'size'):
                if thumbnail.size > MAX_THUMBNAIL_SIZE:
                    size_mb = thumbnail.size / (1024 * 1024)
                    raise forms.ValidationError(
                        f'La imagen es demasiado grande ({size_mb:.1f} MB). '
                        f'El tamaño máximo permitido es 5 MB.'
                    )
        
        return thumbnail
    
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
