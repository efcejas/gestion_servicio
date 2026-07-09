import json

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
    
    estructura_documento_texto = forms.CharField(
        label='Estructura flexible del documento (JSON avanzado)',
        widget=forms.Textarea(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-900 text-white font-mono text-xs',
            'rows': 12,
            'placeholder': '{\n  "modo": "estricta",\n  "permitir_secciones_nuevas": false,\n  "secciones": [\n    {"nombre": "TITULO", "tipo": "titulo", "contenido": "RM DE RODILLA"},\n    {"nombre": "TECNICA", "tipo": "tecnica", "contenido": "..."},\n    {"nombre": "HALLAZGOS", "tipo": "hallazgos", "lineas_base": ["..."]}\n  ]\n}',
            'spellcheck': 'false'
        }),
        help_text=(
            'Opcional. Si se completa, el agente respeta exactamente estas secciones. '
            'Si queda vacio, se deriva desde los campos clasicos.'
        ),
        required=False
    )

    class Meta:
        model = PlantillaEstructurada
        fields = [
            'codigo', 'nombre', 'titulo', 'seccion_tecnica', 'comentarios_base_texto',
            'guia_estilo', 'modo_estructura', 'permitir_secciones_nuevas',
            'estructura_documento_texto', 'activa', 'compartida'
        ]
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
            'guia_estilo': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white',
                'rows': 5,
                'placeholder': 'Ej: Para meniscos usar "de configuración habitual" en normalidad. En desgarros indicar grado Stoller y cuerno comprometido. Mantener conclusión breve en una línea.'
            }),
            'modo_estructura': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 bg-gray-700 text-white'
            }),
            'permitir_secciones_nuevas': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-indigo-600 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
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
            'guia_estilo': 'Guía de Estilo para IA',
            'modo_estructura': 'Modo de estructura',
            'permitir_secciones_nuevas': 'Permitir secciones nuevas',
            'activa': 'Activa',
            'compartida': '¿Compartir esta plantilla con otros usuarios de Dictado IA?'
        }
        help_texts = {
            'guia_estilo': (
                'Instrucciones de redacción para esta plantilla. '
                'La IA las toma con prioridad en modo ESTRUCTURADO.'
            ),
            'compartida': 'Si la compartes, otros usuarios del módulo podrán usarla en Dictado Rápido. Si no, quedará solo para vos y para superusuarios.'
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Si es edición, cargar comentarios_base del JSON a textarea
        if self.instance.pk:
            comentarios = self.instance.comentarios_base or []
            self.fields['comentarios_base_texto'].initial = '\n'.join(comentarios)
            if self.instance.estructura_documento:
                self.fields['estructura_documento_texto'].initial = json.dumps(
                    self.instance.estructura_documento,
                    ensure_ascii=False,
                    indent=2
                )
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

    def clean_estructura_documento_texto(self):
        texto = self.cleaned_data.get('estructura_documento_texto', '').strip()
        modo_estructura = self.cleaned_data.get('modo_estructura') or PlantillaEstructurada.MODO_ESTRUCTURA_LEGACY

        if not texto:
            if modo_estructura != PlantillaEstructurada.MODO_ESTRUCTURA_LEGACY:
                raise forms.ValidationError(
                    'Para usar estructura estricta, flexible o agente, carga una estructura JSON.'
                )
            return {}

        try:
            estructura = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f'JSON invalido: {exc.msg}') from exc

        if not isinstance(estructura, dict):
            raise forms.ValidationError('La estructura debe ser un objeto JSON.')

        secciones = estructura.get('secciones')
        if not isinstance(secciones, list) or not secciones:
            raise forms.ValidationError('La estructura debe incluir una lista no vacia en "secciones".')

        for idx, seccion in enumerate(secciones, 1):
            if not isinstance(seccion, dict):
                raise forms.ValidationError(f'La seccion #{idx} debe ser un objeto JSON.')
            if not str(seccion.get('nombre', '')).strip():
                raise forms.ValidationError(f'La seccion #{idx} debe incluir "nombre".')

            tipo = str(seccion.get('tipo', 'texto')).strip().lower()
            if tipo not in {'titulo', 'tecnica', 'hallazgos', 'conclusion', 'texto'}:
                raise forms.ValidationError(
                    f'La seccion #{idx} tiene tipo "{tipo}" no soportado.'
                )

            lineas_base = seccion.get('lineas_base')
            if lineas_base is not None and not isinstance(lineas_base, list):
                raise forms.ValidationError(f'La seccion #{idx} tiene "lineas_base" pero no es una lista.')

        estructura.setdefault('modo', modo_estructura)
        estructura.setdefault(
            'permitir_secciones_nuevas',
            bool(self.cleaned_data.get('permitir_secciones_nuevas'))
        )
        return estructura
    
    def save(self, commit=True):
        """Guardar comentarios_base como lista JSON"""
        instance = super().save(commit=False)
        instance.comentarios_base = self.cleaned_data['comentarios_base_texto']
        instance.estructura_documento = self.cleaned_data['estructura_documento_texto']
        if commit:
            instance.save()
        return instance


class ImportarPlantillaDocxForm(forms.Form):
    archivo_docx = forms.FileField(
        label='Archivo de plantilla',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'h-full w-full cursor-pointer opacity-0',
            'accept': '.doc,.docx,.txt,.md,.markdown,.rtf,.html,.htm,text/plain,text/markdown,text/rtf,text/html,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
        help_text='Sube una plantilla en formato .docx, .doc, .txt, .md, .rtf o .html. Se mostrara una vista previa antes de guardar.'
    )
    texto_plantilla = forms.CharField(
        label='O pega el texto de la plantilla',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-white text-sm focus:border-green-500 focus:outline-none',
            'rows': 10,
            'placeholder': 'Pega aqui el texto completo de la plantilla...',
        }),
        help_text='Puedes copiar desde Word, PDF, email u otro sistema y pegar aqui el contenido.'
    )

    def clean(self):
        cleaned_data = super().clean()
        archivo = cleaned_data.get('archivo_docx')
        texto = (cleaned_data.get('texto_plantilla') or '').strip()
        if not archivo and not texto:
            raise forms.ValidationError('Sube un archivo o pega el texto de la plantilla.')
        return cleaned_data

    def clean_archivo_docx(self):
        archivo = self.cleaned_data.get('archivo_docx')
        if not archivo:
            return archivo
        nombre = (archivo.name or '').lower()
        extensiones_permitidas = ('.doc', '.docx', '.txt', '.md', '.markdown', '.rtf', '.html', '.htm')
        if not nombre.endswith(extensiones_permitidas):
            raise forms.ValidationError('Formato no soportado. Usa .docx, .doc, .txt, .md, .rtf o .html.')

        max_mb = 5
        if archivo.size and archivo.size > max_mb * 1024 * 1024:
            raise forms.ValidationError(f'El archivo no debe superar {max_mb} MB.')

        return archivo


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
