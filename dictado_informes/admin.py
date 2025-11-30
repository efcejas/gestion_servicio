from django.contrib import admin
from .models import PlantillaInforme, Informe, AudioTranscripcion


@admin.register(PlantillaInforme)
class PlantillaInformeAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo_estudio', 'activa', 'creada_por', 'fecha_creacion']
    list_filter = ['tipo_estudio', 'activa', 'fecha_creacion']
    search_fields = ['nombre', 'contenido']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información General', {
            'fields': ('nombre', 'tipo_estudio', 'activa')
        }),
        ('Contenido', {
            'fields': ('contenido', 'variables')
        }),
        ('Metadatos', {
            'fields': ('creada_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Informe)
class InformeAdmin(admin.ModelAdmin):
    list_display = [
        'numero_estudio', 'apellido_paciente', 'nombre_paciente', 
        'tipo_estudio', 'fecha_estudio', 'estado', 'medico', 'procesado_con_ia'
    ]
    list_filter = ['tipo_estudio', 'estado', 'fecha_estudio', 'procesado_con_ia', 'medico']
    search_fields = ['nombre_paciente', 'apellido_paciente', 'dni_paciente', 'numero_estudio']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'fecha_firma']
    date_hierarchy = 'fecha_estudio'
    
    fieldsets = (
        ('Datos del Paciente', {
            'fields': ('nombre_paciente', 'apellido_paciente', 'dni_paciente', 
                      'edad_paciente', 'fecha_nacimiento')
        }),
        ('Datos del Estudio', {
            'fields': ('tipo_estudio', 'numero_estudio', 'fecha_estudio', 
                      'region_anatomica', 'plantilla_usada')
        }),
        ('Contenido del Informe', {
            'fields': ('indicacion_clinica', 'tecnica', 'hallazgos', 'conclusion')
        }),
        ('Estado y Control', {
            'fields': ('estado', 'medico', 'medico_firma', 'fecha_firma')
        }),
        ('Procesamiento con IA', {
            'fields': ('procesado_con_ia', 'confianza_ia', 'sugerencias_ia'),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notas_privadas',),
            'classes': ('collapse',)
        }),
        ('Metadatos', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es un objeto nuevo
            obj.medico = request.user
        super().save_model(request, obj, form, change)


@admin.register(AudioTranscripcion)
class AudioTranscripcionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'informe', 'duracion_segundos', 'procesado', 
        'fecha_grabacion', 'grabado_por'
    ]
    list_filter = ['procesado', 'servicio_transcripcion', 'fecha_grabacion']
    search_fields = ['informe__numero_estudio', 'informe__apellido_paciente', 'texto_original']
    readonly_fields = ['fecha_grabacion', 'fecha_transcripcion']
    date_hierarchy = 'fecha_grabacion'
    
    fieldsets = (
        ('Información del Audio', {
            'fields': ('informe', 'archivo_audio', 'duracion_segundos', 'grabado_por')
        }),
        ('Transcripción', {
            'fields': ('texto_original', 'texto_mejorado', 'servicio_transcripcion', 
                      'confianza_transcripcion')
        }),
        ('Control', {
            'fields': ('procesado', 'fecha_grabacion', 'fecha_transcripcion')
        }),
    )
