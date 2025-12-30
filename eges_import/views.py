from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import datetime, time
import openpyxl

from .models import ImportBatch, EgesRow
from .forms import ImportarEGESForm


def es_superuser(user):
    """Verifica que el usuario sea superusuario."""
    return user.is_superuser


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def lista_batches(request):
    """
    Vista principal: lista de todos los lotes importados.
    Solo accesible por superusuarios.
    """
    batches = ImportBatch.objects.all().select_related('usuario')
    
    # Calcular estadísticas generales
    from django.db.models import Sum
    stats = batches.aggregate(
        total_filas=Sum('total_filas'),
        total_finalizados=Sum('total_estudios_finalizados')
    )
    
    context = {
        'batches': batches,
        'total_batches': batches.count(),
        'total_filas': stats['total_filas'] or 0,
        'total_finalizados': stats['total_finalizados'] or 0,
        'ultimo_batch': batches.first(),
        'titulo_pagina': 'Importación EGES',
    }
    return render(request, 'eges_import/lista_batches.html', context)


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def dashboard_global(request):
    """
    Dashboard global que consolida TODOS los batches importados.
    Vista ejecutiva para el director.
    """
    # Obtener todos los batches
    batches = ImportBatch.objects.all()
    
    # Métricas globales consolidadas
    total_batches = batches.count()
    total_filas_global = sum(b.total_filas for b in batches)
    total_estudios_finalizados_global = sum(b.total_estudios_finalizados for b in batches)
    
    # Totales por modalidad (consolidado)
    total_tc_global = sum(b.total_tc for b in batches)
    total_rm_global = sum(b.total_rm for b in batches)
    total_rx_global = sum(b.total_rx for b in batches)
    total_eco_global = sum(b.total_eco for b in batches)
    total_otros_global = sum(b.total_otros for b in batches)
    
    # Obtener rango de fechas de todos los datos
    todas_filas = EgesRow.objects.filter(fecha_turno__isnull=False)
    fecha_min = todas_filas.order_by('fecha_turno').first()
    fecha_max = todas_filas.order_by('-fecha_turno').first()
    
    context = {
        'titulo_pagina': 'Dashboard Global EGES',
        'total_batches': total_batches,
        'total_filas_global': total_filas_global,
        'total_estudios_finalizados_global': total_estudios_finalizados_global,
        'total_tc_global': total_tc_global,
        'total_rm_global': total_rm_global,
        'total_rx_global': total_rx_global,
        'total_eco_global': total_eco_global,
        'total_otros_global': total_otros_global,
        'fecha_min': fecha_min.fecha_turno if fecha_min else None,
        'fecha_max': fecha_max.fecha_turno if fecha_max else None,
        'batches': batches,
    }
    return render(request, 'eges_import/dashboard_global.html', context)


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def importar_eges(request):
    """
    Vista para subir un archivo Excel EGES.
    Procesa el archivo, crea un batch y las filas correspondientes.
    """
    if request.method == 'POST':
        form = ImportarEGESForm(request.POST, request.FILES)
        
        if form.is_valid():
            archivo = request.FILES['archivo']
            
            print(f"[EGES] Iniciando importación: {archivo.name} ({archivo.size} bytes)")
            
            # Crear el batch
            batch = ImportBatch.objects.create(
                usuario=request.user,
                archivo_nombre=archivo.name
            )
            
            print(f"[EGES] Batch #{batch.id} creado")
            
            try:
                # Procesar el Excel
                print(f"[EGES] Procesando Excel...")
                resultado = procesar_excel_eges(archivo, batch)
                
                print(f"[EGES] Resultado: {resultado['creadas']} nuevas, {resultado['duplicadas']} duplicadas, {resultado['errores']} errores")
                
                # Calcular métricas
                batch.calcular_metricas()
                
                print(f"[EGES] Batch #{batch.id} completado exitosamente")
                
                # Mensaje personalizado según si hubo duplicados
                if resultado['duplicadas'] > 0:
                    messages.warning(
                        request,
                        f'⚠️ Archivo importado. Se procesaron {resultado["creadas"]} filas nuevas. '
                        f'Se detectaron {resultado["duplicadas"]} filas duplicadas (ya existían en la base de datos). '
                        f'{resultado["errores"]} filas con errores fueron omitidas.'
                    )
                else:
                    messages.success(
                        request,
                        f'✓ Archivo importado correctamente. Se procesaron {resultado["creadas"]} filas nuevas. '
                        f'{resultado["errores"]} filas con errores fueron omitidas.'
                    )
                
                return redirect('eges_import:detalle_batch', batch_id=batch.id)
                
            except Exception as e:
                # Si algo falla, eliminar el batch
                print(f"[EGES] ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
                batch.delete()
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
                return redirect('eges_import:importar')
    else:
        form = ImportarEGESForm()
    
    context = {
        'form': form,
        'titulo_pagina': 'Importar archivo EGES',
    }
    return render(request, 'eges_import/importar.html', context)


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def detalle_batch(request, batch_id):
    """
    Vista de resumen de un batch importado.
    Muestra todas las métricas calculadas.
    """
    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # Obtener algunas filas de ejemplo
    filas_ejemplo = batch.filas.all()[:20]
    
    context = {
        'batch': batch,
        'filas_ejemplo': filas_ejemplo,
        'titulo_pagina': f'Resumen Batch #{batch.id}',
    }
    return render(request, 'eges_import/detalle_batch.html', context)


def procesar_excel_eges(archivo, batch):
    """
    Procesa un archivo Excel EGES y crea las filas en la base de datos.
    Detecta automáticamente duplicados usando get_or_create.
    
    Returns:
        dict: {'creadas': int, 'duplicadas': int, 'errores': int}
    """
    print(f"[EGES] Abriendo workbook...")
    wb = openpyxl.load_workbook(archivo, read_only=True, data_only=True)
    ws = wb.active
    
    print(f"[EGES] Leyendo encabezados...")
    # Leer encabezados (primera fila)
    headers = []
    for cell in ws[1]:
        headers.append(str(cell.value).strip() if cell.value else '')
    
    print(f"[EGES] Encabezados encontrados: {len(headers)} columnas")
    print(f"[EGES] Columnas: {headers[:5]}...")  # Primeras 5
    
    # Mapeo de columnas (ajustar según el Excel real)
    # Buscar índices de las columnas que necesitamos
    def get_col_index(nombre_col, alternativas=[]):
        """Busca una columna por nombre o alternativas."""
        for idx, header in enumerate(headers):
            if nombre_col.lower() in header.lower():
                return idx
            for alt in alternativas:
                if alt.lower() in header.lower():
                    return idx
        return None
    
    idx_nro_turno = get_col_index('Nro. Turno', ['Turno', 'Número'])
    idx_fecha = get_col_index('Fecha Turno', ['Fecha'])
    idx_hora = get_col_index('Hora Turno', ['Hora'])
    idx_centro = get_col_index('Centro de Atención', ['Centro', 'Sucursal'])
    idx_hc = get_col_index('Historia Clínica', ['HC', 'H.C.'])
    idx_nombre = get_col_index('Apellido y Nombre', ['Nombre', 'Paciente'])
    idx_servicio = get_col_index('Servicio', ['Prestación', 'Estudio'])
    idx_equipo = get_col_index('Equipo', ['Modalidad'])
    idx_estado = get_col_index('Estado Turno', ['Estado'])
    
    print(f"[EGES] Índices mapeados. Iniciando procesamiento de filas...")
    
    filas_creadas = 0
    filas_duplicadas = 0
    filas_error = 0
    filas_procesadas = 0
    
    # Procesar filas (saltear encabezado)
    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        filas_procesadas += 1
        
        # Log cada 100 filas
        if filas_procesadas % 100 == 0:
            print(f"[EGES] Procesadas {filas_procesadas} filas: {filas_creadas} nuevas, {filas_duplicadas} duplicadas, {filas_error} errores...")
        
        # Saltar filas vacías
        if not any(row):
            continue
        
        try:
            # Extraer valores
            numero_turno = str(row[idx_nro_turno]) if idx_nro_turno is not None and row[idx_nro_turno] else ''
            
            # Fecha
            fecha_turno = None
            if idx_fecha is not None and row[idx_fecha]:
                fecha_val = row[idx_fecha]
                if isinstance(fecha_val, datetime):
                    fecha_turno = fecha_val.date()
                elif isinstance(fecha_val, str):
                    try:
                        fecha_turno = datetime.strptime(fecha_val, '%d/%m/%Y').date()
                    except:
                        try:
                            fecha_turno = datetime.strptime(fecha_val, '%Y-%m-%d').date()
                        except:
                            pass
            
            # Hora
            hora_turno = None
            if idx_hora is not None and row[idx_hora]:
                hora_val = row[idx_hora]
                if isinstance(hora_val, datetime):
                    hora_turno = hora_val.time()
                elif isinstance(hora_val, time):
                    hora_turno = hora_val
                elif isinstance(hora_val, str):
                    try:
                        hora_turno = datetime.strptime(hora_val, '%H:%M:%S').time()
                    except:
                        try:
                            hora_turno = datetime.strptime(hora_val, '%H:%M').time()
                        except:
                            pass
            
            centro = str(row[idx_centro]) if idx_centro is not None and row[idx_centro] else ''
            hc = str(row[idx_hc]) if idx_hc is not None and row[idx_hc] else ''
            nombre = str(row[idx_nombre]) if idx_nombre is not None and row[idx_nombre] else ''
            servicio = str(row[idx_servicio]) if idx_servicio is not None and row[idx_servicio] else ''
            equipo = str(row[idx_equipo]) if idx_equipo is not None and row[idx_equipo] else ''
            estado = str(row[idx_estado]) if idx_estado is not None and row[idx_estado] else ''
            
            # Usar get_or_create para detectar duplicados
            # El constraint unique_together está en (HC, fecha, hora, centro, servicio)
            fila, created = EgesRow.objects.get_or_create(
                # Campos del unique_together
                historia_clinica=hc,
                fecha_turno=fecha_turno,
                hora_turno=hora_turno,
                centro_atencion=centro,
                servicio=servicio,
                # Defaults para el resto de campos si se crea
                defaults={
                    'batch': batch,
                    'numero_turno': numero_turno,
                    'apellido_nombre': nombre,
                    'equipo': equipo,
                    'estado_turno': estado,
                }
            )
            
            if created:
                filas_creadas += 1
            else:
                filas_duplicadas += 1
                # Opcional: asociar también al batch actual si se quiere tracking
                # fila.batch = batch  
                # fila.save()
            
        except Exception as e:
            # Registrar error pero continuar con las demás filas
            filas_error += 1
            print(f"[EGES] Error en fila {row_idx}: {str(e)}")
            continue
    
    wb.close()
    print(f"[EGES] Workbook cerrado. Total: {filas_creadas} nuevas, {filas_duplicadas} duplicadas, {filas_error} errores de {filas_procesadas} procesadas")
    
    return {
        'creadas': filas_creadas,
        'duplicadas': filas_duplicadas,
        'errores': filas_error
    }


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def grafico_batch_data(request, batch_id):
    """
    Devuelve datos JSON para gráficos Chart.js.
    Agrupa estudios finalizados por mes y modalidad.
    """
    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # Filtrar estudios finalizados: no insumos + estado Informado
    estudios_finalizados = batch.filas.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False
    )
    
    # Agrupar por mes y modalidad
    datos_por_mes = estudios_finalizados.annotate(
        mes=TruncMonth('fecha_turno')
    ).values('mes', 'modalidad').annotate(
        total=Count('id')
    ).order_by('mes', 'modalidad')
    
    # Estructurar datos para Chart.js
    # 1. Obtener todos los meses únicos
    meses = sorted(set(item['mes'] for item in datos_por_mes if item['mes']))
    labels = [mes.strftime('%Y-%m') for mes in meses]
    
    # 2. Preparar datasets por modalidad
    modalidades = ['TC', 'RM', 'RX', 'ECO', 'OTROS']
    colores = {
        'TC': {'border': 'rgb(59, 130, 246)', 'bg': 'rgba(59, 130, 246, 0.1)'},      # Azul
        'RM': {'border': 'rgb(147, 51, 234)', 'bg': 'rgba(147, 51, 234, 0.1)'},     # Púrpura
        'RX': {'border': 'rgb(34, 197, 94)', 'bg': 'rgba(34, 197, 94, 0.1)'},       # Verde
        'ECO': {'border': 'rgb(251, 191, 36)', 'bg': 'rgba(251, 191, 36, 0.1)'},    # Amarillo
        'OTROS': {'border': 'rgb(107, 114, 128)', 'bg': 'rgba(107, 114, 128, 0.1)'} # Gris
    }
    
    # 3. Crear un diccionario de datos indexado por (mes, modalidad)
    datos_dict = {}
    for item in datos_por_mes:
        if item['mes']:
            key = (item['mes'].strftime('%Y-%m'), item['modalidad'])
            datos_dict[key] = item['total']
    
    # 4. Construir datasets
    datasets = []
    for modalidad in modalidades:
        data = []
        for label in labels:
            key = (label, modalidad)
            data.append(datos_dict.get(key, 0))
        
        # Solo agregar si tiene al menos un valor > 0
        if sum(data) > 0:
            datasets.append({
                'label': modalidad,
                'data': data,
                'borderColor': colores[modalidad]['border'],
                'backgroundColor': colores[modalidad]['bg'],
                'borderWidth': 2,
                'tension': 0.3,  # Suavizado de líneas
            })
    
    return JsonResponse({
        'labels': labels,
        'datasets': datasets
    })


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def grafico_dia_semana_data(request, batch_id):
    """
    Devuelve datos para gráfico de distribución por día de la semana.
    """
    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # Filtrar estudios finalizados
    estudios = batch.filas.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False
    )
    
    # Contar por día de semana (0=Lunes, 6=Domingo)
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    conteo_por_dia = [0] * 7
    
    for estudio in estudios:
        dia_numero = estudio.fecha_turno.weekday()  # 0=Lunes, 6=Domingo
        conteo_por_dia[dia_numero] += 1
    
    return JsonResponse({
        'labels': dias_semana,
        'datasets': [{
            'label': 'Estudios Finalizados',
            'data': conteo_por_dia,
            'backgroundColor': [
                'rgba(59, 130, 246, 0.8)',   # Lunes - Azul
                'rgba(16, 185, 129, 0.8)',   # Martes - Verde
                'rgba(245, 158, 11, 0.8)',   # Miércoles - Amarillo
                'rgba(139, 92, 246, 0.8)',   # Jueves - Púrpura
                'rgba(239, 68, 68, 0.8)',    # Viernes - Rojo
                'rgba(107, 114, 128, 0.8)',  # Sábado - Gris
                'rgba(236, 72, 153, 0.8)',   # Domingo - Rosa
            ],
            'borderColor': [
                'rgb(59, 130, 246)',
                'rgb(16, 185, 129)',
                'rgb(245, 158, 11)',
                'rgb(139, 92, 246)',
                'rgb(239, 68, 68)',
                'rgb(107, 114, 128)',
                'rgb(236, 72, 153)',
            ],
            'borderWidth': 2
        }]
    })


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def grafico_franja_horaria_data(request, batch_id):
    """
    Devuelve datos para gráfico de distribución por franja horaria.
    """
    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # Filtrar estudios finalizados con hora
    estudios = batch.filas.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False,
        hora_turno__isnull=False
    )
    
    # Definir franjas horarias (cada 2 horas)
    franjas = [
        '00-02', '02-04', '04-06', '06-08', '08-10', '10-12',
        '12-14', '14-16', '16-18', '18-20', '20-22', '22-24'
    ]
    conteo_por_franja = [0] * 12
    
    for estudio in estudios:
        hora = estudio.hora_turno.hour
        franja_idx = hora // 2  # Dividir en franjas de 2 horas
        if 0 <= franja_idx < 12:
            conteo_por_franja[franja_idx] += 1
    
    return JsonResponse({
        'labels': franjas,
        'datasets': [{
            'label': 'Estudios Finalizados',
            'data': conteo_por_franja,
            'backgroundColor': 'rgba(59, 130, 246, 0.6)',
            'borderColor': 'rgb(59, 130, 246)',
            'borderWidth': 2,
            'borderRadius': 5,
        }]
    })


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def dashboard_global_grafico_data(request):
    """
    Devuelve datos consolidados de TODOS los batches para gráficos.
    Incluye filtros por rango de fechas y modalidades.
    """
    # Obtener parámetros de filtro
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    modalidades_seleccionadas = request.GET.getlist('modalidades[]')
    
    # Base query: todos los estudios finalizados
    estudios = EgesRow.objects.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False
    )
    
    # Aplicar filtros de fecha
    if fecha_desde:
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            estudios = estudios.filter(fecha_turno__gte=fecha_desde_obj)
        except:
            pass
    
    if fecha_hasta:
        try:
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
            estudios = estudios.filter(fecha_turno__lte=fecha_hasta_obj)
        except:
            pass
    
    # Aplicar filtro de modalidades
    if modalidades_seleccionadas:
        estudios = estudios.filter(modalidad__in=modalidades_seleccionadas)
    
    # Agrupar por mes y modalidad
    datos_por_mes = estudios.annotate(
        mes=TruncMonth('fecha_turno')
    ).values('mes', 'modalidad').annotate(
        total=Count('id')
    ).order_by('mes', 'modalidad')
    
    # Estructurar datos para Chart.js
    meses = sorted(set(item['mes'] for item in datos_por_mes if item['mes']))
    labels = [mes.strftime('%Y-%m') for mes in meses]
    
    # Preparar datasets por modalidad
    modalidades = ['TC', 'RM', 'RX', 'ECO', 'OTROS']
    colores = {
        'TC': {'border': 'rgb(59, 130, 246)', 'bg': 'rgba(59, 130, 246, 0.1)'},
        'RM': {'border': 'rgb(147, 51, 234)', 'bg': 'rgba(147, 51, 234, 0.1)'},
        'RX': {'border': 'rgb(34, 197, 94)', 'bg': 'rgba(34, 197, 94, 0.1)'},
        'ECO': {'border': 'rgb(251, 191, 36)', 'bg': 'rgba(251, 191, 36, 0.1)'},
        'OTROS': {'border': 'rgb(107, 114, 128)', 'bg': 'rgba(107, 114, 128, 0.1)'}
    }
    
    # Crear diccionario de datos
    datos_dict = {}
    for item in datos_por_mes:
        if item['mes']:
            key = (item['mes'].strftime('%Y-%m'), item['modalidad'])
            datos_dict[key] = item['total']
    
    # Construir datasets
    datasets = []
    for modalidad in modalidades:
        data = []
        for label in labels:
            key = (label, modalidad)
            data.append(datos_dict.get(key, 0))
        
        if sum(data) > 0:
            datasets.append({
                'label': modalidad,
                'data': data,
                'borderColor': colores[modalidad]['border'],
                'backgroundColor': colores[modalidad]['bg'],
                'borderWidth': 2,
                'tension': 0.3,
            })
    
    return JsonResponse({
        'labels': labels,
        'datasets': datasets
    })


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def dashboard_global_dia_semana_data(request):
    """Datos consolidados por día de semana."""
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    modalidades_seleccionadas = request.GET.getlist('modalidades[]')
    
    estudios = EgesRow.objects.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False
    )
    
    if fecha_desde:
        try:
            estudios = estudios.filter(fecha_turno__gte=datetime.strptime(fecha_desde, '%Y-%m-%d').date())
        except:
            pass
    
    if fecha_hasta:
        try:
            estudios = estudios.filter(fecha_turno__lte=datetime.strptime(fecha_hasta, '%Y-%m-%d').date())
        except:
            pass
    
    if modalidades_seleccionadas:
        estudios = estudios.filter(modalidad__in=modalidades_seleccionadas)
    
    dias_semana = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    conteo_por_dia = [0] * 7
    
    for estudio in estudios:
        dia_numero = estudio.fecha_turno.weekday()
        conteo_por_dia[dia_numero] += 1
    
    return JsonResponse({
        'labels': dias_semana,
        'datasets': [{
            'label': 'Estudios Finalizados',
            'data': conteo_por_dia,
            'backgroundColor': [
                'rgba(59, 130, 246, 0.8)',
                'rgba(16, 185, 129, 0.8)',
                'rgba(245, 158, 11, 0.8)',
                'rgba(139, 92, 246, 0.8)',
                'rgba(239, 68, 68, 0.8)',
                'rgba(107, 114, 128, 0.8)',
                'rgba(236, 72, 153, 0.8)',
            ],
            'borderColor': [
                'rgb(59, 130, 246)',
                'rgb(16, 185, 129)',
                'rgb(245, 158, 11)',
                'rgb(139, 92, 246)',
                'rgb(239, 68, 68)',
                'rgb(107, 114, 128)',
                'rgb(236, 72, 153)',
            ],
            'borderWidth': 2
        }]
    })


