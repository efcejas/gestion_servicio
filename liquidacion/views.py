from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, TemplateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q, Prefetch
from django.http import FileResponse, HttpResponse
from django.contrib.auth import get_user_model
import io, json
from datetime import datetime, date
from collections import defaultdict
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo
from .forms import (
    RegistroEstudiosPorMedicoCreateViewForm, 
    MedicoCreateViewForm, 
    FiltroMedicoMesForm, 
    RegistroProcedimientosIntervensionismoCreateViewForm, 
    FiltroProcedimientosIntervensionismoForm, 
    FiltroEstudiosPorMedicoForm
)
import openpyxl
from openpyxl.styles import Alignment, Font
from django.utils.timezone import now
from openpyxl import Workbook

class MedicoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Medico
    form_class = MedicoCreateViewForm
    template_name = 'liquidacion/medico_form.html'
    # Usa reverse_lazy para resolver el nombre de la URL
    success_url = reverse_lazy('medico_list')
    # success_message = "El médico fue registrado exitosamente"  # Mensaje de éxito

class MedicoListView(LoginRequiredMixin, ListView):
    model = Medico
    template_name = 'liquidacion/medico_list.html'
    # Asegúrate de usar el nombre correcto en la plantilla
    context_object_name = 'medicos'

class EstudiosCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Estudios
    fields = ['nombre', 'tipo', 'conteo_regiones']
    template_name = 'liquidacion/estudios_form.html'
    # Usa reverse_lazy para resolver el nombre de la URL
    success_url = reverse_lazy('estudios_list')
    success_message = "El estudio fue registrado exitosamente"  # Mensaje de éxito

class EstudiosListView(LoginRequiredMixin, ListView):
    model = Estudios
    template_name = 'liquidacion/estudios_list.html'
    # Asegúrate de usar el nombre correcto en la plantilla
    context_object_name = 'estudios'

class RegistroEstudiosPorMedicoCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = RegistroEstudiosPorMedico
    form_class = RegistroEstudiosPorMedicoCreateViewForm
    template_name = 'liquidacion/registroestudios_form.html'
    success_url = reverse_lazy('registroestudios_nuevo')
    success_message = "Registro realizado exitosamente"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = datetime.today()
        
        # Obtener el tipo de estudio desde el POST si el usuario lo ha cambiado recientemente
        tipo_estudio_seleccionado = self.request.POST.get('tipo_estudio', '')

        # Si no hay selección en el POST, recuperar el último tipo de estudio usado por el usuario
        if not tipo_estudio_seleccionado:
            ultimo_registro = RegistroEstudiosPorMedico.objects.filter(medico=user).order_by('-fecha_registro').first()
            if ultimo_registro and ultimo_registro.estudio.exists():
                tipo_estudio_seleccionado = ultimo_registro.estudio.first().tipo

        context['tipo_estudio_seleccionado'] = tipo_estudio_seleccionado
        context['estudios'] = json.dumps(list(Estudios.objects.values('id', 'nombre', 'tipo')))
        context['registros'] = RegistroEstudiosPorMedico.objects.filter(
            medico=user,
            fecha_registro__year=today.year,
            fecha_registro__month=today.month
        ).order_by('-fecha_registro')

        return context

    def form_valid(self, form):
        # Asignar el usuario logueado al campo 'medico'
        form.instance.medico = self.request.user
        return super().form_valid(form)

User = get_user_model()

class RegistroEstudiosPorMedicoListView(LoginRequiredMixin, TemplateView):
    template_name = 'liquidacion/registroestudios_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Fecha actual
        fecha_actual = datetime.now()
        mes_actual = fecha_actual.month
        año_actual = fecha_actual.year

        # Inicializar el formulario
        form = FiltroEstudiosPorMedicoForm(self.request.GET or None)

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

        # Pasar los valores al contexto
        context['form'] = form
        context['mes'] = MESES.get(mes, 'Desconocido')  # Mostrar el nombre del mes
        context['año'] = año

        # Filtrar registros del usuario logueado usando `fecha_del_informe`
        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=self.request.user,
            fecha_del_informe__year=año,
            fecha_del_informe__month=mes
        )

        # Separar registros por tipo de estudio
        registros_eco = registros.filter(estudio__tipo='ECO').distinct()
        registros_otros = registros.exclude(estudio__tipo='ECO').distinct()

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

        return context

