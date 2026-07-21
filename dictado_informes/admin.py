from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from .models import (
    PlantillaInforme,
    PlantillaEstructurada,
    Informe,
    AudioTranscripcion,
    TerminoMedico,
    CorreccionAprendizaje,
    FeedbackCalidadDictado,
    TrazaAgenteDictado,
)


@admin.register(TrazaAgenteDictado)
class TrazaAgenteDictadoAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'usuario', 'region_detectada', 'lateralidad_detectada',
        'codigo_plantilla', 'score_selector', 'margen_selector',
        'confianza_selector', 'codigo_plantilla_sombra',
        'selector_sombra_coincide', 'origen_seleccion', 'modelo_ia',
        'exitosa', 'fecha_creacion',
    ]
    list_filter = [
        'exitosa', 'confianza_selector', 'confianza_selector_sombra',
        'selector_sombra_coincide', 'origen_seleccion', 'conflicto_contexto',
        'region_detectada',
        'lateralidad_detectada', 'modelo_ia', 'fecha_creacion',
    ]
    search_fields = ['codigo_plantilla', 'huella_entrada', 'usuario__username']
    readonly_fields = [
        'usuario', 'fecha_creacion', 'huella_entrada', 'longitud_entrada',
        'region_detectada', 'lateralidad_detectada', 'plantilla_seleccionada',
        'codigo_plantilla', 'score_selector', 'margen_selector',
        'codigo_plantilla_legacy', 'origen_seleccion', 'conflicto_contexto',
        'confianza_selector', 'candidatos', 'guardrails_aplicados',
        'codigo_plantilla_sombra', 'score_selector_sombra',
        'margen_selector_sombra', 'confianza_selector_sombra',
        'candidatos_sombra', 'selector_sombra_coincide',
        'confianza_ia', 'requiere_confirmacion', 'posible_invencion',
        'modelo_ia',
        'duracion_ms', 'exitosa', 'error_detalle',
    ]
    date_hierarchy = 'fecha_creacion'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PlantillaEstructurada)
class PlantillaEstructuradaAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'codigo', 'origen', 'modo_estructura', 'activa', 'fecha_creacion']
    list_filter = ['origen', 'modo_estructura', 'activa', 'fecha_creacion']
    search_fields = ['codigo', 'nombre', 'titulo']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion', 'origen', 'comentarios_base_preview']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('codigo', 'nombre', 'activa')
        }),
        ('Contenido de Plantilla', {
            'fields': ('titulo', 'seccion_tecnica', 'comentarios_base', 'comentarios_base_preview')
        }),
        ('Guía de Estilo para IA', {
            'fields': ('guia_estilo',),
            'description': (
                'Instrucciones en lenguaje natural que la IA recibe al generar informes con esta plantilla. '
                'Ejemplo: "Para meniscos usar \'de configuración habitual\'. '
                'En desgarros indicar siempre grado Stoller y cuerno afectado."'
            ),
        }),
        ('Estructura flexible', {
            'fields': ('modo_estructura', 'permitir_secciones_nuevas', 'estructura_documento'),
            'classes': ('collapse',),
            'description': (
                'Contrato avanzado para plantillas importadas o personalizadas. '
                'Si estructura_documento queda vacio, se deriva desde los campos clasicos.'
            ),
        }),
        ('Metadatos', {
            'fields': ('origen', 'creada_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Solo permite editar si es usuario (no legacy)"""
        readonly = list(self.readonly_fields)
        if obj and obj.origen == 'legacy':
            # Plantillas legadas: estructura de solo lectura, pero guia_estilo siempre editable
            readonly.extend(['codigo', 'titulo', 'seccion_tecnica', 'comentarios_base'])
        return readonly

    def comentarios_base_preview(self, obj):
        """Muestra comentarios base como lista legible en admin."""
        lineas = obj.comentarios_base or []
        if not lineas:
            return '-'

        return format_html(
            "<div style='white-space: normal; line-height: 1.5;'>{}</div>",
            format_html_join('', "<div>• {}</div>", ((linea,) for linea in lineas))
        )
    comentarios_base_preview.short_description = "Vista previa (líneas)"


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


@admin.register(TerminoMedico)
class TerminoMedicoAdmin(admin.ModelAdmin):
    list_display = ['termino_incorrecto', 'termino_correcto', 'categoria', 'frecuencia_uso', 'activo']
    list_filter = ['categoria', 'activo', 'fecha_creacion']
    search_fields = ['termino_incorrecto', 'termino_correcto', 'notas']
    readonly_fields = ['frecuencia_uso', 'fecha_creacion', 'fecha_modificacion']
    list_editable = ['activo']
    ordering = ['-frecuencia_uso', 'termino_incorrecto']
    
    fieldsets = (
        ('Corrección', {
            'fields': ('termino_incorrecto', 'termino_correcto', 'categoria')
        }),
        ('Estadísticas', {
            'fields': ('frecuencia_uso', 'activo')
        }),
        ('Información Adicional', {
            'fields': ('notas', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activar_terminos', 'desactivar_terminos', 'resetear_frecuencia']
    
    def activar_terminos(self, request, queryset):
        count = queryset.update(activo=True)
        self.message_user(request, f'{count} término(s) activado(s).')
    activar_terminos.short_description = "✅ Activar términos seleccionados"
    
    def desactivar_terminos(self, request, queryset):
        count = queryset.update(activo=False)
        self.message_user(request, f'{count} término(s) desactivado(s).')
    desactivar_terminos.short_description = "❌ Desactivar términos seleccionados"
    
    def resetear_frecuencia(self, request, queryset):
        count = queryset.update(frecuencia_uso=0)
        self.message_user(request, f'Frecuencia reseteada para {count} término(s).')
    resetear_frecuencia.short_description = "🔄 Resetear contador de uso"


@admin.register(CorreccionAprendizaje)
class CorreccionAprendizajeAdmin(admin.ModelAdmin):
    """Admin para ver y analizar correcciones del usuario"""
    list_display = [
        'id', 'usuario', 'tipo_estudio', 'preview_cambios', 
        'cantidad_cambios', 'fue_aplicada', 'fecha_creacion'
    ]
    list_filter = ['fue_aplicada', 'tipo_estudio', 'fecha_creacion', 'usuario']
    search_fields = ['texto_original', 'texto_ia', 'texto_final']
    readonly_fields = [
        'fecha_creacion', 'cambios_detectados', 
        'diferencias_visuales', 'texto_original_preview', 
        'texto_ia_preview', 'texto_final_preview'
    ]
    date_hierarchy = 'fecha_creacion'
    
    def get_queryset(self, request):
        """Optimizar queries con select_related para evitar N+1"""
        qs = super().get_queryset(request)
        return qs.select_related('usuario')
    
    fieldsets = (
        ('Información General', {
            'fields': ('usuario', 'tipo_estudio', 'fecha_creacion', 'fue_aplicada', 'votos_utilidad')
        }),
        ('Textos (Preview)', {
            'fields': ('texto_original_preview', 'texto_ia_preview', 'texto_final_preview'),
            'description': 'Vista previa de los textos (primeros 200 caracteres)'
        }),
        ('Textos Completos', {
            'fields': ('texto_original', 'texto_ia', 'texto_final'),
            'classes': ('collapse',)
        }),
        ('Análisis de Cambios', {
            'fields': ('cambios_detectados', 'diferencias_visuales'),
            'description': 'Diferencias detectadas automáticamente'
        }),
    )
    
    actions = [
        'marcar_aplicada', 
        'recalcular_diferencias', 
        'exportar_para_entrenamiento',
        'ver_ejemplos_aprendizaje'
    ]
    
    def preview_cambios(self, obj):
        """Muestra un preview de los cambios"""
        if not obj.cambios_detectados:
            return "Sin cambios"
        
        total = len(obj.cambios_detectados)
        reemplazos = sum(1 for c in obj.cambios_detectados if c.get('tipo') == 'reemplazo')
        return f"{total} cambios ({reemplazos} reemplazos)"
    preview_cambios.short_description = "Preview cambios"
    
    def cantidad_cambios(self, obj):
        """Cantidad total de cambios"""
        return len(obj.cambios_detectados) if obj.cambios_detectados else 0
    cantidad_cambios.short_description = "# Cambios"
    
    def texto_original_preview(self, obj):
        """Preview del texto original"""
        return obj.texto_original[:200] + '...' if len(obj.texto_original) > 200 else obj.texto_original
    texto_original_preview.short_description = "Texto Original (Whisper)"
    
    def texto_ia_preview(self, obj):
        """Preview del texto IA"""
        return obj.texto_ia[:200] + '...' if len(obj.texto_ia) > 200 else obj.texto_ia
    texto_ia_preview.short_description = "Texto IA (modo FIEL)"
    
    def texto_final_preview(self, obj):
        """Preview del texto final"""
        return obj.texto_final[:200] + '...' if len(obj.texto_final) > 200 else obj.texto_final
    texto_final_preview.short_description = "Texto Final (usuario)"

    def diferencias_visuales(self, obj):
        """Muestra las diferencias de forma visual"""
        if not obj.cambios_detectados:
            return "Sin cambios detectados"
        
        html = "<div style='font-family: monospace;'>"
        for i, cambio in enumerate(obj.cambios_detectados[:10], 1):  # Primeros 10
            tipo = cambio.get('tipo', '')
            if tipo == 'reemplazo':
                html += f"<div style='margin: 5px 0;'>"
                html += f"{i}. <span style='background: #ffebee; padding: 2px 4px;'>{cambio['de']}</span> "
                html += f"→ <span style='background: #e8f5e9; padding: 2px 4px;'>{cambio['a']}</span>"
                html += f"</div>"
            elif tipo == 'agregado':
                html += f"<div style='margin: 5px 0;'>"
                html += f"{i}. <span style='background: #e8f5e9; padding: 2px 4px;'>+ {cambio['texto']}</span>"
                html += f"</div>"
            elif tipo == 'eliminado':
                html += f"<div style='margin: 5px 0;'>"
                html += f"{i}. <span style='background: #ffebee; padding: 2px 4px;'>- {cambio['texto']}</span>"
                html += f"</div>"
        
        if len(obj.cambios_detectados) > 10:
            html += f"<div><em>... y {len(obj.cambios_detectados) - 10} cambios más</em></div>"
        html += "</div>"
        
        from django.utils.safestring import mark_safe
        return mark_safe(html)
    diferencias_visuales.short_description = "Diferencias Visuales"
    
    def marcar_aplicada(self, request, queryset):
        count = queryset.update(fue_aplicada=True)
        self.message_user(request, f'{count} corrección(es) marcada(s) como aplicadas.')
    marcar_aplicada.short_description = "✅ Marcar como aplicada al modelo"
    
    def recalcular_diferencias(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.calcular_diferencias()
            obj.save()
            count += 1
        self.message_user(request, f'Diferencias recalculadas para {count} corrección(es).')
    recalcular_diferencias.short_description = "🔄 Recalcular diferencias"
    
    def exportar_para_entrenamiento(self, request, queryset):
        """Exporta correcciones en formato para fine-tuning"""
        import json
        from django.http import JsonResponse
        
        datos_entrenamiento = []
        for obj in queryset:
            datos_entrenamiento.append({
                'input': obj.texto_ia,
                'output': obj.texto_final,
                'cambios': obj.cambios_detectados
            })
        
        response = JsonResponse({'correcciones': datos_entrenamiento}, json_dumps_params={'indent': 2})
        response['Content-Disposition'] = 'attachment; filename="correcciones_entrenamiento.json"'
        return response
    exportar_para_entrenamiento.short_description = "📥 Exportar para entrenamiento"
    
    def ver_ejemplos_aprendizaje(self, request, queryset):
        """Muestra los ejemplos que se están usando en el prompt de IA"""
        from .models import CorreccionAprendizaje
        
        # Obtener ejemplos para el usuario seleccionado
        usuario = queryset.first().usuario if queryset.exists() else None
        ejemplos = CorreccionAprendizaje.obtener_ejemplos_aprendizaje(usuario=usuario, limite=10)
        
        if ejemplos:
            html = f"""
            <div style="padding: 20px; background: #f0f0f0; border-radius: 5px; margin: 10px;">
                <h3>📚 Ejemplos de Aprendizaje Activos (usados en el prompt de IA)</h3>
                <pre style="background: white; padding: 15px; border-radius: 5px; overflow-x: auto;">{ejemplos}</pre>
                <p style="margin-top: 10px; color: #666;">
                    Estos ejemplos se incluyen automáticamente en el prompt cuando la IA procesa nuevos textos.
                </p>
            </div>
            """
            self.message_user(request, mark_safe(html))
        else:
            self.message_user(request, "No hay ejemplos de aprendizaje disponibles todavía.", level='warning')
    ver_ejemplos_aprendizaje.short_description = "👁️ Ver ejemplos usados en prompt IA"


@admin.register(FeedbackCalidadDictado)
class FeedbackCalidadDictadoAdmin(admin.ModelAdmin):
    list_display = [
        'fecha', 'usuario', 'estado_feedback', 'modo_dictado',
        'tipo_estudio', 'tipo_plantilla', 'porcentaje_edicion', 'tuvo_edicion'
    ]
    list_filter = ['estado_feedback', 'modo_dictado', 'tipo_estudio', 'fecha']
    search_fields = ['usuario__username', 'tipo_plantilla']
    readonly_fields = ['fecha']
    date_hierarchy = 'fecha'
