from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, TemplateView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q, Prefetch
from django.http import FileResponse, HttpResponse
from django.contrib.auth import get_user_model
import io, json
import pandas as pd
from datetime import datetime, date
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from .models import Estudios, RegistroEstudiosPorMedico, GuardiaPasiva, SesionContable
from .forms import (
    RegistroEstudiosPorMedicoCreateViewForm,  # Alias de PracticaForm (compatibilidad)
    PracticaForm,
    GuardiaPasivaForm,
    FiltroMedicoMesForm, 
    FiltroEstudiosPorMedicoForm,
    CargaExcelForm,
)
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font
from django.utils.timezone import now
from openpyxl import Workbook
from django.urls import reverse

# ===== PORTAL ADMINISTRATIVO (Sin Login) =====

class PortalLiquidacionInicioView(TemplateView):
    """Vista de inicio del portal administrativo de liquidación"""
    template_name = 'liquidacion/portal_inicio.html'

# ===== VISTAS REGULARES (Requieren Login) =====
from django.utils.http import urlencode
from django.utils.safestring import mark_safe

class EstudiosCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Estudios
    fields = ['nombre', 'tipo', 'conteo_regiones']
    template_name = 'liquidacion/estudios_form.html'
    success_url = reverse_lazy('estudios_list')
    success_message = "El estudio fue registrado exitosamente"  # Mensaje de éxito

class EstudiosListView(LoginRequiredMixin, ListView):
    model = Estudios
    template_name = 'liquidacion/estudios_list.html'
    # Asegúrate de usar el nombre correcto en la plantilla
    context_object_name = 'estudios'

class RegistroEstudiosPorMedicoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista para registro de prácticas médicas - Liquidación v2.0
    Incluye validaciones de sesión contable y cálculo automático de montos
    """
    model = RegistroEstudiosPorMedico
    form_class = RegistroEstudiosPorMedicoCreateViewForm
    template_name = 'liquidacion/registroestudios_form_tailwind.html'
    success_url = reverse_lazy('liquidacion:registroestudios_nuevo')
    success_message = "✅ Registro guardado exitosamente"

    def dispatch(self, request, *args, **kwargs):
        # Validar que sea médico (por rol, no por grupo)
        if not request.user.es_medico():
            messages.warning(request, "No tienes permiso para acceder a esta sección.")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Pasar usuario al form para lógica condicional
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = datetime.today()

        # Obtener o crear sesión contable del mes actual
        sesion, created = SesionContable.objects.get_or_create(
            mes=today.month,
            año=today.year,
            defaults={'estado': 'ABIERTA'}
        )
        context['sesion_contable'] = sesion
        context['puede_registrar'] = sesion.puede_registrar_practicas(user)

        # Tipo de estudio seleccionado (para filtrar estudios con JS)
        tipo_estudio_seleccionado = self.request.POST.get('tipo_estudio', '')
        if not tipo_estudio_seleccionado:
            ultimo_registro = RegistroEstudiosPorMedico.objects.filter(medico=user).order_by('-fecha_registro').first()
            if ultimo_registro and ultimo_registro.estudio.exists():
                tipo_estudio_seleccionado = ultimo_registro.estudio.first().tipo

        context['tipo_estudio_seleccionado'] = tipo_estudio_seleccionado
        
        # Serializar estudios para JS (convertir Decimals a string)
        estudios_data = []
        for estudio in Estudios.objects.filter(activo=True).values(
            'id', 'nombre', 'tipo', 'codigo', 'precio_cober', 'precio_otras_os', 
            'precio_unico', 'conteo_regiones_default'
        ):
            estudio_dict = dict(estudio)
            # Convertir Decimals a string para JSON
            estudio_dict['precio_cober'] = str(estudio_dict['precio_cober'])
            estudio_dict['precio_otras_os'] = str(estudio_dict['precio_otras_os'])
            estudios_data.append(estudio_dict)
        
        context['estudios'] = json.dumps(estudios_data)
        
        # Registros del mes actual con prefetch de estudios
        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=user,
            sesion_contable=sesion
        ).prefetch_related('estudio').order_by('-fecha_registro')
        
        context['registros'] = registros
        
        # Calcular totales del mes
        total_regiones_mes = sum(reg.cantidad_regiones for reg in registros)
        total_monto_mes = sum(reg.monto_calculado for reg in registros)
        
        context['total_regiones_mes'] = total_regiones_mes
        context['total_monto_mes'] = total_monto_mes
        context['total_practicas_mes'] = registros.count()
        
        # Información del médico
        context['es_staff'] = user.rol in ['medico_staff', 'jefe_servicio', 'cardiologo']
        context['trabaja_remoto'] = user.trabaja_remoto

        return context

    def form_valid(self, form):
        user = self.request.user
        
        # Validar que la sesión permita registrar
        sesion, created = SesionContable.objects.get_or_create(
            mes=form.instance.fecha_del_informe.month,
            año=form.instance.fecha_del_informe.year,
            defaults={'estado': 'ABIERTA'}
        )
        
        if not sesion.puede_registrar_practicas(user):
            messages.error(
                self.request,
                f"❌ La sesión de {sesion.get_mes_display()} {sesion.año} está en estado "
                f"{sesion.get_estado_display()}. No puedes registrar prácticas."
            )
            return redirect(self.success_url)
        
        # Verificar duplicados recientes (últimos 5 minutos)
        from django.utils import timezone
        from datetime import timedelta
        
        dni_paciente = form.cleaned_data['dni_paciente']
        fecha_informe = form.cleaned_data['fecha_del_informe']
        estudios_seleccionados = form.cleaned_data['estudio']
        hace_5_minutos = timezone.now() - timedelta(minutes=5)
        
        registros_recientes = RegistroEstudiosPorMedico.objects.filter(
            medico=user,
            dni_paciente=dni_paciente,
            fecha_del_informe=fecha_informe,
            fecha_registro__gte=hace_5_minutos
        )
        
        for registro in registros_recientes:
            estudios_existentes = set(registro.estudio.all())
            if estudios_existentes == set(estudios_seleccionados):
                messages.warning(
                    self.request, 
                    f"⚠️ Ya registraste este mismo estudio hace menos de 5 minutos. "
                    f"Si realmente necesitas crear otro registro, espera unos minutos."
                )
                return redirect(self.success_url)
        
        # Guardar el objeto sin commit para asignar relaciones
        self.object = form.save(commit=False)
        self.object.medico = user
        self.object.sesion_contable = sesion
        
        # IMPORTANTE: Guardar primero para obtener el ID (sin calcular monto aún)
        self.object.save()
        
        # AHORA guardar las relaciones ManyToMany (estudio)
        form.save_m2m()
        
        # AHORA que tenemos M2M guardado, calcular y guardar el monto
        self.object.monto_calculado = self.object.calcular_monto()
        self.object.save(update_fields=['monto_calculado'])
        
        # Mostrar desglose del cálculo
        desglose = self.object.get_desglose_monto()
        mensaje_desglose = (
            f"✅ Práctica registrada | "
            f"Estudio: {desglose['estudio']} | "
            f"Regiones: {desglose['regiones']} | "
            f"OS: {desglose['tipo_os']} | "
            f"Horario: {desglose['horario']} | "
            f"Monto: ${desglose['monto_final']}"
        )
        if desglose.get('bonus_urgencia'):
            mensaje_desglose += f" (incluye bonus urgencia {desglose['bonus_urgencia']})"
        
        messages.success(self.request, mensaje_desglose)
        
        return redirect(self.success_url)


# [DEPRECADO - 16 de febrero 2026]
# RegistrarDiaSinPacientesView NO se usa en Colegiales
# Se mantiene comentado por compatibilidad con código legacy
#
# class RegistrarDiaSinPacientesView(LoginRequiredMixin, FormView):
#     template_name = 'liquidacion/registroestudios_form_tailwind.html'
#     form_class = DiaSinPacientesForm
#     success_url = reverse_lazy('liquidacion:registroestudios_nuevo')
# 
#     def form_valid(self, form):
#         fecha = form.cleaned_data['fecha']
#         medico = self.request.user
# 
#         if DiaSinPacientes.objects.filter(medico=medico, fecha=fecha).exists():
#             messages.warning(self.request, f"Ya registraste el día {fecha.strftime('%d/%m/%Y')}.")
#         else:
#             dia = form.save(commit=False)
#             dia.medico = medico
#             dia.save()
#             messages.success(self.request, f"Se registró el día {fecha.strftime('%d/%m/%Y')} como sin pacientes.")
# 
#         return super().form_valid(form)


# ============================================================================
# NUEVAS VISTAS - LIQUIDACIÓN v2.0
# ============================================================================

class RegistrarGuardiaPasivaView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    """
    Vista para registrar guardias pasivas ($36.500 por día)
    Solo disponible para médicos
    """
    model = GuardiaPasiva
    form_class = GuardiaPasivaForm
    template_name = 'liquidacion/guardia_pasiva_form.html'
    success_url = reverse_lazy('liquidacion:registrar_guardia_pasiva')
    success_message = "✅ Guardia pasiva registrada exitosamente"

    def dispatch(self, request, *args, **kwargs):
        # Solo médicos pueden registrar guardias
        if not request.user.es_medico():
            messages.warning(request, "No tienes permiso para acceder a esta sección.")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = datetime.today()

        # Obtener sesión contable actual
        sesion, created = SesionContable.objects.get_or_create(
            mes=today.month,
            año=today.year,
            defaults={'estado': 'ABIERTA'}
        )
        context['sesion_contable'] = sesion
        context['puede_registrar'] = sesion.puede_registrar_practicas(user)

        # Guardias del mes actual
        guardias = GuardiaPasiva.objects.filter(
            medico=user,
            sesion_contable=sesion
        ).order_by('-fecha_guardia')
        
        context['guardias'] = guardias
        context['total_guardias_mes'] = guardias.count()
        context['total_monto_guardias_mes'] = sum(g.monto for g in guardias)

        return context

    def form_valid(self, form):
        user = self.request.user
        fecha_guardia = form.cleaned_data['fecha_guardia']
        
        # Validar que la sesión permita registrar
        sesion, created = SesionContable.objects.get_or_create(
            mes=fecha_guardia.month,
            año=fecha_guardia.year,
            defaults={'estado': 'ABIERTA'}
        )
        
        if not sesion.puede_registrar_practicas(user):
            messages.error(
                self.request,
                f"❌ La sesión de {sesion.get_mes_display()} {sesion.año} está en estado "
                f"{sesion.get_estado_display()}. No puedes registrar guardias."
            )
            return redirect(self.success_url)
        
        # Verificar que no exista duplicado
        if GuardiaPasiva.objects.filter(medico=user, fecha_guardia=fecha_guardia).exists():
            messages.warning(
                self.request,
                f"⚠️ Ya tienes registrada una guardia para el día {fecha_guardia.strftime('%d/%m/%Y')}."
            )
            return redirect(self.success_url)
        
        # Asignar médico
        form.instance.medico = user
        
        response = super().form_valid(form)
        
        # Mensaje de éxito detallado
        messages.success(
            self.request,
            f"✅ Guardia pasiva registrada | "
            f"Fecha: {fecha_guardia.strftime('%d/%m/%Y')} | "
            f"Tipo: {form.instance.get_tipo_guardia_display()} | "
            f"Monto: ${form.instance.monto}"
        )
        
        return response


class GuardiaPasivaUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    """
    Vista para editar guardias pasivas
    Solo el médico que creó la guardia puede editarla
    """
    model = GuardiaPasiva
    form_class = GuardiaPasivaForm
    template_name = 'liquidacion/guardia_pasiva_update.html'
    success_url = reverse_lazy('liquidacion:registrar_guardia_pasiva')
    success_message = "✅ Guardia pasiva actualizada correctamente"

    def dispatch(self, request, *args, **kwargs):
        # Solo médicos pueden editar guardias
        if not request.user.es_medico():
            messages.warning(request, "No tienes permiso para acceder a esta sección.")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Solo puede editar sus propias guardias
        return GuardiaPasiva.objects.filter(medico=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardia = self.object
        
        # Sesión contable de la guardia
        context['sesion_contable'] = guardia.sesion_contable
        context['puede_editar'] = guardia.sesion_contable.puede_registrar_practicas(self.request.user)
        
        return context

    def form_valid(self, form):
        guardia = self.object
        user = self.request.user
        fecha_guardia = form.cleaned_data['fecha_guardia']
        
        # Validar que la sesión permita editar
        sesion = guardia.sesion_contable
        if not sesion.puede_registrar_practicas(user):
            messages.error(
                self.request,
                f"❌ La sesión de {sesion.get_mes_display()} {sesion.año} está en estado "
                f"{sesion.get_estado_display()}. No puedes editar guardias."
            )
            return redirect(self.success_url)
        
        # Verificar duplicados (excluyendo esta misma guardia)
        if GuardiaPasiva.objects.filter(
            medico=user, 
            fecha_guardia=fecha_guardia
        ).exclude(pk=guardia.pk).exists():
            messages.warning(
                self.request,
                f"⚠️ Ya tienes registrada otra guardia para el día {fecha_guardia.strftime('%d/%m/%Y')}."
            )
            return redirect(self.success_url)
        
        return super().form_valid(form)


class GuardiaPasivaDeleteView(LoginRequiredMixin, DeleteView):
    """
    Vista para eliminar guardias pasivas
    Solo el médico que creó la guardia puede eliminarla
    """
    model = GuardiaPasiva
    template_name = 'liquidacion/guardia_pasiva_confirm_delete.html'
    success_url = reverse_lazy('liquidacion:registrar_guardia_pasiva')

    def dispatch(self, request, *args, **kwargs):
        # Solo médicos pueden eliminar guardias
        if not request.user.es_medico():
            messages.warning(request, "No tienes permiso para acceder a esta sección.")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Solo puede eliminar sus propias guardias
        return GuardiaPasiva.objects.filter(medico=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        guardia = self.object
        
        # Sesión contable de la guardia
        context['sesion_contable'] = guardia.sesion_contable
        context['puede_eliminar'] = guardia.sesion_contable.puede_registrar_practicas(self.request.user)
        
        return context

    def delete(self, request, *args, **kwargs):
        guardia = self.get_object()
        user = request.user
        
        # Validar que la sesión permita eliminar
        sesion = guardia.sesion_contable
        if not sesion.puede_registrar_practicas(user):
            messages.error(
                request,
                f"❌ La sesión de {sesion.get_mes_display()} {sesion.año} está en estado "
                f"{sesion.get_estado_display()}. No puedes eliminar guardias."
            )
            return redirect(self.success_url)
        
        # Guardar datos para el mensaje antes de eliminar
        fecha = guardia.fecha_guardia.strftime('%d/%m/%Y')
        tipo = guardia.get_tipo_guardia_display()
        monto = guardia.monto
        
        response = super().delete(request, *args, **kwargs)
        
        messages.success(
            request,
            f"🗑️ Guardia eliminada | Fecha: {fecha} | Tipo: {tipo} | Monto: ${monto}"
        )
        
        return response


User = get_user_model()

class RegistroEstudiosPorMedicoListView(LoginRequiredMixin, TemplateView):
    """
    Dashboard de prácticas del médico - Liquidación v2.0
    Incluye prácticas, guardias pasivas, totales de montos y sesión contable
    """
    template_name = 'liquidacion/registroestudios_list_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fecha actual
        fecha_actual = datetime.now()
        mes_actual = fecha_actual.month
        año_actual = fecha_actual.year

        # Inicializar el formulario
        params = self.request.GET.copy()
        if not params.get('mes'):
            params['mes'] = str(mes_actual)
        if not params.get('año'):
            params['año'] = str(año_actual)
        form = FiltroEstudiosPorMedicoForm(params)

        if form.is_valid():
            mes = form.cleaned_data.get('mes') or mes_actual
            año = form.cleaned_data.get('año') or año_actual
        else:
            mes, año = mes_actual, año_actual

        mes = int(mes)

        # Diccionario de nombres de meses
        MESES = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }

        # Obtener o crear sesión contable
        sesion, created = SesionContable.objects.get_or_create(
            mes=mes,
            año=año,
            defaults={'estado': 'ABIERTA'}
        )
        context['sesion_contable'] = sesion
        context['puede_registrar'] = sesion.puede_registrar_practicas(self.request.user)

        # Pasar los valores base al contexto
        context['form'] = form
        context['mes'] = MESES.get(mes, 'Desconocido')
        context['año'] = año
        context['mes_num'] = mes
        context['año_num'] = año

        # Filtrar registros del usuario logueado usando sesión contable
        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=self.request.user,
            sesion_contable=sesion
        ).prefetch_related('estudio')

        # Obtener guardias pasivas del mes
        guardias = GuardiaPasiva.objects.filter(
            medico=self.request.user,
            sesion_contable=sesion
        ).order_by('-fecha_guardia')

        # Obtener parámetros de ordenamiento y filtros
        orden = self.request.GET.get('orden', 'fecha_desc')
        filtro_rapido = self.request.GET.get('filtro_rapido', '')
        busqueda = self.request.GET.get('busqueda', '').strip()

        # Aplicar búsqueda por paciente si existe
        if busqueda:
            registros = registros.filter(
                Q(nombre_paciente__icontains=busqueda) | 
                Q(apellido_paciente__icontains=busqueda) |
                Q(dni_paciente__icontains=busqueda)
            )

        # Aplicar filtros rápidos
        if filtro_rapido == 'hoy':
            from datetime import date
            registros = registros.filter(fecha_registro__date=date.today())

        # Aplicar ordenamiento
        if orden == 'fecha_asc':
            registros = registros.order_by('fecha_del_informe', 'fecha_registro')
        elif orden == 'fecha_desc':
            registros = registros.order_by('-fecha_del_informe', '-fecha_registro')
        elif orden == 'paciente_asc':
            registros = registros.order_by('apellido_paciente', 'nombre_paciente')
        elif orden == 'paciente_desc':
            registros = registros.order_by('-apellido_paciente', '-nombre_paciente')

        # Si el filtro rápido es 'hoy', ajustar visualmente mes/año
        if filtro_rapido == 'hoy':
            hoy = datetime.now()
            context['mes'] = MESES.get(hoy.month, 'Desconocido')
            context['año'] = hoy.year
            context['mes_num'] = hoy.month
            context['año_num'] = hoy.year

        # Etiqueta descriptiva del filtro rápido
        filtro_labels = {
            '': '',
            'hoy': 'Solo hoy',
        }
        context['filtro_rapido'] = filtro_rapido
        context['filtro_rapido_label'] = filtro_labels.get(filtro_rapido, '')

        # Separar registros por tipo de estudio (ECO vs OTROS)
        registros_eco = registros.filter(estudio__tipo='ECO').distinct()
        registros_otros = registros.exclude(estudio__tipo='ECO').distinct()

        # Agregar contexto para los controles
        context['orden'] = orden
        context['busqueda'] = busqueda

        # ========== CÁLCULOS v2.0 - Usando monto_calculado ==========
        
        # Totales de prácticas de Ecografías
        total_regiones_eco = sum(reg.cantidad_regiones for reg in registros_eco)
        total_monto_eco = sum(reg.monto_calculado for reg in registros_eco)
        
        # Totales de prácticas Otros estudios
        total_regiones_otros = sum(reg.cantidad_regiones for reg in registros_otros)
        total_monto_otros = sum(reg.monto_calculado for reg in registros_otros)
        
        # Totales de guardias pasivas
        total_guardias = guardias.count()
        total_monto_guardias = sum(g.monto for g in guardias)
        
        # Totales generales del mes
        total_practicas = registros.count()
        total_regiones_general = total_regiones_eco + total_regiones_otros
        total_monto_practicas = total_monto_eco + total_monto_otros
        total_general = total_monto_practicas + total_monto_guardias

        # Agregar todo al contexto
        context['registros_eco'] = registros_eco
        context['total_regiones_eco'] = total_regiones_eco
        context['total_monto_eco'] = total_monto_eco
        
        context['registros_otros'] = registros_otros
        context['total_regiones_otros'] = total_regiones_otros
        context['total_monto_otros'] = total_monto_otros
        
        context['guardias'] = guardias
        context['total_guardias'] = total_guardias
        context['total_monto_guardias'] = total_monto_guardias
        
        context['total_practicas'] = total_practicas
        context['total_regiones_general'] = total_regiones_general
        context['total_monto_practicas'] = total_monto_practicas
        context['total_general'] = total_general
        
        # Determinar qué solapa debe estar activa
        context['tipo_estudio_activo'] = self.request.GET.get('tipo_estudio', 'ecografias')

        return context

class RegistroEstudiosPorMedicoUpdateView(LoginRequiredMixin, UpdateView):
    model = RegistroEstudiosPorMedico
    form_class = RegistroEstudiosPorMedicoCreateViewForm
    template_name = 'liquidacion/registroestudios_update_tailwind.html'

    def get_queryset(self):
        # Filtra los registros que pertenecen al usuario logueado
        return RegistroEstudiosPorMedico.objects.filter(medico=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        registro = self.object

        # JSON para Select2 con todos los estudios (id, nombre, tipo)
        context['estudios'] = json.dumps(
            list(Estudios.objects.values('id', 'nombre', 'tipo'))
        )

        # Estudios y tipo preseleccionado
        if registro and registro.estudio.exists():
            context['tipo_estudio_seleccionado'] = registro.estudio.first().tipo
            context['estudios_seleccionados'] = list(registro.estudio.values_list('id', flat=True))
        else:
            context['tipo_estudio_seleccionado'] = ''
            context['estudios_seleccionados'] = []

        # URL del botón cancelar: vuelve a la lista con mes/año filtrados
        fecha = registro.fecha_del_informe
        context['cancel_url'] = f"{reverse('liquidacion:registroestudios_list')}?{urlencode({'mes': fecha.month, 'año': fecha.year})}"

        return context

    def form_valid(self, form):
        # Agrega mensaje de éxito si el formulario fue válido
        messages.success(self.request, "El registro fue actualizado correctamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        # Mostrar errores del formulario al usuario
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, f"Error: {error}")
                else:
                    field_label = form.fields.get(field).label if field in form.fields else field
                    messages.error(self.request, f"{field_label}: {error}")
        return super().form_invalid(form)

    def get_success_url(self):
        # Redirige a la lista con el mes y año del registro actualizado
        fecha = self.object.fecha_del_informe
        
        # Determinar el tipo de estudio para mantener la solapa activa
        # Solo hay 2 pestañas: 'ecografias' y 'otros' (RAD/TOM/RES)
        tipos = set(self.object.estudio.values_list('tipo', flat=True))
        
        if 'ECO' in tipos:
            tipo_estudio = 'ecografias'
        else:
            # Cualquier otro tipo (RAD, TOM, RES, etc.) va a 'otros'
            tipo_estudio = 'otros'
        
        query_string = urlencode({
            'mes': fecha.month, 
            'año': fecha.year,
            'tipo_estudio': tipo_estudio
        })
        return f"{reverse('liquidacion:registroestudios_list')}?{query_string}"

class RegistroEstudiosPorMedicoDeleteView(LoginRequiredMixin, DeleteView):
    model = RegistroEstudiosPorMedico
    template_name = 'liquidacion/registroestudios_confirm_delete_tailwind.html'

    def get_queryset(self):
        # Limita los registros a los del usuario logueado
        return RegistroEstudiosPorMedico.objects.filter(medico=self.request.user)

    def get_success_url(self):
        # Mantener el filtro de mes/año y tipo de estudio tras eliminar
        registro = self.object
        fecha = registro.fecha_del_informe
        
        # Determinar el tipo de estudio para mantener la solapa activa
        # Solo hay 2 pestañas: 'ecografias' y 'otros' (RAD/TOM/RES)
        tipos = set(registro.estudio.values_list('tipo', flat=True))
        
        if 'ECO' in tipos:
            tipo_estudio = 'ecografias'
        else:
            # Cualquier otro tipo (RAD, TOM, RES, etc.) va a 'otros'
            tipo_estudio = 'otros'
        
        query_string = urlencode({
            'mes': fecha.month,
            'año': fecha.year,
            'tipo_estudio': tipo_estudio
        })
        return f"{reverse('liquidacion:registroestudios_list')}?{query_string}"

    def delete(self, request, *args, **kwargs):
        registro = self.get_object()
        messages.success(request, "✅ Registro eliminado correctamente.")
        return super().delete(request, *args, **kwargs)

# ============================================================
# [ANULADO - 16 de febrero 2026]
# Procedimientos de Intervensionismo - En Colegiales no se usa
# Los procedimientos se registran como Estudios normales
# Si necesitas datos históricos: ver liquidacion_backup_completo_2026-02-16.json
# ============================================================

# ========================================
# VISTA UNIFICADA - v3.0 (Feb 2026)
# ========================================

class LiquidacionPorMedicoPorMesListView(TemplateView):
    """
    Vista unificada de liquidación mensual - Todas las prácticas + Guardias
    
    Muestra en un solo portal:
    - Todas las prácticas (ECO + RAD + TOM + RES)
    - Guardias pasivas
    - Total general
    
    Eliminada lógica obsoleta:
    - DiaSinPacientes (no se usa en Colegiales)
    - Complemento por mínimo garantizado (no aplica)
    - Cálculo de regiones faltantes
    """
    template_name = 'liquidacion/liquidacion_por_medico_por_mes_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroMedicoMesForm(self.request.GET or None)
        context['form'] = form

        registros_por_medico = defaultdict(list)
        guardias_por_medico = defaultdict(list)

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            # Filtrar TODAS las prácticas (sin excluir ningún tipo)
            registros = RegistroEstudiosPorMedico.objects.prefetch_related(
                Prefetch('estudio', queryset=Estudios.objects.all())
            ).distinct()

            # Filtrar guardias pasivas
            guardias = GuardiaPasiva.objects.all()

            if medico:
                registros = registros.filter(medico=medico)
                guardias = guardias.filter(medico=medico)

            if mes and año:
                registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))
                guardias = guardias.filter(fecha_guardia__year=int(año), fecha_guardia__month=int(mes))

            # Agrupar registros por médico
            for registro in registros.order_by('-fecha_del_informe'):
                registros_por_medico[registro.medico].append(registro)
            
            # Agrupar guardias por médico
            for guardia in guardias.order_by('-fecha_guardia'):
                guardias_por_medico[guardia.medico].append(guardia)

        # Preparar el contexto con datos por médico
        medico_data = []
        todos_medicos = set(registros_por_medico.keys()) | set(guardias_por_medico.keys())
        
        for medico in todos_medicos:
            registros = registros_por_medico.get(medico, [])
            guardias = guardias_por_medico.get(medico, [])
            
            # Agrupar prácticas por tipo para mostrar subtotales
            practicas_por_tipo = defaultdict(list)
            for registro in registros:
                for estudio in registro.estudio.all():
                    practicas_por_tipo[estudio.tipo].append(registro)
            
            total_regiones = sum(registro.cantidad_regiones for registro in registros)
            total_monto = sum(registro.monto_calculado for registro in registros)
            total_guardias = len(guardias)
            total_monto_guardias = sum(guardia.monto for guardia in guardias)
            
            medico_data.append({
                'medico': medico,
                'registros': registros,
                'practicas_por_tipo': dict(practicas_por_tipo),
                'guardias': guardias,
                'total_regiones': total_regiones,
                'total_monto': total_monto,
                'total_guardias': total_guardias,
                'total_monto_guardias': total_monto_guardias,
                'total_general': total_monto + total_monto_guardias,
            })

        context['medico_data'] = medico_data
        
        if form.is_valid() and not medico_data:
            medico_seleccionado = form.cleaned_data.get('medico')
            if medico_seleccionado:
                context['mensaje_sin_registros'] = (
                    f"No se encontraron registros para {medico_seleccionado.get_full_name()} en el período consultado."
                )
            else:
                context['mensaje_sin_registros'] = "No se encontraron registros en el período consultado."

        return context

# [ANULADO - 16 de febrero 2026]
# Vista ProcedimientosPorMedicoPorMesListView eliminada
# En Colegiales, los procedimientos se registran como Estudios
# Ver liquidacion_backup_completo_2026-02-16.json para datos históricos

def generar_pdf_liquidacion(request):
    """
    Generar PDF de liquidación - v2.0
    Incluye: prácticas con montos, guardias pasivas, totales
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    Story = []
    styles = getSampleStyleSheet()

    # Título y fecha
    titulo = Paragraph("<b>Liquidación de Estudios por Médico - v2.0</b>", styles["Title"])
    fecha_generacion = Paragraph(
        f"<b>Fecha de generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        styles["Normal"],
    )
    Story.append(titulo)
    Story.append(fecha_generacion)
    Story.append(Spacer(1, 10))

    # Médicos
    medicos = User.objects.filter(es_medico=True)
    for medico in medicos:
        # Encabezado del médico
        encabezado_medico = Paragraph(
            f"<b>Médico:</b> {medico.get_full_name()}", styles["Heading2"]
        )
        Story.append(encabezado_medico)
        Story.append(Spacer(1, 5))

        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=medico
        ).prefetch_related("estudio").order_by("-fecha_registro")

        # ===== PRÁCTICAS =====
        if registros.exists():
            data = [["Fecha", "Paciente", "Estudios", "Regiones", "OS", "Horario", "Monto"]]
            total_regiones = 0
            total_monto = 0

            for registro in registros:
                estudios_texto = ", ".join([est.nombre for est in registro.estudio.all()])
                regiones = registro.cantidad_regiones
                total_regiones += regiones
                total_monto += registro.monto_calculado

                data.append([
                    registro.fecha_del_informe.strftime('%d/%m/%Y') if registro.fecha_del_informe else "N/A",
                    f"{registro.apellido_paciente.upper()} {registro.nombre_paciente.upper()}",
                    estudios_texto,
                    str(regiones),
                    registro.get_tipo_obra_social_display(),
                    registro.get_horario_display(),
                    f"${registro.monto_calculado:,.2f}"
                ])

            # Agregar total de prácticas
            data.append(["", "", "TOTAL PRÁCTICAS", str(total_regiones), "", "", f"${total_monto:,.2f}"])

            # Crear tabla
            tabla = Table(data, colWidths=[60, 100, 120, 50, 60, 50, 70])
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (3, 1), (3, -1), 'CENTER'),
                ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#e0e0e0")),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            Story.append(tabla)
        else:
            Story.append(Paragraph(
                "<i>No hay prácticas registradas para este médico.</i>", styles["Normal"]))

        Story.append(Spacer(1, 10))

        # ===== GUARDIAS PASIVAS =====
        guardias = GuardiaPasiva.objects.filter(medico=medico).order_by('-fecha_guardia')
        if guardias.exists():
            encabezado_guardias = Paragraph("<b>Guardias Pasivas</b>", styles["Heading3"])
            Story.append(encabezado_guardias)
            Story.append(Spacer(1, 3))

            data_guardias = [["Fecha", "Tipo Guardia", "Monto", "Observaciones"]]
            total_guardias = 0

            for guardia in guardias:
                total_guardias += guardia.monto
                data_guardias.append([
                    guardia.fecha_guardia.strftime('%d/%m/%Y'),
                    guardia.get_tipo_guardia_display(),
                    f"${guardia.monto:,.2f}",
                    guardia.observaciones or ""
                ])

            data_guardias.append(["", "TOTAL GUARDIAS", f"${total_guardias:,.2f}", ""])

            tabla_guardias = Table(data_guardias, colWidths=[70, 100, 80, 260])
            tabla_guardias.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#70AD47")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#E2EFDA")),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            Story.append(tabla_guardias)
            Story.append(Spacer(1, 10))

            # Total General
            if registros.exists():
                total_general = total_monto + total_guardias
                total_general_text = Paragraph(
                    f"<b>TOTAL GENERAL (Prácticas + Guardias): ${total_general:,.2f}</b>",
                    styles["Heading3"]
                )
                Story.append(total_general_text)

        Story.append(Spacer(1, 15))

    # Construir PDF
    doc.build(Story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="Liquidacion_Medicos_v2.pdf")

