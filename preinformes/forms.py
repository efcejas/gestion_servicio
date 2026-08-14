from django import forms
from django.contrib.auth import get_user_model
from .models import (
    Preinforme,
    PlantillaPreinforme,
    RevisionPreinforme,
    TipoEstudio,
    Region,
    prepare_editor_html_content,
)

User = get_user_model()

DEMO_PATIENT_SENTINEL = '[DEMO]'
PATIENT_IDENTITY_FIELDS = (
    'apellido_paciente',
    'nombre_paciente',
    'dni_paciente',
    'edad_paciente',
    'sexo_paciente',
)


class PreinformeForm(forms.ModelForm):
    """Formulario para crear/editar preinformes"""
    
    # Campo adicional para asignar revisor
    revisor = forms.ModelChoiceField(
        queryset=User.objects.filter(
            rol__in=['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'],
            is_demo_user=False,
        ).order_by('first_name', 'last_name'),
        required=False,
        empty_label="Asignar revisor (opcional)",
        label="Asignar a",
        help_text="Selecciona un médico staff para que revise este preinforme",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
        })
    )
    
    # Campo para asignación compartida
    asignacion_compartida = forms.BooleanField(
        required=False,
        initial=False,
        label="Pool compartido",
        help_text="Enviar a pool compartido de jefes/instructores (no asignar a revisor específico)",
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded',
            'id': 'id_asignacion_compartida'
        })
    )
    
    class Meta:
        model = Preinforme
        fields = [
            'numero_estudio',
            'tipo_estudio', 
            'region',
            'sistema_destino',
            'plantilla_utilizada',
            'revisor',
            'asignacion_compartida',
            'apellido_paciente',
            'nombre_paciente',
            'dni_paciente',
            'edad_paciente',
            'sexo_paciente',
            'contexto_clinico',
            'informe_html'  # Campo único simplificado
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
                'placeholder': 'DNI (opcional)',
            }),
            'edad_paciente': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'min': '0',
                'max': '120'
            }),
            'sexo_paciente': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
            }),
            'contexto_clinico': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors resize-y min-h-[72px]',
                'rows': 2,
                'maxlength': 1000,
                'placeholder': 'Ej: dolor en FID, control postoperatorio, sospecha clinica o pregunta concreta.'
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
            # informe_html usa CKEditor5Field del modelo - NO necesita widget aquí
        }
    
    def __init__(self, *args, **kwargs):
        # Extraer el usuario del kwargs
        user = kwargs.pop('user', None)
        self.user = user
        self.is_demo_user = bool(getattr(user, 'is_demo_user', False))
        super().__init__(*args, **kwargs)
        
        # Configurar el campo revisor para mostrar nombre completo
        self.fields['revisor'].label_from_instance = lambda obj: obj.get_full_name() or obj.username
        
        # Hacer que el DNI no sea obligatorio para residentes
        self.fields['dni_paciente'].required = False

        if self.is_demo_user:
            for field_name in PATIENT_IDENTITY_FIELDS:
                self.fields.pop(field_name, None)
        
        # Si estamos procesando datos del formulario (POST), permitir todas las plantillas activas
        # para que pase la validación inicial. El método clean_plantilla_utilizada validará correctamente
        if self.is_bound and self.data:
            self.fields['plantilla_utilizada'].queryset = PlantillaPreinforme.objects.filter(activa=True)
        else:
            # En carga inicial, mantener vacío para carga dinámica via JavaScript
            self.fields['plantilla_utilizada'].queryset = PlantillaPreinforme.objects.none()
            self.fields['plantilla_utilizada'].empty_label = "Primero selecciona tipo y región"
        
        # Filtrar tipos de estudio y regiones activas
        self.fields['tipo_estudio'].queryset = TipoEstudio.objects.filter(activo=True)
        self.fields['region'].queryset = Region.objects.filter(activo=True)
        
        # Filtrar revisores según el rol del usuario
        if user:
            if user.rol == 'medico_residente':
                # Residentes pueden asignar a: staff, jefes, instructores y jefe servicio
                self.fields['revisor'].queryset = User.objects.filter(
                    rol__in=['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'],
                    is_demo_user=False,
                ).order_by('first_name', 'last_name')
            elif user.rol in ['jefe_residentes', 'instructor_residentes']:
                # Jefes e instructores solo pueden asignar a: staff y jefe servicio
                self.fields['revisor'].queryset = User.objects.filter(
                    rol__in=['medico_staff', 'jefe_servicio'],
                    is_demo_user=False,
                ).order_by('first_name', 'last_name')
    
    def clean_plantilla_utilizada(self):
        """
        Validación personalizada para plantilla_utilizada.
        Como el queryset inicial es .none() para carga dinámica,
        necesitamos validar manualmente contra la base de datos.
        """
        plantilla = self.cleaned_data.get('plantilla_utilizada')
        
        if plantilla:
            # Validar que la plantilla existe y es válida para el tipo y región seleccionados
            tipo_estudio = self.cleaned_data.get('tipo_estudio')
            region = self.cleaned_data.get('region')
            
            try:
                # Verificar que la plantilla existe y coincide con tipo_estudio y region
                plantilla_valida = PlantillaPreinforme.objects.get(
                    id=plantilla.id,
                    tipo_estudio=tipo_estudio,
                    region=region,
                    activa=True
                )
                return plantilla_valida
            except PlantillaPreinforme.DoesNotExist:
                raise forms.ValidationError(
                    "La plantilla seleccionada no es válida para el tipo de estudio y región especificados."
                )
        
        return plantilla
    
    def clean(self):
        """Validación para asegurar que asignación compartida y revisor no estén ambos activos"""
        cleaned_data = super().clean()
        asignacion_compartida = cleaned_data.get('asignacion_compartida')
        revisor = cleaned_data.get('revisor')
        
        if asignacion_compartida and revisor:
            raise forms.ValidationError(
                "No puedes asignar a un revisor específico si el estudio está en pool compartido. "
                "Desmarca 'Pool compartido' o deja el revisor vacío."
            )
        
        return cleaned_data

    def clean_informe_html(self):
        contenido = self.cleaned_data.get('informe_html', '')
        return prepare_editor_html_content(contenido)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.is_demo_user:
            instance.apellido_paciente = DEMO_PATIENT_SENTINEL
            instance.nombre_paciente = DEMO_PATIENT_SENTINEL
            instance.dni_paciente = ''
            instance.edad_paciente = None
            instance.sexo_paciente = None
            instance.es_registro_demo = True
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class FiltroPreinformesForm(forms.Form):
    """Formulario para filtrar preinformes"""
    
    ESTADO_CHOICES = [('', 'Todos')] + Preinforme.ESTADO_CHOICES
    
    estado = forms.ChoiceField(
        choices=ESTADO_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500'})
    )

    sistema_destino = forms.ChoiceField(
        choices=[('', 'Todos los sistemas')] + list(Preinforme.SISTEMA_CHOICES),
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

    apellido_paciente = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Buscar por apellido de paciente...'
        })
    )

    nombre_paciente = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Buscar por nombre de paciente...'
        })
    )

    paciente = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 bg-white text-gray-900 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'DNI, nombre, apellido o N.º de estudio...',
            'autocomplete': 'off',
        }),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if getattr(user, 'is_demo_user', False):
            self.fields.pop('paciente', None)
            self.fields.pop('apellido_paciente', None)
            self.fields.pop('nombre_paciente', None)


