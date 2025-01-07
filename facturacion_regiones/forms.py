from django import forms
from .models import RegistroEstudio, Estudio
from django.db import models

class RegistroEstudioForm(forms.ModelForm):
    class Meta:
        model = RegistroEstudio
        fields = ['paciente_nombre', 'paciente_dni', 'fecha_estudio', 'estudios']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['paciente_nombre'].widget.attrs.update({'class': 'form-control'})
        self.fields['paciente_dni'].widget.attrs.update({'class': 'form-control'})
        self.fields['fecha_estudio'].widget.attrs.update({'class': 'form-control', 'type': 'date'})

        # Configurar las opciones del campo "estudios"
        estudios = Estudio.objects.all()
        self.fields['estudios'].queryset = estudios
        self.fields['estudios'].widget.attrs.update({'class': 'form-control', 'multiple': 'multiple'})

        # Añadir `data-regiones` a cada opción
        self.fields['estudios'].widget.choices = [
            (estudio.id, f"{estudio.nombre} ({estudio.get_modalidad_display()})")
            for estudio in estudios
        ]
        for option in self.fields['estudios'].widget.choices:
            estudio = estudios.get(id=option[0])
            regiones_count = estudio.regiones.aggregate(total=models.Sum('peso'))['total'] or 0
            self.fields['estudios'].widget.attrs[f'data-regiones-{option[0]}'] = regiones_count