class RegistroEstudiosPorMedicoUpdateView(LoginRequiredMixin, UpdateView):
    model = RegistroEstudiosPorMedico
    form_class = RegistroEstudiosPorMedicoCreateViewForm
    template_name = 'liquidacion/registroestudios_update.html'
    success_url = reverse_lazy('registroestudios_list')

    def get_queryset(self):
        # Limita los registros al usuario logueado
        return RegistroEstudiosPorMedico.objects.filter(medico=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Cargar todos los estudios y convertirlos a JSON
        context['estudios'] = json.dumps(list(Estudios.objects.values('id', 'nombre', 'tipo')))

        # Obtener el tipo de estudio y los estudios seleccionados en el registro
        registro = self.object
        if registro and registro.estudio.exists():
            context['tipo_estudio_seleccionado'] = registro.estudio.first().tipo
            context['estudios_seleccionados'] = list(registro.estudio.values_list('id', flat=True))
        else:
            context['tipo_estudio_seleccionado'] = ''
            context['estudios_seleccionados'] = []

        return context

class RegistroEstudiosPorMedicoDeleteView(LoginRequiredMixin, DeleteView):
    model = RegistroEstudiosPorMedico
    template_name = 'liquidacion/registroestudios_confirm_delete.html'
    success_url = reverse_lazy('registroestudios_list')

    def get_queryset(self):
        # Limita los registros a los del usuario logueado
        return RegistroEstudiosPorMedico.objects.filter(medico=self.request.user)

class ProcedimientosIntervensionismoListCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = RegistroProcedimientosIntervensionismo
    form_class = RegistroProcedimientosIntervensionismoCreateViewForm
    template_name = 'liquidacion/procedimientos_intervensionismo_form.html'
    success_url = reverse_lazy('procedimientos_intervensionismo')
    success_message = "Registro realizado exitosamente"

    def form_valid(self, form):
        form.instance.medico = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['registros'] = RegistroProcedimientosIntervensionismo.objects.filter(medico=user).order_by('-fecha_registro')
        return context

class ProcedimientosIntervensionismoListView(LoginRequiredMixin, ListView):
    model = RegistroProcedimientosIntervensionismo
    template_name = 'liquidacion/procedimientos_intervensionismo_list.html'
    context_object_name = 'registros'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Obtener el mes y año actual
        fecha_actual = datetime.now()
        mes_actual = fecha_actual.month
        año_actual = fecha_actual.year

        # Inicializar el formulario con los valores actuales
        form = FiltroProcedimientosIntervensionismoForm(self.request.GET or None, initial={'mes': mes_actual, 'año': año_actual})

        # Inicializar los valores de mes y año con los valores actuales
        mes = mes_actual
        año = año_actual

        # Si el formulario es válido, actualizar los valores de mes y año
        if form.is_valid():
            mes = form.cleaned_data.get('mes') or mes_actual
            año = form.cleaned_data.get('año') or año_actual

        # Filtrar registros del usuario logueado para el mes y año seleccionados
        registros = RegistroProcedimientosIntervensionismo.objects.filter(
            medico=user,
            fecha_del_procedimiento__month=mes,
            fecha_del_procedimiento__year=año
        ).order_by('-fecha_registro')

        context['form'] = form
        context['registros'] = registros
        context['total_regiones'] = registros.aggregate(total=Sum('conteo_regiones'))['total'] or 0
        context['total_pacientes'] = registros.count()
        context['mes'] = mes
        context['año'] = año
        return context

class ProcedimientosIntervensionismoUpdateView(LoginRequiredMixin, UpdateView):
    model = RegistroProcedimientosIntervensionismo
    form_class = RegistroProcedimientosIntervensionismoCreateViewForm
    template_name = 'liquidacion/procedimientos_intervensionismo_update.html'
    success_url = reverse_lazy('mis_procedimientos')

    def get_queryset(self):
        return RegistroProcedimientosIntervensionismo.objects.filter(medico=self.request.user)

class ProcedimientosIntervensionismoDeleteView(LoginRequiredMixin, DeleteView):
    model = RegistroProcedimientosIntervensionismo
    template_name = 'liquidacion/procedimientos_intervensionismo_confirm_delete.html'
    success_url = reverse_lazy('mis_procedimientos')

    def get_queryset(self):
        return RegistroProcedimientosIntervensionismo.objects.filter(medico=self.request.user)

# Vistas para quienes consultan la liquidación sin loguearse

class InformadosPorMedicoPorMesListView(TemplateView):
    template_name = 'liquidacion/informados_por_medico_por_mes.html'

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
    template_name = 'liquidacion/ecografias_por_medico_por_mes.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroMedicoMesForm(self.request.GET or None)
        context['form'] = form

        registros_por_medico = defaultdict(list)
        mostrar_totales_con_complemento = False  # 🚨 Inicializamos en False
        fecha_minima = date(date.today().year, 3, 1)

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            # 🚨 Si el mes consultado es marzo o posterior, habilitamos mostrar complementos
            if mes and año and (int(año), int(mes)) >= (fecha_minima.year, fecha_minima.month):
                mostrar_totales_con_complemento = True

            # Filtrar registros de tipo ECO
            registros = RegistroEstudiosPorMedico.objects.filter(estudio__tipo='ECO').distinct()

            if medico:
                registros = registros.filter(medico=medico)

            if mes and año:
                registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))

            # Agrupar registros por médico
            for registro in registros.order_by('-fecha_del_informe'):
                registros_por_medico[registro.medico].append(registro)

        # Preparar el contexto con datos por médico
        fecha_minima = date(date.today().year, 3, 1)

        medico_data = []

        for medico, registros in registros_por_medico.items():
            registros_por_dia = defaultdict(list)
            for registro in registros:
                registros_por_dia[registro.fecha_del_informe].append(registro)

            dias = []
            total_regiones_mes = 0
            total_complemento_mes = 0

            for fecha, registros_dia in registros_por_dia.items():
                regiones_hechas = sum(r.total_regiones() for r in registros_dia)
                es_computable = fecha >= fecha_minima
                regiones_faltantes = max(0, 12 - regiones_hechas) if es_computable else 0
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
                })

            medico_data.append({
                'medico': medico,
                'dias': dias,
                'total_regiones_mes': total_regiones_mes,
                'total_complemento_mes': total_complemento_mes,
                'total_a_pagar_mes': total_regiones_mes + total_complemento_mes,
            })

        context['medico_data'] = medico_data
        context['mostrar_totales_con_complemento'] = mostrar_totales_con_complemento  # 🚨 Lo pasamos al template
        context['now'] = now()  # 🚨 Pasamos la fecha actual al template

        return context

