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
        context['estudios'] = json.dumps(list(Estudios.objects.filter(activo=True).values(
            'id', 'nombre', 'tipo', 'codigo', 'precio_cober', 'precio_otras_os', 
            'precio_unico', 'conteo_regiones_default'
        )))
        
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
        
        # Asignar el usuario logueado
        form.instance.medico = user
        
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
        
        # Guardar y mostrar desglose del monto
        response = super().form_valid(form)
        
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
        
        return response


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


User = get_user_model()

class RegistroEstudiosPorMedicoListView(LoginRequiredMixin, TemplateView):
    template_name = 'liquidacion/registroestudios_list_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fecha actual
        fecha_actual = datetime.now()
        mes_actual = fecha_actual.month
        año_actual = fecha_actual.year

        # Inicializar el formulario
        # Si en la query no vienen mes/año (caso botones rápidos), forzamos valores actuales
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

        # Convertir el mes a un valor entero si es necesario (por ejemplo, si el formulario lo devuelve como cadena)
        mes = int(mes)

        # Diccionario de nombres de meses
        MESES = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }

        # Pasar los valores base al contexto
        context['form'] = form
        context['mes'] = MESES.get(mes, 'Desconocido')  # Mostrar el nombre del mes
        context['año'] = año
        # Valores numéricos para construir URLs de acciones (orden, botones rápidos)
        context['mes_num'] = mes
        context['año_num'] = año

        # Filtrar registros del usuario logueado usando `fecha_del_informe`
        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=self.request.user,
            fecha_del_informe__year=año,
            fecha_del_informe__month=mes
        )

        # Obtener parámetros de ordenamiento y filtros
        orden = self.request.GET.get('orden', 'fecha_desc')  # Por defecto: más recientes primero
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
        # Se elimina ordenamiento por DNI según requerimiento

        # Si el filtro rápido es 'hoy', ajustar visualmente mes/año
        if filtro_rapido == 'hoy':
            hoy = datetime.now()
            context['mes'] = MESES.get(hoy.month, 'Desconocido')
            context['año'] = hoy.year
            context['mes_num'] = hoy.month
            context['año_num'] = hoy.year

        # Etiqueta descriptiva del filtro rápido para mostrar en UI
        filtro_labels = {
            '': '',
            'hoy': 'Solo hoy',
        }
        context['filtro_rapido'] = filtro_rapido
        context['filtro_rapido_label'] = filtro_labels.get(filtro_rapido, '')

        # Separar registros por tipo de estudio
        registros_eco = registros.filter(estudio__tipo='ECO').distinct()
        registros_otros = registros.exclude(estudio__tipo='ECO').distinct()

        # Agregar contexto para los controles
        context['orden'] = orden
        context['filtro_rapido'] = filtro_rapido
        context['busqueda'] = busqueda

        # Calcular totales de regiones considerando la cantidad de estudios
        total_regiones_eco = sum(
            estudio.conteo_regiones * (registro.cantidad_estudio or 1)
            for registro in registros_eco
            for estudio in registro.estudio.all()
        )
        total_regiones_otros = sum(
            estudio.conteo_regiones * (registro.cantidad_estudio or 1)
            for registro in registros_otros
            for estudio in registro.estudio.all()
        )

        # Agregar registros al contexto
        context['registros_eco'] = registros_eco
        context['total_regiones_eco'] = total_regiones_eco
        context['registros_otros'] = registros_otros
        context['total_regiones_otros'] = total_regiones_otros
        
        # Determinar qué solapa debe estar activa (por defecto 'ecografias')
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

    def get_success_url(self):
        # Redirige a la lista con el mes y año del registro actualizado
        fecha = self.object.fecha_del_informe
        
        # Determinar el tipo de estudio para mantener la solapa activa
        tipo_estudio = 'otros'  # Por defecto
        if self.object.estudio.filter(tipo='ECO').exists():
            tipo_estudio = 'ecografias'
        
        query_string = urlencode({
            'mes': fecha.month, 
            'año': fecha.year,
            'tipo_estudio': tipo_estudio
        })
        return f"{reverse('liquidacion:registroestudios_list')}?{query_string}"

