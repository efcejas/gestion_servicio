from django import forms
from django.contrib.auth import get_user_model

from .models import ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA
from .services_jornadas import DIAS_SEMANA, INICIO_JORNADAS


class JornadaContractualForm(forms.Form):
    profesional = forms.ModelChoiceField(queryset=get_user_model().objects.none())
    vigencia_desde = forms.DateField(initial=INICIO_JORNADAS, label='Vigente desde',
                                    widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))
    observacion = forms.CharField(label='Referencia o motivo', max_length=1000,
                                 widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profesional'].queryset = get_user_model().objects.filter(
            is_active=True, rol__in=ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA
        ).order_by('last_name', 'first_name', 'username')
        self.fields['profesional'].label_from_instance = lambda user: f'{user.get_full_name() or user.username} ({user.username})'
        for dia in range(7):
            self.fields[f'dia_{dia}'] = forms.ChoiceField(
                choices=[('', 'Elegir'), ('sin', 'Sin jornada'), ('con', 'Con jornada')], label='Jornada')
            for tramo in range(2):
                for limite in ('desde', 'hasta'):
                    self.fields[f'{dia}_{tramo}_{limite}'] = forms.TimeField(
                        required=False, label=limite.capitalize(), input_formats=['%H:%M'],
                        widget=forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'))

    def clean(self):
        data = super().clean()
        semana = {}
        for dia in range(7):
            tramos = []
            for tramo in range(2):
                inicio = data.get(f'{dia}_{tramo}_desde')
                fin = data.get(f'{dia}_{tramo}_hasta')
                if inicio or fin:
                    if not inicio or not fin or inicio >= fin:
                        self.add_error(f'{dia}_{tramo}_hasta', 'Completa un tramo con fin posterior al inicio.')
                    else:
                        tramos.append([inicio.strftime('%H:%M'), fin.strftime('%H:%M')])
            tramos.sort()
            estado = data.get(f'dia_{dia}')
            if estado == 'sin' and tramos:
                self.add_error(f'dia_{dia}', 'Quita los horarios o elige Con jornada.')
            if estado == 'con' and not tramos:
                self.add_error(f'dia_{dia}', 'Completa al menos un tramo.')
            if len(tramos) == 2 and tramos[1][0] < tramos[0][1]:
                self.add_error(f'dia_{dia}', 'Los tramos no deben superponerse.')
            semana[str(dia)] = tramos
        data['semana'] = semana
        return data

    @property
    def dias(self):
        return [{'nombre': nombre, 'estado': self[f'dia_{dia}'], 'tramos': [
            {'desde': self[f'{dia}_{tramo}_desde'], 'hasta': self[f'{dia}_{tramo}_hasta']}
            for tramo in range(2)
        ]} for dia, nombre in enumerate(DIAS_SEMANA)]
