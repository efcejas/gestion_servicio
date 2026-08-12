from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, IntegrityError, transaction
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.paginator import Paginator
from django.core.files.uploadedfile import UploadedFile
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core import signing
from django.db.models import Q, Count, Avg, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_http_methods
import json
import logging
import os
import re
import html
import unicodedata

from accounts.decorators import medical_staff_required, role_required
from .models import (
    Preinforme, TipoEstudio, Region, PlantillaPreinforme, 
    RevisionPreinforme, HistorialEstudios, EtiquetaPreinforme,
    AdjuntoPreinforme,
    EncuestaResidente,
    AplicacionPlantillaPreinforme, PropuestaPlantillaPreinforme,
    VersionPlantillaPreinforme,
    prepare_editor_html_content,
    normalizar_texto_busqueda,
)
from .forms import (
    PreinformeForm, FiltroPreinformesForm, 
    RevisionPreinformeForm, PlantillaPreinformeForm,
    NuevaPlantillaResidenteForm, GenerarPlantillaIAForm,
)
from .exceptions import GeneracionPlantillaError
from .template_generator_service import TemplateGeneratorService

User = get_user_model()
logger = logging.getLogger(__name__)

BORRADOR_PLANTILLA_IA_SALT = 'preinformes.borrador-plantilla-ia.v1'
BORRADOR_PLANTILLA_IA_MAX_AGE = 60 * 60

MAX_ADJUNTOS_POR_ORIGEN = 3
MAX_ADJUNTO_SIZE_MB = 5
ALLOWED_ADJUNTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def _preinformes_visibles_para(user):
    """Evita que registros demo entren en flujos clínicos de otros usuarios."""
    qs = Preinforme.objects.all()
    if getattr(user, 'is_demo_user', False):
        return qs.filter(Q(es_registro_demo=False) | Q(es_registro_demo=True, residente=user))
    return qs.filter(es_registro_demo=False)

from .services import (
    evaluar_sesion_mentor as _autoevaluar_sesion_mentor_al_enviar,
    obtener_o_preparar_revision,
)
from .selectors import (
    get_asignados_de,
    get_asignados_a_otros,
    get_pendientes_sin_revisor,
    get_revision_queryset,
)


def _guardar_adjuntos_preinforme(preinforme, archivos, subido_por, origen):
    """Valida y guarda adjuntos de imágenes para un preinforme."""
    if not archivos:
        return 0, None

    existentes = AdjuntoPreinforme.objects.filter(
        preinforme=preinforme,
        origen=origen,
        activo=True,
    ).count()

    if existentes + len(archivos) > MAX_ADJUNTOS_POR_ORIGEN:
        disponibles = max(0, MAX_ADJUNTOS_POR_ORIGEN - existentes)
        return 0, f'Solo puedes subir {MAX_ADJUNTOS_POR_ORIGEN} imágenes por rol. Te quedan {disponibles} disponibles.'

    archivos_validos = []
    for archivo in archivos:
        if not isinstance(archivo, UploadedFile):
            return 0, 'Archivo inválido recibido.'

        extension = os.path.splitext(archivo.name)[1].lower()
        if extension not in ALLOWED_ADJUNTO_EXTENSIONS:
            return 0, 'Formato no permitido. Usa JPG, PNG o WEBP.'

        if archivo.size > MAX_ADJUNTO_SIZE_MB * 1024 * 1024:
            return 0, f'Cada imagen debe ser menor a {MAX_ADJUNTO_SIZE_MB} MB.'

        archivos_validos.append(archivo)

    creados = []
    try:
        with transaction.atomic():
            for archivo in archivos_validos:
                creado = AdjuntoPreinforme.objects.create(
                    preinforme=preinforme,
                    imagen=archivo,
                    subido_por=subido_por,
                    origen=origen,
                    descripcion_corta='',
                    activo=True,
                )
                creados.append(creado)
    except Exception:
        return 0, 'No se pudieron guardar las imágenes. Inténtalo nuevamente.'

    return len(creados), None


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _area_equipo_para_tipo_estudio(tipo_estudio):
    nombre = unicodedata.normalize('NFKD', tipo_estudio.nombre or '')
    nombre = ''.join(char for char in nombre if not unicodedata.combining(char)).lower()
    if 'reson' in nombre or nombre.strip() == 'rm':
        return 'RM'
    if 'tomograf' in nombre or nombre.strip() in {'tc', 'tom'}:
        return 'TOM'
    if 'radiograf' in nombre or 'rayos' in nombre or nombre.strip() == 'rx':
        return 'RX'
    if 'ecograf' in nombre or nombre.strip() == 'eco':
        return 'ECO'
    return None


@require_http_methods(['POST'])
@medical_staff_required
def generar_plantilla_ia(request):
    """Genera una propuesta privada y estructurada para vista previa."""
    if not getattr(settings, 'PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO', False):
        return JsonResponse({'error': 'El generador no está habilitado.'}, status=404)

    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'La solicitud no contiene JSON válido.'}, status=400)

    form = GenerarPlantillaIAForm(payload)
    if not form.is_valid():
        return JsonResponse(
            {'error': 'Revisá los datos ingresados.', 'fields': form.errors},
            status=400,
        )

    servicio = TemplateGeneratorService()
    condiciones = servicio.inferir_condiciones(
        form.cleaned_data['tipo_estudio'],
        form.cleaned_data['estudio_especifico'],
    )
    try:
        propuesta = servicio.generar_propuesta(
            autor=request.user,
            tipo_estudio=form.cleaned_data['tipo_estudio'],
            region=form.cleaned_data['region'],
            estudio_especifico=form.cleaned_data['estudio_especifico'],
            instruccion_usuario=form.cleaned_data['instruccion_usuario'],
            **condiciones,
            fuentes_autorizadas=[],
            persistir=False,
        )
    except GeneracionPlantillaError as error:
        logger.warning(
            'No se pudo generar plantilla IA para usuario %s: %s',
            request.user.pk,
            error,
        )
        return JsonResponse({'error': str(error)}, status=422)

    from equipos.models import EquipoImagen
    equipos_queryset = EquipoImagen.objects.filter(en_servicio=True)
    area_equipo = _area_equipo_para_tipo_estudio(form.cleaned_data['tipo_estudio'])
    if area_equipo:
        equipos_queryset = equipos_queryset.filter(area=area_equipo)
    equipos = list(
        equipos_queryset
        .values('id', 'nombre', 'fabricante', 'modelo', 'area')
        .order_by('area', 'nombre')
    )
    return JsonResponse({
        'propuesta': {
            'titulo': propuesta.titulo,
            'encabezado': propuesta.encabezado,
            'hallazgos': propuesta.hallazgos,
            'variables': propuesta.variables,
        },
        'borrador_token': signing.dumps(
            {
                'autor_id': request.user.pk,
                'tipo_estudio_id': propuesta.tipo_estudio_id,
                'region_id': propuesta.region_id,
                'estudio_especifico': propuesta.estudio_especifico,
                'instruccion_usuario': propuesta.instruccion_usuario,
                'titulo': propuesta.titulo,
                'encabezado': propuesta.encabezado,
                'hallazgos': propuesta.hallazgos,
                'variables': propuesta.variables,
                'fuentes': propuesta.fuentes,
                'proveedor_ia': propuesta.proveedor_ia,
                'modelo_ia': propuesta.modelo_ia,
                'version_instrucciones': propuesta.version_instrucciones,
                'observacion_revision': propuesta.observacion_revision,
            },
            salt=BORRADOR_PLANTILLA_IA_SALT,
            compress=True,
        ),
        'equipos': equipos,
    })


@require_http_methods(['POST'])
@medical_staff_required
def aceptar_borrador_plantilla_ia(request):
    """Persiste y envía a revisión el borrador temporal aceptado."""
    if not getattr(settings, 'PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO', False):
        return JsonResponse({'error': 'El generador no está habilitado.'}, status=404)

    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'La solicitud no contiene JSON válido.'}, status=400)
    token = payload.get('borrador_token', '')
    try:
        borrador = signing.loads(
            token,
            salt=BORRADOR_PLANTILLA_IA_SALT,
            max_age=BORRADOR_PLANTILLA_IA_MAX_AGE,
        )
    except signing.SignatureExpired:
        return JsonResponse({
            'error': 'El borrador temporal venció. Generá nuevamente la propuesta.'
        }, status=410)
    except signing.BadSignature:
        return JsonResponse({'error': 'El borrador temporal no es válido.'}, status=400)

    if borrador.get('autor_id') != request.user.pk:
        return JsonResponse({'error': 'El borrador pertenece a otro usuario.'}, status=403)

    servicio = TemplateGeneratorService()
    try:
        with transaction.atomic():
            propuesta = PropuestaPlantillaPreinforme.objects.create(
                autor=request.user,
                tipo_estudio_id=borrador['tipo_estudio_id'],
                region_id=borrador['region_id'],
                estudio_especifico=borrador['estudio_especifico'],
                instruccion_usuario=borrador.get('instruccion_usuario', ''),
                titulo=borrador['titulo'],
                encabezado=borrador['encabezado'],
                hallazgos=borrador['hallazgos'],
                variables=borrador.get('variables', []),
                fuentes=borrador.get('fuentes', []),
                proveedor_ia=borrador.get('proveedor_ia', ''),
                modelo_ia=borrador.get('modelo_ia', ''),
                version_instrucciones=borrador.get('version_instrucciones', ''),
                observacion_revision=borrador.get('observacion_revision', ''),
            )
            servicio.actualizar_borrador(
                propuesta=propuesta,
                usuario=request.user,
                titulo=payload.get('titulo', ''),
                encabezado=propuesta.encabezado,
                hallazgos=payload.get('hallazgos', ''),
            )
            propuesta.enviar_a_revision()
    except (KeyError, GeneracionPlantillaError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=422)

    return JsonResponse({
        'propuesta_id': propuesta.pk,
        'variables': propuesta.variables,
        'estado': propuesta.estado,
    })


@require_http_methods(['POST'])
@medical_staff_required
def aceptar_plantilla_ia(request, pk):
    """Guarda la base en la biblioteca pendiente y abre los datos del estudio."""
    if not getattr(settings, 'PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO', False):
        return JsonResponse({'error': 'El generador no está habilitado.'}, status=404)

    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'La solicitud no contiene JSON válido.'}, status=400)

    propuesta = get_object_or_404(
        PropuestaPlantillaPreinforme,
        pk=pk,
        autor=request.user,
    )
    servicio = TemplateGeneratorService()
    try:
        servicio.actualizar_borrador(
            propuesta=propuesta,
            usuario=request.user,
            titulo=payload.get('titulo', ''),
            encabezado=propuesta.encabezado,
            hallazgos=payload.get('hallazgos', ''),
        )
        propuesta.enviar_a_revision()
    except (GeneracionPlantillaError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=422)

    return JsonResponse({
        'propuesta_id': propuesta.pk,
        'variables': propuesta.variables,
        'estado': propuesta.estado,
    })


@require_http_methods(['POST'])
@medical_staff_required
def aplicar_plantilla_ia(request, pk):
    """Resuelve los datos del estudio y carga la base aceptada."""
    if not getattr(settings, 'PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO', False):
        return JsonResponse({'error': 'El generador no está habilitado.'}, status=404)

    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'La solicitud no contiene JSON válido.'}, status=400)

    propuesta = get_object_or_404(
        PropuestaPlantillaPreinforme,
        Q(
            autor=request.user,
            estado__in=[
                PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
                PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
            ],
        ) | Q(
            estado=PropuestaPlantillaPreinforme.ESTADO_APROBADA,
            version_publicada__vigente=True,
            version_publicada__plantilla__activa=True,
            version_publicada__plantilla__estado='publica',
        ),
        pk=pk,
    )
    try:
        valores = payload.get('valores', {})
        fuente = (
            propuesta.version_publicada
            if propuesta.estado == PropuestaPlantillaPreinforme.ESTADO_APROBADA
            else propuesta
        )
        contenido = TemplateGeneratorService().renderizar_propuesta(
            propuesta=fuente,
            valores=valores,
        )
    except (GeneracionPlantillaError, ValidationError) as error:
        return JsonResponse({'error': str(error)}, status=422)
    except Exception:
        logger.exception('Error inesperado al aplicar propuesta de plantilla %s', propuesta.pk)
        return JsonResponse({
            'error': 'No se pudo cargar la plantilla. Intentá nuevamente.'
        }, status=500)

    return JsonResponse({
        'propuesta_id': propuesta.pk,
        'contenido': contenido,
        'valores': valores,
        'estado': propuesta.estado,
    })


def _registrar_aplicacion_plantilla_ia(request, preinforme):
    propuesta_id = request.POST.get('propuesta_plantilla_ia_id', '').strip()
    valores_raw = request.POST.get('valores_plantilla_ia', '').strip()
    if not propuesta_id:
        return None

    try:
        valores = json.loads(valores_raw)
        propuesta = PropuestaPlantillaPreinforme.objects.get(
            Q(
                autor=request.user,
                estado__in=[
                    PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
                    PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
                ],
            ) | Q(
                estado=PropuestaPlantillaPreinforme.ESTADO_APROBADA,
                version_publicada__vigente=True,
                version_publicada__plantilla__activa=True,
                version_publicada__plantilla__estado='publica',
            ),
            pk=propuesta_id,
        )
        version = (
            propuesta.version_publicada
            if propuesta.estado == PropuestaPlantillaPreinforme.ESTADO_APROBADA
            else None
        )
        TemplateGeneratorService().renderizar_propuesta(
            propuesta=version or propuesta,
            valores=valores,
        )
        equipo = None
        if valores.get('equipo'):
            from equipos.models import EquipoImagen
            equipo = EquipoImagen.objects.get(pk=valores['equipo'], en_servicio=True)

        aplicacion = AplicacionPlantillaPreinforme(
            preinforme=preinforme,
            plantilla=version.plantilla if version else None,
            version=version,
            propuesta=propuesta,
            valores_variables=valores,
            equipo=equipo,
            lateralidad=valores.get('lateralidad', ''),
            contraste_ev=valores.get('contraste_ev'),
            volumen_contraste_ml=valores.get('volumen_contraste_ml') or None,
            marca_contraste=valores.get('marca_contraste', ''),
            contraste_oral=valores.get('contraste_oral'),
            contenido_renderizado=preinforme.informe_html or '',
            aplicada_por=request.user,
        )
        aplicacion.full_clean()
        aplicacion.save()
        return None
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
        ObjectDoesNotExist,
        PropuestaPlantillaPreinforme.DoesNotExist,
        ValidationError,
    ):
        return (
            'El preinforme se guardó, pero no pudo registrarse la trazabilidad '
            'de la plantilla generada.'
        )


