from django import forms
from .models import TerminoMedico, CategoriaTerminoMedico


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