class RegistroEstudiosPorMedicoDeleteView(LoginRequiredMixin, DeleteView):
    model = RegistroEstudiosPorMedico
    template_name = 'liquidacion/registroestudios_confirm_delete_tailwind.html'
    success_url = reverse_lazy('liquidacion:registroestudios_list')

    def get_queryset(self):
        # Limita los registros a los del usuario logueado
        return RegistroEstudiosPorMedico.objects.filter(medico=self.request.user)

# ============================================================
# [ANULADO - 16 de febrero 2026]
# Procedimientos de Intervensionismo - En Colegiales no se usa
# Los procedimientos se registran como Estudios normales
# Si necesitas datos históricos: ver liquidacion_backup_completo_2026-02-16.json
# ============================================================

# Vistas para quienes consultan la liquidación sin loguearse

class InformadosPorMedicoPorMesListView(TemplateView):
    template_name = 'liquidacion/informados_por_medico_por_mes_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroMedicoMesForm(self.request.GET or None)
        context['form'] = form

        registros_por_medico = defaultdict(list)

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            # Filtrar registros excluyendo los estudios tipo 'ECO'
            registros = RegistroEstudiosPorMedico.objects.exclude(estudio__tipo='ECO').prefetch_related(
                Prefetch('estudio', queryset=Estudios.objects.all())
            ).distinct()

            if medico:
                registros = registros.filter(medico=medico)

            if mes and año:
                registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))

            # Agrupar registros por médico
            for registro in registros.order_by('-fecha_del_informe'):
                registros_por_medico[registro.medico].append(registro)

        # Preparar el contexto con datos por médico
        medico_data = []
        for medico, registros in registros_por_medico.items():
            total_regiones = sum(registro.total_regiones() for registro in registros)
            medico_data.append({
                'medico': medico,
                'registros': registros,
                'total_regiones': total_regiones,
            })

        context['medico_data'] = medico_data
        return context

User = get_user_model()

