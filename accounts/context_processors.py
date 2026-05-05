"""
Context processor para el navbar dinámico.
Construye los grupos de navegación según el rol del usuario.

Grupos disponibles: Recursos · Docencia · Guardias · Gestión
Único grupo Django activo: 'Administrativo - Docencia'
"""

from django.urls import reverse, NoReverseMatch


def _resolve(url_name):
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def _has_group(user, group_name):
    return user.groups.filter(name=group_name).exists()


def _is_active(request, ns=None, url_names=None, exclude_url_names=None):
    match = request.resolver_match
    if not match:
        return False
    current_url_name = match.url_name or ''
    if exclude_url_names and any(ex in current_url_name for ex in exclude_url_names):
        return False
    if ns and match.namespace == ns:
        return True
    if url_names and any(u in current_url_name for u in url_names):
        return True
    return False


def navbar_links(request):
    """
    Retorna {'nav_groups': [...]} con la estructura de navegación para el usuario actual.
    Cada grupo: {'label', 'icon', 'active', 'items': [{'label', 'icon', 'url', 'active'}]}
    """
    if not request.user.is_authenticated:
        return {'nav_groups': []}

    user = request.user

    def item(label, icon, url_name, active_ns=None, active_url_names=None, exclude_url_names=None):
        url = _resolve(url_name)
        if url is None:
            return None
        return {
            'label': label,
            'icon': icon,
            'url': url,
            'active': _is_active(
                request,
                ns=active_ns,
                url_names=active_url_names,
                exclude_url_names=exclude_url_names,
            ),
        }

    def group(label, icon, *items_list):
        valid = [i for i in items_list if i is not None]
        if not valid:
            return None
        return {
            'label': label,
            'icon': icon,
            'active': any(i['active'] for i in valid),
            'items': valid,
        }

    # ── Items reutilizables ───────────────────────────────────────────────────
    def i_protocolos():
        return item('Protocolos', 'fa-book-medical',
                    'protocolos:elegir', active_ns='protocolos')

    def i_stock():
        return item('Stock', 'fa-boxes',
                    'control_stock:dashboard', active_ns='control_stock')

    def i_novedades():
        return item('Novedades', 'fa-bell',
                    'gestion_eventos:lista_eventos', active_ns='gestion_eventos')

    def i_clases():
        return item('Clases', 'fa-graduation-cap',
                    'clases_residentes:lista', active_ns='clases_residentes',
                    exclude_url_names=['guia_presentaciones'])

    def i_guia():
        return item('Guía de Presentaciones', 'fa-lightbulb',
                    'clases_residentes:guia_presentaciones',
                    active_url_names=['guia_presentaciones'])

    def i_preinformes():
        return item('Preinformes', 'fa-file-medical',
                    'preinformes:dashboard_residente', active_ns='preinformes',
                    exclude_url_names=['staff', 'revision', 'banco'])

    def i_banco():
        return item('Banco de Informes', 'fa-archive',
                    'preinformes:lista_banco_informes',
                    active_url_names=['banco'])

    def i_revision():
        return item('Revisión', 'fa-user-md',
                    'preinformes:dashboard_staff',
                    active_url_names=['staff', 'revision'],
                    exclude_url_names=['banco'])

    def i_pedidos():
        return item('Pedidos de Estudios', 'fa-clipboard-list',
                    'pedidos_estudios:dashboard', active_ns='pedidos_estudios')

    def i_dictado_rapido():
        return item('Dictado Rápido', 'fa-microphone-lines',
                    'dictado_informes:dictado_rapido', active_url_names=['dictado_rapido'])

    def i_plantillas_estructuradas():
        return item('Plantillas Estructuradas', 'fa-layer-group',
                    'dictado_informes:plantilla_estructurada_list', active_url_names=['plantilla_estructurada'])

    # def i_demo_dictado_ia():  # SILENCIADA — reactivar descomentando
    #     return item('Demo IA Colegiales', 'fa-person-chalkboard',
    #                 'dictado_informes:demo_presentacion_ia',
    #                 active_url_names=['demo_presentacion_ia'])

    def i_consultorios():
        return item('Consultorios', 'fa-door-open',
                    'consultorios:dashboard', active_ns='consultorios')

    groups = []

    # ── SUPERUSUARIO ──────────────────────────────────────────────────────────
    if user.is_superuser:
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_stock(),
                i_novedades(),
            ),
            group('Docencia', 'fa-graduation-cap',
                i_clases(),
                i_guia(),
                i_preinformes(),
                i_revision(),
                i_banco(),
                item('CADI 2026', 'fa-chart-bar',
                     'preinformes:resultados_encuesta',
                     active_url_names=['resultados_encuesta']),
            ),
            group('Dictado IA', 'fa-wave-square',
                i_dictado_rapido(),
                i_plantillas_estructuradas(),
                # i_demo_dictado_ia(),  # SILENCIADA
            ),
            group('Guardias', 'fa-shield-alt',
                item('Portal de Guardias', 'fa-calendar-alt',
                     'control_guardias:index', active_ns='control_guardias'),
            ),
            group('Gestión', 'fa-cogs',
                i_pedidos(),
                i_consultorios(),
            ),
        ] if g]

    # ── MÉDICO RESIDENTE ───────────────────────────────────────────────────────
    elif user.rol == 'medico_residente':
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_stock(),
                i_novedades(),
            ),
            group('Docencia', 'fa-graduation-cap',
                i_clases(),
                i_guia(),
                i_preinformes(),
                i_banco(),
            ),
            group('Guardias', 'fa-shield-alt',
                item('Mis Guardias', 'fa-calendar-alt',
                     'control_guardias:index', active_ns='control_guardias'),
            ),
        ] if g]

    # ── JEFE DE RESIDENTES / INSTRUCTOR ───────────────────────────────────────
    elif user.rol in ('jefe_residentes', 'instructor_residentes'):
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_stock(),
                i_novedades(),
            ),
            group('Docencia', 'fa-graduation-cap',
                i_clases(),
                i_guia(),
                i_preinformes(),
                i_revision(),
                i_banco(),
            ),
            group('Guardias', 'fa-shield-alt',
                item('Portal de Guardias', 'fa-calendar-alt',
                     'control_guardias:index', active_ns='control_guardias'),
            ),
            # Para habilitar Pedidos de Estudios, agregar aquí:
            # group('Gestión', 'fa-cogs',
            #     i_pedidos(),
            # ),
        ] if g]
    elif user.rol == 'medico_staff':
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_stock(),
                i_novedades(),
            ),
            group('Docencia', 'fa-graduation-cap',
                i_revision(),
            ),
        ] if g]

    # ── JEFE DE SERVICIO ───────────────────────────────────────────────────────
    elif user.rol == 'jefe_servicio':
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_stock(),
                i_novedades(),
            ),
            group('Docencia', 'fa-graduation-cap',
                i_revision(),
            ),
            group('Gestión', 'fa-cogs',
                i_pedidos(),
                i_consultorios(),
            ),
        ] if g]

    # ── TÉCNICO RADIÓLOGO ──────────────────────────────────────────────────────
    elif user.rol == 'tecnico':
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_stock(),
                i_novedades(),
            ),
        ] if g]

    # ── CARDIÓLOGO ────────────────────────────────────────────────────────────
    elif user.rol == 'cardiologo':
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_protocolos(),
                i_novedades(),
            ),
        ] if g]

    # ── ADMINISTRATIVO ────────────────────────────────────────────────────────
    # Grupo Django: 'Administrativo - Docencia' → Clases + Panel Docente
    elif user.rol == 'administrativo':
        es_docencia = _has_group(user, 'Administrativo - Docencia')
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_novedades(),
            ),
            group('Docencia', 'fa-graduation-cap',
                item('Guía de Ateneos', 'fa-lightbulb',
                     'clases_residentes:guia_presentaciones',
                     active_url_names=['guia_presentaciones']),
                item('Clases de Residentes', 'fa-graduation-cap',
                     'clases_residentes:lista', active_ns='clases_residentes',
                     exclude_url_names=['guia_presentaciones']) if es_docencia else None,
                item('Panel Docente', 'fa-chart-line',
                     'preinformes:panel_docencia',
                     active_url_names=['panel_docencia']) if es_docencia else None,
            ),
            group('Gestión', 'fa-cogs',
                i_consultorios(),
            ),
        ] if g]

    # ── PILOTO DICTADO IA ───────────────────────────────────────────────────
    elif user.rol == 'piloto_dictado':
        groups = [g for g in [
            group('Dictado IA', 'fa-wave-square',
                i_dictado_rapido(),
                i_plantillas_estructuradas(),
            ),
        ] if g]

    # ── ENFERMERÍA / OTRO ──────────────────────────────────────────────────────
    elif user.rol in ('enfermeria', 'otro'):
        groups = [g for g in [
            group('Recursos', 'fa-toolbox',
                i_novedades(),
            ),
        ] if g]

    return {'nav_groups': groups}


