"""
services.py — Generación de documentos del módulo liquidacion.

Encapsula la lógica de construcción de PDF y Excel, separada del ciclo HTTP.
Las funciones retornan buffers (BytesIO) listos para ser enviados como descarga.
"""
import io
from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from django.db.models import Prefetch, Q

from .grupo_tarifario_mapping import es_eco_general_real_estudio
from .models import (
    CorreccionPacsRegistro,
    Estudios,
    GuardiaPasiva,
    ReglaDescuentoResidencia,
    RegistroEstudiosPorMedico,
)


ROLES_RESIDENCIA = {
    'medico_residente',
    'jefe_residentes',
    'instructor_residentes',
}

ROLES_DESCUENTO_INTRA_RESIDENCIA = {
    'medico_residente',
}

CAMPO_REGLA_DESCUENTO_POR_ROL = {
    'medico_residente': 'aplica_medico_residente',
    'jefe_residentes': 'aplica_jefe_residentes',
    'instructor_residentes': 'aplica_instructor_residentes',
}


def adjuntar_ultima_correccion_pacs(registros):
    """Adjunta el resultado consolidado de correcciones PACS, sin recalcular montos."""
    registros = list(registros)
    registro_ids = [registro.pk for registro in registros]
    ultima_correccion_por_registro = {}
    monto_original_por_registro = {}

    if registro_ids:
        correcciones = (
            CorreccionPacsRegistro.objects
            .filter(registro_id__in=registro_ids)
            .select_related('corregido_por')
            .order_by('registro_id', '-fecha_correccion')
        )
        for correccion in correcciones:
            if correccion.registro_id not in ultima_correccion_por_registro:
                ultima_correccion_por_registro[correccion.registro_id] = correccion
            # El recorrido descendente termina dejando el monto anterior
            # de la primera correccion aplicada sobre el registro.
            monto_original_por_registro[correccion.registro_id] = correccion.monto_anterior

    for registro in registros:
        correccion = ultima_correccion_por_registro.get(registro.pk)
        monto_original = monto_original_por_registro.get(registro.pk)
        monto_vigente = correccion.monto_nuevo if correccion else None
        registro.correccion_pacs_info = correccion
        registro.tiene_correccion_pacs = correccion is not None
        registro.monto_original_correccion_pacs = monto_original
        registro.monto_vigente_correccion_pacs = monto_vigente
        registro.impacto_correccion_pacs = (
            monto_vigente - monto_original
            if correccion
            else 0
        )

    return registros


def _resultado_descuento_residencia(aplica, fuente, regla_id=None, motivo=''):
    return {
        'aplica': bool(aplica),
        'fuente': fuente,
        'regla_id': regla_id,
        'motivo': motivo,
    }


def _regla_vigente_para_estudio(estudio, fecha_ref):
    return (
        ReglaDescuentoResidencia.objects
        .filter(
            estudio=estudio,
            activo=True,
            vigencia_desde__lte=fecha_ref,
        )
        .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha_ref))
        .order_by('-vigencia_desde', '-id')
        .first()
    )


def _regla_vigente_para_grupo(grupo_tarifario, fecha_ref):
    if not grupo_tarifario:
        return None

    return (
        ReglaDescuentoResidencia.objects
        .filter(
            grupo_tarifario=grupo_tarifario,
            activo=True,
            vigencia_desde__lte=fecha_ref,
        )
        .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha_ref))
        .order_by('-vigencia_desde', '-id')
        .first()
    )


def _resultado_desde_regla(regla, rol, fuente):
    campo_rol = CAMPO_REGLA_DESCUENTO_POR_ROL[rol]
    aplica = getattr(regla, campo_rol)
    return _resultado_descuento_residencia(
        aplica=aplica,
        fuente=fuente,
        regla_id=regla.id,
        motivo=f"Regla explicita por {fuente}.",
    )


