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
    
    # Campo oculto para guardar el public_id del video subido a Cloudinary
    archivo_video_public_id = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    class Meta:
        model = ClaseResidente
        fields = ['titulo', 'descripcion', 'categoria', 'anios_dirigidos', 
                  'archivo', 'archivo_video', 'archivo_thumbnail', 'fecha_clase', 'tags', 'es_destacada']
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
            'archivo_video': forms.HiddenInput(),  # Se maneja con widget de Cloudinary
            'archivo_thumbnail': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none',
                'accept': 'image/*'
            }),
            'fecha_clase': forms.DateInput(format='%Y-%m-%d', attrs={
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
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Si el usuario NO es jefe o instructor, ocultar campo es_destacada
        if self.usuario and self.usuario.rol not in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']:
            self.fields['es_destacada'].widget = forms.HiddenInput()
        # Forzar formato de fecha para edición
        if 'fecha_clase' in self.fields and self.instance and self.instance.pk and self.instance.fecha_clase:
            self.initial['fecha_clase'] = self.instance.fecha_clase.strftime('%Y-%m-%d')
    
    def clean_archivo(self):
        """
        Valida que el archivo tenga una extensión permitida (solo documentos).
        Los videos se manejan por separado.
        """
        archivo = self.cleaned_data.get('archivo')
        if archivo:
            # Solo validar si es un archivo nuevo (no un FileField existente)
            if hasattr(archivo, 'name'):
                nombre_archivo = archivo.name.lower()
                extension = nombre_archivo.split('.')[-1] if '.' in nombre_archivo else ''
                
                EXTENSIONES_DOCUMENTO = [
                    'ppt', 'pptx', 'pdf', 'key'
                ]
                
                if extension not in EXTENSIONES_DOCUMENTO:
                    raise forms.ValidationError(
                        f'Formato de archivo no soportado. '
                        f'Extensiones permitidas para documentos: {", ".join(EXTENSIONES_DOCUMENTO)}. '
                        f'Para videos, usa el botón "Subir Video".'
                    )
        
        return archivo
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Convertir MultipleChoiceField a lista para JSONField
        anios = self.cleaned_data.get('anios_dirigidos', [])
        instance.anios_dirigidos = list(anios) if anios else []
        
        # Manejar public_id de video de Cloudinary
        archivo_video_public_id = self.cleaned_data.get('archivo_video_public_id')
        if archivo_video_public_id:
            instance.archivo_video = archivo_video_public_id
            instance.tipo_archivo = 'video'
            # Limpiar archivo de documento si se sube video
            instance.archivo = None
        
        # Detectar automáticamente el tipo de archivo si hay un archivo de documento nuevo
        archivo = self.cleaned_data.get('archivo')
        if archivo and hasattr(archivo, 'name'):
            nombre_archivo = archivo.name.lower()
            extension = nombre_archivo.split('.')[-1] if '.' in nombre_archivo else ''
            instance.tipo_archivo = 'documento'
            # Limpiar video si se sube documento
            instance.archivo_video = None

        # Eliminar archivo si el usuario lo solicita
        request = getattr(self, 'request', None)
        if request is not None:
            if request.POST.get('eliminar_archivo') == '1' and instance.archivo:
                instance.archivo.delete(save=False)
                instance.archivo = None
            if request.POST.get('eliminar_video') == '1' and instance.archivo_video:
                instance.archivo_video = None
            if request.POST.get('eliminar_imagen') == '1' and instance.archivo_thumbnail:
                instance.archivo_thumbnail = None

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
