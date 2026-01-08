from django import forms
from django.contrib.auth import get_user_model
from .models import Preinforme, PlantillaPreinforme, RevisionPreinforme, TipoEstudio, Region

User = get_user_model()


class PreinformeForm(forms.ModelForm):
    """Formulario para crear/editar preinformes"""
    
    class Meta:
        model = Preinforme
        fields = [
            'numero_estudio',
            'tipo_estudio', 
            'region',
            'sistema_destino',
            'plantilla_utilizada',
            'apellido_paciente',
            'nombre_paciente',
            'dni_paciente',
            'edad_paciente',
            'sexo_paciente',
            'tecnica',
            'hallazgos',
            'conclusion'
        ]
        widgets = {
            'numero_estudio': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'Ej: 2024-001234'
            }),
            'apellido_paciente': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'Apellido del paciente'
            }),
            'nombre_paciente': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'Nombre del paciente'
            }),
            'dni_paciente': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'DNI del paciente (ej: 12345678)',
                'pattern': '[0-9]{7,8}',
                'title': 'Ingrese un DNI válido (7 u 8 dígitos)'
            }),
            'edad_paciente': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'min': '0',
                'max': '120'
            }),
            'sexo_paciente': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
            }),
            'tipo_estudio': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'id': 'id_tipo_estudio'
            }),
            'region': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'id': 'id_region'
            }),
            'sistema_destino': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'id': 'id_sistema_destino'
            }),
            'plantilla_utilizada': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'id': 'id_plantilla'
            }),
            # tecnica, hallazgos y conclusion usan CKEditor5Field del modelo
            # NO necesitan widgets aquí
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar plantillas activas
        self.fields['plantilla_utilizada'].queryset = PlantillaPreinforme.objects.filter(activa=True)
        self.fields['plantilla_utilizada'].empty_label = "Seleccionar plantilla (opcional)"
        
        # Filtrar tipos de estudio y regiones activas
        self.fields['tipo_estudio'].queryset = TipoEstudio.objects.filter(activo=True)
        self.fields['region'].queryset = Region.objects.filter(activo=True)


class FiltroPreinformesForm(forms.Form):
    """Formulario para filtrar preinformes"""
    
    ESTADO_CHOICES = [('', 'Todos')] + Preinforme.ESTADO_CHOICES
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'})
    )
    
    tipo_estudio = forms.ModelChoiceField(
        queryset=TipoEstudio.objects.filter(activo=True),
        required=False,
        empty_label="Todos los tipos",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'})
    )
    
    region = forms.ModelChoiceField(
        queryset=Region.objects.filter(activo=True),
        required=False,
        empty_label="Todas las regiones",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'})
    )
    
    residente = forms.ModelChoiceField(
        queryset=User.objects.filter(rol='medico_residente'),
        required=False,
        empty_label="Todos los residentes",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'})
    )
    
    fecha_desde = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'type': 'date'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'type': 'date'
        })
    )
    
    numero_estudio = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Buscar por número de estudio...'
        })
    )


class RevisionPreinformeForm(forms.ModelForm):
    """Formulario para revisar preinformes"""
    
    class Meta:
        model = RevisionPreinforme
        fields = [
            'informe_final_html',
            'comentarios_generales',
            'puntuacion'
        ]
        widgets = {
            'comentarios_generales': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'rows': 4,
                'placeholder': 'Comentarios y sugerencias para el residente...'
            }),
            'puntuacion': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'min': '1',
                'max': '10',
                'placeholder': 'Puntuación del 1 al 10 (opcional)'
            })
            # informe_final_html uses CKEditor5Field from model
            # NO widget needed here
        }
    
    def __init__(self, *args, **kwargs):
        preinforme = kwargs.pop('preinforme', None)
        super().__init__(*args, **kwargs)
        
        # La vista ya maneja la pre-carga de informe_final_html
        # Aquí solo necesitamos asignar el preinforme si es nuevo
        if preinforme and not self.instance.pk:
            self.instance.preinforme = preinforme
        
        # Seguridad adicional: si por alguna razón llegamos aquí sin contenido,
        # usar el snapshot como initial value
        if self.instance.pk and not self.instance.informe_final_html:
            if self.instance.informe_residente_snapshot:
                self.fields['informe_final_html'].initial = self.instance.informe_residente_snapshot
            elif hasattr(self.instance, 'preinforme'):
                self.fields['informe_final_html'].initial = self.instance.generar_informe_original_residente()


class PlantillaPreinformeForm(forms.ModelForm):
    """Formulario para crear/editar plantillas"""
    
    class Meta:
        model = PlantillaPreinforme
        fields = ['nombre', 'tipo_estudio', 'region', 'contenido', 'activa']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-input rounded-md border-gray-300',
                'placeholder': 'Nombre de la plantilla'
            }),
            'tipo_estudio': forms.Select(attrs={
                'class': 'form-select rounded-md border-gray-300'
            }),
            'region': forms.Select(attrs={
                'class': 'form-select rounded-md border-gray-300'
            }),
            'contenido': forms.Textarea(attrs={
                'class': 'form-textarea rounded-md border-gray-300',
                'rows': 10,
                'placeholder': 'Contenido de la plantilla. Use {HALLAZGOS} para marcar donde el residente debe escribir...'
            }),
            'activa': forms.CheckboxInput(attrs={
                'class': 'form-checkbox rounded border-gray-300'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_estudio'].queryset = TipoEstudio.objects.filter(activo=True)
        self.fields['region'].queryset = Region.objects.filter(activo=True)


class NuevaPlantillaResidenteForm(forms.ModelForm):
    """Formulario simplificado para que residentes creen plantillas"""
    compartir = forms.BooleanField(
        required=False,
        initial=False,
        label="Compartir con todos los residentes",
        help_text="Si no se marca, solo tú podrás ver esta plantilla",
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500'
        })
    )
    
    class Meta:
        model = PlantillaPreinforme
        fields = ['nombre', 'sistema_destino', 'tecnica_template', 'hallazgos_template', 'conclusion_template']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500',
                'placeholder': 'Ej: TC Tórax Normal, RX Rodilla con Fractura...'
            }),
            'sistema_destino': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500',
                'id': 'id_sistema_destino_plantilla'
            }),
            'tecnica_template': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none',
                'rows': 2,
                'placeholder': 'Describe la técnica utilizada...'
            }),
            'hallazgos_template': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none',
                'rows': 3,
                'placeholder': 'Describe los hallazgos principales...'
            }),
            'conclusion_template': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none',
                'rows': 2,
                'placeholder': 'Escribe la conclusión o impresión diagnóstica...'
            }),
        }
    
    def __init__(self, *args, tipo_estudio=None, region=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo_estudio = tipo_estudio
        self.region = region
        
        # Hacer que al menos un campo de contenido sea requerido
        self.fields['tecnica_template'].required = False
        self.fields['hallazgos_template'].required = False
        self.fields['conclusion_template'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        tecnica = cleaned_data.get('tecnica_template')
        hallazgos = cleaned_data.get('hallazgos_template')
        conclusion = cleaned_data.get('conclusion_template')
        
        # Al menos uno debe tener contenido
        if not any([tecnica, hallazgos, conclusion]):
            raise forms.ValidationError(
                "Debe completar al menos una sección (Técnica, Hallazgos o Conclusión)"
            )
        
        return cleaned_data