class EcografiasPorMedicoPorMesListView(TemplateView):
    template_name = 'liquidacion/ecografias_por_medico_por_mes_tailwind.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroMedicoMesForm(self.request.GET or None)
        context['form'] = form

        registros_por_medico = defaultdict(list)
        dias_sin_pacientes_por_medico = defaultdict(list)
        mostrar_totales_con_complemento = False
        fecha_minima = date(date.today().year, 3, 1)

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            if mes and año and (int(año), int(mes)) >= (fecha_minima.year, fecha_minima.month):
                mostrar_totales_con_complemento = True

            registros = RegistroEstudiosPorMedico.objects.filter(estudio__tipo='ECO').distinct()
            # [DEPRECADO] DiaSinPacientes no se usa en Colegiales
            # dias_sin_pacientes = DiaSinPacientes.objects.all()

            if medico:
                registros = registros.filter(medico=medico)
                dias_sin_pacientes = dias_sin_pacientes.filter(medico=medico)

            if mes and año:
                registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))
                dias_sin_pacientes = dias_sin_pacientes.filter(fecha__year=int(año), fecha__month=int(mes))

            for registro in registros.order_by('-fecha_del_informe'):
                registros_por_medico[registro.medico].append(registro)

            for dia in dias_sin_pacientes:
                dias_sin_pacientes_por_medico[dia.medico].append(dia)

        medico_data = []
        todos_medicos = set(registros_por_medico.keys()) | set(dias_sin_pacientes_por_medico.keys())

        for medico in todos_medicos:
            registros = registros_por_medico.get(medico, [])
            registros_por_dia = defaultdict(list)
            for registro in registros:
                registros_por_dia[registro.fecha_del_informe].append(registro)

            for dia in dias_sin_pacientes_por_medico.get(medico, []):
                if dia.fecha not in registros_por_dia:
                    registros_por_dia[dia.fecha] = []

            dias = []
            total_regiones_mes = 0
            total_complemento_mes = 0

            for fecha, registros_dia in sorted(registros_por_dia.items()):
                regiones_hechas = sum(r.total_regiones() for r in registros_dia)
                es_computable = fecha >= fecha_minima
                es_dia_sin_pacientes = len(registros_dia) == 0 and any(
                    d.fecha == fecha for d in dias_sin_pacientes_por_medico.get(medico, [])
                )

                regiones_faltantes = 0
                if es_computable:
                    regiones_faltantes = 12 if es_dia_sin_pacientes else max(0, 12 - regiones_hechas)

                total_regiones_mes += regiones_hechas
                if es_computable:
                    total_complemento_mes += regiones_faltantes

                dias.append({
                    'fecha': fecha,
                    'registros': registros_dia,
                    'regiones_hechas': regiones_hechas,
                    'regiones_faltantes': regiones_faltantes,
                    'total_a_pagar': regiones_hechas + regiones_faltantes,
                    'mostrar_complemento': es_computable,
                    'es_dia_sin_pacientes': es_dia_sin_pacientes,
                })

            medico_data.append({
                'medico': medico,
                'dias': dias,
                'total_regiones_mes': total_regiones_mes,
                'total_complemento_mes': total_complemento_mes,
                'total_a_pagar_mes': total_regiones_mes + total_complemento_mes,
            })

        context['medico_data'] = medico_data
        context['mostrar_totales_con_complemento'] = mostrar_totales_con_complemento
        context['now'] = now()

        if form.is_valid() and not medico_data:
            medico_seleccionado = form.cleaned_data.get('medico')
            if medico_seleccionado:
                context['mensaje_sin_registros'] = (
                    f"No se encontraron registros para el profesional seleccionado ({medico_seleccionado.get_full_name()}) en el mes consultado."
                )
            else:
                context['mensaje_sin_registros'] = "No se encontraron registros para ningún médico en el mes consultado."

        return context

# [ANULADO - 16 de febrero 2026]
# Vista ProcedimientosPorMedicoPorMesListView eliminada
# En Colegiales, los procedimientos se registran como Estudios
# Ver liquidacion_backup_completo_2026-02-16.json para datos históricos

def generar_pdf_liquidacion(request):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    Story = []
    styles = getSampleStyleSheet()

    # Título y fecha
    titulo = Paragraph("<b>Estudios realizados por médico</b>", styles["Title"])
    fecha_generacion = Paragraph(
        f"<b>Fecha de generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        styles["Normal"],
    )
    Story.append(titulo)
    Story.append(fecha_generacion)
    Story.append(Spacer(1, 10))

    # Médicos
    medicos = User.objects.all()
    for medico in medicos:
        # Encabezado del médico
        encabezado_medico = Paragraph(
            f"<b>Médico:</b> {medico.nombre} {medico.apellido}", styles["Heading2"]
        )
        Story.append(encabezado_medico)
        Story.append(Spacer(1, 5))

        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=medico
        ).prefetch_related("estudio").order_by("-fecha_registro")

        if registros.exists():
            data = [["Paciente", "DNI", "Estudios", "Fecha del Informe", "Regiones"]]
            total_regiones = 0

            for registro in registros:
                # Crear lista de estudios con salto de línea entre cada uno
                estudios_texto = "\n".join(
                    [f"- {estudio.nombre}" for estudio in registro.estudio.all()]
                )

                # Calcular el total de regiones
                regiones = registro.total_regiones()
                total_regiones += regiones

                data.append([
                    f"{registro.nombre_paciente} {registro.apellido_paciente}",
                    registro.dni_paciente,
                    estudios_texto,
                    registro.fecha_del_informe.strftime('%d/%m/%Y') if registro.fecha_del_informe else "N/A",
                    str(regiones),
                ])

            # Agregar total de regiones al pie de la tabla
            data.append(["", "", "", "Total", str(total_regiones)])

            # Crear tabla
            tabla = Table(data, colWidths=[None, None, None, None, None])
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#003366")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (4, 1), (4, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 6),  # Tamaño de fuente más pequeño
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Alineación superior
                ('TEXTWRAP', (0, 1), (-1, -1)),  # Ajustar texto en todas las columnas
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#e0e0e0")),  # Fondo gris para Total
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            Story.append(tabla)
        else:
            Story.append(Paragraph(
                "<i>No hay registros disponibles para este médico.</i>", styles["Normal"]))

        Story.append(Spacer(1, 15))

    # Construir PDF
    doc.build(Story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="Estudios_por_medico.pdf")

