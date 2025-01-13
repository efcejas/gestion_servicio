from django.shortcuts import render, redirect
from django.views.generic import View
from .forms import RegistroDiarioForm, DetalleRegistroFormSet

class RegistroDiarioCreateView(View):
    template_name = 'liquidacion/registro_diario_form.html'

    def get(self, request):
        form = RegistroDiarioForm()
        formset = DetalleRegistroFormSet()
        return render(request, self.template_name, {'form': form, 'formset': formset})

    def post(self, request):
        form = RegistroDiarioForm(request.POST)
        formset = DetalleRegistroFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            registro_diario = form.save()  # Guardar el Registro Diario
            detalles = formset.save(commit=False)
            for detalle in detalles:
                detalle.registro = registro_diario  # Asignar el registro principal
                detalle.save()

            registro_diario.calcular_total_regiones()  # Actualizar el total de regiones
            return redirect('nombre_de_la_url_listado')  # Redirigir tras guardar

        return render(request, self.template_name, {'form': form, 'formset': formset})
