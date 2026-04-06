from django.urls import path

from .views import (
    AusenciasView,
    BorradorView,
    CalendarioView,
    CancelarBorradorView,
    CancelarCambioView,
    CambiosGuardiaView,
    ConfiguracionView,
    CuotaMensualFormView,
    DistribucionView,
    FeriadoCreateView,
    FeriadoDeleteView,
    GuardiasApiView,
    GuardiasIndexView,
    MisGuardiasView,
    NotificacionesGuardiaView,
    PublicarBorradorView,
    ReportarAusenciaView,
    ResolverAusenciaView,
    ResponderCambioView,
    RevisarCambioView,
    SolicitarCambioView,
    TipoGuardiaCreateView,
    TipoGuardiaDeleteView,
    TipoGuardiaUpdateView,
)

app_name = 'control_guardias'

urlpatterns = [
    # -- Vistas generales --
    path('', GuardiasIndexView.as_view(), name='index'),
    path('calendario/', CalendarioView.as_view(), name='calendario'),
    path('mis-guardias/', MisGuardiasView.as_view(), name='mis_guardias'),
    path('notificaciones/', NotificacionesGuardiaView.as_view(), name='notificaciones'),
    path('api/guardias/', GuardiasApiView.as_view(), name='guardias_api'),

    # -- Configuración (jefes/instructores) --
    path('configuracion/', ConfiguracionView.as_view(), name='configuracion'),

    # Tipos de guardia
    path('configuracion/tipos/nuevo/', TipoGuardiaCreateView.as_view(), name='tipo_guardia_crear'),
    path('configuracion/tipos/<int:pk>/editar/', TipoGuardiaUpdateView.as_view(), name='tipo_guardia_editar'),
    path('configuracion/tipos/<int:pk>/eliminar/', TipoGuardiaDeleteView.as_view(), name='tipo_guardia_eliminar'),

    # Cuotas mensuales
    path('configuracion/cuotas/<str:anio>/editar/', CuotaMensualFormView.as_view(), name='cuota_editar'),

    # Feriados
    path('configuracion/feriados/nuevo/', FeriadoCreateView.as_view(), name='feriado_crear'),
    path('configuracion/feriados/<int:pk>/eliminar/', FeriadoDeleteView.as_view(), name='feriado_eliminar'),

    # -- Distribución automática (Fase 3) --
    path('configuracion/distribucion/', DistribucionView.as_view(), name='distribucion'),
    path('configuracion/distribucion/<int:mes>/<int:anio>/', BorradorView.as_view(), name='distribucion_borrador'),
    path('configuracion/distribucion/<int:mes>/<int:anio>/publicar/', PublicarBorradorView.as_view(), name='distribucion_publicar'),
    path('configuracion/distribucion/<int:mes>/<int:anio>/cancelar/', CancelarBorradorView.as_view(), name='distribucion_cancelar'),

    # -- Ausencias (Fase 5) --
    path('ausencias/', AusenciasView.as_view(), name='ausencias'),
    path('ausencias/reportar/', ReportarAusenciaView.as_view(), name='ausencia_reportar'),
    path('ausencias/<int:pk>/resolver/', ResolverAusenciaView.as_view(), name='ausencia_resolver'),

    # -- Cambios de guardia (Fase 5) --
    path('cambios/', CambiosGuardiaView.as_view(), name='cambios'),
    path('guardias/<int:guardia_pk>/solicitar-cambio/', SolicitarCambioView.as_view(), name='solicitar_cambio'),
    path('cambios/<int:pk>/responder/', ResponderCambioView.as_view(), name='cambio_responder'),
    path('cambios/<int:pk>/revisar/', RevisarCambioView.as_view(), name='cambio_revisar'),
    path('cambios/<int:pk>/cancelar/', CancelarCambioView.as_view(), name='cambio_cancelar'),
]