# Vistas para la creacción de un excel

User = get_user_model()

def exportar_excel_informes(request):
    # Obtener los filtros de la URL
    medico_id = request.GET.get('medico')
    mes = request.GET.get('mes')
    año = request.GET.get('año')

    # Imprimir los valores de los filtros para depuración
    print(f"Filtros - Medico ID: {medico_id}, Mes: {mes}, Año: {año}")

    # Filtrar registros basados en los parámetros, excluyendo los estudios tipo 'ECO'
    registros = RegistroEstudiosPorMedico.objects.exclude(estudio__tipo='ECO').prefetch_related(
        Prefetch('estudio', queryset=Estudios.objects.all())
    ).distinct()

    print(f"Total registros antes de filtrar: {registros.count()}")

    if medico_id:
        registros = registros.filter(medico_id=medico_id)
        print(f"Registros después de filtrar por medico_id: {registros.count()}")
    if mes and año:
        registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))
        print(f"Registros después de filtrar por mes y año: {registros.count()}")

    # Verificar si hay registros después del filtrado
    print(f"Registros encontrados: {registros.count()}")

    # Obtener el nombre del médico
    medico = None
    if medico_id:
        medico = get_object_or_404(User, id=medico_id)
        nombre_medico = f"{medico.first_name}_{medico.last_name}"
    else:
        nombre_medico = "todos_los_medicos"

    # Crear un libro de Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Informes por Médico"

    # Establecer la fila de encabezados
    headers = [
        "Paciente", "DNI", "Fecha del Informe", "Estudios", "Cantidad", "Total de Regiones"
    ]
    ws.append(headers)

    # Alinear encabezados al centro
    for cell in ws[1]:
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Agregar registros al Excel
    for registro in registros:
        estudios_nombres = ", ".join([est.nombre for est in registro.estudio.all()])
        ws.append([
            f"{registro.apellido_paciente.upper()} {registro.nombre_paciente.upper()}",
            registro.dni_paciente,
            registro.fecha_del_informe.strftime("%d/%m/%Y"),
            estudios_nombres,
            registro.cantidad_estudio or 1,
            registro.total_regiones()
        ])

    # Ajustar ancho de columnas automáticamente
    for column in ws.columns:
        max_length = max(len(str(cell.value)) for cell in column) + 2
        ws.column_dimensions[column[0].column_letter].width = max_length

    # Preparar respuesta HTTP
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="informes_medicos_{nombre_medico}.xlsx"'
    wb.save(response)
    return response