def consultorios_badges(request):
    """
    Inyecta en todos los templates el contador de tareas EGES pendientes
    y solicitudes de agenda extra pendientes de aprobación.
    Solo activo si el usuario está autenticado y tiene rol relevante.
    """
    if not request.user.is_authenticated:
        return {}

    user = request.user
    rol = getattr(user, 'rol', None)

    tareas_eges_pendientes = 0
    solicitudes_extra_pendientes = 0

    try:
        if user.is_superuser or rol in ('administrativo', 'jefe_servicio'):
            from consultorios.models import TareaAgendaEGES, EstadoTareaEGES, SolicitudAgendaExtra, EstadoSolicitudExtra
            tareas_eges_pendientes = TareaAgendaEGES.objects.filter(
                estado=EstadoTareaEGES.PENDIENTE
            ).count()

        if user.is_superuser or rol == 'jefe_servicio':
            from consultorios.models import SolicitudAgendaExtra, EstadoSolicitudExtra
            solicitudes_extra_pendientes = SolicitudAgendaExtra.objects.filter(
                estado=EstadoSolicitudExtra.PENDIENTE
            ).count()
    except Exception:
        pass

    return {
        'tareas_eges_pendientes': tareas_eges_pendientes,
        'solicitudes_extra_pendientes': solicitudes_extra_pendientes,
    }