class ProcedimientosPorMedicoPorMesListView(TemplateView):
    template_name = 'liquidacion/procedimientos_por_medico_por_mes.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroProcedimientosIntervensionismoForm(self.request.GET or None)
        context['form'] = form

        medico_data = []

        if form.is_valid():
            medicos = User.objects.filter(groups__name='Médicos de staff')
            medico = form.cleaned_data.get('medico')
            mes = int(form.cleaned_data.get('mes')) if form.cleaned_data.get('mes') else None
            año = int(form.cleaned_data.get('año')) if form.cleaned_data.get('año') else None

            if medico:
                medicos = medicos.filter(id=medico.id)

            for medico in medicos:
                registros = RegistroProcedimientosIntervensionismo.objects.filter(medico=medico)

                if mes and año:
                    registros = registros.filter(fecha_del_procedimiento__year=año, fecha_del_procedimiento__month=mes)

                registros = registros.order_by('-fecha_del_procedimiento')

                total_regiones = registros.aggregate(total=Sum('conteo_regiones'))['total'] or 0

                medico_data.append({
                    'medico': medico,
                    'registros': registros,
                    'total_regiones': total_regiones,
                    'total_pacientes': registros.count(),
                })

        context['medico_data'] = medico_data
        return context

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
    medicos = Medico.objects.all()
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
    # Obtener los filtros de la URL
    medico_id = request.GET.get('medico')
    mes = request.GET.get('mes')
    año = request.GET.get('año')

    # Imprimir los valores de los filtros para depuración
    print(f"Filtros - Medico ID: {medico_id}, Mes: {mes}, Año: {año}")

    # Filtrar registros basados en los parámetros, solo estudios tipo 'ECO'
    registros = RegistroEstudiosPorMedico.objects.filter(estudio__tipo='ECO').prefetch_related(
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
    ws.title = "Ecografías por Médico"

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
    response["Content-Disposition"] = f'attachment; filename="ecografias_medicos_{nombre_medico}.xlsx"'
    wb.save(response)
    return response

def exportar_excel_procedimientos(request):
    # Obtener los filtros de la URL
    medico_id = request.GET.get('medico')
    mes = request.GET.get('mes')
    año = request.GET.get('año')

    # Imprimir los valores de los filtros para depuración
    print(f"Filtros - Medico ID: {medico_id}, Mes: {mes}, Año: {año}")

    # Filtrar registros basados en los parámetros
    registros = RegistroProcedimientosIntervensionismo.objects.all()

    if medico_id:
        registros = registros.filter(medico_id=medico_id)
        print(f"Registros después de filtrar por medico_id: {registros.count()}")

    if mes and año:
        registros = registros.filter(fecha_del_procedimiento__month=mes, fecha_del_procedimiento__year=año)
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
    wb = Workbook()
    ws = wb.active
    ws.title = "Procedimientos"

    # Establecer la fila de encabezados
    headers = ["Paciente", "DNI", "Fecha del Procedimiento", "Procedimiento", "Cantidad de Regiones", "Notas"]
    ws.append(headers)

    # Alinear encabezados al centro
    for cell in ws[1]:
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Agregar registros al Excel
    for registro in registros:
        nombre_completo = f"{registro.apellido_paciente.upper()} {registro.nombre_paciente.upper()}"
        ws.append([
            nombre_completo,
            registro.dni_paciente,
            registro.fecha_del_procedimiento.strftime("%d/%m/%Y"),
            registro.procedimiento.upper(),
            registro.conteo_regiones,
            registro.notas
        ])

    # Ajustar ancho de columnas automáticamente
    for column in ws.columns:
        max_length = max(len(str(cell.value)) for cell in column) + 2
        ws.column_dimensions[column[0].column_letter].width = max_length

    # Preparar respuesta HTTP
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="procedimientos_{nombre_medico}.xlsx"'
    wb.save(response)
    return response