def exportar_excel_ecografias(request):
    medico_id = request.GET.get('medico')
    mes = request.GET.get('mes')
    año = request.GET.get('año')

    registros = RegistroEstudiosPorMedico.objects.filter(estudio__tipo='ECO').prefetch_related(
        Prefetch('estudio', queryset=Estudios.objects.all())
    ).distinct()

    # [DEPRECADO] DiaSinPacientes no se usa en Colegiales
    # dias_sin_pacientes = DiaSinPacientes.objects.all()

    if medico_id:
        registros = registros.filter(medico_id=medico_id)
        dias_sin_pacientes = dias_sin_pacientes.filter(medico_id=medico_id)
        medico = get_object_or_404(User, id=medico_id)
        nombre_medico = f"{medico.first_name}_{medico.last_name}"
    else:
        nombre_medico = "todos_los_medicos"
        medico = None  # no lo usamos si son todos

    if mes and año:
        registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))
        dias_sin_pacientes = dias_sin_pacientes.filter(fecha__year=int(año), fecha__month=int(mes))

    # Agrupar registros por día
    from collections import defaultdict
    registros_por_dia = defaultdict(list)
    for r in registros:
        registros_por_dia[r.fecha_del_informe].append(r)

    # Agregar días sin pacientes si no están
    for dia in dias_sin_pacientes:
        if dia.fecha not in registros_por_dia:
            registros_por_dia[dia.fecha] = []

    # Crear Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ecografías por Médico"

    ws.append(["Paciente", "DNI", "Fecha del Informe", "Estudios", "Cantidad", "Total de Regiones"])
    for cell in ws[1]:
        cell.alignment = Alignment(horizontal="center", vertical="center")

    total_regiones_mes = 0
    total_complemento_mes = 0
    fecha_minima = date(date.today().year, 3, 1)

    for fecha, registros_dia in sorted(registros_por_dia.items()):
        regiones_dia = 0
        es_computable = fecha >= fecha_minima
        es_dia_sin_pacientes = len(registros_dia) == 0 and dias_sin_pacientes.filter(fecha=fecha).exists()

        # Agregar pacientes si los hay
        for r in registros_dia:
            estudios_nombres = ", ".join([e.nombre for e in r.estudio.all()])
            total = r.total_regiones()
            ws.append([
                f"{r.apellido_paciente.upper()} {r.nombre_paciente.upper()}",
                r.dni_paciente,
                r.fecha_del_informe.strftime("%d/%m/%Y"),
                estudios_nombres,
                r.cantidad_estudio or 1,
                total
            ])
            regiones_dia += total

        # Si fue día sin pacientes
        if es_dia_sin_pacientes:
            ws.append([
                "DÍA SIN PACIENTES", "", fecha.strftime("%d/%m/%Y"),
                "Se compensan 12 regiones", "", ""
            ])

        # Resumen del día
        faltantes = 0
        if es_computable:
            faltantes = 12 if es_dia_sin_pacientes else max(0, 12 - regiones_dia)
            total_complemento_mes += faltantes
        total_a_pagar = regiones_dia + faltantes
        total_regiones_mes += regiones_dia

        ws.append([
            f"→ Total {fecha.strftime('%d/%m/%Y')}", "", "", "",
            f"Faltantes: {faltantes}" if es_computable else "Sin complemento",
            f"Total a pagar: {total_a_pagar}"
        ])

    # Línea vacía
    ws.append([])

    # Resumen mensual
    ws.append(["RESUMEN MENSUAL"])
    ws.append(["Total de regiones reales", total_regiones_mes])
    ws.append(["Total de complemento", total_complemento_mes])
    ws.append(["Total a pagar", total_regiones_mes + total_complemento_mes])

    # Estilizar
    for row in ws.iter_rows(min_row=ws.max_row - 2, max_row=ws.max_row):
        for cell in row:
            cell.font = Font(bold=True)

    for column in ws.columns:
        max_length = max(len(str(cell.value)) for cell in column) + 2
        ws.column_dimensions[column[0].column_letter].width = max_length

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="ecografias_medicos_{nombre_medico}.xlsx"'
    wb.save(response)
    return response

# [ANULADO - 16 de febrero 2026]
# Función exportar_excel_procedimientos eliminada
# En Colegiales los procedimientos se registran como estudios
# Ver ANALISIS_LIQUIDACION_COLEGIALES.md para más detalles

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