class FiltroRevisionPreinformesForm(FiltroPreinformesForm):
    """Filtros de staff con una única búsqueda identificatoria."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('numero_estudio', None)
        self.fields.pop('apellido_paciente', None)
        self.fields.pop('nombre_paciente', None)


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

        # Setear spellcheck solo si el destino es EGES
        sistema_destino = None
        if preinforme:
            sistema_destino = getattr(preinforme, 'sistema_destino', None)
        elif hasattr(self.instance, 'preinforme') and self.instance.preinforme:
            sistema_destino = getattr(self.instance.preinforme, 'sistema_destino', None)

        if sistema_destino == 'eges':
            self.fields['informe_final_html'].widget.attrs['spellcheck'] = 'true'
        else:
            self.fields['informe_final_html'].widget.attrs['spellcheck'] = 'false'

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

    def clean_informe_final_html(self):
        contenido = self.cleaned_data.get('informe_final_html', '')
        return prepare_editor_html_content(contenido)


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

    def clean_contenido(self):
        contenido = self.cleaned_data.get('contenido', '')
        return prepare_editor_html_content(contenido)


class GenerarPlantillaIAForm(forms.Form):
    """Datos mínimos que orientan la propuesta estructurada."""

    tipo_estudio = forms.ModelChoiceField(
        queryset=TipoEstudio.objects.filter(activo=True),
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.filter(activo=True),
    )
    estudio_especifico = forms.CharField(min_length=2, max_length=200)
    instruccion_usuario = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea,
    )
    lateralidad_aplicable = forms.BooleanField(required=False)
    equipo_aplicable = forms.BooleanField(required=False)
    contraste_ev_aplicable = forms.BooleanField(required=False)
    contraste_oral_aplicable = forms.BooleanField(required=False)


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
        fields = ['nombre', 'sistema_destino', 'contenido']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500',
                'placeholder': 'Ej: TC Tórax Normal, RX Rodilla con Fractura...'
            }),
            'sistema_destino': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-sm border border-gray-300 bg-white text-gray-900 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500',
                'id': 'id_sistema_destino_plantilla'
            }),
            # contenido usa CKEditor5Field del modelo - NO necesita widget aquí (se renderiza automáticamente)
        }
    
    def __init__(self, *args, tipo_estudio=None, region=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tipo_estudio = tipo_estudio
        self.region = region
        
        # Hacer que al menos un campo de contenido sea requerido
        self.fields['contenido'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        contenido = cleaned_data.get('contenido')
        
        # Validar que tenga contenido
        if not contenido or not contenido.strip():
            raise forms.ValidationError(
                "Debe ingresar el contenido de la plantilla"
            )
        
        return cleaned_data

    def clean_contenido(self):
        contenido = self.cleaned_data.get('contenido', '')
        return prepare_editor_html_content(contenido)
