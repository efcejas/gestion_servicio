from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, TemplateView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
import io
from django.http import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo
from .forms import RegistroEstudiosPorMedicoCreateViewForm, MedicoCreateViewForm, FiltroMedicoMesForm, RegistroProcedimientosIntervensionismoCreateViewForm, FiltroProcedimientosIntervensionismoForm
from datetime import datetime
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from django.contrib.auth import get_user_model

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
        context['registros'] = RegistroEstudiosPorMedico.objects.all().order_by('-fecha_registro')
        return context

    def form_valid(self, form):
        # Asignar el usuario logueado al campo 'medico'
        form.instance.medico = self.request.user
        return super().form_valid(form)

class RegistroEstudiosPorMedicoListView(LoginRequiredMixin, TemplateView):
    template_name = 'liquidacion/registroestudios_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Obtener todos los médicos
        medicos = Medico.objects.all()

        # Calcular datos por médico
        medico_data = []
        for medico in medicos:
            registros = RegistroEstudiosPorMedico.objects.filter(
                medico=medico).prefetch_related('estudio').order_by('-fecha_registro')

            # Calcular el total de regiones para el médico
            total_regiones = registros.aggregate(
                total=Sum('estudio__conteo_regiones')
            )['total'] or 0

            # Reunir información en un diccionario por médico
            medico_data.append({
                'medico': medico,
                'registros': registros,
                'total_regiones': total_regiones,
            })

        # Agregar información al contexto
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

# Vistas para quienes consultan la liquidación sin loguearse

CustomUser = get_user_model()  # Obtener el modelo de usuario personalizado

class InformadosPorMedicoPorMesListView(TemplateView):
    template_name = 'liquidacion/informados_por_medico_por_mes.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroMedicoMesForm(self.request.GET or None)
        context['form'] = form

        medico_data = []

        if form.is_valid():
            medicos = User.objects.filter(groups__name='Médicos de staff - informes')
            mes = int(form.cleaned_data.get('mes')) if form.cleaned_data.get('mes') else None
            año = int(form.cleaned_data.get('año')) if form.cleaned_data.get('año') else None

            registros = RegistroEstudiosPorMedico.objects.all()

            if medico:
                registros = registros.filter(medico=medico)

            if mes and año:
                registros = registros.filter(fecha_registro__year=año, fecha_registro__month=mes)

            # Calcular los datos para el médico seleccionado
            total_regiones = registros.aggregate(total=Sum('estudio__conteo_regiones'))['total'] or 0

            medico_data.append({
                'medico': medico,
                'registros': registros,
                'total_regiones': total_regiones,
            })

        context['medico_data'] = medico_data
        return context

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
        form = FiltroProcedimientosIntervensionismoForm(self.request.GET or None)
        registros = RegistroProcedimientosIntervensionismo.objects.filter(medico=user).order_by('fecha_registro')

        if form.is_valid():
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')
            if mes:
                registros = registros.filter(fecha_del_procedimiento__month=mes)
            if año:
                registros = registros.filter(fecha_del_procedimiento__year=año)

        context['form'] = form
        context['registros'] = registros
        context['total_regiones'] = registros.aggregate(total=Sum('conteo_regiones'))['total'] or 0
        context['total_pacientes'] = registros.count()
        return context

User = get_user_model()

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