from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import EventoServicio
from .forms import EventoServicioForm

class EventoServicioCreateView(LoginRequiredMixin, CreateView):
    model = EventoServicio
    form_class = EventoServicioForm
    template_name = 'gestion_eventos/crear_evento.html'
    success_url = reverse_lazy('home')  # Temporalmente redirige a la página principal

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        return super().form_valid(form)
