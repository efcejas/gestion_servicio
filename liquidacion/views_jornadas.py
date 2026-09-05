from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView

from .forms_jornadas import JornadaContractualForm
from .models import JornadaContractual, ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA
from .services_jornadas import (
    crear_jornada_contractual, dias_jornada, puede_gestionar_jornadas, puede_ver_todas_jornadas,
)


class JornadasContractualesView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'liquidacion/jornadas_contractuales.html'

    def test_func(self):
        return (puede_ver_todas_jornadas(self.request.user)
                or self.request.user.rol in ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profesionales = get_user_model().objects.filter(rol__in=ROLES_LIQUIDAR_COMO_EXTRA_RESIDENCIA)
        if not puede_ver_todas_jornadas(self.request.user):
            profesionales = profesionales.filter(pk=self.request.user.pk)
        profesionales = list(profesionales.order_by('last_name', 'first_name', 'username'))
        jornadas = JornadaContractual.objects.filter(profesional__in=profesionales).select_related(
            'profesional', 'creado_por', 'cerrado_por')
        por_profesional = {user.pk: [] for user in profesionales}
        for jornada in jornadas:
            por_profesional[jornada.profesional_id].append({'jornada': jornada, 'dias': dias_jornada(jornada)})
        context.update({
            'profesionales_data': [{'profesional': user, 'versiones': por_profesional[user.pk]}
                                   for user in profesionales],
            'puede_gestionar': puede_gestionar_jornadas(self.request.user),
            'es_administrativo': puede_ver_todas_jornadas(self.request.user),
        })
        return context


class JornadaContractualCreateView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'liquidacion/jornada_contractual_form.html'
    form_class = JornadaContractualForm
    success_url = reverse_lazy('liquidacion:jornadas_contractuales')

    def test_func(self):
        return puede_gestionar_jornadas(self.request.user)

    def get_initial(self):
        initial = super().get_initial()
        profesional_id = self.request.GET.get('profesional', '')
        if profesional_id.isdecimal():
            initial['profesional'] = profesional_id
            ultima = JornadaContractual.objects.filter(profesional_id=profesional_id).order_by('-vigencia_desde').first()
            if ultima:
                initial['vigencia_desde'] = None
                for dia, tramos in ultima.semana.items():
                    initial[f'dia_{dia}'] = 'con' if tramos else 'sin'
                    for indice, (inicio, fin) in enumerate(tramos):
                        initial[f'{dia}_{indice}_desde'] = inicio
                        initial[f'{dia}_{indice}_hasta'] = fin
        return initial

    def form_valid(self, form):
        try:
            crear_jornada_contractual(
                profesional=form.cleaned_data['profesional'],
                vigencia_desde=form.cleaned_data['vigencia_desde'],
                semana=form.cleaned_data['semana'], observacion=form.cleaned_data['observacion'],
                user=self.request.user,
            )
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, 'Jornada contractual guardada. Los cruces y validaciones existentes se conservan.')
        return redirect(self.success_url)