# [ANULADO - 16 de febrero 2026 y ELIMINADAS v3.0 - 17 feb 2026]
# Funciones exportar_excel_informes y exportar_excel_ecografias eliminadas
# Usar exportar_excel_liquidacion (vista unificada) en su lugar
# En Colegiales los procedimientos se registran como estudios
# Ver ANALISIS_LIQUIDACION_COLEGIALES.md para más detalles


# ========================================
# EXPORTACIÓN UNIFICADA - v3.0 (Feb 2026)
# ========================================

def exportar_excel_liquidacion(request):
    """
    Exportar liquidación completa a Excel - v3.1 UNIFICADA (Una sola solapa)
    
    Incluye en una sola hoja:
    - Todas las prácticas (ECO + RAD + TOM + RES)
    - Guardias pasivas
    - Total general
    """
    medico_id = request.GET.get('medico')
    mes = request.GET.get('mes')
    año = request.GET.get('año')

    # Filtrar TODAS las prácticas (sin excluir ningún tipo)
    registros = RegistroEstudiosPorMedico.objects.prefetch_related(
        Prefetch('estudio', queryset=Estudios.objects.all())
    ).distinct()

    if medico_id:
        registros = registros.filter(medico_id=medico_id)
    if mes and año:
        registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))

    # Obtener guardias pasivas
    guardias = GuardiaPasiva.objects.none()
    if medico_id and mes and año:
        guardias = GuardiaPasiva.objects.filter(
            medico_id=medico_id,
            fecha_guardia__year=int(año),
            fecha_guardia__month=int(mes)
        ).order_by('fecha_guardia')

    # Obtener nombre del médico para el archivo
    medico = None
    if medico_id:
        medico = get_object_or_404(User, id=medico_id)
        nombre_medico = f"{medico.first_name}_{medico.last_name}"
    else:
        nombre_medico = "todos_los_medicos"

    # Crear libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liquidación Completa"

    # ======== SECCIÓN: PRÁCTICAS ========
    # Encabezados prácticas
    headers_practicas = [
        "Fecha", "Paciente", "DNI", "Estudios", 
        "Tipo", "Regiones", "Obra Social", "Horario", "Monto", "Bonus"
    ]
    ws.append(headers_practicas)

    # Estilo encabezados prácticas
    for cell in ws[1]:
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    # Agregar registros de prácticas
    total_regiones = 0
    total_monto_practicas = 0
    
    for registro in registros.order_by('-fecha_del_informe'):
        estudios_nombres = ", ".join([est.nombre for est in registro.estudio.all()])
        tipos_estudios = ", ".join(sorted(set([est.tipo for est in registro.estudio.all()])))
        bonus_icon = "⚡ SÍ" if registro.paciente_internado else ""
        
        ws.append([
            registro.fecha_del_informe.strftime("%d/%m/%Y"),
            f"{registro.apellido_paciente.upper()} {registro.nombre_paciente.upper()}",
            registro.dni_paciente,
            estudios_nombres,
            tipos_estudios,
            registro.cantidad_regiones,
            registro.get_tipo_obra_social_display(),
            registro.get_horario_display(),
            float(registro.monto_calculado),
            bonus_icon
        ])
        
        total_regiones += registro.cantidad_regiones
        total_monto_practicas += registro.monto_calculado

    # Fila de totales prácticas
    ws.append([])
    totales_practicas_row = ws.max_row + 1
    ws.append(["", "", "", "", "SUBTOTAL PRÁCTICAS", total_regiones, "", "", float(total_monto_practicas), ""])
    
    for cell in ws[totales_practicas_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    
    ws.cell(row=totales_practicas_row, column=9).number_format = '$#,##0.00'

    # ======== SECCIÓN: GUARDIAS ========
    total_monto_guardias = 0
    
    if guardias.exists():
        # Espaciado
        ws.append([])
        ws.append([])
        
        # Encabezados guardias
        headers_guardias = ["Fecha", "Tipo de Guardia", "Monto", "Observaciones"]
        header_row = ws.max_row + 1
        ws.append(headers_guardias)
        
        # Estilo encabezados guardias
        for col_num, cell in enumerate(ws[header_row], 1):
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        
        # Agregar guardias
        for guardia in guardias:
            ws.append([
                guardia.fecha_guardia.strftime("%d/%m/%Y"),
                guardia.get_tipo_guardia_display(),
                float(guardia.monto),
                guardia.observaciones or ""
            ])
            total_monto_guardias += guardia.monto
        
        # Totales guardias
        ws.append([])
        totales_guardias_row = ws.max_row + 1
        ws.append(["", "SUBTOTAL GUARDIAS", float(total_monto_guardias), ""])
        
        for cell in ws[totales_guardias_row]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        
        ws.cell(row=totales_guardias_row, column=3).number_format = '$#,##0.00'

    # ======== TOTAL GENERAL ========
    ws.append([])
    ws.append([])
    total_general_row = ws.max_row + 1
    ws.append(["", "", "", "", "TOTAL GENERAL", "", "", "", float(total_monto_practicas + total_monto_guardias), ""])
    
    for cell in ws[total_general_row]:
        cell.font = Font(bold=True, size=12)
        cell.fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
    
    ws.cell(row=total_general_row, column=9).number_format = '$#,##0.00'

    # ======== FORMATO DE MONEDA EN TODAS LAS FILAS ========
    # Columna 9 (Monto) en sección de prácticas
    for row in range(2, totales_practicas_row):
        ws.cell(row=row, column=9).number_format = '$#,##0.00'
    
    # Columna 3 (Monto) en sección de guardias si existen
    if guardias.exists():
        guardias_start = header_row + 1
        guardias_end = totales_guardias_row - 1
        for row in range(guardias_start, guardias_end + 1):
            ws.cell(row=row, column=3).number_format = '$#,##0.00'

    # ======== AJUSTE AUTOMÁTICO DE ANCHO DE COLUMNAS ========
    for column_cells in ws.columns:
        length = 0
        column_letter = column_cells[0].column_letter
        
        for cell in column_cells:
            try:
                if cell.value:
                    cell_length = len(str(cell.value))
                    if cell_length > length:
                        length = cell_length
            except:
                pass
        
        # Ajustar ancho con margen adicional
        adjusted_width = (length + 3)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Preparar respuesta HTTP
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="liquidacion_completa_{nombre_medico}_{mes}_{año}.xlsx"'
    wb.save(response)
    return response

# A continuación, se agrega el formulario para carga masiva de estudios

User = get_user_model()

# --- Carga masiva desactivada temporalmente ---
from django.contrib.auth.mixins import UserPassesTestMixin

class CargaMasivaView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'liquidacion/carga_formulario.html'
    form_class = CargaExcelForm
    success_url = reverse_lazy('carga-masiva')

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def post(self, request, *args, **kwargs):
        if 'datos_serializados' in request.POST:
            return self.confirmar_carga(request)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        archivo = form.cleaned_data['archivo_excel']
        df = pd.read_excel(archivo)
        registros_preview = []
        mapeo_estudios = {
            'US': {'tipo': 'ECO', 'nombre': 'ECO ABDOMINAL'},
            'CR': {'tipo': 'RAD', 'nombre': 'RX DE TÓRAX'},
            'DX': {'tipo': 'RAD', 'nombre': 'RX DE TÓRAX'},
            'CT': {'tipo': 'TOM', 'nombre': 'TC DE CEREBRO'},
            'MR': {'tipo': 'RES', 'nombre': 'RM CEREBRO C/ DIFUSIÓN'}
        }
        for _, fila in df.iterrows():
            try:
                nombre_medico = fila['Informe firmado por'].strip()
                medico = User.objects.filter(
                    first_name__in=nombre_medico.split(),
                    last_name__in=nombre_medico.split()
                ).first()
                if not medico:
                    continue
                dni = str(fila['Id. paciente'])[:8]
                nombre_completo = fila['Nombre del paciente'].strip()
                if ',' in nombre_completo:
                    partes = nombre_completo.split(',')
                    apellido = partes[0].strip()
                    nombre = partes[1].strip() if len(partes) > 1 else ''
                else:
                    partes = nombre_completo.split()
                    apellido = partes[0]
                    nombre = ' '.join(partes[1:]) if len(partes) > 1 else ''
                fecha = pd.to_datetime(fila['Fecha de firma final'], dayfirst=True).date()
                mod = fila['Mod.'].strip().upper()
                info_estudio = mapeo_estudios.get(mod)
                estudio = None
                if info_estudio:
                    estudio = Estudios.objects.filter(
                        tipo=info_estudio['tipo'],
                        nombre__iexact=info_estudio['nombre']
                    ).first()
                registros_preview.append({
                    'medico': medico.get_full_name(),
                    'nombre': nombre,
                    'apellido': apellido,
                    'dni': dni,
                    'fecha': str(fecha),
                    'mod': mod,
                    'estudio_base': info_estudio['nombre'] if info_estudio else 'No encontrado',
                    'estudio_tipo': info_estudio['tipo'] if info_estudio else '',
                })
            except Exception:
                continue
        context = self.get_context_data(form=form)
        context['registros'] = registros_preview
        context['registros_json'] = mark_safe(json.dumps(registros_preview, ensure_ascii=False))
        return self.render_to_response(context)

    def confirmar_carga(self, request):
        try:
            registros_json = request.POST.get('datos_serializados')
            registros = json.loads(registros_json)
            cargados = 0
            errores = 0
            for item in registros:
                try:
                    medico = User.objects.filter(
                        first_name__in=item['medico'].split(),
                        last_name__in=item['medico'].split()
                    ).first()
                    if not medico:
                        continue
                    estudio = Estudios.objects.filter(
                        tipo=item['estudio_tipo'],
                        nombre__iexact=item['estudio_base']
                    ).first()
                    if not estudio:
                        continue
                    registro = RegistroEstudiosPorMedico.objects.create(
                        medico=medico,
                        nombre_paciente=item['nombre'],
                        apellido_paciente=item['apellido'],
                        dni_paciente=item['dni'],
                        fecha_del_informe=item['fecha'],
                        cantidad_estudio=1
                    )
                    registro.estudio.add(estudio)
                    cargados += 1
                except Exception:
                    errores += 1
                    continue
            messages.success(request, f"✅ Se cargaron correctamente {cargados} registros. Errores: {errores}")
        except Exception as e:
            messages.error(request, f"❌ Error procesando la carga: {str(e)}")
        return redirect('carga-masiva')