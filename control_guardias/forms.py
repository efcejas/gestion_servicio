from django import forms
from datetime import datetime
from .models import MedicoGuardia, Guardia

class FiltroGuardiasPorMedicoForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=MedicoGuardia.objects.select_related('user').order_by('user__last_name', 'user__first_name'), 
        required=False,
        label="Médico",
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
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
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medico'].label_from_instance = lambda obj: obj.user.get_full_name() if obj.user else "Sin usuario"

class GuardiaForm(forms.ModelForm):
    class Meta:
        model = Guardia
        fields = ['franja_horaria', 'medico', 'fecha']
        widgets = {
            'franja_horaria': forms.Select(attrs={'class': 'form-select'}),
            'medico': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
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
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )