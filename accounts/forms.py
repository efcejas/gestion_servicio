from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser


class UsernameRecoveryForm(forms.Form):
    """Formulario para recuperar el nombre de usuario por email."""
    email = forms.EmailField(
        label='Correo electrónico',
        widget=forms.EmailInput(attrs={
            'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
            'placeholder': 'Ingresa el email registrado en tu cuenta',
            'autofocus': True,
        }),
    )

class CustomUserCreationForm(UserCreationForm):
    """
    Formulario de registro simplificado.
    Solo datos esenciales: username, email, password.
    El resto se completa después en CompletarPerfilForm.
    """
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Clase base Tailwind para todos los inputs
        base_class = 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = base_class
            field.widget.attrs['placeholder'] = field.label
        
        # Campos obligatorios
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class CompletarPerfilForm(forms.ModelForm):
    """
    Formulario para completar perfil post-registro.
    Pide rol, cargo específico, teléfono y preferencias.
    Para residentes, incluye fecha de ingreso para cálculo automático de año.
    """
    class Meta:
        model = CustomUser
        fields = ['rol', 'fecha_ingreso_residencia', 'cargo', 'telefono', 'recibir_notificaciones']
        widgets = {
            'rol': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'required': True,
                'onchange': 'toggleFechaIngreso()',
            }),
            'fecha_ingreso_residencia': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'type': 'date',
                'id': 'id_fecha_ingreso',
            }),
            'cargo': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'Ej: Diagnóstico por Imágenes',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'placeholder': 'Ej: +54 11 1234-5678',
            }),
            'recibir_notificaciones': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
        }
        labels = {
            'rol': '¿Cuál es tu rol en el servicio? *',
            'fecha_ingreso_residencia': 'Fecha de ingreso a la residencia *',
            'cargo': 'Especialidad o área (opcional)',
            'telefono': 'Teléfono de contacto',
            'recibir_notificaciones': 'Deseo recibir notificaciones por email',
        }
        help_texts = {
            'rol': 'Selecciona el rol que mejor describe tu función principal',
            'fecha_ingreso_residencia': 'Tu año de residencia (R1, R2, etc.) se calculará automáticamente',
            'cargo': 'Puedes especificar tu especialidad o área de interés',
            'telefono': 'Para contacto en caso de urgencias o guardias',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].required = True
        # Fecha de ingreso solo obligatoria para residentes
        self.fields['fecha_ingreso_residencia'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        rol = cleaned_data.get('rol')
        fecha_ingreso = cleaned_data.get('fecha_ingreso_residencia')
        
        # Validar que residentes tengan fecha de ingreso
        if rol == 'medico_residente' and not fecha_ingreso:
            self.add_error('fecha_ingreso_residencia', 
                          'La fecha de ingreso es obligatoria para residentes')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Marcar perfil como completo (esto también calcula año de residencia)
            user.marcar_perfil_completo()
        return user


class CustomUserChangeForm(UserChangeForm):
    """Formulario para editar perfil de usuario existente."""
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'rol', 'fecha_ingreso_residencia', 'anio_residencia', 'cargo', 'telefono', 'recibir_notificaciones']
        widgets = {
            'rol': forms.Select(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'onchange': 'toggleFechaIngresoEdit()',
            }),
            'fecha_ingreso_residencia': forms.DateInput(attrs={
                'class': 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors',
                'type': 'date',
                'id': 'id_fecha_ingreso_edit',
            }),
            'anio_residencia': forms.TextInput(attrs={
                'readonly': 'readonly',
                'class': 'w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-sm text-gray-600 cursor-not-allowed',
            }),
            'recibir_notificaciones': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = 'w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors'
        
        for field_name, field in self.fields.items():
            if field_name not in ['rol', 'fecha_ingreso_residencia', 'anio_residencia', 'recibir_notificaciones']:
                field.widget.attrs['class'] = base_class
            field.widget.attrs['placeholder'] = field.label
        
        # Remover el campo de password del formulario de edición
        if 'password' in self.fields:
            del self.fields['password']
        
        # Hacer que anio_residencia sea de solo lectura (si está presente)
        if 'anio_residencia' in self.fields:
            self.fields['anio_residencia'].disabled = True
            self.fields['anio_residencia'].help_text = 'Este campo se calcula automáticamente'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Roles que pueden tener fecha de ingreso a residencia
        roles_con_residencia = ['medico_residente', 'jefe_residentes', 'instructor_residentes']
        
        # Actualizar año de residencia si cambió la fecha o el rol
        if user.rol == 'medico_residente' and user.fecha_ingreso_residencia:
            user.anio_residencia = user.calcular_anio_residencia()
        elif user.rol not in roles_con_residencia:
            # Solo limpiar campos de residencia para roles que NO son relacionados con residencia
            user.anio_residencia = None
            user.fecha_ingreso_residencia = None
        
        if commit:
            user.save()
        return user
        return user