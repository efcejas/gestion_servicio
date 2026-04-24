from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import (
    ConfiguracionTipoGuardiaForm,
    CuotaMensualGuardiaForm,
        AjustePenalizacionForm,
    FeriadoForm,
    GenerarDistribucionForm,
    AusenciaResidenteForm,
    RotacionExternaForm,
    SolicitudCambioGuardiaForm,
    SolicitudSlotVacanteForm,
    NotasRechazoForm,
)
from .models import (
    AsignacionGuardia,
    AjusteCuotaGuardia,
    AusenciaResidente,
    ConfiguracionTipoGuardia,
    CuotaMensualGuardia,
    Feriado,
    NotificacionGuardia,
    RotacionExterna,
    SolicitudCambioGuardia,
    SolicitudSlotVacante,
)
# Paleta de colores por residente (estable: residente.pk % len(_RESIDENTE_PALETTE))
_RESIDENTE_PALETTE = [
    '#3b82f6',  # blue-500
    '#10b981',  # emerald-500
    '#8b5cf6',  # violet-500
    '#ef4444',  # red-500
    '#ec4899',  # pink-500
    '#14b8a6',  # teal-500
    '#f97316',  # orange-500
    '#6366f1',  # indigo-500
    '#06b6d4',  # cyan-500
    '#84cc16',  # lime-500
]

from .services import (
    CambioGuardiaError,
    DistribucionError,
    aceptar_cambio_receptor,
    aprobar_cambio,
    aprobar_slot_vacante,
    cancelar_ausencia,
    cancelar_borrador,
    cancelar_cambio,
    cancelar_slot_vacante,
    eliminar_guardia_excepcion,
    generar_distribucion,
    obtener_metricas_mes,
    publicar_borrador,
    rechazar_cambio_jefe,
    rechazar_cambio_receptor,
    rechazar_slot_vacante,
    reportar_ausencia,
    resolver_ausencia,
    solicitar_cambio,
    sugerir_reemplazo,
)


class JefeInstructorMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Acceso exclusivo para jefe_residentes, instructor_residentes y superusuarios."""
    login_url = 'login'

    def test_func(self):
        user = self.request.user
        return user.rol in ['jefe_residentes', 'instructor_residentes'] or user.is_superuser


def _safe_return_url(request, fallback, focus=''):
    return_to = (
        request.POST.get('return_to')
        or request.GET.get('return_to')
        or ''
    )

    if return_to and url_has_allowed_host_and_scheme(
        return_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = return_to
    else:
        target = fallback

    focus_value = (
        request.POST.get('focus')
        or request.GET.get('focus')
        or str(focus or '')
    )
    if not focus_value:
        return target

    separator = '&' if '?' in target else '?'
    return f'{target}{separator}focus={focus_value}'


class GuardiasIndexView(LoginRequiredMixin, TemplateView):
    """
    Vista de índice principal del módulo de guardias.
    Muestra contenido diferente según el rol del usuario.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/index.html']
        return ['control_guardias/portal/index.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        hoy = timezone.now().date()

        # Notificaciones no leídas (todos los roles)
        context['notificaciones_no_leidas'] = (
            NotificacionGuardia.objects
            .filter(destinatario=user, leida=False)
            .count()
        )

        if user.es_residente():
            proximas = (
                AsignacionGuardia.objects
                .filter(residente=user, fecha__gte=hoy, estado='PUBLICADA')
                .select_related('tipo_guardia')
                .order_by('fecha')[:5]
            )
            context['proximas_guardias'] = proximas
            context['ausencias_pendientes_residente'] = (
                AusenciaResidente.objects
                .filter(residente=user, estado='PENDIENTE')
                .count()
            )
            context['cambios_pendientes_residente'] = (
                SolicitudCambioGuardia.objects
                .filter(receptor=user, estado='PENDIENTE_RECEPTOR')
                .count()
            )
        elif user.rol in ('jefe_residentes', 'instructor_residentes') or user.is_superuser:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            context['total_residentes'] = User.objects.filter(rol='medico_residente', is_active=True).count()
            context['ausencias_pendientes'] = AusenciaResidente.objects.filter(estado='PENDIENTE').count()
            context['cambios_pendiente_jefe'] = SolicitudCambioGuardia.objects.filter(estado='PENDIENTE_JEFE').count()
            context['guardias_borrador'] = AsignacionGuardia.objects.filter(estado='BORRADOR').count()
            context['guardias_publicadas_mes'] = (
                AsignacionGuardia.objects
                .filter(estado='PUBLICADA', fecha__month=hoy.month, fecha__year=hoy.year)
                .count()
            )
            context['proximas_sin_asignar'] = (
                AsignacionGuardia.objects
                .filter(fecha__gte=hoy, estado='PUBLICADA')
                .select_related('tipo_guardia', 'residente')
                .order_by('fecha')[:8]
            )
        return context


class MisGuardiasView(LoginRequiredMixin, ListView):
    """Vista personal del residente: sus guardias asignadas."""
    model = AsignacionGuardia
    context_object_name = 'guardias'
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/mis_guardias.html']
        return ['control_guardias/portal/mis_guardias.html']

    def get_queryset(self):
        return (
            AsignacionGuardia.objects
            .filter(residente=self.request.user)
            .select_related('tipo_guardia')
            .order_by('fecha')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.now().date()
        qs = self.get_queryset()
        context['proximas_guardias'] = qs.filter(fecha__gte=hoy, estado='PUBLICADA')
        context['guardias_pasadas'] = qs.filter(fecha__lt=hoy).order_by('-fecha')
        return context


class NotificacionesGuardiaView(LoginRequiredMixin, ListView):
    """Inbox interno de notificaciones de guardias."""
    model = NotificacionGuardia
    context_object_name = 'notificaciones'
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/notificaciones.html']
        return ['control_guardias/portal/notificaciones.html']

    def get_queryset(self):
        return (
            NotificacionGuardia.objects
            .filter(destinatario=self.request.user)
            .order_by('-fecha')
        )

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Marcar todas como leídas al abrir el inbox
        NotificacionGuardia.objects.filter(
            destinatario=request.user, leida=False
        ).update(leida=True)
        return response


class GuardiasApiView(LoginRequiredMixin, TemplateView):
    """
    Endpoint JSON para FullCalendar.
    - Residentes: solo sus propias guardias PUBLICADAS.
    - Jefes/instructores/superusuarios: todas las guardias (PUBLICADA + BORRADOR),
      con filtro opcional por ?residente_id=<pk>.
    """
    login_url = 'login'

    _COLOR_BORRADOR = '#6b7280'        # gris (borradores no publicados)
    _COLOR_PENDIENTE_CAMBIO = '#f59e0b'  # ámbar

    def _build_pendencias_por_guardia(self, user, guardia_ids):
        if not guardia_ids:
            return {}

        solicitudes = (
            SolicitudCambioGuardia.objects
            .filter(
                estado__in=['PENDIENTE_RECEPTOR', 'PENDIENTE_JEFE']
            )
            .filter(
                models.Q(guardia_solicitante_id__in=guardia_ids)
                | models.Q(guardia_receptor_id__in=guardia_ids)
            )
            .select_related('solicitante', 'receptor')
            .order_by('-fecha_solicitud')
        )

        pendencias = {}
        for solicitud in solicitudes:
            guardias_relacionadas = [solicitud.guardia_solicitante_id, solicitud.guardia_receptor_id]
            for guardia_id in guardias_relacionadas:
                if guardia_id not in guardia_ids or guardia_id in pendencias:
                    continue

                if solicitud.estado == 'PENDIENTE_RECEPTOR':
                    if solicitud.receptor_id == user.pk:
                        label = 'Pendiente de tu respuesta'
                    else:
                        label = 'Cambio pendiente de respuesta'
                else:
                    label = 'Cambio pendiente de aprobación'

                pendencias[guardia_id] = {
                    'estado': solicitud.estado,
                    'label': label,
                    'solicitud_id': solicitud.pk,
                }

        return pendencias

    def get(self, request, *args, **kwargs):
        user = request.user
        es_gestor = (
            user.rol in ['jefe_residentes', 'instructor_residentes']
            or user.is_superuser
        )
        ver_todas = request.GET.get('ver_todas') == '1'

        start_param = request.GET.get('start', '')
        end_param = request.GET.get('end', '')
        residente_id = request.GET.get('residente_id', '')

        if es_gestor:
            qs = (
                AsignacionGuardia.objects
                .filter(estado__in=['PUBLICADA', 'BORRADOR'])
                .select_related('residente', 'tipo_guardia')
            )
            if residente_id:
                qs = qs.filter(residente_id=residente_id)
        else:
            qs = AsignacionGuardia.objects.filter(estado='PUBLICADA').select_related('residente', 'tipo_guardia')
            if not ver_todas:
                qs = qs.filter(residente=user)

        if start_param and end_param:
            try:
                start_date = start_param.split('T')[0]
                end_date = end_param.split('T')[0]
                qs = qs.filter(fecha__gte=start_date, fecha__lt=end_date)
            except (ValueError, IndexError):
                pass

        qs = list(qs)
        pendencias_por_guardia = self._build_pendencias_por_guardia(
            request.user,
            {asignacion.pk for asignacion in qs},
        )

        eventos = []
        for asignacion in qs:
            nombre = asignacion.residente.get_full_name()
            pendiente = pendencias_por_guardia.get(asignacion.pk)
            if asignacion.estado == 'BORRADOR':
                color = self._COLOR_BORRADOR
            elif pendiente:
                color = self._COLOR_PENDIENTE_CAMBIO
            else:
                color = _RESIDENTE_PALETTE[asignacion.residente_id % len(_RESIDENTE_PALETTE)]

            eventos.append({
                'id': str(asignacion.pk),
                'title': f'{nombre} – {asignacion.tipo_guardia.nombre}',
                'start': asignacion.fecha.isoformat(),
                'allDay': True,
                'backgroundColor': color,
                'borderColor': color,
                'textColor': '#fff',
                'extendedProps': {
                    'guardia_id': asignacion.pk,
                    'residente_id': asignacion.residente_id,
                    'residente': nombre,
                    'tipo_guardia': asignacion.tipo_guardia.nombre,
                    'hora_inicio': asignacion.tipo_guardia.hora_inicio.strftime('%H:%M'),
                    'hora_fin': asignacion.tipo_guardia.hora_fin.strftime('%H:%M'),
                    'es_feriado': asignacion.es_feriado,
                    'estado': asignacion.estado,
                    'es_mia': asignacion.residente_id == user.pk,
                    'cambio_pendiente': bool(pendiente),
                    'cambio_pendiente_estado': pendiente['estado'] if pendiente else '',
                    'cambio_pendiente_label': pendiente['label'] if pendiente else '',
                    'cambio_pendiente_solicitud_id': pendiente['solicitud_id'] if pendiente else '',
                }
            })

        return JsonResponse(eventos, safe=False)


# ---------------------------------------------------------------------------
# Fase 4: Calendario interactivo FullCalendar
# ---------------------------------------------------------------------------

class CalendarioView(LoginRequiredMixin, TemplateView):
    """
    Vista del calendario mensual con FullCalendar.
    - Residentes: solo ven sus propias guardias.
    - Jefes/instructores/superusuarios: ven todas las guardias con selector de residente.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/calendario.html']
        return ['control_guardias/portal/calendario.html']

    def get_context_data(self, **kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        context = super().get_context_data(**kwargs)
        user = self.request.user
        es_gestor = (
            user.rol in ['jefe_residentes', 'instructor_residentes']
            or user.is_superuser
        )
        context['es_gestor'] = es_gestor
        context['tipos_guardia'] = ConfiguracionTipoGuardia.objects.filter(activo=True)
        # Retorno contextual: si se llega desde borrador, volver allí; en otro caso, ir al inicio.
        return_to_q = self.request.GET.get('return_to', '')
        if return_to_q and url_has_allowed_host_and_scheme(
            return_to_q,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            context['calendario_return_url'] = return_to_q
            context['calendario_back_label'] = 'Volver al borrador'
        else:
            context['calendario_return_url'] = reverse('control_guardias:index')
            context['calendario_back_label'] = 'Ir al inicio'
        # Permite abrir el calendario directamente en un mes/año objetivo (ej. desde borrador)
        context['calendario_initial_date'] = ''
        mes_q = self.request.GET.get('mes')
        anio_q = self.request.GET.get('anio')
        if mes_q and anio_q:
            try:
                mes = int(mes_q)
                anio = int(anio_q)
                if 1 <= mes <= 12 and 2000 <= anio <= 2100:
                    context['calendario_initial_date'] = f'{anio:04d}-{mes:02d}-01'
            except (TypeError, ValueError):
                pass
        # Feriados del rango visible (±6 meses) para colorear casilleros en el JS
        import json as _json
        from datetime import date as _date, timedelta as _td
        hoy = _date.today()
        feriados = list(
            Feriado.objects
            .filter(fecha__gte=hoy - _td(days=180), fecha__lte=hoy + _td(days=365))
            .values_list('fecha', flat=True)
        )
        context['feriados_json'] = _json.dumps([f.isoformat() for f in feriados])
        if es_gestor:
            residentes_qs = (
                User.objects
                .filter(rol='medico_residente', is_active=True)
                .order_by('last_name', 'first_name')
            )
            context['residentes'] = residentes_qs
            context['residentes_con_color'] = [
                {'residente': r, 'color': _RESIDENTE_PALETTE[r.pk % len(_RESIDENTE_PALETTE)]}
                for r in residentes_qs
            ]
        else:
            context['mi_color'] = _RESIDENTE_PALETTE[user.pk % len(_RESIDENTE_PALETTE)]
            context['mis_guardias_para_cambio'] = (
                AsignacionGuardia.objects
                .filter(
                    residente=user,
                    estado='PUBLICADA',
                    fecha__gte=timezone.now().date(),
                )
                .select_related('tipo_guardia')
                .order_by('fecha', 'tipo_guardia__nombre')
            )
        return context


# ---------------------------------------------------------------------------
# Fase 2: Módulo de Configuración (jefes/instructores)
# ---------------------------------------------------------------------------

class ConfiguracionView(JefeInstructorMixin, TemplateView):
    """Página principal de configuración del módulo de guardias."""

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/configuracion.html']
        return ['control_guardias/portal/configuracion.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_guardia'] = ConfiguracionTipoGuardia.objects.select_related('creado_por')
        cuotas_map = {c.anio_residencia: c for c in CuotaMensualGuardia.objects.all()}
        context['cuotas_filas'] = [
            {'anio': anio, 'cuota': cuotas_map.get(anio)}
            for anio in ['R1', 'R2', 'R3', 'R4']
        ]
        context['feriados'] = Feriado.objects.order_by('fecha')
        context['feriado_form'] = FeriadoForm()
        context['rotaciones_activas'] = (
            RotacionExterna.objects.filter(activo=True)
            .select_related('residente')
            .order_by('fecha_inicio')
        )
        return context


class TipoGuardiaCreateView(JefeInstructorMixin, CreateView):
    model = ConfiguracionTipoGuardia
    form_class = ConfiguracionTipoGuardiaForm
    success_url = reverse_lazy('control_guardias:configuracion')

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/tipo_guardia_form.html']
        return ['control_guardias/portal/tipo_guardia_form.html']

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, 'Tipo de guardia creado correctamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nuevo tipo de guardia'
        return context


class TipoGuardiaUpdateView(JefeInstructorMixin, UpdateView):
    model = ConfiguracionTipoGuardia
    form_class = ConfiguracionTipoGuardiaForm
    success_url = reverse_lazy('control_guardias:configuracion')

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/tipo_guardia_form.html']
        return ['control_guardias/portal/tipo_guardia_form.html']

    def form_valid(self, form):
        messages.success(self.request, 'Tipo de guardia actualizado correctamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar: {self.object.nombre}'
        return context


class TipoGuardiaDeleteView(JefeInstructorMixin, DeleteView):
    model = ConfiguracionTipoGuardia
    success_url = reverse_lazy('control_guardias:configuracion')

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/tipo_guardia_confirm_delete.html']
        return ['control_guardias/portal/tipo_guardia_confirm_delete.html']

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            messages.success(self.request, 'Tipo de guardia eliminado.')
            return response
        except Exception:
            messages.error(self.request, 'No se puede eliminar: tiene asignaciones asociadas.')
            return self.handle_no_permission()


class CuotaMensualFormView(JefeInstructorMixin, TemplateView):
    """Crea o edita la cuota mensual de un año de residencia (R1-R4)."""

    ANIOS_VALIDOS = ['R1', 'R2', 'R3', 'R4']

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/cuota_mensual_form.html']
        return ['control_guardias/portal/cuota_mensual_form.html']

    def _get_or_create_cuota(self, anio):
        if anio not in self.ANIOS_VALIDOS:
            from django.http import Http404
            raise Http404(f"Año de residencia inválido: {anio}")
        obj, created = CuotaMensualGuardia.objects.get_or_create(
            anio_residencia=anio,
            defaults={'guardias_por_mes': 4, 'atenuante_porcentaje': 0},
        )
        return obj, created

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        anio = self.kwargs['anio']
        obj, created = self._get_or_create_cuota(anio)
        context['object'] = obj
        context['is_new'] = created
        context['form'] = kwargs.get('form', CuotaMensualGuardiaForm(instance=obj))
        return context

    def post(self, request, anio, *args, **kwargs):
        obj, _ = self._get_or_create_cuota(anio)
        form = CuotaMensualGuardiaForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cuota de {obj.get_anio_residencia_display()} guardada correctamente.')
            from django.urls import reverse
            return redirect(reverse('control_guardias:configuracion') + '?tab=cuotas')
        return self.render_to_response(self.get_context_data(form=form))


class PenalizacionCuotaCreateView(JefeInstructorMixin, CreateView):
    """Registrar penalización manual que agrega guardias a la cuota mensual del residente."""
    model = AjusteCuotaGuardia
    form_class = AjustePenalizacionForm
    template_name = 'control_guardias/portal/penalizacion_form.html'

    def form_valid(self, form):
        form.instance.tipo = 'PENALIZACION'
        form.instance.creado_por = self.request.user
        messages.success(self.request, 'Penalización registrada correctamente.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('control_guardias:configuracion') + '?tab=cuotas'


class FeriadoCreateView(JefeInstructorMixin, CreateView):
    model = Feriado
    form_class = FeriadoForm

    def get_success_url(self):
        from django.urls import reverse
        return reverse('control_guardias:configuracion') + '?tab=feriados'

    def form_valid(self, form):
        messages.success(self.request, 'Feriado agregado correctamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Error al agregar feriado. Verificá los datos.')
        return self.render_to_response(self.get_context_data(feriado_form=form))

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/configuracion.html']
        return ['control_guardias/portal/configuracion.html']

    def get_context_data(self, **kwargs):
        cuotas_map = {c.anio_residencia: c for c in CuotaMensualGuardia.objects.all()}
        return {
            'tipos_guardia': ConfiguracionTipoGuardia.objects.select_related('creado_por'),
            'cuotas_filas': [
                {'anio': anio, 'cuota': cuotas_map.get(anio)}
                for anio in ['R1', 'R2', 'R3', 'R4']
            ],
            'feriados': Feriado.objects.order_by('fecha'),
            'feriado_form': kwargs.get('feriado_form', FeriadoForm()),
                    'rotaciones_activas': RotacionExterna.objects.filter(activo=True).select_related('residente').order_by('fecha_inicio'),
        }


class FeriadoDeleteView(JefeInstructorMixin, DeleteView):
    model = Feriado

    def get_success_url(self):
        from django.urls import reverse
        return reverse('control_guardias:configuracion') + '?tab=feriados'

    def get(self, request, *args, **kwargs):
        """No mostramos página de confirmación — elimina directamente vía POST desde el template."""
        return self.post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Feriado eliminado.')
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Fase 3: Distribución automática
# ---------------------------------------------------------------------------

class DistribucionView(JefeInstructorMixin, TemplateView):
    """
    GET:  Muestra el formulario para generar una distribución de guardias.
    POST: Ejecuta el algoritmo y redirige al borrador generado.
    """

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/distribucion_form.html']
        return ['control_guardias/portal/distribucion_form.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = GenerarDistribucionForm()
        # Mostrar borradores activos para que el jefe sepa qué meses tienen borrador
        from django.db.models import Min, Max
        borradores = (
            AsignacionGuardia.objects
            .filter(estado='BORRADOR')
            .values('fecha__year', 'fecha__month')
            .annotate(total=models.Count('id'), min_fecha=Min('fecha'), max_fecha=Max('fecha'))
            .order_by('fecha__year', 'fecha__month')
        )
        context['borradores_activos'] = borradores
        return context

    def post(self, request, *args, **kwargs):
        form = GenerarDistribucionForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        mes = int(form.cleaned_data['mes'])
        anio = form.cleaned_data['anio']
        tipos_guardia = form.cleaned_data['tipos_guardia']
        reemplazar = form.cleaned_data.get('reemplazar_borradores', False)
        restricciones = form.cleaned_data.get('restricciones_anio', False)

        try:
            resultado = generar_distribucion(
                mes=mes,
                anio=anio,
                tipos_guardia=tipos_guardia,
                creado_por=request.user,
                reemplazar_borradores=reemplazar,
                restricciones_anio=restricciones,
            )
        except DistribucionError as e:
            messages.error(request, str(e))
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)

        n = resultado['asignaciones_creadas']
        messages.success(request, f"Distribución generada: {n} asignación(es) en borrador.")
        for adv in resultado.get('advertencias', []):
            messages.warning(request, adv)

        return redirect('control_guardias:distribucion_borrador', mes=mes, anio=anio)

    def get_context_data(self, **kwargs):
        context = super(TemplateView, self).get_context_data(**kwargs)
        if 'form' not in kwargs:
            context['form'] = GenerarDistribucionForm()
        else:
            context['form'] = kwargs['form']
        # Borradores activos
        borradores = (
            AsignacionGuardia.objects
            .filter(estado='BORRADOR')
            .values('fecha__year', 'fecha__month')
            .annotate(
                total=models.Count('id'),
                min_fecha=models.Min('fecha'),
            )
            .order_by('fecha__year', 'fecha__month')
        )
        context['borradores_activos'] = list(borradores)
        return context


class BorradorView(JefeInstructorMixin, TemplateView):
    """
    Vista del borrador de distribución para un mes/año específico.
    Permite publicar o cancelar.
    """

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/distribucion_borrador.html']
        return ['control_guardias/portal/distribucion_borrador.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mes = self.kwargs['mes']
        anio = self.kwargs['anio']
        from datetime import date
        import calendar as cal_module
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, cal_module.monthrange(anio, mes)[1])

        asignaciones = (
            AsignacionGuardia.objects
            .filter(fecha__gte=primer_dia, fecha__lte=ultimo_dia, estado='BORRADOR')
            .select_related('residente', 'tipo_guardia')
            .order_by('fecha', 'tipo_guardia__nombre')
        )
        context['asignaciones'] = asignaciones
        context['mes'] = mes
        context['anio'] = anio
        context['nombre_mes'] = _nombre_mes_view(mes)
        context['metricas'] = obtener_metricas_mes(mes, anio)
        context['hay_borradores'] = asignaciones.exists()
        return context


class PublicarBorradorView(JefeInstructorMixin, TemplateView):
    """POST: Publica todas las asignaciones BORRADOR del mes/año."""
    template_name = None  # solo POST

    def post(self, request, mes, anio):
        count = publicar_borrador(mes, anio)
        if count:
            messages.success(request, f"{count} guardia(s) publicada(s) correctamente.")
        else:
            messages.warning(request, "No había asignaciones en borrador para publicar.")
        return redirect(f"{reverse('control_guardias:calendario')}?mes={mes}&anio={anio}")

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:distribucion_borrador',
                        mes=kwargs['mes'], anio=kwargs['anio'])


class CancelarBorradorView(JefeInstructorMixin, TemplateView):
    """POST: Elimina todas las asignaciones BORRADOR del mes/año."""
    template_name = None

    def post(self, request, mes, anio):
        count = cancelar_borrador(mes, anio)
        if count:
            messages.success(request, f"Borrador cancelado: {count} asignación(es) eliminada(s).")
        else:
            messages.warning(request, "No había asignaciones en borrador para cancelar.")
        return redirect('control_guardias:distribucion')

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:distribucion_borrador',
                        mes=kwargs['mes'], anio=kwargs['anio'])


def _nombre_mes_view(mes):
    MESES = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
    ]
    return MESES[mes]


# ---------------------------------------------------------------------------
# Fase 5: Ausencias
# ---------------------------------------------------------------------------

class AusenciasView(LoginRequiredMixin, TemplateView):
    """
    Lista de ausencias.
    - Residentes: solo las propias.
    - Gestores: todas, ordenadas por más recientes primero.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/ausencias.html']
        return ['control_guardias/portal/ausencias.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        es_gestor = user.rol in ['jefe_residentes', 'instructor_residentes'] or user.is_superuser
        context['es_gestor'] = es_gestor
        if es_gestor:
            qs = (
                AusenciaResidente.objects
                .select_related('residente', 'resuelta_por')
                .prefetch_related('guardias_afectadas', 'documentos')
                .order_by('estado', '-reportada_en')
            )
        else:
            qs = (
                AusenciaResidente.objects
                .filter(residente=user)
                .select_related('resuelta_por')
                .prefetch_related('guardias_afectadas', 'documentos')
                .order_by('-reportada_en')
            )
        context['ausencias'] = qs
        return context


class ReportarAusenciaView(LoginRequiredMixin, TemplateView):
    """
    GET: muestra el formulario para reportar une ausencia.
    POST: crea la ausencia y vincula guardias afectadas.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/reportar_ausencia_form.html']
        return ['control_guardias/portal/reportar_ausencia_form.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = kwargs.get('form', AusenciaResidenteForm())
        return context

    def post(self, request, *args, **kwargs):
        form = AusenciaResidenteForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        try:
            ausencia = reportar_ausencia(
                residente=request.user,
                fecha_inicio=form.cleaned_data['fecha_inicio'],
                fecha_fin=form.cleaned_data['fecha_fin'],
                motivo=form.cleaned_data['motivo'],
                descripcion=form.cleaned_data.get('descripcion', ''),
                certificados_adicionales=form.cleaned_data.get('certificados_adicionales', []),
            )
            n = ausencia.guardias_afectadas.count()
            messages.success(
                request,
                f"Ausencia reportada. Se detectaron {n} guardia(s) afectada(s). "
                "El jefe/instructor fue notificado."
            )
            return redirect('control_guardias:ausencias')
        except Exception as e:
            messages.error(request, str(e))
            return self.render_to_response(self.get_context_data(form=form))


class ResolverAusenciaView(JefeInstructorMixin, TemplateView):
    """
    GET:  muestra las guardias afectadas con sugerencias de reemplazo.
    POST: confirma reasignaciones y cierra la ausencia.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/resolver_ausencia_form.html']
        return ['control_guardias/portal/resolver_ausencia_form.html']

    def _get_ausencia(self, pk):
        return get_object_or_404(AusenciaResidente, pk=pk)

    def _return_url(self, ausencia_pk=None):
        fallback = reverse('control_guardias:ausencias')
        return _safe_return_url(self.request, fallback, focus=ausencia_pk)

    def get(self, request, pk, *args, **kwargs):
        ausencia = self._get_ausencia(pk)
        if ausencia.estado == 'RESUELTA':
            messages.warning(request, 'Esta ausencia ya fue resuelta.')
            return redirect(self._return_url(ausencia.pk))
        return self.render_to_response(self._build_context(ausencia))

    def post(self, request, pk, *args, **kwargs):
        ausencia = self._get_ausencia(pk)
        if ausencia.estado == 'RESUELTA':
            messages.warning(request, 'Esta ausencia ya fue resuelta.')
            return redirect(self._return_url(ausencia.pk))

        # Leer reasignaciones del formulario: reemplazante_<guardia_pk>
        reasignaciones = {}
        for guardia in ausencia.guardias_afectadas.all():
            val = request.POST.get(f'reemplazante_{guardia.pk}', '').strip()
            if val:
                try:
                    reasignaciones[guardia.pk] = int(val)
                except ValueError:
                    pass

        resolver_ausencia(ausencia, request.user, reasignaciones=reasignaciones)

        n_total = ausencia.guardias_afectadas.count()
        n_reasig = len(reasignaciones)
        n_ausente = n_total - n_reasig
        partes = []
        if n_reasig:
            partes.append(f'{n_reasig} guardia(s) reasignada(s)')
        if n_ausente:
            partes.append(f'{n_ausente} marcada(s) como ausente')
        resumen = ' · '.join(partes) if partes else 'sin guardias afectadas'
        messages.success(
            request,
            f'Ausencia de {ausencia.residente.get_full_name()} resuelta — {resumen}.'
        )
        return redirect(self._return_url(ausencia.pk))

    def _build_context(self, ausencia):
        guardias_data = []
        for guardia in ausencia.guardias_afectadas.select_related(
            'tipo_guardia', 'residente'
        ).order_by('fecha'):
            candidatos, sugerido = sugerir_reemplazo(guardia)
            guardias_data.append({
                'guardia': guardia,
                'candidatos': candidatos,   # lista de {'residente': obj, 'guardias_mes': int}
                'sugerido': sugerido,
            })
        return {
            'ausencia': ausencia,
            'guardias_data': guardias_data,
            'return_to_url': self._return_url(),
            'focus_id': ausencia.pk,
        }


# ---------------------------------------------------------------------------
# Fase 5: Cambios de guardia
# ---------------------------------------------------------------------------

class CambiosGuardiaView(LoginRequiredMixin, TemplateView):
    """
    Lista de solicitudes de cambio de guardia.
    - Residentes: ven sus solicitudes enviadas y recibidas.
    - Gestores: ven todas pendientes de su validación + historial.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/cambios.html']
        return ['control_guardias/portal/cambios.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        es_gestor = user.rol in ['jefe_residentes', 'instructor_residentes'] or user.is_superuser
        context['es_gestor'] = es_gestor

        base_qs = (
            SolicitudCambioGuardia.objects
            .select_related(
                'solicitante', 'receptor',
                'guardia_solicitante__tipo_guardia',
                'guardia_receptor__tipo_guardia',
                'revisado_por',
            )
        )

        if es_gestor:
            context['pendientes_jefe'] = base_qs.filter(estado='PENDIENTE_JEFE').order_by('-fecha_solicitud')
            context['historial'] = base_qs.exclude(estado__in=['PENDIENTE_RECEPTOR', 'PENDIENTE_JEFE']).order_by('-fecha_resolucion')
        else:
            context['enviadas'] = base_qs.filter(solicitante=user).order_by('-fecha_solicitud')
            context['recibidas'] = base_qs.filter(receptor=user, estado='PENDIENTE_RECEPTOR').order_by('-fecha_solicitud')
        return context


class SolicitarCambioView(LoginRequiredMixin, TemplateView):
    """
    GET: muestra el formulario para solicitar cambio de una guardia propia.
    POST: crea la SolicitudCambioGuardia.
    URL: /guardias/<guardia_pk>/solicitar-cambio/
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/solicitar_cambio_form.html']
        return ['control_guardias/portal/solicitar_cambio_form.html']

    def _get_guardia(self, guardia_pk):
        return get_object_or_404(
            AsignacionGuardia,
            pk=guardia_pk,
            residente=self.request.user,
            estado='PUBLICADA',
        )

    def _return_url(self, guardia_pk=None):
        fallback = reverse('control_guardias:cambios')
        return _safe_return_url(self.request, fallback, focus=guardia_pk)

    def _get_target_guardia_id(self):
        raw = self.request.GET.get('target_guardia', '').strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def _build_form(self, data=None):
        initial = {}
        target_guardia_id = self._get_target_guardia_id()
        if data is None and target_guardia_id:
            initial['guardia_receptor'] = target_guardia_id
        return SolicitudCambioGuardiaForm(
            data,
            solicitante=self.request.user,
            initial=initial,
        )

    def _get_guardia_objetivo(self, form):
        target_guardia_id = self._get_target_guardia_id()
        if not target_guardia_id:
            return None
        return form.fields['guardia_receptor'].queryset.filter(pk=target_guardia_id).first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardia = self._get_guardia(self.kwargs['guardia_pk'])
        form = kwargs.get('form', self._build_form())
        context['guardia'] = guardia
        context['form'] = form
        context['guardia_objetivo'] = self._get_guardia_objetivo(form)
        context['return_to_url'] = self._return_url(guardia.pk)
        context['focus_id'] = guardia.pk
        return context

    def post(self, request, guardia_pk, *args, **kwargs):
        guardia_sol = self._get_guardia(guardia_pk)
        form = self._build_form(request.POST)
        if not form.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form)
            )
        try:
            solicitar_cambio(
                solicitante=request.user,
                guardia_solicitante=guardia_sol,
                guardia_receptor=form.cleaned_data['guardia_receptor'],
            )
            messages.success(request, "Solicitud de cambio enviada. El receptor fue notificado.")
            return redirect(self._return_url(guardia_sol.pk))
        except CambioGuardiaError as e:
            messages.error(request, str(e))
            return self.render_to_response(self.get_context_data(form=form))


class ResponderCambioView(LoginRequiredMixin, TemplateView):
    """
    POST: receptor acepta o rechaza una solicitud de cambio.
    ?accion=aceptar|rechazar
    """
    template_name = None
    login_url = 'login'

    def post(self, request, pk, *args, **kwargs):
        solicitud = get_object_or_404(SolicitudCambioGuardia, pk=pk)
        accion = request.POST.get('accion', '')
        try:
            if accion == 'aceptar':
                aceptar_cambio_receptor(solicitud, request.user)
                messages.success(request, "Aceptaste el cambio. Queda pendiente de validación por el jefe/instructor.")
            elif accion == 'rechazar':
                rechazar_cambio_receptor(solicitud, request.user)
                messages.success(request, "Rechazaste la solicitud de cambio.")
            else:
                messages.error(request, "Acción no válida.")
        except CambioGuardiaError as e:
            messages.error(request, str(e))
        return redirect(
            _safe_return_url(
                request,
                reverse('control_guardias:cambios'),
                focus=solicitud.pk,
            )
        )

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:cambios')


class RevisarCambioView(JefeInstructorMixin, TemplateView):
    """
    GET: muestra formulario de notas para aprobar/rechazar.
    POST: jefe aprueba (?accion=aprobar) o rechaza (?accion=rechazar) el cambio.
    """
    login_url = 'login'

    def get_template_names(self):
        if self.request.user.is_superuser:
            return ['control_guardias/revisar_cambio_form.html']
        return ['control_guardias/portal/revisar_cambio_form.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        solicitud = get_object_or_404(SolicitudCambioGuardia, pk=self.kwargs['pk'])
        context['solicitud'] = solicitud
        context['form'] = kwargs.get('form', NotasRechazoForm())
        context['return_to_url'] = _safe_return_url(
            self.request,
            reverse('control_guardias:cambios'),
            focus=solicitud.pk,
        )
        context['focus_id'] = solicitud.pk
        return context

    def post(self, request, pk, *args, **kwargs):
        solicitud = get_object_or_404(SolicitudCambioGuardia, pk=pk)
        form = NotasRechazoForm(request.POST)
        accion = request.POST.get('accion', '')
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        notas = form.cleaned_data.get('notas', '')
        try:
            if accion == 'aprobar':
                aprobar_cambio(solicitud, request.user, notas=notas)
                messages.success(request, "Cambio de guardia aprobado. Las asignaciones fueron actualizadas.")
            elif accion == 'rechazar':
                rechazar_cambio_jefe(solicitud, request.user, notas=notas)
                messages.success(request, "Cambio de guardia rechazado.")
            else:
                messages.error(request, "Acción no válida.")
        except CambioGuardiaError as e:
            messages.error(request, str(e))
        return redirect(
            _safe_return_url(
                request,
                reverse('control_guardias:cambios'),
                focus=solicitud.pk,
            )
        )


class CancelarCambioView(LoginRequiredMixin, TemplateView):
    """POST: solicitante cancela su propia solicitud (PENDIENTE_RECEPTOR o PENDIENTE_JEFE)."""
    template_name = None
    login_url = 'login'

    def post(self, request, pk, *args, **kwargs):
        solicitud = get_object_or_404(SolicitudCambioGuardia, pk=pk)
        try:
            cancelar_cambio(solicitud, request.user)
            messages.success(request, "Solicitud cancelada.")
        except CambioGuardiaError as e:
            messages.error(request, str(e))
        return redirect(
            _safe_return_url(
                request,
                reverse('control_guardias:cambios'),
                focus=solicitud.pk,
            )
        )

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:cambios')


class CancelarAusenciaView(LoginRequiredMixin, TemplateView):
    """POST: residente cancela su propia ausencia (solo PENDIENTE)."""
    template_name = None
    login_url = 'login'

    def post(self, request, pk, *args, **kwargs):
        ausencia = get_object_or_404(AusenciaResidente, pk=pk)
        try:
            cancelar_ausencia(ausencia, request.user)
            messages.success(request, "Ausencia cancelada.")
        except DistribucionError as e:
            messages.error(request, str(e))
        return redirect(
            _safe_return_url(
                request,
                reverse('control_guardias:ausencias'),
                focus=ausencia.pk,
            )
        )

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:ausencias')


# ─────────────────────────────────────────────────────────────────
# Rotaciones externas (jefe) — CRUD simple
# ─────────────────────────────────────────────────────────────────

class RotacionExternaListView(JefeInstructorMixin, ListView):
    """Jefe: lista todas las rotaciones externas registradas."""
    model = RotacionExterna
    template_name = 'control_guardias/portal/rotaciones_externas.html'
    context_object_name = 'rotaciones'
    login_url = 'login'

    def get_queryset(self):
        return RotacionExterna.objects.select_related('residente', 'creado_por').order_by('-fecha_inicio')


class RotacionExternaCreateView(JefeInstructorMixin, CreateView):
    """Jefe: registra una nueva rotación externa."""
    model = RotacionExterna
    form_class = RotacionExternaForm
    template_name = 'control_guardias/portal/rotacion_externa_form.html'
    login_url = 'login'

    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, 'Rotación registrada correctamente.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('control_guardias:rotaciones_lista')


class RotacionExternaDeleteView(JefeInstructorMixin, DeleteView):
    """Jefe: elimina una rotación externa."""
    model = RotacionExterna
    template_name = 'control_guardias/portal/rotacion_externa_confirmar_eliminar.html'
    login_url = 'login'
    success_url = reverse_lazy('control_guardias:rotaciones_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Rotación eliminada.')
        return super().form_valid(form)


# ─────────────────────────────────────────────────────────────────
# Eliminar guardia por excepción (jefe) — carry-over automático
# ─────────────────────────────────────────────────────────────────

class EliminarGuardiaExcepcionView(JefeInstructorMixin, TemplateView):
    """
    POST: jefe elimina una guardia PUBLICADA por excepción.
    Si trasladar_cuota=True (default), crea carry-over al mes siguiente.
    """
    template_name = None
    login_url = 'login'

    def post(self, request, guardia_pk, *args, **kwargs):
        guardia = get_object_or_404(AsignacionGuardia, pk=guardia_pk)
        trasladar = request.POST.get('trasladar_cuota', 'true').lower() != 'false'
        motivo = request.POST.get('motivo', '').strip()
        try:
            resultado = eliminar_guardia_excepcion(guardia, request.user, trasladar_cuota=trasladar, motivo=motivo)
            if resultado.get('ajuste_creado'):
                messages.success(
                    request,
                    f"Guardia eliminada. Se creó carry-over para "
                    f"{guardia.residente.get_full_name()} en el mes siguiente."
                )
            else:
                messages.success(request, 'Guardia eliminada sin carry-over.')
        except (DistribucionError, CambioGuardiaError) as e:
            messages.error(request, str(e))
        return _safe_return_url(
            request,
            reverse('control_guardias:calendario'),
        )

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:calendario')


# ─────────────────────────────────────────────────────────────────
# Solicitudes de slot vacante (residente → jefe)
# ─────────────────────────────────────────────────────────────────

class SolicitarSlotVacanteView(LoginRequiredMixin, TemplateView):
    """
    Residente solicita mover su guardia a un slot vacío.
    GET: muestra modal con formulario.
    POST: crea la SolicitudSlotVacante.
    """
    template_name = 'control_guardias/portal/solicitar_slot_vacante.html'
    login_url = 'login'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        guardia = get_object_or_404(AsignacionGuardia, pk=self.kwargs['guardia_pk'])
        if guardia.residente_id != self.request.user.id or guardia.estado != 'PUBLICADA':
            from django.http import Http404
            raise Http404('Guardia no disponible para solicitud de slot vacante.')
        ctx['guardia'] = guardia
        ctx['form'] = SolicitudSlotVacanteForm()
        # Slots vacíos: mismos tipos de guardia, mismo mes/año, sin asignación existente
        import calendar
        fecha = guardia.fecha
        ultimo_dia = calendar.monthrange(fecha.year, fecha.month)[1]
        from datetime import date
        inicio_mes = date(fecha.year, fecha.month, 1)
        fin_mes = date(fecha.year, fecha.month, ultimo_dia)
        guardias_ocupadas = AsignacionGuardia.objects.filter(
            fecha__range=(inicio_mes, fin_mes),
            tipo_guardia=guardia.tipo_guardia,
            estado__in=['BORRADOR', 'PUBLICADA'],
        ).values_list('fecha', flat=True)
        from django.contrib.auth import get_user_model
        dias_libres = [
            date(fecha.year, fecha.month, d)
            for d in range(1, ultimo_dia + 1)
            if date(fecha.year, fecha.month, d) not in guardias_ocupadas
            and date(fecha.year, fecha.month, d) != fecha
        ]
        ctx['slots_disponibles'] = dias_libres
        ctx['tipo_guardia'] = guardia.tipo_guardia
        return ctx

    def post(self, request, guardia_pk, *args, **kwargs):
        guardia = get_object_or_404(AsignacionGuardia, pk=guardia_pk)
        if guardia.residente_id != request.user.id or guardia.estado != 'PUBLICADA':
            messages.error(request, 'Solo podés solicitar slot vacante sobre una guardia propia en estado PUBLICADA.')
            return redirect(reverse('control_guardias:mis_guardias'))
        form = SolicitudSlotVacanteForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Formulario inválido.')
            return redirect(reverse('control_guardias:solicitar_slot_vacante', kwargs={'guardia_pk': guardia_pk}))

        slot_fecha_str = request.POST.get('slot_fecha')
        tipo_id = request.POST.get('slot_tipo_guardia')
        if not slot_fecha_str or not tipo_id:
            messages.error(request, 'Debés seleccionar un slot destino.')
            return redirect(reverse('control_guardias:solicitar_slot_vacante', kwargs={'guardia_pk': guardia_pk}))

        from datetime import date as date_cls
        try:
            slot_fecha = date_cls.fromisoformat(slot_fecha_str)
        except ValueError:
            messages.error(request, 'Fecha de slot inválida.')
            return redirect(reverse('control_guardias:solicitar_slot_vacante', kwargs={'guardia_pk': guardia_pk}))

        tipo = get_object_or_404(ConfiguracionTipoGuardia, pk=tipo_id)
        SolicitudSlotVacante.objects.create(
            solicitante=request.user,
            guardia_ceder=guardia,
            slot_fecha=slot_fecha,
            slot_tipo_guardia=tipo,
            notas_solicitante=form.cleaned_data.get('notas_solicitante', ''),
        )
        messages.success(request, 'Solicitud enviada. El jefe la revisará a la brevedad.')
        return redirect(_safe_return_url(request, reverse('control_guardias:mis_guardias')))


class CancelarSlotVacanteView(LoginRequiredMixin, TemplateView):
    """POST: residente cancela su propia solicitud de slot vacante (solo PENDIENTE)."""
    template_name = None
    login_url = 'login'

    def post(self, request, pk, *args, **kwargs):
        solicitud = get_object_or_404(SolicitudSlotVacante, pk=pk, solicitante=request.user)
        try:
            cancelar_slot_vacante(solicitud, request.user)
            messages.success(request, 'Solicitud cancelada.')
        except (DistribucionError, CambioGuardiaError) as e:
            messages.error(request, str(e))
        return redirect(_safe_return_url(request, reverse('control_guardias:mis_guardias')))

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:mis_guardias')


class SolicitudesSlotVacanteView(JefeInstructorMixin, ListView):
    """Jefe: lista solicitudes de slot vacante pendientes."""
    model = SolicitudSlotVacante
    template_name = 'control_guardias/portal/solicitudes_slot_vacante.html'
    context_object_name = 'solicitudes'
    login_url = 'login'

    def get_queryset(self):
        return SolicitudSlotVacante.objects.filter(
            estado='PENDIENTE'
        ).select_related(
            'solicitante', 'guardia_ceder', 'guardia_ceder__tipo_guardia', 'slot_tipo_guardia'
        ).order_by('fecha_solicitud')


class RevisarSlotVacanteView(JefeInstructorMixin, TemplateView):
    """
    Jefe: aprueba o rechaza una SolicitudSlotVacante.
    POST con accion=aprobar|rechazar.
    """
    template_name = None
    login_url = 'login'

    def post(self, request, pk, *args, **kwargs):
        solicitud = get_object_or_404(SolicitudSlotVacante, pk=pk)
        accion = request.POST.get('accion')
        notas = request.POST.get('notas_jefe', '').strip()
        try:
            if accion == 'aprobar':
                aprobar_slot_vacante(solicitud, request.user, notas=notas)
                messages.success(request, 'Solicitud aprobada. Guardia reasignada correctamente.')
            elif accion == 'rechazar':
                rechazar_slot_vacante(solicitud, request.user, notas=notas)
                messages.warning(request, 'Solicitud rechazada.')
            else:
                messages.error(request, 'Acción inválida.')
        except (DistribucionError, CambioGuardiaError) as e:
            messages.error(request, str(e))
        return redirect(
            _safe_return_url(request, reverse('control_guardias:solicitudes_slot_vacante'))
        )

    def get(self, request, *args, **kwargs):
        return redirect('control_guardias:solicitudes_slot_vacante')

