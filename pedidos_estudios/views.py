from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.html import strip_tags
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, FormMixin
from django.views.generic.list import ListView

from .forms import ActualizarEstadoPedidoForm, PedidoEstudioForm, PedidoEstudioNotaForm
from .models import HistorialPedidoEstudio, PedidoEstudio, PedidoEstudioNota

class PedidoEstudioDetailView(LoginRequiredMixin, FormMixin, DetailView):
    model = PedidoEstudio
    template_name = 'pedidos_estudios/detalle_pedido.html'
    context_object_name = 'pedido'
    form_class = PedidoEstudioNotaForm  # Para el formulario de notas

    def get_object(self, queryset=None):
        queryset = self.get_queryset().prefetch_related('notas', 'historial')
        pedido = super().get_object(queryset)
        usuario = self.request.user

        # Registrar visualización
        HistorialPedidoEstudio.objects.get_or_create(
            pedido=pedido,
            usuario=usuario,
            cambio='visualizacion',
            defaults={'valor_anterior': '', 'valor_nuevo': 'Visto'}
        )

        return pedido

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['nota_form'] = PedidoEstudioNotaForm()
        context['estado_form'] = ActualizarEstadoPedidoForm(initial={'estado': self.object.estado})
        context['notas'] = self.object.notas.order_by('fecha')
        context['historial'] = self.object.historial.order_by('-fecha')
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if 'comentario' in request.POST:
            nota_form = PedidoEstudioNotaForm(request.POST)
            if nota_form.is_valid():
                nota = nota_form.save(commit=False)
                nota.pedido = self.object
                nota.creado_por = request.user
                nota.save()
                messages.success(request, "Comentario agregado correctamente.")

        elif 'actualizar_estado' in request.POST:
            estado_form = ActualizarEstadoPedidoForm(request.POST, instance=self.object)
            if estado_form.is_valid():
                estado_form.save(usuario=request.user)
                messages.success(request, f"Estado actualizado a {self.object.get_estado_display()}.")
            else:
                messages.error(request, "No se pudo actualizar el estado. Verifica los datos ingresados.")
                print(estado_form.errors)  # Imprime los errores del formulario en la consola

        return redirect(reverse('pedidos_estudios:detalle_pedido', kwargs={'pk': self.object.pk}))

class PedidoEstudioListView(LoginRequiredMixin, ListView):
    model = PedidoEstudio
    template_name = 'pedidos_estudios/lista_pedidos.html'
    context_object_name = 'pedidos'
    ordering = ['-fecha_creacion']
    paginate_by = 10  # Opcional: para paginación

    def get_queryset(self):
        queryset = PedidoEstudio.objects.all().order_by('-fecha_creacion')

        estado = self.request.GET.get('estado')
        prioridad = self.request.GET.get('prioridad')
        modalidad = self.request.GET.get('modalidad')

        if estado:
            queryset = queryset.filter(estado=estado)
        if prioridad:
            queryset = queryset.filter(prioridad=prioridad)
        if modalidad:
            queryset = queryset.filter(modalidad=modalidad)

        return queryset

class PedidoEstudioCreateView(CreateView):
    model = PedidoEstudio
    form_class = PedidoEstudioForm
    template_name = 'pedidos_estudios/crear_pedido.html'
    success_url = reverse_lazy('pedidos_estudios:lista_pedidos')

    def form_valid(self, form):
        response = super().form_valid(form)

        # Enviar correo
        pedido = self.object
        subject = f"Nuevo pedido de estudio ingresado – {pedido.nombre_paciente}"

        # Cuerpo del correo desde un template de texto
        cuerpo_html = render_to_string('pedidos_estudios/email_nuevo_pedido.html', {'pedido': pedido})
        cuerpo_texto = strip_tags(cuerpo_html)  # Por si querés soporte en texto plano

        send_mail(
            subject,
            cuerpo_texto,
            None,  # Reemplazá con tu mail remitente si hace falta
            ['analia.fernandez@dupuytren.com.ar'],     # Cambiá esto por el mail real del área administrativa
            fail_silently=False,
        )

        messages.success(self.request, "El pedido fue registrado correctamente.")
        return response

