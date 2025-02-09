from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, TemplateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Q
import io, json
from django.http import FileResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from .models import Medico, Estudios, RegistroEstudiosPorMedico, RegistroProcedimientosIntervensionismo
from .forms import RegistroEstudiosPorMedicoCreateViewForm, MedicoCreateViewForm, FiltroMedicoMesForm, RegistroProcedimientosIntervensionismoCreateViewForm, FiltroProcedimientosIntervensionismoForm, FiltroEstudiosPorMedicoForm
from datetime import datetime, date
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import inch
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from collections import defaultdict

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
        tipo_estudio_seleccionado = self.request.POST.get('tipo_estudio', '')  # Obtener el tipo de estudio seleccionado
        context['tipo_estudio_seleccionado'] = tipo_estudio_seleccionado
        context['estudios'] = json.dumps(list(Estudios.objects.values('id', 'nombre', 'tipo')))
        today = datetime.today()
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

        # Calcular totales de regiones
        total_regiones_eco = registros_eco.aggregate(total=Sum('estudio__conteo_regiones'))['total'] or 0
        total_regiones_otros = registros_otros.aggregate(total=Sum('estudio__conteo_regiones'))['total'] or 0

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

# Vistas para quienes consultan la liquidación sin loguearse

class InformadosPorMedicoPorMesListView(TemplateView):
    template_name = 'liquidacion/informados_por_medico_por_mes.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = FiltroMedicoMesForm(self.request.GET or None)
        context['form'] = form

        medico_data = []

        # Solo realizar la consulta si el formulario es válido
        if form.is_valid():
            medico = form.cleaned_data.get('medico')  # Ahora es una instancia de CustomUser
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

            # Filtrar registros excluyendo los estudios de tipo 'ECO'
            registros = RegistroEstudiosPorMedico.objects.exclude(estudio__tipo='ECO').distinct()

            if medico:
                registros = registros.filter(medico=medico)

            if mes and año:
                registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))

            # Ordenar los registros por la fecha del informe (de más reciente a más antiguo)
            registros = registros.order_by('-fecha_del_informe')

            # Calcular el total de regiones
            total_regiones = registros.aggregate(total=Sum('estudio__conteo_regiones'))['total'] or 0

            # Agregar datos al contexto
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

        if form.is_valid():
            medico = form.cleaned_data.get('medico')
            mes = form.cleaned_data.get('mes')
            año = form.cleaned_data.get('año')

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