from django import forms
from datetime import datetime
from .models import MedicoGuardia, Guardia

class FiltroGuardiasPorMedicoForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=MedicoGuardia.objects.select_related('user').order_by('user__last_name', 'user__first_name'), 
        required=False,
        label="Médico",
        widget=forms.Select(attrs={
            'class': 'rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
        }),
        empty_label="Todos los médicos"
    )
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        required=False,
        label="Mes",
        initial=datetime.now().month,
        widget=forms.Select(attrs={
            'class': 'rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
        }),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={
            'class': 'rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
        }),
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: obj.user.get_full_name() if obj.user else "Sin usuario"

class GuardiaForm(forms.ModelForm):
    class Meta:
        model = Guardia
        fields = ['franja_horaria', 'medico', 'fecha']
        widgets = {
            'franja_horaria': forms.Select(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'medico': forms.Select(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
            }),
            'fecha': forms.DateInput(attrs={
                'class': 'block w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: obj.user.get_full_name() if obj.user else "Sin usuario"
        
class FiltroMisGuardiasForm(forms.Form):
    mes = forms.ChoiceField(
        choices=[
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ],
        required=False,
        label="Mes",
        initial=datetime.now().month,
        widget=forms.Select(attrs={
            'class': 'rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
        }),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={
            'class': 'rounded-lg border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-gray-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500'
        }),
    )