def estudio_aplica_descuento_residencia(estudio, rol, fecha=None):
    """Resuelve elegibilidad de descuento residencia sin modificar calculos.

    Precedencia: regla por estudio > regla por grupo tarifario > fallback legado.
    """
    if rol not in ROLES_RESIDENCIA:
        return _resultado_descuento_residencia(
            aplica=False,
            fuente='rol_no_residencia',
            motivo='El rol no pertenece a residencia.',
        )
    if rol not in ROLES_DESCUENTO_INTRA_RESIDENCIA:
        return _resultado_descuento_residencia(
            aplica=False,
            fuente='rol_residencia_sin_descuento_intra',
            motivo='El rol de residencia no aplica descuento INTRA.',
        )

    fecha_ref = fecha or timezone.localdate()
    regla_estudio = _regla_vigente_para_estudio(estudio, fecha_ref)
    if regla_estudio:
        return _resultado_desde_regla(regla_estudio, rol, fuente='estudio')

    regla_grupo = _regla_vigente_para_grupo(getattr(estudio, 'grupo_tarifario', None), fecha_ref)
    if regla_grupo:
        return _resultado_desde_regla(regla_grupo, rol, fuente='grupo')

    es_doppler = (getattr(estudio, 'tipo', '') or '').upper() == 'DOP'
    aplica_fallback = es_eco_general_real_estudio(estudio) or es_doppler
    return _resultado_descuento_residencia(
        aplica=aplica_fallback,
        fuente='fallback_legado',
        motivo=(
            'Fallback residencia ECO general/Doppler.'
            if aplica_fallback
            else 'Fallback legado sin descuento.'
        ),
    )


def es_fecha_feriado_liquidacion(fecha):
    """Retorna True si la fecha esta configurada como feriado institucional."""
    if not fecha:
        return False
    if hasattr(fecha, 'date'):
        fecha = timezone.localtime(fecha).date() if timezone.is_aware(fecha) else fecha.date()

    from control_guardias.models import Feriado

    return Feriado.objects.filter(fecha=fecha).exists()


def clasificar_horario_residencia_por_proxy(
    rol,
    fecha_registro,
    tiene_eco_general,
    fecha_practica=None,
    tiene_doppler=False,
):
    """
    Clasifica horario INTRA/EXTRA para residencia usando fecha_registro como proxy.

    Retorna:
        'INTRA', 'EXTRA' o None (cuando no aplica la regla)
    """
    if rol not in ROLES_RESIDENCIA:
        return None
    practica_clasificable = tiene_eco_general or (
        rol == 'medico_residente' and tiene_doppler
    )
    if not practica_clasificable:
        return None
    if not fecha_registro:
        return None

    fecha_local = timezone.localtime(fecha_registro)
    fecha_calendario = fecha_practica or fecha_local.date()
    if hasattr(fecha_calendario, 'date'):
        fecha_calendario = fecha_calendario.date()

    # Feriados institucionales centralizados en control_guardias.
    if fecha_calendario.weekday() >= 5:
        return 'EXTRA'
    if es_fecha_feriado_liquidacion(fecha_calendario):
        return 'EXTRA'

    return 'INTRA' if 8 <= fecha_local.hour < 17 else 'EXTRA'


