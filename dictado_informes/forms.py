from django import forms
from .models import TerminoMedico, CategoriaTerminoMedico, PlantillaEstructurada


class PlantillaEstructuradaForm(forms.ModelForm):
    """Formulario para crear/editar plantillas estructuradas con comentarios base"""
    
    # Campo para editar comentarios como texto (uno por línea)
    comentarios_base_texto = forms.CharField(
        label='Comentarios Base (una línea por anatomía normal)',
        widget=forms.Textarea(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
            'rows': 8,
            'placeholder': 'Meniscos de altura y señal normales.\nLigamentos cruzados de trayecto y morfología conservados.\nResto de tendones y ligamentos de la rodilla sin alteraciones.\n...\n\n(Cada línea es un comentario separado de anatomía normal)',
            'spellcheck': 'false'
        }),
        help_text='Escribe cada línea de anatomía normal en una nueva línea. Estas líneas se preservan en modo ESTRUCTURADO si no fueron mencionadas en el dictado.',
        required=False
    )
    
    class Meta:
        model = PlantillaEstructurada
        fields = ['codigo', 'nombre', 'titulo', 'seccion_tecnica', 'comentarios_base_texto', 'activa', 'compartida']
        widgets = {
            'codigo': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'placeholder': 'RODILLA, CADERA, HOMBRO, etc.',
                'readonly': True,  # No permitir cambiar código después de creado
            }),
            'nombre': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'placeholder': 'RM de Rodilla'
            }),
            'titulo': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'placeholder': 'RM DE RODILLA [<DERECHA/IZQUIERDA>]'
            }),
            'seccion_tecnica': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'rows': 4,
                'placeholder': 'Se exploró la rodilla [<lado>] con secuencias que ponderan tiempos de relajación T1, T2 y STIR en los diferentes planos.'
            }),
            'activa': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-indigo-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
            }),
            'compartida': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-indigo-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
            })
        }
        labels = {
            'codigo': 'Código Único',
            'nombre': 'Nombre Descriptivo',
            'titulo': 'Título de la Plantilla',
            'seccion_tecnica': 'Sección Técnica',
            'activa': 'Activa',
            'compartida': '¿Compartir esta plantilla con otros usuarios de Dictado IA?'
        }
        help_texts = {
            'compartida': 'Si la compartes, otros usuarios del módulo podrán usarla en Dictado Rápido. Si no, quedará solo para vos y para superusuarios.'
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Si es edición, cargar comentarios_base del JSON a textarea
        if self.instance.pk:
            comentarios = self.instance.comentarios_base or []
            self.fields['comentarios_base_texto'].initial = '\n'.join(comentarios)
            # Permitir editar código solo en creación
            if self.instance.pk:
                self.fields['codigo'].widget.attrs['readonly'] = True
        else:
            # En creación, permitir editar código
            self.fields['codigo'].widget.attrs['readonly'] = False

        if user and getattr(user, 'rol', None) == 'piloto_dictado' and not self.instance.pk:
            self.fields['compartida'].initial = False
    
    def clean_codigo(self):
        """Validar que el código sea único (excepto para la instancia actual)"""
        codigo = self.cleaned_data.get('codigo', '').upper().strip()
        
        if not codigo:
            raise forms.ValidationError('El código no puede estar vacío.')
        
        # Permitir el mismo código si estamos editando
        if self.instance.pk:
            existing = PlantillaEstructurada.objects.filter(codigo=codigo).exclude(pk=self.instance.pk)
        else:
            existing = PlantillaEstructurada.objects.filter(codigo=codigo)
        
        if existing.exists():
            raise forms.ValidationError(f'Ya existe una plantilla con el código "{codigo}". El código debe ser único.')
        
        return codigo.upper()
    
    def clean_comentarios_base_texto(self):
        """Convertir textarea a lista JSON"""
        texto = self.cleaned_data.get('comentarios_base_texto', '').strip()
        
        if not texto:
            return []
        
        # Dividir por líneas y filtrar vacías
        lineas = [l.strip() for l in texto.split('\n') if l.strip()]
        
        if not lineas:
            return []
        
        return lineas
    
    def save(self, commit=True):
        """Guardar comentarios_base como lista JSON"""
        instance = super().save(commit=False)
        instance.comentarios_base = self.cleaned_data['comentarios_base_texto']
        if commit:
            instance.save()
        return instance


class TerminoMedicoForm(forms.ModelForm):
    """Formulario para crear/editar términos médicos"""
    
    class Meta:
        model = TerminoMedico
        fields = ['termino_incorrecto', 'termino_correcto', 'categoria', 'notas', 'activo']
        widgets = {
            'termino_incorrecto': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'placeholder': 'Ej: con artrosis trick compartimental'
            }),
            'termino_correcto': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'placeholder': 'Ej: gonartrosis tricompartimental'
            }),
            'categoria': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white'
            }),
            'notas': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'rows': 3,
                'placeholder': 'Notas opcionales sobre este término...'
            }),
            'activo': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-indigo-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
            })
        }
        labels = {
            'termino_incorrecto': 'Término Incorrecto (como lo transcribe el navegador)',
            'termino_correcto': 'Término Correcto (término médico profesional)',
            'categoria': 'Categoría',
            'notas': 'Notas',
            'activo': 'Activo'
        }
