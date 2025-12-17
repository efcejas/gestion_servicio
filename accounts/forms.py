from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

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
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label
        
        # Campos obligatorios
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class CompletarPerfilForm(forms.ModelForm):
    """
    Formulario para completar perfil post-registro.
    Pide rol, cargo específico, teléfono y preferencias.
    """
    class Meta:
        model = CustomUser
        fields = ['rol', 'cargo', 'telefono', 'recibir_notificaciones']
        widgets = {
            'rol': forms.Select(attrs={
                'class': 'form-select',
                'required': True,
            }),
            'cargo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Residente R3 Diagnóstico por Imágenes',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: +54 11 1234-5678',
            }),
            'recibir_notificaciones': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }
        labels = {
            'rol': '¿Cuál es tu rol en el servicio? *',
            'cargo': 'Cargo o especialización (opcional)',
            'telefono': 'Teléfono de contacto',
            'recibir_notificaciones': 'Deseo recibir notificaciones por email',
        }
        help_texts = {
            'rol': 'Selecciona el rol que mejor describe tu función principal',
            'cargo': 'Puedes especificar tu año de residencia, especialidad, etc.',
            'telefono': 'Para contacto en caso de urgencias o guardias',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rol'].required = True
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Marcar perfil como completo
            user.marcar_perfil_completo()
        return user


class CustomUserChangeForm(UserChangeForm):
    """Formulario para editar perfil de usuario existente."""
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'rol', 'cargo', 'telefono', 'recibir_notificaciones']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'rol':
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
            field.widget.attrs['placeholder'] = field.label
        
        # Remover el campo de password del formulario de edición
        if 'password' in self.fields:
            del self.fields['password']