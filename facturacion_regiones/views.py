from django.shortcuts import render
from django.views.generic import CreateView
from django.urls import reverse_lazy
from .models import RegistroEstudio, Estudio
from .forms import RegistroEstudioForm

class RegistroEstudioCreateView(CreateView):
    model = RegistroEstudio
    form_class = RegistroEstudioForm
    template_name = "facturacion/registro_form.html"
    success_url = reverse_lazy('lista_registros')

    def form_valid(self, form):
        form.instance.medico = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['debug_estudios'] = Estudio.objects.all()  # Agregamos la consulta para depuración
        return context
