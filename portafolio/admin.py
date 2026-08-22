from django.contrib import admin

from .models import ActividadCurricular, DocumentoActividadCurricular


class DocumentoActividadInline(admin.TabularInline):
    model = DocumentoActividadCurricular
    extra = 0
    readonly_fields = ('nombre_original', 'tipo_mime', 'tamanio_bytes', 'sha256')


@admin.register(ActividadCurricular)
class ActividadCurricularAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'residente', 'tipo', 'fecha_inicio', 'estado')
    list_filter = ('estado', 'tipo')
    search_fields = ('titulo', 'residente__first_name', 'residente__last_name')
    inlines = (DocumentoActividadInline,)
