from django import forms
from datetime import datetime
from .models import MedicoGuardia

class FiltroGuardiasPorMedicoForm(forms.Form):
    medico = forms.ModelChoiceField(
        queryset=MedicoGuardia.objects.all().order_by('apellido', 'nombre'),
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
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
    año = forms.ChoiceField(
        choices=[(i, i) for i in range(2000, 2031)],
        required=False,
        label="Año",
        initial=datetime.now().year,
        widget=forms.Select(attrs={'class': 'form-control form-control-sm'}),
    )