@login_required
@user_passes_test(es_superuser, login_url='/admin/')
def dashboard_global_franja_horaria_data(request):
    """Datos consolidados por franja horaria."""
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    modalidades_seleccionadas = request.GET.getlist('modalidades[]')
    
    estudios = EgesRow.objects.filter(
        es_insumo=False,
        estado_turno__iexact='Informado',
        fecha_turno__isnull=False,
        hora_turno__isnull=False
    )
    
    if fecha_desde:
        try:
            estudios = estudios.filter(fecha_turno__gte=datetime.strptime(fecha_desde, '%Y-%m-%d').date())
        except:
            pass
    
    if fecha_hasta:
        try:
            estudios = estudios.filter(fecha_turno__lte=datetime.strptime(fecha_hasta, '%Y-%m-%d').date())
        except:
            pass
    
    if modalidades_seleccionadas:
        estudios = estudios.filter(modalidad__in=modalidades_seleccionadas)
    
    franjas = [
        '00-02', '02-04', '04-06', '06-08', '08-10', '10-12',
        '12-14', '14-16', '16-18', '18-20', '20-22', '22-24'
    ]
    conteo_por_franja = [0] * 12
    
    for estudio in estudios:
        hora = estudio.hora_turno.hour
        franja_idx = hora // 2
        if 0 <= franja_idx < 12:
            conteo_por_franja[franja_idx] += 1
    
    return JsonResponse({
        'labels': franjas,
        'datasets': [{
            'label': 'Estudios Finalizados',
            'data': conteo_por_franja,
            'backgroundColor': 'rgba(59, 130, 246, 0.6)',
            'borderColor': 'rgb(59, 130, 246)',
            'borderWidth': 2,
            'borderRadius': 5,
        }]
    })