def generar_buffer_pdf_liquidacion():
    """
    Genera el PDF de liquidación completa (todos los médicos).

    Retorna:
        BytesIO posicionado al inicio, listo para su descarga.
    """
    from django.contrib.auth import get_user_model
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    User = get_user_model()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    Story = []
    styles = getSampleStyleSheet()

    titulo = Paragraph("<b>Liquidación de Estudios por Médico - v2.0</b>", styles["Title"])
    fecha_generacion = Paragraph(
        f"<b>Fecha de generación:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        styles["Normal"],
    )
    Story.append(titulo)
    Story.append(fecha_generacion)
    Story.append(Spacer(1, 10))

    medicos = User.objects.filter(es_medico=True)
    for medico in medicos:
        encabezado_medico = Paragraph(
            f"<b>Médico:</b> {medico.get_full_name()}", styles["Heading2"]
        )
        Story.append(encabezado_medico)
        Story.append(Spacer(1, 5))

        registros = RegistroEstudiosPorMedico.objects.filter(
            medico=medico,
            anulado=False,
        ).prefetch_related("estudio").order_by("-fecha_registro")

        if registros.exists():
            data = [["Fecha", "Paciente", "Estudios", "Regiones", "OS", "Horario", "Monto"]]
            total_regiones = 0
            total_monto = 0

            for registro in registros:
                estudios_lista = registro.estudio.all()
                estudios_texto = ", ".join(e.nombre for e in estudios_lista) if estudios_lista.exists() else "N/A"
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

            data.append(["", "", "TOTAL PRÁCTICAS", str(total_regiones), "", "", f"${total_monto:,.2f}"])

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

            if registros.exists():
                total_general = total_monto + total_guardias
                total_general_text = Paragraph(
                    f"<b>TOTAL GENERAL (Prácticas + Guardias): ${total_general:,.2f}</b>",
                    styles["Heading3"]
                )
                Story.append(total_general_text)

        Story.append(Spacer(1, 15))

    doc.build(Story)
    buffer.seek(0)
    return buffer