def _asegurar_resumen_ia_revision(revision):
    """Genera el resumen IA pre-revision sin bloquear el flujo si falla."""
    if revision.resumen_ia_revision:
        from .asistente_service import limpiar_resumen_pre_revision

        resumen_limpio = limpiar_resumen_pre_revision(revision.resumen_ia_revision)
        if resumen_limpio != revision.resumen_ia_revision:
            revision.resumen_ia_revision = resumen_limpio
            revision.save(update_fields=['resumen_ia_revision'])
        return
    if revision.resumen_ia_revision_error:
        return
    if not getattr(settings, 'PREINFORMES_RESUMEN_IA_REVISION_AUTO_GENERAR', True):
        return

    try:
        from django.utils import timezone as _timezone
        from .asistente_service import AsistenteRadiologicoBot

        resultado = AsistenteRadiologicoBot().generar_resumen_pre_revision(revision.preinforme)
        if resultado.get('success'):
            revision.resumen_ia_revision = resultado.get('resumen') or {}
            revision.resumen_ia_revision_generado_en = _timezone.now()
            revision.resumen_ia_revision_error = ''
            revision.save(update_fields=[
                'resumen_ia_revision',
                'resumen_ia_revision_generado_en',
                'resumen_ia_revision_error',
            ])
        elif resultado.get('error') != 'Bot no disponible.':
            revision.resumen_ia_revision_error = resultado.get('error') or 'No se pudo generar el resumen IA.'
            revision.save(update_fields=['resumen_ia_revision_error'])
    except Exception as exc:
        logger.warning("No se pudo generar resumen IA pre-revision para revision %s: %s", revision.pk, exc)


def _generar_evaluacion_ia_final_revision(revision):
    """Genera evaluacion IA final sin bloquear el cierre de la revision."""
    try:
        from django.utils import timezone as _timezone
        from .asistente_service import AsistenteRadiologicoBot

        resultado = AsistenteRadiologicoBot().generar_evaluacion_final_revision(revision)
        if resultado.get('success'):
            revision.evaluacion_ia_final = resultado.get('evaluacion') or {}
            revision.evaluacion_ia_final_generada_en = _timezone.now()
            revision.evaluacion_ia_final_error = ''
            revision.save(update_fields=[
                'evaluacion_ia_final',
                'evaluacion_ia_final_generada_en',
                'evaluacion_ia_final_error',
            ])
        elif resultado.get('error') != 'Bot no disponible.':
            revision.evaluacion_ia_final_error = resultado.get('error') or 'No se pudo generar la evaluacion IA final.'
            revision.save(update_fields=['evaluacion_ia_final_error'])
    except Exception as exc:
        logger.warning("No se pudo generar evaluacion IA final para revision %s: %s", revision.pk, exc)


def _normalizar_html_editor(content):
    """Aplica una normalización HTML suave para usar una base consistente en editor/exportación."""
    return prepare_editor_html_content(content)


def _html_a_texto_plano_exportacion(html_content, ascii_only=False):
    """Convierte HTML a texto plano preservando saltos de línea clínicamente útiles."""
    from django.utils.html import strip_tags

    texto_con_saltos = html_content or ''
    texto_con_saltos = texto_con_saltos.replace('</p>', '\n').replace('</P>', '\n')
    texto_con_saltos = re.sub(r'<br\s*/?>', '\n', texto_con_saltos, flags=re.IGNORECASE)
    texto_con_saltos = texto_con_saltos.replace('</div>', '\n').replace('</DIV>', '\n')
    texto_con_saltos = re.sub(r'</h[1-6]>', '\n', texto_con_saltos, flags=re.IGNORECASE)
    texto_con_saltos = texto_con_saltos.replace('</li>', '\n').replace('</LI>', '\n')

    informe_texto = strip_tags(texto_con_saltos)
    informe_texto = html.unescape(informe_texto)

    if ascii_only:
        informe_texto = unicodedata.normalize('NFKD', informe_texto).encode('ascii', 'ignore').decode('ascii')

    while '\n\n\n' in informe_texto:
        informe_texto = informe_texto.replace('\n\n\n', '\n\n')

    return informe_texto.strip()


def _construir_payload_exportacion(html_content, sistema_destino):
    """Construye la representación final para copiar según sistema destino."""
    from bs4 import BeautifulSoup

    html_normalizado = _normalizar_html_editor(html_content)

    if sistema_destino == 'netterm':
        informe_texto = _html_a_texto_plano_exportacion(html_normalizado, ascii_only=True)
        return {
            'informe_html': html_normalizado,
            'informe_texto': informe_texto,
            'informe_final': informe_texto,
            'sistema_destino': sistema_destino,
        }

    soup = BeautifulSoup(html_normalizado, 'html.parser')

    for span in soup.find_all('span'):
        if not span.has_attr('style'):
            continue

        style = span['style']
        style_parts = [s.strip() for s in style.split(';') if s.strip()]
        color_value = None
        for part in style_parts:
            if part.lower().startswith('color:'):
                color_value = part.split(':', 1)[1].strip()
                break

        if color_value:
            font_tag = soup.new_tag('font', color=color_value)
            for child in list(span.contents):
                font_tag.append(child.extract())
            span.replace_with(font_tag)

    for tag in soup.find_all(True):
        if tag.has_attr('style'):
            style = tag['style']
            style_parts = [s.strip() for s in style.split(';') if s.strip()]
            cleaned_parts = [p for p in style_parts if not p.lower().startswith('background')]
            if cleaned_parts:
                tag['style'] = '; '.join(cleaned_parts)
            else:
                del tag['style']

    informe_html = str(soup)
    informe_texto = _html_a_texto_plano_exportacion(informe_html, ascii_only=False)

    return {
        'informe_html': informe_html,
        'informe_texto': informe_texto,
        'informe_final': informe_texto,
        'sistema_destino': sistema_destino,
    }


def _eliminar_adjuntos_residente(preinforme, adjunto_ids, usuario):
    """Elimina adjuntos activos del residente para un preinforme editable."""
    if not adjunto_ids:
        return 0

    ids_validos = []
    for adjunto_id in adjunto_ids:
        try:
            ids_validos.append(int(adjunto_id))
        except (TypeError, ValueError):
            continue

    if not ids_validos:
        return 0

    adjuntos = AdjuntoPreinforme.objects.filter(
        id__in=ids_validos,
        preinforme=preinforme,
        origen='residente',
        subido_por=usuario,
        activo=True,
    )

    eliminados = 0
    for adjunto in adjuntos:
        if adjunto.imagen:
            adjunto.imagen.delete(save=False)
        adjunto.delete()
        eliminados += 1

    return eliminados