def generar_buffer_excel_liquidacion(medico=None, mes=None, año=None):
    """
    Genera el Excel de liquidación.

    Parámetros:
        medico : instancia de User (o None para todos los médicos)
        mes    : str o int (1-12) o None
        año    : str o int (4 dígitos) o None

    Retorna:
        (BytesIO, str): buffer posicionado al inicio y nombre del médico
                        para usar en el Content-Disposition del filename.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from .services_auditoria import (
        COLUMNAS_COMPARACION_DOPPLER_MMII,
        adjuntar_comparacion_doppler_mmii,
        agregar_hoja_auditoria_doppler_mmii,
        resumir_comparacion_doppler_mmii,
        valores_comparacion_doppler_mmii,
    )

    medico_id = medico.id if medico else None
    nombre_medico = f"{medico.first_name}_{medico.last_name}" if medico else "todos_los_medicos"

    registros = RegistroEstudiosPorMedico.objects.filter(anulado=False).select_related('medico').prefetch_related(
        Prefetch('estudio', queryset=Estudios.objects.all()),
        'registroestudio_set',
    ).distinct()

    if medico_id:
        registros = registros.filter(medico_id=medico_id)
    if mes and año:
        registros = registros.filter(fecha_del_informe__year=int(año), fecha_del_informe__month=int(mes))

    guardias = GuardiaPasiva.objects.none()
    if medico_id and mes and año:
        guardias = GuardiaPasiva.objects.filter(
            medico_id=medico_id,
            fecha_guardia__year=int(año),
            fecha_guardia__month=int(mes)
        ).order_by('fecha_guardia')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liquidación Completa"

    registros = adjuntar_comparacion_doppler_mmii(
        adjuntar_ultima_correccion_pacs(registros.order_by('-fecha_del_informe')),
    )

    headers_practicas = [
        "Fecha", "Paciente", "DNI", "Estudios",
        "Tipo", "Regiones", "Obra Social", "Horario", "Monto", "Bonus",
        "Ajuste PACS", "Tipo ajuste PACS", "Horario anterior", "Horario nuevo",
        "Monto anterior PACS", "Monto nuevo PACS", "Hora PACS", "Observacion ajuste PACS",
    ] + COLUMNAS_COMPARACION_DOPPLER_MMII
    ws.append(headers_practicas)

    for cell in ws[1]:
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

    total_regiones = 0
    total_monto_practicas = 0

    for registro in registros:
        estudios_lista = registro.estudio.all()
        estudios_nombres = ", ".join(e.nombre for e in estudios_lista) if estudios_lista.exists() else "N/A"
        tipos_estudios = ", ".join(e.get_tipo_display() for e in estudios_lista) if estudios_lista.exists() else "N/A"
        bonus_icon = "⚡ SÍ" if registro.paciente_internado else ""
        correccion = getattr(registro, 'correccion_pacs_info', None)

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
            bonus_icon,
            "SI" if correccion else "NO",
            correccion.get_tipo_correccion_display() if correccion else "",
            correccion.horario_anterior if correccion and correccion.horario_anterior else "",
            correccion.horario_nuevo if correccion and correccion.horario_nuevo else "",
            float(registro.monto_original_correccion_pacs) if correccion else "",
            float(registro.monto_vigente_correccion_pacs) if correccion else "",
            correccion.hora_pacs.strftime("%H:%M") if correccion and correccion.hora_pacs else "",
            correccion.observacion if correccion else "",
        ] + valores_comparacion_doppler_mmii(registro))

        total_regiones += registro.cantidad_regiones
        total_monto_practicas += registro.monto_calculado

    ws.append([])
    totales_practicas_row = ws.max_row + 1
    ws.append(["", "", "", "", "SUBTOTAL PRÁCTICAS", total_regiones, "", "", float(total_monto_practicas), "", "", "", "", "", "", "", "", ""])

    for cell in ws[totales_practicas_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

    ws.cell(row=totales_practicas_row, column=9).number_format = '$#,##0.00'

    total_monto_guardias = 0
    header_row = None
    totales_guardias_row = None

    if guardias.exists():
        ws.append([])
        ws.append([])

        headers_guardias = ["Fecha", "Tipo de Guardia", "Monto", "Observaciones"]
        header_row = ws.max_row + 1
        ws.append(headers_guardias)

        for col_num, cell in enumerate(ws[header_row], 1):
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")

        for guardia in guardias:
            ws.append([
                guardia.fecha_guardia.strftime("%d/%m/%Y"),
                guardia.get_tipo_guardia_display(),
                float(guardia.monto),
                guardia.observaciones or ""
            ])
            total_monto_guardias += guardia.monto

        ws.append([])
        totales_guardias_row = ws.max_row + 1
        ws.append(["", "SUBTOTAL GUARDIAS", float(total_monto_guardias), ""])

        for cell in ws[totales_guardias_row]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")

        ws.cell(row=totales_guardias_row, column=3).number_format = '$#,##0.00'

    ws.append([])
    ws.append([])
    total_general_row = ws.max_row + 1
    ws.append(["", "", "", "", "TOTAL GENERAL", "", "", "", float(total_monto_practicas + total_monto_guardias), "", "", "", "", "", "", "", "", ""])

    for cell in ws[total_general_row]:
        cell.font = Font(bold=True, size=12)
        cell.fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")

    ws.cell(row=total_general_row, column=9).number_format = '$#,##0.00'
    resumen_doppler = resumir_comparacion_doppler_mmii(registros)
    ws.append(['Diferencia estimada Doppler no aplicada (excluye residentes)', float(resumen_doppler['diferencia_estimada'])])
    ws.append(['Diferencia informativa residentes (sin debito)', float(resumen_doppler['diferencia_informativa_residentes'])])
    ws.append(['Registros con estimacion disponible', resumen_doppler['registros_estimados']])
    ws.append(['Registros pendientes de estimacion', resumen_doppler['pendientes_estimacion']])
    agregar_hoja_auditoria_doppler_mmii(wb, registros)

    for row in range(2, totales_practicas_row):
        ws.cell(row=row, column=9).number_format = '$#,##0.00'
        ws.cell(row=row, column=15).number_format = '$#,##0.00'
        ws.cell(row=row, column=16).number_format = '$#,##0.00'
        for columna in (19, 20, 21):
            ws.cell(row=row, column=columna).number_format = '$#,##0.00'

    if guardias.exists() and header_row and totales_guardias_row:
        guardias_start = header_row + 1
        guardias_end = totales_guardias_row - 1
        for row in range(guardias_start, guardias_end + 1):
            ws.cell(row=row, column=3).number_format = '$#,##0.00'

    for column_cells in ws.columns:
        length = 0
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            try:
                if cell.value:
                    cell_length = len(str(cell.value))
                    if cell_length > length:
                        length = cell_length
            except Exception:
                pass
        ws.column_dimensions[column_letter].width = length + 3

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer, nombre_medico


def generar_buffer_excel_mis_registros(*, usuario, mes, año, registros, guardias):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    from .services_auditoria import (
        adjuntar_comparacion_doppler_mmii,
        resumir_comparacion_doppler_mmii,
        valores_proyeccion_doppler_mmii,
    )

    residente = usuario.rol == 'medico_residente'
    registros = adjuntar_comparacion_doppler_mmii(registros)
    guardias = list(guardias)
    resumen = resumir_comparacion_doppler_mmii(registros)
    total_practicas = sum((registro.monto_calculado for registro in registros), Decimal('0.00'))
    total_guardias = sum((guardia.monto for guardia in guardias), Decimal('0.00'))
    tiene_credito = not residente and resumen['posible_credito'] > 0
    wb = Workbook()
    portada = wb.active
    portada.title = 'Resumen'
    practicas = wb.create_sheet('Practicas')
    headers = [
        'Fecha informe', 'Fecha carga', 'Paciente', 'DNI', 'Obra social', 'Horario',
        'Estudios', 'Modalidades', 'Regiones', 'Monto registrado', 'Sesion contable',
        'Estado sesion', 'Revision Doppler',
    ]
    if not residente:
        headers.append('Posible debito (no aplicado)')
        if tiene_credito:
            headers.append('Posible credito (no aplicado)')
        headers.append('Monto estimado si se corrige')
    practicas.append(headers)
    for registro in registros:
        relaciones = list(registro.registroestudio_set.all())
        estudios = []
        modalidades = []
        for relacion in relaciones:
            cantidad = f' x{relacion.cantidad}' if relacion.cantidad > 1 else ''
            contexto = f' ({relacion.get_contexto_display()})' if relacion.contexto else ''
            estudios.append(f'{relacion.estudio.nombre}{contexto}{cantidad}')
            modalidades.append(relacion.estudio.get_tipo_display())
        comparacion = registro.comparacion_doppler
        estado = comparacion['estado'] if comparacion else 'Sin revision Doppler'
        if comparacion and comparacion['parcial']:
            estado += ' (revision parcial)'
        sesion = registro.sesion_contable
        fila = [
            registro.fecha_del_informe.strftime('%d/%m/%Y'),
            timezone.localtime(registro.fecha_registro).strftime('%d/%m/%Y %H:%M'),
            f'{registro.apellido_paciente}, {registro.nombre_paciente}', registro.dni_paciente,
            registro.get_tipo_obra_social_display(), registro.get_horario_display(),
            '; '.join(estudios), '; '.join(dict.fromkeys(modalidades)), registro.cantidad_regiones,
            float(registro.monto_calculado), f'{sesion.mes}/{sesion.año}' if sesion else '',
            sesion.get_estado_display() if sesion else '', estado,
        ]
        if not residente:
            debito, credito, proyectado = valores_proyeccion_doppler_mmii(registro)
            fila.append(debito)
            if tiene_credito:
                fila.append(credito)
            fila.append(proyectado)
        practicas.append(fila)
    ultima_practica = practicas.max_row
    fila_total = ultima_practica + 1
    totales = [''] * len(headers)
    totales[7] = 'Totales'
    totales[8] = f'=SUM(I2:I{ultima_practica})' if registros else 0
    totales[9] = f'=SUM(J2:J{ultima_practica})' if registros else 0
    if not residente:
        totales[13] = float(resumen['posible_debito'])
        if tiene_credito:
            totales[14] = float(resumen['posible_credito'])
        totales[-1] = float(resumen['monto_proyectado_practicas'])
    practicas.append(totales)

    hoja_guardias = wb.create_sheet('Guardias')
    hoja_guardias.append(['Fecha', 'Tipo', 'Monto registrado', 'Observaciones'])
    for guardia in guardias:
        hoja_guardias.append([
            guardia.fecha_guardia.strftime('%d/%m/%Y'), guardia.get_tipo_guardia_display(),
            float(guardia.monto), guardia.observaciones,
        ])
    hoja_guardias.append(['', 'Total guardias', float(total_guardias), ''])

    revision = wb.create_sheet('Revision Doppler')
    revision_headers = [
        'Fecha', 'Registro', 'Paciente', 'Estudio', 'Cantidad registrada',
        'Cantidad segun regla', 'Estado', 'Observacion', 'Revisado por', 'Fecha revision',
    ]
    if not residente:
        revision_headers += ['Monto actual del registro', 'Posible debito', 'Monto estimado del registro']
    revision_headers.append('Fuentes verificadas')
    revision.append(revision_headers)
    for registro in registros:
        for indice, caso in enumerate(registro.auditorias_doppler_mmii):
            snapshot = caso.datos_originales_json
            fila = [
                registro.fecha_del_informe.strftime('%d/%m/%Y'), registro.pk,
                f'{registro.apellido_paciente}, {registro.nombre_paciente}', snapshot.get('estudio'),
                snapshot.get('cantidad_declarada'), snapshot.get('cantidad_esperada', 'Pendiente'),
                caso.get_estado_display(), caso.observacion,
                (caso.revisado_por.get_full_name() or caso.revisado_por.username) if caso.revisado_por else '',
                timezone.localtime(caso.fecha_revision).strftime('%d/%m/%Y %H:%M') if caso.fecha_revision else '',
            ]
            if not residente:
                debito, credito, proyectado = valores_proyeccion_doppler_mmii(registro)
                fila += [float(registro.monto_calculado), debito, proyectado] if indice == 0 else ['', '', '']
            fila.append('; '.join(
                nombre for campo, nombre in (
                    ('orden_medica_verificada', 'Orden medica'),
                    ('visualmedical_verificado', 'VisualMedical'),
                    ('eges_verificado', 'EGES'), ('netterm_verificado', 'NetTerm'),
                ) if getattr(caso, campo)
            ))
            revision.append(fila)

    nombre = usuario.get_full_name() or usuario.username
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    portada.append(['Liquidacion del periodo'])
    portada.append([nombre])
    portada.append([f'{meses[mes - 1]} {año} | {"Residente" if residente else usuario.get_rol_display()}'])
    portada.append([])
    portada.append(['Practicas · todas las modalidades', float(total_practicas), f'{len(registros)} registros'])
    portada.append(['Guardias', float(total_guardias), f'{len(guardias)} guardias'])
    portada.append(['TOTAL ACTUAL', float(total_practicas + total_guardias), 'Importe registrado'])
    portada.append([])
    if residente:
        portada.append(['Revision Doppler', 'Informativa: no modifica tu liquidacion.'])
        portada.append(['Registros con revision', resumen['registros_auditados']])
        portada.append(['El detalle de cantidades y observaciones esta en la hoja Revision Doppler.'])
    else:
        portada.append(['POSIBLE DEBITO', float(resumen['posible_debito']), 'Aun no aplicado'])
        if tiene_credito:
            portada.append(['Posible credito', float(resumen['posible_credito']), 'Aun no aplicado'])
        portada.append(['TOTAL ESTIMADO SI SE CORRIGE', float(resumen['monto_proyectado_practicas'] + total_guardias)])
        if resumen['pendientes_economicos']:
            portada.append([f'Estimacion parcial: {resumen["pendientes_economicos"]} registros con revision pendiente.'])
        elif not resumen['registros_auditados']:
            portada.append(['Sin revisiones Doppler registradas; no se proponen ajustes.'])
        else:
            portada.append(['Estimacion de las cantidades confirmadas. No se aplicaron ajustes.'])
        portada.append(['Revisa la hoja Revision Doppler para conocer los casos y sus fundamentos.'])
    portada.append([])
    portada.append(['Incluye todos tus registros vigentes y guardias del mes, de todas las modalidades.'])
    portada.append(['Los importes registrados no acreditan facturacion ni pago.'])

    for hoja in (practicas, hoja_guardias, revision):
        hoja.freeze_panes = 'A2'
        ultima_fila_datos = hoja.max_row - 1 if hoja != revision else hoja.max_row
        hoja.auto_filter.ref = f'A1:{get_column_letter(hoja.max_column)}{max(1, ultima_fila_datos)}'
        for celda in hoja[1]:
            celda.font = Font(bold=True, color='FFFFFF')
            celda.fill = PatternFill('solid', fgColor='334155')
            celda.alignment = Alignment(vertical='center', wrap_text=True)
        hoja.row_dimensions[1].height = 32
        for fila in hoja.iter_rows(min_row=2):
            for celda in fila:
                celda.alignment = Alignment(vertical='top', wrap_text=True)
                if isinstance(celda.value, str) and celda.data_type == 'f' and not (
                    hoja == practicas and celda.row == fila_total and celda.column in (9, 10)
                ):
                    celda.data_type = 's'
        for columna in hoja.columns:
            hoja.column_dimensions[get_column_letter(columna[0].column)].width = min(
                max(len(str(celda.value or '')) for celda in columna) + 2, 44,
            )
        hoja.sheet_view.showGridLines = False
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        hoja.page_setup.orientation = 'landscape'
        hoja.page_setup.paperSize = hoja.PAPERSIZE_A4
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        hoja.print_title_rows = '1:1'
    for fila in practicas.iter_rows(min_row=2):
        for celda in fila:
            if celda.column == 10 or (not residente and celda.column >= 14):
                celda.number_format = '$#,##0.00'
    for fila in hoja_guardias.iter_rows(min_row=2):
        fila[2].number_format = '$#,##0.00'
    if not residente:
        for fila in revision.iter_rows(min_row=2, min_col=11, max_col=13):
            for celda in fila:
                celda.number_format = '$#,##0.00'
    for columna in ('B', 'K', 'L'):
        practicas.column_dimensions[columna].hidden = True
    for hoja, numero in ((practicas, fila_total), (hoja_guardias, hoja_guardias.max_row)):
        for celda in hoja[numero]:
            celda.font = Font(bold=True)
            celda.fill = PatternFill('solid', fgColor='E2E8F0')

    portada.column_dimensions['A'].width = 42
    portada.column_dimensions['B'].width = 28
    portada.column_dimensions['C'].width = 28
    portada.sheet_view.showGridLines = False
    portada.print_options.horizontalCentered = True
    portada.print_area = f'A1:C{portada.max_row}'
    portada.page_setup.paperSize = portada.PAPERSIZE_A4
    portada.page_setup.fitToWidth = 1
    portada.page_setup.fitToHeight = 1
    portada.sheet_properties.pageSetUpPr.fitToPage = True
    for numero in range(1, portada.max_row + 1):
        portada.row_dimensions[numero].height = 25
        for celda in portada[numero]:
            celda.font = Font(name='Calibri', size=11)
            celda.alignment = Alignment(vertical='center', wrap_text=True)
        if numero <= 3 or (numero >= 11 and portada.cell(numero, 2).value is None):
            portada.merge_cells(start_row=numero, start_column=1, end_row=numero, end_column=3)
        if isinstance(portada.cell(numero, 2).value, (int, float)) and not (residente and numero == 10):
            portada.cell(numero, 2).number_format = '$#,##0.00'
        if numero == 1:
            portada.cell(numero, 1).font = Font(name='Calibri', size=16, bold=True)
            portada.row_dimensions[numero].height = 32
        if portada.cell(numero, 1).value in {'TOTAL ACTUAL', 'POSIBLE DEBITO', 'TOTAL ESTIMADO SI SE CORRIGE'}:
            portada.row_dimensions[numero].height = 36
            color = 'E2E8F0' if numero == 7 else 'FEF3C7'
            for celda in portada[numero]:
                celda.font = Font(name='Calibri', size=12, bold=True)
                celda.fill = PatternFill('solid', fgColor=color)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