# === VISTAS PARA RESIDENTES ===

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def dashboard_residente(request):
    """Dashboard principal para residentes"""
    # Obtener o crear historial del residente
    historial, created = HistorialEstudios.objects.get_or_create(residente=request.user)
    if created:
        historial.actualizar_estadisticas()
    
    # Estadísticas rápidas
    preinformes_pendientes = Preinforme.objects.filter(
        residente=request.user,
        estado__in=['borrador', 'pendiente_revision']
    ).count()
    
    preinformes_en_revision = Preinforme.objects.filter(
        residente=request.user,
        estado='en_revision'
    ).count()
    correcciones_pendientes = Preinforme.objects.filter(
        residente=request.user,
        estado='finalizado',
        revision__isnull=False,
        fecha_correccion_vista__isnull=True,
    ).count()
    
    # Últimos preinformes
    ultimos_preinformes = Preinforme.objects.filter(
        residente=request.user
    ).order_by('-fecha_creacion')[:5]
    
    # Preinformes en edición activa (por cualquier residente)
    tiempo_limite = timezone.now() - timezone.timedelta(minutes=15)
    preinformes_en_edicion = Preinforme.objects.filter(
        en_edicion_por__isnull=False,
        ultima_actividad_edicion__gt=tiempo_limite,
        estado__in=['borrador', 'pendiente_revision', 'en_revision']
    ).exclude(
        en_edicion_por=request.user
    ).select_related('en_edicion_por', 'tipo_estudio', 'revisor').order_by('-ultima_actividad_edicion')

    encuesta_completada = EncuestaResidente.objects.filter(residente=request.user).exists()

    context = {
        'historial': historial,
        'preinformes_pendientes': preinformes_pendientes,
        'preinformes_en_revision': preinformes_en_revision,
        'correcciones_pendientes': correcciones_pendientes,
        'ultimos_preinformes': ultimos_preinformes,
        'preinformes_en_edicion': preinformes_en_edicion,
        'encuesta_completada': encuesta_completada,
    }
    
    return render(request, 'preinformes/dashboard_residente.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def crear_preinforme(request):
    """Crear un nuevo preinforme"""
    if request.method == 'POST':
        # Guardar datos del formulario en sesión antes de procesar
        if 'crear_plantilla' in request.POST:
            # Usuario quiere crear una plantilla nueva
            request.session['preinforme_form_data'] = request.POST.dict()
            tipo_estudio = request.POST.get('tipo_estudio', '').strip()
            region = request.POST.get('region', '').strip()
            
            # Validar que tipo_estudio y region sean valores válidos
            if not tipo_estudio or not region or tipo_estudio in ['None', 'null', ''] or region in ['None', 'null', '']:
                messages.error(request, 'Debes seleccionar primero el tipo de estudio y región antes de crear una plantilla.')
                return redirect('preinformes:crear_preinforme')
            
            return redirect(f"{reverse('preinformes:crear_plantilla_residente')}?tipo_estudio={tipo_estudio}&region={region}")
        
        form = PreinformeForm(request.POST, user=request.user)
        if form.is_valid():
            preinforme = form.save(commit=False)
            preinforme.residente = request.user
            preinforme.save()
            error_aplicacion_ia = _registrar_aplicacion_plantilla_ia(
                request,
                preinforme,
            )
            if error_aplicacion_ia:
                messages.warning(request, error_aplicacion_ia)

            archivos = [] if request.user.is_demo_user else request.FILES.getlist('imagenes_residente')
            cantidad_adjuntos, error_adjuntos = _guardar_adjuntos_preinforme(
                preinforme=preinforme,
                archivos=archivos,
                subido_por=request.user,
                origen='residente',
            )
            if error_adjuntos:
                messages.warning(request, f'Preinforme creado, pero hubo un problema al subir imágenes: {error_adjuntos}')
            elif cantidad_adjuntos:
                messages.success(request, f'Se adjuntaron {cantidad_adjuntos} imagen(es) al preinforme.')
            
            # Limpiar datos guardados en sesión
            if 'preinforme_form_data' in request.session:
                del request.session['preinforme_form_data']
            
            # Actualizar historial
            historial, created = HistorialEstudios.objects.get_or_create(residente=request.user)
            historial.actualizar_estadisticas()
            
            messages.success(request, 'Preinforme creado exitosamente.')
            
            if 'guardar_y_continuar' in request.POST:
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                _autoevaluar_sesion_mentor_al_enviar(
                    preinforme,
                    request.POST.get('asistente_conversacion_id') or None,
                )
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                return redirect('preinformes:dashboard_residente')
    else:
        # GET: Restaurar datos del formulario si existen en sesión
        initial_data = {}
        if 'preinforme_form_data' in request.session:
            saved_data = request.session['preinforme_form_data']
            # Restaurar solo los campos que queremos preservar
            fields_to_restore = [
                'numero_estudio', 'tipo_estudio', 'region', 'sistema_destino',
                'apellido_paciente', 'nombre_paciente', 'dni_paciente',
                'edad_paciente', 'sexo_paciente', 'fecha_estudio'
            ]
            for field in fields_to_restore:
                if field in saved_data and saved_data[field]:
                    initial_data[field] = saved_data[field]
        
        # Si viene de crear plantilla, cargar la plantilla en el formulario
        plantilla_id = request.GET.get('plantilla_id')
        if plantilla_id:
            try:
                plantilla = PlantillaPreinforme.objects.get(id=plantilla_id)
                initial_data['plantilla'] = plantilla.id
                messages.success(request, f'Plantilla "{plantilla.nombre}" cargada exitosamente.')
            except PlantillaPreinforme.DoesNotExist:
                pass
        
        form = PreinformeForm(initial=initial_data if initial_data else None, user=request.user)
    
    context = {
        'form': form,
        'adjuntos_residente': [],
        'adjuntos_revisor': [],
        'dictado_cursor_habilitado': getattr(settings, 'PREINFORMES_DICTADO_CURSOR_HABILITADO', False),
        'generador_plantillas_ia_habilitado': getattr(
            settings,
            'PREINFORMES_GENERADOR_PLANTILLAS_IA_HABILITADO',
            False,
        ),
        'title': 'Nuevo Preinforme'
    }
    
    return render(request, 'preinformes/form_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def editar_preinforme(request, pk):
    """Editar preinforme existente (solo si está pendiente de revisión y es el creador)"""
    preinforme = get_object_or_404(_preinformes_visibles_para(request.user), pk=pk)
    if preinforme.residente != request.user:
        messages.error(request, 'No tiene permiso para editar este preinforme.')
        return redirect('preinformes:mis_preinformes')
    if preinforme.estado not in ['borrador', 'pendiente_revision']:
        messages.error(request, 'Solo puede editar preinformes en borrador o pendientes de revisión.')
        return redirect('preinformes:mis_preinformes')

    # Marcar como en edición al abrir el formulario
    if request.method == 'GET':
        preinforme.marcar_en_edicion(request.user)

    if request.method == 'POST':
        form = PreinformeForm(request.POST, instance=preinforme, user=request.user)
        if form.is_valid():
            form.save()

            ids_adjuntos_eliminar = request.POST.getlist('eliminar_adjuntos_residente')
            eliminados = _eliminar_adjuntos_residente(
                preinforme=preinforme,
                adjunto_ids=ids_adjuntos_eliminar,
                usuario=request.user,
            )
            if eliminados:
                messages.success(request, f'Se eliminaron {eliminados} imagen(es) cargadas previamente.')

            archivos = request.FILES.getlist('imagenes_residente')
            cantidad_adjuntos, error_adjuntos = _guardar_adjuntos_preinforme(
                preinforme=preinforme,
                archivos=archivos,
                subido_por=request.user,
                origen='residente',
            )

            if error_adjuntos:
                messages.warning(request, f'Preinforme actualizado, pero hubo un problema al subir imágenes: {error_adjuntos}')
            elif cantidad_adjuntos:
                messages.success(request, f'Se adjuntaron {cantidad_adjuntos} imagen(es).')

            messages.success(request, 'Preinforme actualizado exitosamente.')

            if 'guardar_y_continuar' in request.POST:
                preinforme.marcar_en_edicion(request.user)
                return redirect('preinformes:editar_preinforme', pk=preinforme.pk)
            elif 'guardar_y_enviar' in request.POST:
                preinforme.enviar_a_revision()
                _autoevaluar_sesion_mentor_al_enviar(
                    preinforme,
                    request.POST.get('asistente_conversacion_id') or None,
                )
                preinforme.liberar_edicion()
                messages.success(request, 'Preinforme enviado para revisión.')
                return redirect('preinformes:dashboard_residente')
            else:
                preinforme.liberar_edicion()
                return redirect('preinformes:dashboard_residente')
    else:
        form = PreinformeForm(instance=preinforme, user=request.user)

    context = {
        'form': form,
        'preinforme': preinforme,
        'adjuntos_residente': preinforme.adjuntos.filter(origen='residente', activo=True),
        'adjuntos_revisor': preinforme.adjuntos.filter(origen='revisor', activo=True),
        'dictado_cursor_habilitado': getattr(settings, 'PREINFORMES_DICTADO_CURSOR_HABILITADO', False),
        'title': 'Editar Preinforme'
    }

    return render(request, 'preinformes/form_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def eliminar_preinforme(request, pk):
    """Permite al preinformante eliminar sus preinformes no tomados por staff."""
    if request.user.is_demo_user:
        return HttpResponseForbidden('La eliminación de preinformes no está disponible en modo demo.')

    preinforme = get_object_or_404(Preinforme, pk=pk, residente=request.user)
    next_url = request.POST.get('next') or reverse('preinformes:mis_preinformes')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse('preinformes:mis_preinformes')

    if preinforme.estado not in ['borrador', 'pendiente_revision']:
        messages.error(request, 'Solo podés eliminar preinformes en borrador o pendientes de revisión.')
        return redirect(next_url)

    numero_estudio = preinforme.numero_estudio
    for adjunto in preinforme.adjuntos.all():
        if adjunto.imagen:
            adjunto.imagen.delete(save=False)

    preinforme.delete()

    historial, _ = HistorialEstudios.objects.get_or_create(residente=request.user)
    historial.actualizar_estadisticas()

    messages.success(request, f'Preinforme #{numero_estudio} eliminado.')
    return redirect(next_url)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def mis_preinformes(request):
    """Lista de preinformes del residente"""
    form = FiltroPreinformesForm(request.GET, user=request.user)
    preinformes = Preinforme.objects.filter(residente=request.user).select_related('revision')
    correcciones_qs = Preinforme.objects.filter(
        residente=request.user,
        estado='finalizado',
        revision__isnull=False,
        fecha_correccion_vista__isnull=True,
    ).order_by('fecha_finalizacion', 'pk')
    correcciones_pendientes = correcciones_qs.count()
    primera_correccion_pendiente = correcciones_qs.first()
    
    # Aplicar filtros
    if form.is_valid():
        if form.cleaned_data['estado']:
            preinformes = preinformes.filter(estado=form.cleaned_data['estado'])
        if form.cleaned_data['sistema_destino']:
            preinformes = preinformes.filter(sistema_destino=form.cleaned_data['sistema_destino'])
        if form.cleaned_data['tipo_estudio']:
            preinformes = preinformes.filter(tipo_estudio=form.cleaned_data['tipo_estudio'])
        if form.cleaned_data['region']:
            preinformes = preinformes.filter(region=form.cleaned_data['region'])
        if form.cleaned_data['fecha_desde']:
            preinformes = preinformes.filter(fecha_creacion__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data['fecha_hasta']:
            preinformes = preinformes.filter(fecha_creacion__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data['numero_estudio']:
            preinformes = preinformes.filter(numero_estudio__icontains=form.cleaned_data['numero_estudio'])
        if not request.user.is_demo_user and form.cleaned_data.get('apellido_paciente'):
            preinformes = preinformes.filter(apellido_paciente__icontains=form.cleaned_data['apellido_paciente'])
        if not request.user.is_demo_user and form.cleaned_data.get('nombre_paciente'):
            preinformes = preinformes.filter(nombre_paciente__icontains=form.cleaned_data['nombre_paciente'])
    
    # Filtro por etiquetas (parámetro GET)
    etiquetas_ids = request.GET.getlist('etiquetas')
    if etiquetas_ids:
        preinformes = preinformes.filter(etiquetas__id__in=etiquetas_ids).distinct()
    
    preinformes = preinformes.order_by('-fecha_creacion')
    
    # Paginación
    paginator = Paginator(preinformes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Etiquetas disponibles para filtrar
    etiquetas_disponibles = EtiquetaPreinforme.objects.filter(
        preinformes__residente=request.user
    ).distinct().annotate(
        total=Count('preinformes')
    ).order_by('-total', 'nombre')
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'etiquetas_disponibles': etiquetas_disponibles,
        'etiquetas_seleccionadas': [int(id) for id in etiquetas_ids],
        'correcciones_pendientes': correcciones_pendientes,
        'primera_correccion_pendiente': primera_correccion_pendiente,
        'title': 'Mis Preinformes'
    }
    
    return render(request, 'preinformes/mis_preinformes.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def ver_preinforme(request, pk):
    """Ver detalle de preinforme con revisión si existe"""
    if request.user.is_demo_user:
        preinforme = get_object_or_404(Preinforme, pk=pk)
    else:
        preinforme = get_object_or_404(Preinforme, pk=pk, residente=request.user)

    en_cola_correcciones = (
        request.GET.get('cola') == 'correcciones'
        and preinforme.residente_id == request.user.id
        and preinforme.estado == 'finalizado'
    )
    volver_url = request.GET.get('next') or reverse('preinformes:mis_preinformes')
    if not url_has_allowed_host_and_scheme(
        volver_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        volver_url = reverse('preinformes:mis_preinformes')
    correcciones_pendientes = Preinforme.objects.filter(
        residente=request.user,
        estado='finalizado',
        revision__isnull=False,
        fecha_correccion_vista__isnull=True,
    ).count()

    context = {
        'preinforme': preinforme,
        'adjuntos_residente': [] if request.user.is_demo_user else preinforme.adjuntos.filter(origen='residente', activo=True),
        'adjuntos_revisor': [] if request.user.is_demo_user else preinforme.adjuntos.filter(origen='revisor', activo=True),
        'en_cola_correcciones': en_cola_correcciones,
        'correcciones_pendientes': correcciones_pendientes,
        'volver_url': volver_url,
        'title': f'Preinforme {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/ver_preinforme.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
@require_http_methods(['POST'])
def marcar_correccion_vista(request, pk):
    """Confirma la lectura y avanza a la siguiente corrección pendiente."""
    preinforme = get_object_or_404(
        Preinforme,
        pk=pk,
        residente=request.user,
        estado='finalizado',
        revision__isnull=False,
    )
    if preinforme.fecha_correccion_vista is None:
        preinforme.fecha_correccion_vista = timezone.now()
        preinforme.save(update_fields=['fecha_correccion_vista', 'fecha_modificacion'])

    volver_url = request.POST.get('next') or reverse('preinformes:mis_preinformes')
    if not url_has_allowed_host_and_scheme(
        volver_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        volver_url = reverse('preinformes:mis_preinformes')
    if request.POST.get('cola') != 'correcciones':
        messages.success(request, 'Corrección marcada como revisada.')
        return redirect(volver_url)

    siguiente = Preinforme.objects.filter(
        residente=request.user,
        estado='finalizado',
        revision__isnull=False,
        fecha_correccion_vista__isnull=True,
    ).exclude(pk=preinforme.pk).order_by('fecha_finalizacion', 'pk').first()
    if siguiente:
        return redirect(
            f"{reverse('preinformes:ver_preinforme', args=[siguiente.pk])}?cola=correcciones"
        )

    messages.success(request, 'Ya revisaste todas tus correcciones pendientes.')
    return redirect('preinformes:mis_preinformes')


# === BANCO DE INFORMES (pool compartido de finalizados) ===

SECCIONES_INFORME_BUSQUEDA = (
    ('datos clinicos', 'Datos clínicos'),
    ('indicacion', 'Indicación'),
    ('tecnica', 'Técnica'),
    ('hallazgos', 'Hallazgos'),
    ('conclusion', 'Conclusión'),
    ('impresion diagnostica', 'Impresión diagnóstica'),
    ('diagnostico', 'Diagnóstico'),
)


def _seccion_de_coincidencia(texto_normalizado, posicion):
    """Identifica el encabezado clínico más cercano anterior a una coincidencia."""
    encontrada = ('Informe definitivo', -1)
    for marcador, etiqueta in SECCIONES_INFORME_BUSQUEDA:
        inicio = texto_normalizado.rfind(marcador, 0, posicion + 1)
        if inicio > encontrada[1]:
            encontrada = (etiqueta, inicio)
    return encontrada[0]


def _fragmento_alrededor(texto, inicio, fin, margen=125):
    antes_inicio = max(0, inicio - margen)
    despues_fin = min(len(texto), fin + margen)
    return {
        'antes': ('…' if antes_inicio else '') + texto[antes_inicio:inicio],
        'texto': texto[inicio:fin],
        'despues': texto[fin:despues_fin] + ('…' if despues_fin < len(texto) else ''),
    }


def _resumen_visual_semantico(texto, conceptos):
    """Elige el pasaje con más vocabulario de la consulta sin inventar contenido."""
    palabras = {
        palabra
        for concepto in conceptos
        for palabra in normalizar_texto_busqueda(concepto).split()
        if len(palabra) >= 4 and palabra not in {'casos', 'caso', 'informe', 'informes', 'necesito'}
    }
    fragmentos = [
        fragmento.strip()
        for fragmento in re.split(r'(?<=[.!?;])\s+', texto)
        if fragmento.strip()
    ]
    if not fragmentos:
        return ''
    mejor = max(
        fragmentos,
        key=lambda fragmento: sum(
            palabra in normalizar_texto_busqueda(fragmento) for palabra in palabras
        ),
    )
    if len(mejor) > 300:
        mejor = mejor[:300].rsplit(' ', 1)[0] + '…'
    return mejor


PALABRAS_BUSQUEDA_GENERICAS = {
    'casos', 'caso', 'informe', 'informes', 'necesito', 'buscar', 'estudio',
    'estudios', 'tomografia', 'computada', 'resonancia', 'radiografia',
}


def _tiene_evidencia_clinica(texto_normalizado, conceptos):
    """Exige vocabulario clínico concreto antes de aceptar una similitud global."""
    palabras_informe = set(re.findall(r'\b\w{4,}\b', texto_normalizado))
    for concepto in conceptos:
        palabras = {
            palabra
            for palabra in normalizar_texto_busqueda(concepto).split()
            if len(palabra) >= 4 and palabra not in PALABRAS_BUSQUEDA_GENERICAS
        }
        if not palabras:
            continue
        minimo = 1 if len(palabras) == 1 else 2
        presentes = len(palabras & palabras_informe)
        if presentes >= minimo:
            return True
    return False

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def lista_banco_informes(request):
    """Lista de todos los preinformes finalizados del equipo residente.
    Permite que el residente A busque y copie el informe definitivo del residente B.
    No muestra datos de evaluación (puntuación, comentarios del revisor).
    """
    qs = Preinforme.objects.filter(
        es_registro_demo=False,
        estado='finalizado',
        residente__rol='medico_residente',
    ).select_related('residente', 'tipo_estudio', 'region', 'revision').order_by('-fecha_finalizacion')

    # Filtros GET
    q_numero = request.GET.get('numero_estudio', '').strip()
    q_paciente = '' if request.user.is_demo_user else request.GET.get('paciente', '').strip()
    q_tipo = request.GET.get('tipo_estudio', '')
    q_region = request.GET.get('region', '')
    q_contenido = request.GET.get('contenido', '').strip()
    q_ia = request.GET.get('q_ia', '').strip()[:500]
    interpretacion_ia = None
    error_ia = ''
    estado_semantico = None
    puntajes_semanticos = {}

    if q_numero:
        qs = qs.filter(numero_estudio__icontains=q_numero)
    if q_paciente:
        qs = qs.filter(
            Q(apellido_paciente__icontains=q_paciente) |
            Q(nombre_paciente__icontains=q_paciente)
        )
    if q_tipo:
        qs = qs.filter(tipo_estudio_id=q_tipo)
    if q_region:
        qs = qs.filter(region_id=q_region)
    contenido_normalizado = normalizar_texto_busqueda(q_contenido)
    if contenido_normalizado:
        qs = qs.filter(revision__informe_final_busqueda__icontains=contenido_normalizado)

    terminos_busqueda = [contenido_normalizado] if contenido_normalizado else []
    if q_ia and getattr(settings, 'PREINFORMES_BUSCADOR_IA_HABILITADO', True):
        from .buscador_casos_service import BuscadorCasosIA

        interpretacion_ia = BuscadorCasosIA().interpretar(q_ia)
        error_ia = interpretacion_ia.get('error', '')
        consulta_corregida = interpretacion_ia.get('consulta_corregida') or q_ia
        terminos_ia = [
            normalizar_texto_busqueda(termino)
            for termino in [q_ia, consulta_corregida, *interpretacion_ia.get('terminos', [])]
            if normalizar_texto_busqueda(termino)
        ]
        terminos_ia = list(dict.fromkeys(terminos_ia))
        terminos_busqueda.extend(terminos_ia)

        def ids_catalogo_compatibles(modelo, texto):
            buscado = normalizar_texto_busqueda(texto)
            if not buscado:
                return []
            tokens = {token for token in buscado.split() if len(token) >= 2}
            ids = []
            for objeto in modelo.objects.only('id', 'nombre'):
                nombre = normalizar_texto_busqueda(objeto.nombre)
                nombre_tokens = set(nombre.split())
                if buscado in nombre or nombre in buscado or tokens & nombre_tokens:
                    ids.append(objeto.id)
            return ids

        tipo_ia = interpretacion_ia.get('tipo_estudio', '')
        region_ia = interpretacion_ia.get('region', '')
        tipos_ids = ids_catalogo_compatibles(TipoEstudio, tipo_ia)
        regiones_ids = ids_catalogo_compatibles(Region, region_ia)
        if tipos_ids:
            qs = qs.filter(tipo_estudio_id__in=tipos_ids)
        if regiones_ids:
            qs = qs.filter(region_id__in=regiones_ids)

        filtro_literal_ia = Q()
        puntaje_ia = Value(0, output_field=IntegerField())
        for posicion, termino in enumerate(terminos_ia):
            condicion = Q(revision__informe_final_busqueda__icontains=termino)
            filtro_literal_ia |= condicion
            if posicion == 0:
                peso_literal = 10000
            elif posicion == 1:
                peso_literal = 8000
            else:
                peso_literal = max(2000, 5000 - (posicion * 300))
            puntaje_ia += Case(
                When(condicion, then=Value(peso_literal)),
                default=Value(0),
                output_field=IntegerField(),
            )

        from .busqueda_semantica_service import BusquedaSemanticaInformes

        consulta_semantica = consulta_corregida
        if terminos_ia:
            consulta_semantica += '. Conceptos relacionados: ' + ', '.join(terminos_ia)
        revisiones_semanticas = list(RevisionPreinforme.objects.filter(
            preinforme_id__in=qs.values('pk'),
            embedding_busqueda__isnull=False,
        ).only(
            'id', 'preinforme_id', 'embedding_busqueda', 'embedding_modelo',
            'informe_final_busqueda',
        ))
        resultado_semantico = BusquedaSemanticaInformes().buscar(
            consulta_semantica,
            revisiones_semanticas,
        )
        revisiones_por_id = {revision.id: revision for revision in revisiones_semanticas}
        umbral_preciso = getattr(
            settings, 'PREINFORMES_EMBEDDING_UMBRAL_PRECISO', 0.50
        )
        resultados_originales = resultado_semantico.get('resultados', [])
        resultados_con_evidencia = []
        for resultado in resultados_originales:
            revision = revisiones_por_id.get(resultado['revision_id'])
            if (
                revision
                and resultado['similitud'] >= umbral_preciso
                and _tiene_evidencia_clinica(
                    revision.informe_final_busqueda, terminos_ia
                )
            ):
                resultados_con_evidencia.append(resultado)
        resultado_semantico['resultados'] = resultados_con_evidencia
        resultado_semantico['descartados_sin_evidencia'] = (
            len(resultados_originales) - len(resultados_con_evidencia)
        )
        if len(resultados_con_evidencia) < resultado_semantico.get('max_resultados', 50):
            resultado_semantico['limite_alcanzado'] = False
        estado_semantico = resultado_semantico
        ids_semanticos = [
            resultado['preinforme_id']
            for resultado in resultado_semantico.get('resultados', [])
        ]
        puntajes_semanticos = {
            resultado['preinforme_id']: resultado['similitud']
            for resultado in resultado_semantico.get('resultados', [])
        }

        filtro_combinado = filtro_literal_ia
        if ids_semanticos:
            filtro_combinado |= Q(pk__in=ids_semanticos)
            for preinforme_id, similitud in puntajes_semanticos.items():
                puntaje_ia += Case(
                    When(pk=preinforme_id, then=Value(round(similitud * 1000))),
                    default=Value(0),
                    output_field=IntegerField(),
                )
        if terminos_ia or ids_semanticos:
            qs = qs.filter(filtro_combinado).annotate(relevancia_ia=puntaje_ia)
            qs = qs.order_by('-relevancia_ia', '-fecha_finalizacion')

    paginator = Paginator(qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if terminos_busqueda:
        for preinforme in page_obj.object_list:
            texto = preinforme.revision.informe_final_texto
            texto_normalizado = preinforme.revision.informe_final_busqueda
            termino_encontrado = next(
                (termino for termino in terminos_busqueda if termino in texto_normalizado),
                '',
            )
            inicio = texto_normalizado.find(termino_encontrado) if termino_encontrado else -1
            if inicio >= 0:
                fin = inicio + len(termino_encontrado)
                fragmento = _fragmento_alrededor(texto, inicio, fin)
                preinforme.coincidencia_antes = fragmento['antes']
                preinforme.coincidencia_texto = fragmento['texto']
                preinforme.coincidencia_despues = fragmento['despues']
                preinforme.coincidencia_seccion = _seccion_de_coincidencia(
                    texto_normalizado, inicio
                )
                preinforme.coincidencia_explicacion = (
                    f'El informe menciona “{preinforme.coincidencia_texto}” '
                    f'en {preinforme.coincidencia_seccion.lower()}.'
                )
            elif preinforme.pk in puntajes_semanticos:
                preinforme.resumen_semantico = _resumen_visual_semantico(
                    texto, [q_ia, *terminos_busqueda]
                )
                preinforme.explicacion_semantica = (
                    'El contenido global del informe es clínicamente relacionado con la búsqueda, '
                    'aunque no contiene una frase equivalente exacta.'
                )
                preinforme.similitud_semantica = puntajes_semanticos[preinforme.pk]
                if preinforme.similitud_semantica >= 0.55:
                    preinforme.relevancia_semantica = 'Alta'
                else:
                    preinforme.relevancia_semantica = 'Fuerte'

    context = {
        'page_obj': page_obj,
        'tipos_estudio': TipoEstudio.objects.all().order_by('nombre'),
        'regiones': Region.objects.all().order_by('nombre'),
        'q_numero': q_numero,
        'q_paciente': q_paciente,
        'q_tipo': q_tipo,
        'q_region': q_region,
        'q_contenido': q_contenido,
        'q_ia': q_ia,
        'interpretacion_ia': interpretacion_ia,
        'error_ia': error_ia,
        'estado_semantico': estado_semantico,
        'buscador_ia_habilitado': getattr(
            settings, 'PREINFORMES_BUSCADOR_IA_HABILITADO', True
        ),
        'title': 'Banco de Informes',
    }
    return render(request, 'preinformes/lista_banco_informes.html', context)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def ver_banco_preinforme(request, pk):
    """Vista limpia del informe final para el pool del equipo.
    Solo muestra el informe definitivo y el botón de copia.
    Sin datos de la evaluación (puntuación, comentarios al residente).
    """
    preinforme = get_object_or_404(
        _preinformes_visibles_para(request.user),
        pk=pk,
        estado='finalizado',
        residente__rol='medico_residente',
    )
    context = {
        'preinforme': preinforme,
        'title': f'Informe {preinforme.numero_estudio}',
    }
    return render(request, 'preinformes/ver_banco_preinforme.html', context)


# === VISTAS PARA STAFF ===

@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def dashboard_staff(request):
    """Dashboard para médicos de staff"""
    # Preinformes asignados a mí (pendientes o en revisión)
    mis_asignados = get_asignados_de(request.user).count()
    
    # Preinformes sin asignar (pendientes de revisión sin revisor)
    pendientes_revision = get_pendientes_sin_revisor(request.user).count()
    asignados_otros = get_asignados_a_otros(request.user).count()
    
    # Preinformes en revisión por este usuario
    en_revision = Preinforme.objects.filter(
        es_registro_demo=False,
        estado='en_revision',
        revisor=request.user
    ).count()
    
    # Estadísticas generales
    total_preinformes_mes = Preinforme.objects.filter(
        es_registro_demo=False,
        fecha_creacion__month=timezone.now().month,
        fecha_creacion__year=timezone.now().year
    ).count()
    
    # Últimos preinformes asignados a mí
    mis_ultimos_asignados = get_asignados_de(request.user).order_by('-fecha_envio_revision')[:5]
    
    # Últimos preinformes pendientes sin asignar
    ultimos_pendientes = get_pendientes_sin_revisor(request.user).order_by('-fecha_envio_revision')[:5]
    
    context = {
        'mis_asignados': mis_asignados,
        'pendientes_revision': pendientes_revision,
        'asignados_otros': asignados_otros,
        'en_revision': en_revision,
        'total_preinformes_mes': total_preinformes_mes,
        'mis_ultimos_asignados': mis_ultimos_asignados,
        'ultimos_pendientes': ultimos_pendientes,
    }
    
    return render(request, 'preinformes/dashboard_staff.html', context)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def lista_revision(request):
    """Lista de preinformes para revisar"""
    form = FiltroPreinformesForm(request.GET, user=request.user)
    
    # Filtro para mostrar diferentes categorías
    mostrar = request.GET.get('mostrar', 'asignados')  # 'asignados', 'sin_asignar', 'compartidos', 'todos', 'finalizados'
    
    if mostrar == 'asignados':
        # Solo mis preinformes asignados
        preinformes = Preinforme.objects.filter(
            Q(revisor=request.user) & Q(estado__in=['pendiente_revision', 'en_revision'])
        )
    elif mostrar == 'sin_asignar':
        # Preinformes sin revisor asignado (excluir compartidos)
        preinformes = Preinforme.objects.filter(
            estado__in=['pendiente_revision', 'en_revision'],
            revisor__isnull=True,
            asignacion_compartida=False
        )
    elif mostrar == 'compartidos':
        # Pool compartido para jefes/instructores
        if request.user.rol in ['jefe_residentes', 'instructor_residentes']:
            preinformes = Preinforme.objects.filter(
                asignacion_compartida=True,
                revisor__isnull=True,
                estado__in=['pendiente_revision', 'en_revision']
            )
        else:
            # Si no tiene el rol adecuado, mostrar lista vacía
            preinformes = Preinforme.objects.none()
    elif mostrar == 'finalizados':
        # Preinformes que ya revisé y están finalizados
        preinformes = Preinforme.objects.filter(
            revisor=request.user,
            estado='finalizado',
        ).select_related('revision', 'residente', 'tipo_estudio', 'region')
    else:
        # Todos: pendientes/en_revision sin asignar (excluir compartidos para staff), o asignados a mí
        base_filter = Q(estado__in=['pendiente_revision', 'en_revision'], revisor=request.user)
        
        # Para estudios sin asignar, depende del rol
        if request.user.rol in ['jefe_residentes', 'instructor_residentes']:
            # Jefes e instructores ven todos los sin asignar (incluidos compartidos)
            base_filter |= Q(estado__in=['pendiente_revision', 'en_revision'], revisor__isnull=True)
        else:
            # Staff solo ve sin asignar que NO sean compartidos
            base_filter |= Q(
                estado__in=['pendiente_revision', 'en_revision'], 
                revisor__isnull=True,
                asignacion_compartida=False
            )
        
        preinformes = Preinforme.objects.filter(base_filter)

    # Fuente efectiva de las bandejas: mantener centralizada la regla en selectors.py.
    preinformes = get_revision_queryset(request.user, mostrar)
    
    # Aplicar filtros
    if form.is_valid():
        if form.cleaned_data.get('estado'):
            preinformes = preinformes.filter(estado=form.cleaned_data['estado'])
        if form.cleaned_data.get('sistema_destino'):
            preinformes = preinformes.filter(sistema_destino=form.cleaned_data['sistema_destino'])
        if form.cleaned_data.get('tipo_estudio'):
            preinformes = preinformes.filter(tipo_estudio=form.cleaned_data['tipo_estudio'])
        if form.cleaned_data.get('region'):
            preinformes = preinformes.filter(region=form.cleaned_data['region'])
        if form.cleaned_data.get('residente'):
            preinformes = preinformes.filter(residente=form.cleaned_data['residente'])
        if form.cleaned_data.get('fecha_desde'):
            preinformes = preinformes.filter(fecha_envio_revision__date__gte=form.cleaned_data['fecha_desde'])
        if form.cleaned_data.get('fecha_hasta'):
            preinformes = preinformes.filter(fecha_envio_revision__date__lte=form.cleaned_data['fecha_hasta'])
        if form.cleaned_data.get('numero_estudio'):
            preinformes = preinformes.filter(numero_estudio__icontains=form.cleaned_data['numero_estudio'])
        if not request.user.is_demo_user and form.cleaned_data.get('apellido_paciente'):
            preinformes = preinformes.filter(apellido_paciente__icontains=form.cleaned_data['apellido_paciente'])
    
    preinformes = preinformes.order_by('-fecha_envio_revision')
    
    # Paginación
    paginator = Paginator(preinformes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'form': form,
        'title': 'Preinformes para Revisar',
        'mostrar': mostrar,  # Para debugging y preservar filtro
    }
    
    return render(request, 'preinformes/lista_revision.html', context)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def asignar_revisor(request, pk):
    """Asignar un revisor a un preinforme (o asignarse a uno mismo)"""
    preinforme = get_object_or_404(_preinformes_visibles_para(request.user), pk=pk)
    
    # Obtener de dónde viene para redirigir correctamente
    mostrar = request.GET.get('mostrar', 'asignados')
    redirect_url = f"{reverse('preinformes:lista_revision')}?mostrar={mostrar}"
    
    # Solo se pueden asignar preinformes pendientes o en revisión
    if preinforme.estado not in ['pendiente_revision', 'en_revision']:
        messages.error(request, 'Solo se pueden asignar preinformes pendientes o en revisión.')
        return redirect(redirect_url)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'asignarme':
            # Asignarse a sí mismo
            revisor_anterior = preinforme.revisor
            if revisor_anterior and revisor_anterior != request.user and preinforme.estado == 'en_revision':
                messages.error(
                    request,
                    'No se puede tomar un preinforme que ya esta en revision por otro staff.'
                )
                return redirect(redirect_url)
            preinforme.revisor = request.user
            preinforme.save()
            if revisor_anterior and revisor_anterior != request.user:
                messages.success(
                    request,
                    f'Tomaste el preinforme #{preinforme.numero_estudio}, antes asignado a {revisor_anterior.get_full_name()}.'
                )
            else:
                messages.success(request, f'Te asignaste el preinforme #{preinforme.numero_estudio}.')
        elif action == 'desasignar':
            # Desasignar el preinforme
            preinforme.revisor = None
            # Si estaba en revisión, volver a pendiente
            if preinforme.estado == 'en_revision':
                preinforme.estado = 'pendiente_revision'
            preinforme.save()
            messages.success(request, f'Desasignaste el preinforme #{preinforme.numero_estudio}.')
        else:
            # Asignar a otro usuario específico
            revisor_id = request.POST.get('revisor_id')
            if revisor_id:
                try:
                    revisor = User.objects.get(pk=revisor_id, rol__in=['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'])
                    preinforme.revisor = revisor
                    preinforme.save()
                    messages.success(request, f'Asignaste el preinforme #{preinforme.numero_estudio} a {revisor.get_full_name()}.')
                except User.DoesNotExist:
                    messages.error(request, 'Revisor no válido.')
    
    return redirect(redirect_url)


@login_required
@role_required('jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def tomar_estudio(request, pk):
    """Tomar un estudio del pool compartido y asignarlo al usuario actual"""
    mostrar = request.GET.get('mostrar', 'compartidos')
    redirect_url = f"{reverse('preinformes:lista_revision')}?mostrar={mostrar}"
    
    try:
        # Usar transacción atómica con lock pesimista para evitar race conditions
        with transaction.atomic():
            # select_for_update bloquea la fila hasta que termine la transacción
            preinforme = _preinformes_visibles_para(request.user).select_for_update().get(pk=pk)
            
            # Validar que el estudio puede ser tomado
            if not preinforme.puede_ser_tomado_por(request.user):
                messages.error(
                    request, 
                    'Este estudio no está disponible para tomar. '
                    'Puede que ya haya sido asignado a otro revisor.'
                )
                return redirect(redirect_url)
            
            # Asignar al usuario actual
            preinforme.revisor = request.user
            preinforme.asignacion_compartida = False  # Ya no está en el pool
            
            # Si está pendiente, cambiar a en_revision
            if preinforme.estado == 'pendiente_revision':
                preinforme.estado = 'en_revision'
                preinforme.fecha_inicio_revision = timezone.now()
            
            preinforme.save()
            
            messages.success(
                request, 
                f'Has tomado el estudio #{preinforme.numero_estudio} para revisión.'
            )
            
            # Redirigir directamente a la vista de revisión
            return redirect('preinformes:revisar_preinforme', pk=preinforme.pk)
            
    except Preinforme.DoesNotExist:
        messages.error(request, 'El estudio no existe.')
        return redirect(redirect_url)


@login_required
@role_required('medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def revisar_preinforme(request, pk):
    """Revisar y corregir preinforme"""
    preinforme = get_object_or_404(
        _preinformes_visibles_para(request.user),
        pk=pk,
        estado__in=['pendiente_revision', 'en_revision', 'finalizado']
    )
    es_edicion_finalizada = preinforme.estado == 'finalizado'
    
    # Lógica de asignación automática
    if preinforme.estado == 'pendiente_revision':
        # Si está pendiente, iniciar revisión y asignar al usuario actual
        preinforme.iniciar_revision(request.user)
    elif preinforme.estado == 'en_revision':
        # Si está en revisión, verificar quién es el revisor
        if preinforme.revisor is None:
            # Sin revisor asignado → asignarse automáticamente
            preinforme.revisor = request.user
            preinforme.save(update_fields=['revisor'])
        elif preinforme.revisor != request.user:
            # Otro médico lo está revisando
            messages.error(
                request, 
                f'Este preinforme está siendo revisado por {preinforme.revisor.get_full_name()}.'
            )
            return redirect('preinformes:lista_revision')
    elif preinforme.estado == 'finalizado':
        if preinforme.revisor != request.user:
            messages.error(request, 'Solo el revisor asignado puede editar un preinforme finalizado.')
            return redirect('preinformes:lista_revision')
    
    revision, created = obtener_o_preparar_revision(preinforme, request.user)

    if request.method == 'POST' and 'liberar_revision' in request.POST:
        if preinforme.estado == 'en_revision' and preinforme.revisor == request.user:
            preinforme.revisor = None
            preinforme.estado = 'pendiente_revision'
            preinforme.save(update_fields=['revisor', 'estado', 'fecha_modificacion'])
            messages.success(request, 'Liberaste la revisión. El residente podrá editar y el estudio queda disponible nuevamente.')
            return redirect('preinformes:lista_revision')

        messages.error(request, 'Solo podés liberar una revisión activa asignada a vos.')
        return redirect('preinformes:lista_revision')

    if request.method == 'POST':
        # Guardar y finalizar revisión
        form = RevisionPreinformeForm(request.POST, instance=revision, preinforme=preinforme)
        if form.is_valid():
            revision = form.save(commit=False)
            # El informe final ya está en informe_final_html, no necesitamos generar nada
            revision.save()

            archivos = [] if request.user.is_demo_user else request.FILES.getlist('imagenes_revisor')
            cantidad_adjuntos, error_adjuntos = _guardar_adjuntos_preinforme(
                preinforme=preinforme,
                archivos=archivos,
                subido_por=request.user,
                origen='revisor',
            )
            if error_adjuntos:
                messages.warning(request, f'Revisión guardada, pero hubo un problema al subir imágenes: {error_adjuntos}')
            elif cantidad_adjuntos:
                messages.success(request, f'Se adjuntaron {cantidad_adjuntos} imagen(es) de feedback.')
            
            if 'guardar_y_continuar' in request.POST:
                messages.success(request, 'Revisión guardada exitosamente.')
                return redirect('preinformes:revisar_preinforme', pk=pk)
            elif 'finalizar_revision' in request.POST:
                preinforme.finalizar_revision()
                _generar_evaluacion_ia_final_revision(revision)
                # Actualizar historial del residente
                historial, _ = HistorialEstudios.objects.get_or_create(residente=preinforme.residente)
                historial.actualizar_estadisticas()
                if es_edicion_finalizada:
                    messages.success(request, 'Revision actualizada exitosamente.')
                    return redirect(f"{reverse('preinformes:lista_revision')}?mostrar=finalizados")
                messages.success(request, 'Revisión finalizada exitosamente.')
                return redirect('preinformes:lista_revision')
            else:
                messages.success(request, 'Revisión guardada exitosamente.')
                return redirect('preinformes:lista_revision')
    else:
        # GET: El form se crea con la instancia que ya tiene informe_final_html cargado
        _asegurar_resumen_ia_revision(revision)
        form = RevisionPreinformeForm(instance=revision, preinforme=preinforme)
    
    context = {
        'form': form,
        'preinforme': preinforme,
        'revision': revision,
        'resumen_ia_revision': revision.resumen_ia_revision or {},
        'adjuntos_residente': [] if request.user.is_demo_user else preinforme.adjuntos.filter(origen='residente', activo=True),
        'adjuntos_revisor': [] if request.user.is_demo_user else preinforme.adjuntos.filter(origen='revisor', activo=True),
        'dictado_cursor_habilitado': getattr(settings, 'PREINFORMES_DICTADO_CURSOR_HABILITADO', False),
        'es_edicion_finalizada': es_edicion_finalizada,
        'title': f'Editar Revision {preinforme.numero_estudio}' if es_edicion_finalizada else f'Revisar Preinforme {preinforme.numero_estudio}'
    }
    
    return render(request, 'preinformes/revisar_preinforme.html', context)


# === AUTOSAVE ===

@login_required
@require_http_methods(["POST"])
def autosave_revision(request, pk):
    """Guarda automáticamente el informe_final_html sin recargar la página"""
    from django.http import Http404
    try:
        # pk es el ID del preinforme, no de la revisión
        preinforme = get_object_or_404(
            Preinforme,
            pk=pk,
            estado__in=['pendiente_revision', 'en_revision', 'finalizado']
        )
        
        # Obtener la revisión asociada
        revision = get_object_or_404(
            RevisionPreinforme,
            preinforme=preinforme,
            revisor=request.user
        )
        
        data = json.loads(request.body)
        informe_html = data.get('informe_final_html', '')
        
        if not informe_html:
            return JsonResponse({'success': False, 'error': 'Contenido vacío'}, status=400)
        
        # Guardar sin validaciones complejas
        revision.informe_final_html = informe_html
        revision.save(update_fields=['informe_final_html', 'fecha_modificacion'])
        
        return JsonResponse({
            'success': True,
            'message': 'Guardado automático exitoso',
            'timestamp': timezone.localtime(revision.fecha_modificacion).strftime('%H:%M'),
        })

    except Http404:
        raise
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# === VISTAS AJAX ===

@login_required
def cargar_plantillas(request):
    """Cargar plantillas según tipo de estudio, región y sistema destino"""
    tipo_estudio_id = request.GET.get('tipo_estudio_id')
    region_id = request.GET.get('region_id')
    sistema_destino = request.GET.get('sistema_destino', 'eges')
    
    # Filtrar plantillas activas
    plantillas = PlantillaPreinforme.objects.filter(activa=True)
    
    # Filtrar por tipo y región si se proporcionan
    if tipo_estudio_id:
        plantillas = plantillas.filter(tipo_estudio_id=tipo_estudio_id)
    
    if region_id:
        plantillas = plantillas.filter(region_id=region_id)
    
    # Filtrar por sistema: mostrar plantillas del sistema específico o universales
    plantillas = plantillas.filter(
        Q(sistema_destino=sistema_destino) | Q(sistema_destino='universal')
    )
    
    # Filtrar según permisos:
    # - Plantillas públicas: todos las ven
    # - Plantillas borrador: solo el creador las ve
    if request.user.is_authenticated:
        plantillas = plantillas.filter(
            Q(estado='publica') | Q(creada_por=request.user)
        )
    else:
        plantillas = plantillas.filter(estado='publica')
    
    plantillas_data = []
    for plantilla in plantillas.prefetch_related('versiones_institucionales'):
        version = next(
            (
                item for item in plantilla.versiones_institucionales.all()
                if item.vigente and item.propuesta_origen_id
            ),
            None,
        )
        plantillas_data.append({
            'id': (
                f'propuesta-{version.propuesta_origen_id}'
                if version else plantilla.id
            ),
            'nombre': plantilla.nombre,
            'contenido': (
                '' if version else _normalizar_html_editor(plantilla.contenido)
            ),
            'es_propia': (
                plantilla.creada_por == request.user
                if request.user.is_authenticated else False
            ),
            'es_propuesta_ia': bool(version),
            'es_institucional': bool(version),
            'estado': plantilla.estado,
            'sistema_destino': (
                'Institucional'
                if version else plantilla.get_sistema_destino_display()
            ),
        })

    propuestas = PropuestaPlantillaPreinforme.objects.filter(
        autor=request.user,
        estado__in=[
            PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
            PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
        ],
    )
    if tipo_estudio_id:
        propuestas = propuestas.filter(tipo_estudio_id=tipo_estudio_id)
    if region_id:
        propuestas = propuestas.filter(region_id=region_id)
    plantillas_data.extend([
        {
            'id': f'propuesta-{propuesta.pk}',
            'nombre': propuesta.estudio_especifico,
            'contenido': '',
            'es_propia': True,
            'es_propuesta_ia': True,
            'estado': propuesta.estado,
            'sistema_destino': 'Pendiente de aprobación',
        }
        for propuesta in propuestas
    ])
    
    return JsonResponse({'plantillas': plantillas_data})


@login_required
def propuesta_plantilla_json(request, pk):
    """Carga una propuesta propia pendiente o una versión institucional."""
    propuesta = get_object_or_404(
        PropuestaPlantillaPreinforme,
        Q(
            autor=request.user,
            estado__in=[
                PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
                PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
            ],
        ) | Q(
            estado=PropuestaPlantillaPreinforme.ESTADO_APROBADA,
            version_publicada__vigente=True,
            version_publicada__plantilla__activa=True,
            version_publicada__plantilla__estado='publica',
        ),
        pk=pk,
    )
    if propuesta.estado != PropuestaPlantillaPreinforme.ESTADO_APROBADA:
        TemplateGeneratorService().actualizar_contrato_propuesta(propuesta)
    from equipos.models import EquipoImagen
    equipos_queryset = EquipoImagen.objects.filter(en_servicio=True)
    area = _area_equipo_para_tipo_estudio(propuesta.tipo_estudio)
    if area:
        equipos_queryset = equipos_queryset.filter(area=area)
    return JsonResponse({
        'propuesta': {
            'id': propuesta.pk,
            'nombre': propuesta.estudio_especifico,
            'variables': propuesta.variables,
            'estado': propuesta.estado,
        },
        'equipos': list(
            equipos_queryset.values(
                'id', 'nombre', 'fabricante', 'modelo', 'area'
            ).order_by('area', 'nombre')
        ),
    })


@role_required('jefe_servicio')
def lista_validacion_plantillas(request):
    estado = request.GET.get('estado', 'pendientes')
    propuestas = PropuestaPlantillaPreinforme.objects.select_related(
        'autor', 'tipo_estudio', 'region', 'revisor',
    ).annotate(total_usos=Count('aplicaciones'))
    if estado == 'resueltas':
        propuestas = propuestas.filter(estado__in=[
            PropuestaPlantillaPreinforme.ESTADO_APROBADA,
            PropuestaPlantillaPreinforme.ESTADO_RECHAZADA,
        ])
    else:
        estado = 'pendientes'
        propuestas = propuestas.filter(estado__in=[
            PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
            PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
        ])
    return render(request, 'preinformes/plantillas_validacion_lista.html', {
        'propuestas': propuestas,
        'estado_filtro': estado,
        'pendientes_total': PropuestaPlantillaPreinforme.objects.filter(
            estado__in=[
                PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
                PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
            ],
        ).count(),
    })


@role_required('jefe_servicio')
def validar_plantilla(request, pk):
    propuesta = get_object_or_404(
        PropuestaPlantillaPreinforme.objects.select_related(
            'autor', 'tipo_estudio', 'region', 'revisor',
        ).annotate(total_usos=Count('aplicaciones')),
        pk=pk,
    )
    editable = propuesta.estado in {
        PropuestaPlantillaPreinforme.ESTADO_PENDIENTE,
        PropuestaPlantillaPreinforme.ESTADO_EN_REVISION,
    }
    if request.method == 'POST':
        if not editable:
            messages.error(request, 'La propuesta ya fue resuelta.')
            return redirect('preinformes:validar_plantilla', pk=pk)
        accion = request.POST.get('accion')
        observacion = request.POST.get('observacion_revision', '').strip()
        servicio = TemplateGeneratorService()
        try:
            servicio.actualizar_borrador(
                propuesta=propuesta,
                usuario=request.user,
                titulo=request.POST.get('titulo', ''),
                encabezado=request.POST.get('encabezado', ''),
                hallazgos=request.POST.get('hallazgos', ''),
            )
            if accion == 'aprobar':
                version = servicio.aprobar_y_publicar(
                    propuesta=propuesta,
                    usuario=request.user,
                    observacion=observacion,
                )
                messages.success(
                    request,
                    f'Plantilla aprobada y publicada como versión {version.numero}.',
                )
                return redirect('preinformes:lista_validacion_plantillas')
            if accion == 'rechazar':
                propuesta.rechazar(request.user, observacion)
                messages.success(request, 'La propuesta fue rechazada.')
                return redirect('preinformes:lista_validacion_plantillas')
            if propuesta.estado == PropuestaPlantillaPreinforme.ESTADO_PENDIENTE:
                propuesta.iniciar_revision(request.user)
            messages.success(request, 'Cambios guardados. La propuesta quedó en revisión.')
            return redirect('preinformes:validar_plantilla', pk=pk)
        except (GeneracionPlantillaError, ValidationError) as error:
            messages.error(request, str(error))

    return render(request, 'preinformes/plantillas_validacion_detalle.html', {
        'propuesta': propuesta,
        'editable': editable,
    })


@login_required
def plantilla_json(request, pk):
    """Endpoint JSON para obtener una plantilla específica"""
    try:
        plantilla = PlantillaPreinforme.objects.get(pk=pk, activa=True)
        
        # Verificar permisos: pública o creada por el usuario
        if plantilla.estado != 'publica' and plantilla.creada_por != request.user:
            return JsonResponse({'error': 'No tienes permiso para acceder a esta plantilla'}, status=403)
        
        data = {
            'contenido': _normalizar_html_editor(plantilla.contenido),
            'nombre': plantilla.nombre
        }
        
        return JsonResponse(data)
        
    except PlantillaPreinforme.DoesNotExist:
        return JsonResponse({'error': 'Plantilla no encontrada'}, status=404)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def crear_plantilla_residente(request):
    """Vista para que residentes creen nuevas plantillas (página completa)"""
    # Obtener tipo_estudio y region desde GET o sesión
    tipo_estudio_id = request.GET.get('tipo_estudio') or request.session.get('plantilla_tipo_estudio')
    region_id = request.GET.get('region') or request.session.get('plantilla_region')
    
    # Validar que no sean strings "None" o valores inválidos
    if tipo_estudio_id in [None, '', 'None', 'null'] or region_id in [None, '', 'None', 'null']:
        messages.error(request, 'Debes seleccionar primero el tipo de estudio y región en el formulario de preinforme.')
        return redirect('preinformes:crear_preinforme')
    
    try:
        tipo_estudio = TipoEstudio.objects.get(id=tipo_estudio_id)
        region = Region.objects.get(id=region_id)
    except (TipoEstudio.DoesNotExist, Region.DoesNotExist, ValueError):
        messages.error(request, 'Tipo de estudio o región no válidos.')
        return redirect('preinformes:crear_preinforme')
    
    # Guardar en sesión para persistencia
    request.session['plantilla_tipo_estudio'] = tipo_estudio_id
    request.session['plantilla_region'] = region_id
    
    if request.method == 'POST':
        form = NuevaPlantillaResidenteForm(
            request.POST,
            tipo_estudio=tipo_estudio,
            region=region
        )
        
        if form.is_valid():
            nombre = form.cleaned_data['nombre']
            compartir = form.cleaned_data.get('compartir', False)
            sistema_destino = form.cleaned_data['sistema_destino']
            
            # Verificar duplicados según el tipo de plantilla
            if compartir:
                # Para plantillas públicas: NO permitir duplicados
                plantilla_existente = PlantillaPreinforme.objects.filter(
                    nombre__iexact=nombre,
                    tipo_estudio=tipo_estudio,
                    region=region,
                    estado='publica',
                    sistema_destino=sistema_destino
                ).first()
                
                if plantilla_existente:
                    messages.error(
                        request,
                        f'❌ Ya existe una plantilla pública con el nombre "{nombre}" '
                        f'para {tipo_estudio.nombre} - {region.nombre} ({sistema_destino}). '
                        f'No se pueden crear plantillas públicas duplicadas. '
                        f'Cambia el nombre o usa la plantilla existente creada por '
                        f'{plantilla_existente.creada_por.get_full_name() or plantilla_existente.creada_por.username}.'
                    )
                    context = {
                        'form': form,
                        'tipo_estudio': tipo_estudio,
                        'region': region,
                        'plantilla_existente': plantilla_existente,
                        'mostrar_advertencia': True
                    }
                    return render(request, 'preinformes/crear_plantilla.html', context)
            else:
                # Para plantillas privadas: solo advertir si el mismo usuario tiene una similar
                plantilla_similar = PlantillaPreinforme.objects.filter(
                    nombre__iexact=nombre,
                    tipo_estudio=tipo_estudio,
                    region=region,
                    creada_por=request.user,
                    estado='borrador',
                    sistema_destino=sistema_destino
                ).first()
                
                if plantilla_similar:
                    messages.info(
                        request,
                        f'ℹ️ Ya tienes una plantilla privada con el nombre "{nombre}" '
                        f'para {tipo_estudio.nombre} - {region.nombre}. '
                        f'Se creará esta nueva plantilla de todas formas.'
                    )
            
            # Crear la plantilla
            plantilla = form.save(commit=False)
            plantilla.tipo_estudio = tipo_estudio
            plantilla.region = region
            plantilla.creada_por = request.user
            plantilla.activa = True
            plantilla.estado = 'publica' if compartir else 'borrador'
            plantilla.contenido = prepare_editor_html_content(plantilla.contenido)
            
            try:
                plantilla.save()
                
                messages.success(
                    request,
                    f'Plantilla "{plantilla.nombre}" creada exitosamente. ' +
                    ('Visible para todos.' if compartir else 'Solo visible para ti.')
                )
                
                # Redirigir al formulario de preinforme con la plantilla seleccionada
                return redirect(f"{reverse('preinformes:crear_preinforme')}?plantilla_id={plantilla.id}")
            
            except IntegrityError:
                # Ya existe una plantilla con el mismo nombre, tipo_estudio y región
                messages.error(
                    request,
                    f'Ya existe una plantilla con el nombre "{form.cleaned_data["nombre"]}" '
                    f'para {tipo_estudio.nombre} - {region.nombre}. '
                    f'Por favor, elige un nombre diferente.'
                )
                # Volver a renderizar el formulario con los datos ingresados
                return render(request, 'preinformes/crear_plantilla.html', {
                    'form': form,
                    'tipo_estudio': tipo_estudio,
                    'region': region,
                })
    else:
        form = NuevaPlantillaResidenteForm(
            tipo_estudio=tipo_estudio,
            region=region
        )
    
    context = {
        'form': form,
        'tipo_estudio': tipo_estudio,
        'region': region,
    }
    
    return render(request, 'preinformes/crear_plantilla.html', context)

@login_required
def autosave_preinforme(request, pk):
    """Endpoint para autoguardado de preinforme via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        preinforme = get_object_or_404(
            Preinforme, 
            pk=pk, 
            residente=request.user,
            estado__in=['borrador', 'pendiente_revision']
        )
        
        # Renovar marca de edición
        preinforme.marcar_en_edicion(request.user)
        
        # Obtener contenido del POST
        informe_html = request.POST.get('informe_html', '')
        
        # Guardar solo si hay cambios
        if preinforme.informe_html != informe_html:
            preinforme.informe_html = informe_html
            preinforme.save(update_fields=['informe_html'])
            return JsonResponse({
                'success': True,
                'message': 'Preinforme guardado automáticamente',
                'timestamp': timezone.localtime(preinforme.fecha_modificacion).strftime('%H:%M'),
            })
        else:
            return JsonResponse({
                'success': True,
                'message': 'Sin cambios para guardar',
                'timestamp': timezone.localtime(preinforme.fecha_modificacion).strftime('%H:%M'),
            })
            
    except Preinforme.DoesNotExist:
        return JsonResponse({'error': 'Preinforme no encontrado o no editable'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error al guardar: {str(e)}'}, status=500)


@login_required
def generar_informe_final(request, pk):
    """Obtener informe final actual de la revisión"""
    try:
        preinforme = get_object_or_404(_preinformes_visibles_para(request.user), pk=pk)
        
        # Verificar permisos
        if not (
            request.user == preinforme.revisor or
            request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
        ):
            return JsonResponse({'error': 'Sin permisos para acceder a esta revisión'}, status=403)
        
        # Obtener la revisión
        revision = get_object_or_404(RevisionPreinforme, preinforme=preinforme)
        
        # Retornar el informe final actual (ya editado por el staff)
        informe_final = revision.informe_final_html or ''
        
        return JsonResponse({
            'success': True,
            'informe_final': informe_final
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error obteniendo informe: {str(e)}'}, status=500)


@login_required
def copiar_informe_final(request, pk):
    """Copiar informe final al portapapeles"""
    preinforme = get_object_or_404(_preinformes_visibles_para(request.user), pk=pk)
    
    # Verificar permisos
    if not (
        request.user == preinforme.residente or 
        request.user == preinforme.revisor or
        request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'] or
        # Banco de informes: cualquier residente puede copiar un informe finalizado de un compañero
        (request.user.rol == 'medico_residente' and preinforme.estado == 'finalizado')
    ):
        return JsonResponse({'error': 'Sin permisos para ver este informe'}, status=403)
    
    # Obtener HTML e informe final
    if hasattr(preinforme, 'revision') and preinforme.revision.informe_final_html:
        # HTML con formato desde la revisión finalizada
        informe_html_original = preinforme.revision.informe_final_html
    else:
        # Si no hay revisión, usar el preinforme original con método unificado
        informe_html_original = preinforme.get_informe_html_or_legacy()

    payload = _construir_payload_exportacion(informe_html_original, preinforme.sistema_destino)
    return JsonResponse(payload)


# === VISTAS DE ESTADÍSTICAS ===

def _agregar_promedio_evaluacion_final_ia(residentes):
    """Agrega el promedio de la evaluacion IA posterior a la revision."""
    residentes = list(residentes)
    acumulados = {}
    revisiones = RevisionPreinforme.objects.filter(
        preinforme__residente_id__in=[residente.pk for residente in residentes],
        preinforme__es_registro_demo=False,
    ).exclude(evaluacion_ia_final={}).values_list(
        'preinforme__residente_id', 'evaluacion_ia_final'
    )

    for residente_id, evaluacion in revisiones:
        if not isinstance(evaluacion, dict):
            continue
        puntaje = evaluacion.get('puntaje_global')
        if isinstance(puntaje, (int, float)):
            acumulados.setdefault(residente_id, []).append(float(puntaje))

    for residente in residentes:
        puntajes = acumulados.get(residente.pk, [])
        residente.promedio_evaluacion_final_ia = (
            round(sum(puntajes) / len(puntajes), 1) if puntajes else None
        )
    return residentes


@login_required
@role_required('jefe_residentes', 'instructor_residentes', 'jefe_servicio')
def estadisticas(request):
    """Estadísticas generales del sistema"""
    # Estadísticas por residente
    residentes_stats = User.objects.filter(
        rol='medico_residente'
    ).annotate(
        total_preinformes=Count(
            'preinformes_realizados',
            filter=Q(preinformes_realizados__es_registro_demo=False),
        ),
        preinformes_finalizados=Count(
            'preinformes_realizados',
            filter=Q(
                preinformes_realizados__estado='finalizado',
                preinformes_realizados__es_registro_demo=False,
            )
        ),
        promedio_puntuacion=Avg(
            'preinformes_realizados__revision__puntuacion',
            filter=Q(preinformes_realizados__es_registro_demo=False),
        ),
        promedio_scoring_ia=Avg(
            'conversaciones_asistente_preinforme__puntuacion_global',
            filter=Q(conversaciones_asistente_preinforme__evaluada=True)
        ),
    ).order_by('-total_preinformes')
    residentes_stats = _agregar_promedio_evaluacion_final_ia(residentes_stats)
    
    # Estadísticas por tipo de estudio
    estudios_stats = TipoEstudio.objects.annotate(
        total_preinformes=Count(
            'preinforme',
            filter=Q(preinforme__es_registro_demo=False),
        )
    ).order_by('-total_preinformes')
    
    # Estadísticas temporales
    preinformes_mes_actual = Preinforme.objects.filter(
        es_registro_demo=False,
        fecha_creacion__month=timezone.now().month,
        fecha_creacion__year=timezone.now().year
    ).count()
    
    context = {
        'residentes_stats': residentes_stats,
        'estudios_stats': estudios_stats,
        'preinformes_mes_actual': preinformes_mes_actual,
        'title': 'Estadísticas del Sistema'
    }
    
    return render(request, 'preinformes/estadisticas.html', context)


@login_required
def panel_docencia(request):
    """
    Panel de actividad docente para administrativos del grupo 'Administrativo - Docencia'.
    Solo lectura — no expone contenido clínico de los informes.
    """
    if not (request.user.is_superuser or
            request.user.groups.filter(name='Administrativo - Docencia').exists()):
        messages.error(request, 'No tenés permisos para acceder a esta sección.')
        return redirect('home')

    residentes = User.objects.filter(
        rol='medico_residente',
        perfil_completo=True,
    ).annotate(
        total_preinformes=Count(
            'preinformes_realizados',
            filter=Q(preinformes_realizados__es_registro_demo=False),
            distinct=True,
        ),
        preinformes_finalizados=Count(
            'preinformes_realizados',
            filter=Q(
                preinformes_realizados__estado='finalizado',
                preinformes_realizados__es_registro_demo=False,
            ),
            distinct=True,
        ),
        preinformes_pendientes=Count(
            'preinformes_realizados',
            filter=Q(
                preinformes_realizados__estado__in=['borrador', 'pendiente_revision'],
                preinformes_realizados__es_registro_demo=False,
            ),
            distinct=True,
        ),
        promedio_puntuacion=Avg(
            'preinformes_realizados__revision__puntuacion',
            filter=Q(preinformes_realizados__es_registro_demo=False),
        ),
        promedio_ia=Avg(
            'conversaciones_asistente_preinforme__puntuacion_global',
            filter=Q(conversaciones_asistente_preinforme__evaluada=True),
        ),
        clases_subidas=Count('clases_creadas', distinct=True),
    ).order_by('anio_residencia', 'last_name', 'first_name')

    # Última actividad por residente (calculada en Python para compatibilidad con SQLite)
    ultima_actividad = {}
    for p in Preinforme.objects.filter(
        residente__in=residentes,
        es_registro_demo=False,
    ).order_by('residente_id', '-fecha_modificacion'):
        if p.residente_id not in ultima_actividad:
            ultima_actividad[p.residente_id] = p.fecha_modificacion

    residentes = _agregar_promedio_evaluacion_final_ia(residentes)
    residentes_data = []
    for r in residentes:
        r.ultima_actividad = ultima_actividad.get(r.pk)
        if r.promedio_puntuacion:
            r.promedio_puntuacion = round(float(r.promedio_puntuacion), 1)
        if r.promedio_ia:
            r.promedio_ia = round(float(r.promedio_ia), 1)
        residentes_data.append(r)

    context = {
        'residentes': residentes_data,
        'total_residentes': len(residentes_data),
    }
    return render(request, 'preinformes/panel_docencia.html', context)


@login_required
def ver_comparacion_revision(request, pk):
    """Vista para que el residente vea la comparación entre su versión y la del staff"""
    preinforme = get_object_or_404(_preinformes_visibles_para(request.user), pk=pk)
    
    # Verificar permisos: solo el residente autor o staff puede ver
    if not (
        request.user == preinforme.residente or
        request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    ):
        messages.error(request, 'No tienes permisos para ver esta revisión.')
        return redirect('preinformes:mis_preinformes')
    
    # Verificar que existe la revisión
    if not hasattr(preinforme, 'revision'):
        messages.error(request, 'Este preinforme no ha sido revisado aún.')
        return redirect('preinformes:ver_preinforme', pk=pk)
    
    revision = preinforme.revision
    
    # Si no hay snapshot, crearlo ahora (retrocompatibilidad)
    if not revision.informe_residente_snapshot:
        revision.crear_snapshot_residente()
    
    # Determinar si quien ve es el residente autor o el staff revisor
    es_residente = (request.user == preinforme.residente)
    es_staff = request.user.rol in ['medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    
    context = {
        'preinforme': preinforme,
        'revision': revision,
        'title': f'Comparación de Revisión - {preinforme.numero_estudio}',
        'es_residente': es_residente,
        'es_staff': es_staff,
    }
    
    return render(request, 'preinformes/comparacion_revision.html', context)


# === VISTAS PARA ETIQUETAS ===

@login_required
@require_http_methods(["POST"])
def agregar_etiquetas(request, pk):
    """Agregar etiquetas a un preinforme (AJAX)"""
    preinforme = get_object_or_404(Preinforme, pk=pk, residente=request.user)
    
    try:
        data = json.loads(request.body)
        etiquetas_nombres = data.get('etiquetas', [])
        
        if not isinstance(etiquetas_nombres, list):
            return JsonResponse({'success': False, 'error': 'Formato inválido'}, status=400)
        
        # Limpiar etiquetas existentes
        preinforme.etiquetas.clear()
        
        # Agregar las nuevas
        for nombre in etiquetas_nombres:
            nombre = nombre.strip()
            if nombre:
                # Obtener o crear etiqueta
                etiqueta, created = EtiquetaPreinforme.objects.get_or_create(
                    nombre__iexact=nombre,
                    defaults={
                        'nombre': nombre,
                        'creada_por': request.user
                    }
                )
                preinforme.etiquetas.add(etiqueta)
        
        # Devolver las etiquetas actualizadas
        etiquetas_actuales = list(preinforme.etiquetas.values('id', 'nombre', 'color'))
        
        return JsonResponse({
            'success': True,
            'etiquetas': etiquetas_actuales
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def buscar_etiquetas(request):
    """Buscar etiquetas para autocomplete (AJAX)"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        # Devolver las más usadas
        etiquetas = EtiquetaPreinforme.objects.annotate(
            num_usos=Count('preinformes')
        ).order_by('-num_usos')[:10]
    else:
        # Buscar por nombre
        etiquetas = EtiquetaPreinforme.objects.filter(
            nombre__icontains=query
        ).order_by('nombre')[:10]
    
    resultados = [
        {'id': e.id, 'nombre': e.nombre, 'color': e.color}
        for e in etiquetas
    ]
    
    return JsonResponse({'etiquetas': resultados})


@login_required
def verificar_duplicado_preinforme(request):
    """Verificar si existe un preinforme duplicado (AJAX)"""
    if request.user.is_demo_user:
        return JsonResponse(
            {'error': 'La verificación de datos de paciente no está disponible en modo demo.'},
            status=403,
        )

    numero_estudio = request.GET.get('numero_estudio', '').strip()
    dni_paciente = request.GET.get('dni_paciente', '').strip()
    tipo_estudio_id = request.GET.get('tipo_estudio')
    preinforme_actual_id = request.GET.get('preinforme_id')  # Para excluir en edición
    
    duplicados = []
    
    # Buscar por número de estudio (más preciso)
    if numero_estudio:
        query = Preinforme.objects.filter(
            numero_estudio__iexact=numero_estudio,
            es_registro_demo=False,
        )
        
        # Excluir el preinforme actual si estamos editando
        if preinforme_actual_id:
            query = query.exclude(pk=preinforme_actual_id)
        
        for p in query.select_related('residente', 'tipo_estudio', 'region')[:5]:
            duplicados.append({
                'id': p.pk,
                'numero_estudio': p.numero_estudio,
                'paciente': f"{p.apellido_paciente}, {p.nombre_paciente}",
                'dni': p.dni_paciente,
                'tipo_estudio': p.tipo_estudio.nombre,
                'region': p.region.nombre,
                'estado': p.get_estado_display(),
                'estado_code': p.estado,
                'residente': f"{p.residente.first_name} {p.residente.last_name}",
                'fecha': p.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'criterio': 'numero_estudio'
            })
    
    # Buscar por DNI + tipo de estudio similar (menos preciso pero útil)
    if dni_paciente and tipo_estudio_id and not duplicados:
        try:
            query = Preinforme.objects.filter(
                dni_paciente__iexact=dni_paciente,
                tipo_estudio_id=tipo_estudio_id,
                es_registro_demo=False,
            )
            
            if preinforme_actual_id:
                query = query.exclude(pk=preinforme_actual_id)
            
            for p in query.select_related('residente', 'tipo_estudio', 'region')[:3]:
                duplicados.append({
                    'id': p.pk,
                    'numero_estudio': p.numero_estudio,
                    'paciente': f"{p.apellido_paciente}, {p.nombre_paciente}",
                    'dni': p.dni_paciente,
                    'tipo_estudio': p.tipo_estudio.nombre,
                    'region': p.region.nombre,
                    'estado': p.get_estado_display(),
                    'estado_code': p.estado,
                    'residente': f"{p.residente.first_name} {p.residente.last_name}",
                    'fecha': p.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                    'criterio': 'dni_tipo'
                })
        except (ValueError, TypeError):
            pass
    
    return JsonResponse({
        'duplicados': duplicados,
        'total': len(duplicados)
    })


# ======================================================================
# ASISTENTE IA RADIÓLOGO MENTOR
# ======================================================================

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def asistente_preinforme_chat(request):
    """
    Endpoint AJAX para el asistente IA de elaboración de preinformes.
    Recibe el mensaje del residente y el contexto del estudio actual.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    mensaje = data.get('mensaje', '').strip()
    conversacion_id = data.get('conversacion_id')
    contexto_raw = data.get('contexto', {})

    if not mensaje:
        return JsonResponse({'success': False, 'error': 'El mensaje no puede estar vacío'}, status=400)

    if len(mensaje) > 500:
        return JsonResponse({'success': False, 'error': 'Mensaje demasiado largo (máx. 500 caracteres)'}, status=400)

    # Rate limiting: máximo 30 mensajes por hora por usuario
    cache_key = f'asistente_preinforme_rate_{request.user.id}'
    mensajes_enviados = cache.get(cache_key, 0)
    if mensajes_enviados >= 30:
        return JsonResponse({
            'success': False,
            'error': 'Alcanzaste el límite de 30 mensajes por hora. Intentá más tarde.'
        }, status=429)

    # Armar contexto seguro (nunca enviar nombre ni DNI)
    contexto_estudio = {
        'tipo_estudio': contexto_raw.get('tipo_estudio', ''),
        'region': contexto_raw.get('region', ''),
        'edad': contexto_raw.get('edad', ''),
        'sexo': contexto_raw.get('sexo', ''),
        'contexto_clinico': contexto_raw.get('contexto_clinico', ''),
        'contenido_editor': contexto_raw.get('contenido_editor', ''),
    }

    from .asistente_service import AsistenteRadiologicoBot
    bot = AsistenteRadiologicoBot()
    resultado = bot.chat(
        usuario=request.user,
        mensaje=mensaje,
        conversacion_id=conversacion_id,
        contexto_estudio=contexto_estudio
    )

    # Incrementar rate limiting solo si el request fue válido
    cache.set(cache_key, mensajes_enviados + 1, 3600)

    if resultado['success']:
        return JsonResponse({
            'success': True,
            'respuesta': resultado['respuesta'],
            'conversacion_id': resultado['conversacion_id'],
            'mensaje_id': resultado.get('mensaje_id'),
        })
    else:
        return JsonResponse({'success': False, 'error': resultado['error']}, status=500)


@login_required
@require_http_methods(["POST"])
def asistente_preinforme_feedback(request):
    """
    Endpoint AJAX para registrar feedback (👍/👎) sobre respuestas del asistente.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    mensaje_id = data.get('mensaje_id')
    feedback = data.get('feedback')

    if not mensaje_id or feedback not in ('positivo', 'negativo'):
        return JsonResponse({'success': False, 'error': 'Parámetros inválidos'}, status=400)

    from .models import MensajeAsistentePreinforme
    try:
        mensaje = MensajeAsistentePreinforme.objects.select_related(
            'conversacion'
        ).get(id=mensaje_id)
    except MensajeAsistentePreinforme.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Mensaje no encontrado'}, status=404)

    if mensaje.conversacion.usuario != request.user:
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

    if mensaje.rol != 'assistant':
        return JsonResponse({'success': False, 'error': 'Solo se puede valorar respuestas del asistente'}, status=400)

    mensaje.feedback = feedback
    mensaje.save(update_fields=['feedback'])

    return JsonResponse({'success': True})


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio')
@require_http_methods(["POST"])
def asistente_preinforme_evaluar(request):
    """
    Endpoint AJAX para evaluar la calidad del razonamiento del residente.
    Exclusivo para roles docentes (jefe_residentes, instructor_residentes, jefe_servicio).
    Los médicos residentes no pueden disparar evaluaciones.
    """
    ROLES_DOCENTES = ('jefe_residentes', 'instructor_residentes', 'jefe_servicio')
    if not (request.user.is_superuser or request.user.rol in ROLES_DOCENTES):
        return JsonResponse({'success': False, 'error': 'Sin permiso'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    conversacion_id = data.get('conversacion_id')
    if not conversacion_id:
        return JsonResponse({'success': False, 'error': 'Falta conversacion_id'}, status=400)

    from .asistente_service import AsistenteRadiologicoBot
    bot = AsistenteRadiologicoBot()
    # La conversación pertenece al residente, no al docente que dispara la evaluación.
    resultado = bot.evaluar_conversacion(conversacion_id)

    if not resultado['success']:
        status_code = 400 if resultado.get('insufficient') else 500
        return JsonResponse(resultado, status=status_code)

    return JsonResponse(resultado)


@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
@require_http_methods(["POST"])
def asistente_analizar_borrador(request):
    """
    Endpoint AJAX para análisis proactivo del borrador del preinforme.
    La IA detecta problemas (terminología, ortografía, redundancias) y
    retorna un mensaje socrático si encuentra algo relevante.
    Rate limit: 1 llamada / 60s por usuario.
    """
    rate_key = f'analizar_borrador_{request.user.pk}'
    if cache.get(rate_key):
        return JsonResponse({'success': True, 'tiene_observacion': False, 'rate_limited': True})

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)

    contenido_html = data.get('contenido_html', '')
    tipo_estudio = data.get('tipo_estudio', '')
    region = data.get('region', '')

    if not contenido_html or len(contenido_html.strip()) < 50:
        return JsonResponse({'success': True, 'tiene_observacion': False})

    cache.set(rate_key, True, timeout=60)

    from .asistente_service import AsistenteRadiologicoBot
    bot = AsistenteRadiologicoBot()
    resultado = bot.analizar_borrador(
        contenido_html=contenido_html,
        tipo_estudio=tipo_estudio,
        region=region,
    )
    return JsonResponse(resultado)


@login_required
def perfil_residente_docente(request, pk):
    """
    Perfil de un residente con historial de evaluaciones del Asistente IA.
    Accesible para roles docentes y el grupo 'Administrativo - Docencia'.
    """
    roles_docentes = ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']
    es_admin_docencia = request.user.groups.filter(name='Administrativo - Docencia').exists()
    if not (request.user.is_superuser or
            request.user.rol in roles_docentes or
            es_admin_docencia):
        messages.error(request, 'No tenés permisos para acceder a esta sección.')
        return redirect('home')
    residente = get_object_or_404(User, pk=pk, rol='medico_residente')

    from .models import ConversacionAsistentePreinforme
    from django.db.models import Avg as _Avg

    conversaciones_evaluadas = ConversacionAsistentePreinforme.objects.filter(
        usuario=residente,
        evaluada=True,
        preinforme__es_registro_demo=False,
    ).select_related('preinforme__tipo_estudio', 'preinforme__region').order_by('-fecha_actualizacion')

    promedio_scoring = conversaciones_evaluadas.aggregate(
        promedio=_Avg('puntuacion_global')
    )['promedio']
    if promedio_scoring is not None:
        promedio_scoring = round(promedio_scoring, 1)

    revisiones_evaluadas_qs = RevisionPreinforme.objects.filter(
        preinforme__residente=residente,
        preinforme__es_registro_demo=False,
    ).exclude(evaluacion_ia_final={}).select_related(
        'preinforme__tipo_estudio', 'preinforme__region', 'revisor'
    ).order_by('-evaluacion_ia_final_generada_en', '-fecha_modificacion')
    puntajes_finales = [
        revision.evaluacion_ia_final.get('puntaje_global')
        for revision in revisiones_evaluadas_qs
        if isinstance(revision.evaluacion_ia_final.get('puntaje_global'), (int, float))
    ]
    promedio_evaluacion_final = (
        round(sum(puntajes_finales) / len(puntajes_finales), 1)
        if puntajes_finales else None
    )
    revisiones_paginator = Paginator(revisiones_evaluadas_qs, 10)
    revisiones_evaluadas = revisiones_paginator.get_page(
        request.GET.get('evaluaciones_page')
    )

    # Promedios por dimensión (calculados en Python desde el JSONField)
    dims_acum = {'razonamiento_clinico': [], 'terminologia': [], 'autonomia': [], 'receptividad': []}
    for conv in conversaciones_evaluadas:
        ev = conv.evaluacion_ia or {}
        for dim in dims_acum:
            val = ev.get(dim)
            if isinstance(val, (int, float)):
                dims_acum[dim].append(val)

    promedios_dims = {
        dim: round(sum(vals) / len(vals), 1) if vals else None
        for dim, vals in dims_acum.items()
    }

    historial = HistorialEstudios.objects.filter(residente=residente).first()

    context = {
        'residente': residente,
        'conversaciones_evaluadas': conversaciones_evaluadas,
        'promedio_scoring': promedio_scoring,
        'revisiones_evaluadas': revisiones_evaluadas,
        'promedio_evaluacion_final': promedio_evaluacion_final,
        'promedios_dims': promedios_dims,
        'historial': historial,
    }
    return render(request, 'preinformes/perfil_residente_docente.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# ENCUESTA CADI 2026
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@role_required('medico_residente', 'jefe_residentes', 'instructor_residentes')
def encuesta_uso(request):
    """Formulario de encuesta de experiencia para residentes. Una sola vez por residente."""
    # Si ya respondió, redirigir a su dashboard
    if EncuestaResidente.objects.filter(residente=request.user).exists():
        messages.info(request, 'Ya completaste la encuesta. ¡Gracias por tu participación!')
        return redirect('preinformes:dashboard_residente')

    PREGUNTAS_LIKERT = [
        ('p1_usabilidad',       'El sistema es fácil de usar'),
        ('p2_acceso',           'Acceder desde mi dispositivo es cómodo'),
        ('p3_feedback_util',    'Los comentarios del staff fueron útiles para mi aprendizaje'),
        ('p4_feedback_oportuno','El feedback fue oportuno (llegó en tiempo razonable)'),
        ('p5_mejora_redaccion', 'Siento que mejoré mi redacción de informes usando el sistema'),
        ('p6_banco_informes',   'El banco de informes me ayudó como referencia'),
        ('p7_comparacion',      'Comparando con lo que describiste arriba, este sistema mejoró mi proceso de trabajo'),
        ('p8_ia_asistente',     'El asistente IA (Radiólogo Mentor) fue útil'),
        ('p9_supervision',      'La supervisión del staff se volvió más estructurada'),
        ('p10_recomendacion',   'Recomendaría este sistema a otros servicios de residencia'),
    ]

    if request.method == 'POST':
        errores = []
        datos = {}

        # Validar Likert (1-5)
        for campo, _ in PREGUNTAS_LIKERT:
            if campo == 'p7_comparacion':
                continue  # se valida por separado después de la abierta
            val = request.POST.get(campo)
            if not val or not val.isdigit() or not (1 <= int(val) <= 5):
                errores.append(f"Respondé la pregunta requerida ({campo}).")
            else:
                datos[campo] = int(val)

        # p7 comparación
        val7 = request.POST.get('p7_comparacion')
        if not val7 or not val7.isdigit() or not (1 <= int(val7) <= 5):
            errores.append("Respondé la pregunta de comparación.")
        else:
            datos['p7_comparacion'] = int(val7)

        # Campos abiertos (no obligatorios)
        datos['p_contexto_previo'] = request.POST.get('p_contexto_previo', '').strip()
        datos['p_util']   = request.POST.get('p_util', '').strip()
        datos['p_mejora'] = request.POST.get('p_mejora', '').strip()
        datos['anonimizar'] = request.POST.get('anonimizar') == 'on'

        if errores:
            messages.error(request, 'Por favor completá todas las preguntas obligatorias.')
            return render(request, 'preinformes/encuesta_uso.html', {
                'preguntas_likert': PREGUNTAS_LIKERT,
                'post_data': request.POST,
            })

        EncuestaResidente.objects.create(residente=request.user, **datos)
        messages.success(request, '¡Gracias por completar la encuesta! Tu opinión es muy valiosa.')
        return redirect('preinformes:dashboard_residente')

    return render(request, 'preinformes/encuesta_uso.html', {
        'preguntas_likert': PREGUNTAS_LIKERT,
        'post_data': {},
    })


@login_required
def resultados_encuesta(request):
    """Panel de resultados de la encuesta — visible para staff y superusuarios."""
    from django.db.models import Avg
    from dictado_informes.ai_services import ai_service

    if not (request.user.is_superuser or request.user.rol in [
        'medico_staff', 'jefe_residentes', 'instructor_residentes', 'jefe_servicio'
    ]):
        messages.error(request, 'No tenés permisos para ver esta sección.')
        return redirect('preinformes:dashboard_residente')

    encuestas = EncuestaResidente.objects.select_related('residente').all()
    n = encuestas.count()

    if n == 0:
        return render(request, 'preinformes/resultados_encuesta.html', {
            'n': 0, 'promedios': {}, 'encuestas': [], 'analisis_ia': None
        })

    # Calcular promedios
    agg = encuestas.aggregate(
        p1=Avg('p1_usabilidad'), p2=Avg('p2_acceso'),
        p3=Avg('p3_feedback_util'), p4=Avg('p4_feedback_oportuno'),
        p5=Avg('p5_mejora_redaccion'), p6=Avg('p6_banco_informes'),
        p7=Avg('p7_comparacion'), p8=Avg('p8_ia_asistente'),
        p9=Avg('p9_supervision'), p10=Avg('p10_recomendacion'),
    )
    promedios = {k: round(v, 2) if v else 0 for k, v in agg.items()}
    promedio_global = round(sum(promedios.values()) / len(promedios), 2)

    # Respuestas abiertas (se anonimiza el nombre si el residente lo pidió)
    def get_abiertas(campo):
        return [
            getattr(e, campo)
            for e in encuestas
            if getattr(e, campo, '').strip()
        ]

    respuestas_abiertas = {
        'contexto_previo': get_abiertas('p_contexto_previo'),
        'util':   get_abiertas('p_util'),
        'mejora': get_abiertas('p_mejora'),
    }

    analisis_ia = None
    regenerar = request.GET.get('regenerar') == '1'

    if regenerar or request.method == 'POST':
        datos_para_ia = {
            'n_respuestas': n,
            'promedios': promedios,
            'promedio_global': promedio_global,
            'respuestas_abiertas': respuestas_abiertas,
        }
        analisis_ia = ai_service.analizar_resultados_encuesta(datos_para_ia)
        # Normalizar etiquetas de hallazgos para el template
        _LABELS_HALLAZGOS = {
            'usabilidad': 'Usabilidad',
            'feedback': 'Feedback del staff',
            'aprendizaje': 'Aprendizaje',
            'comparacion': 'Comparación',
            'ia_y_supervision': 'IA y Supervisión',
            'recomendacion': 'Recomendación',
        }
        if analisis_ia and 'error' not in analisis_ia and 'hallazgos_por_dimension' in analisis_ia:
            analisis_ia['hallazgos_por_dimension'] = {
                _LABELS_HALLAZGOS.get(k, k.replace('_', ' ').title()): v
                for k, v in analisis_ia['hallazgos_por_dimension'].items()
            }
        # Guardar en la última encuesta (referencia global)
        if analisis_ia and 'error' not in analisis_ia:
            encuestas.last().encuesta_set if False else None  # no-op
            # Guardamos en la propia instancia del modelo para persistencia
            EncuestaResidente.objects.filter(pk=encuestas.last().pk).update(analisis_ia=analisis_ia)

    # Tabla de respuestas individuales (respetando anonimato)
    tabla = []
    for e in encuestas:
        tabla.append({
            'nombre': 'Anónimo' if e.anonimizar else e.residente.get_full_name(),
            'anio': getattr(e.residente, 'anio_residencia', '—'),
            'promedio': round(e.promedio_likert, 2),
            'fecha': e.fecha_respuesta,
        })

    LABELS = {
        'p1': 'Usabilidad general',
        'p2': 'Comodidad de acceso',
        'p3': 'Utilidad del feedback del staff',
        'p4': 'Oportunidad del feedback',
        'p5': 'Mejora en redacción de informes',
        'p6': 'Banco de informes como referencia',
        'p7': 'Mejora respecto al método anterior',
        'p8': 'Utilidad del asistente IA',
        'p9': 'Supervisión más estructurada',
        'p10': 'Recomendaría a otros servicios',
    }
    promedios_lista = [(LABELS.get(k, k), k, v) for k, v in promedios.items()]

    context = {
        'n': n,
        'promedios': promedios,
        'promedios_lista': promedios_lista,
        'promedio_global': promedio_global,
        'tabla': tabla,
        'analisis_ia': analisis_ia,
        'respuestas_abiertas': respuestas_abiertas,
    }
    return render(request, 'preinformes/resultados_encuesta.html', context)
