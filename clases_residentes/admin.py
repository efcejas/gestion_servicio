from django.contrib import admin
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from .models import ClaseResidente, ComentarioClase, FavoritoClase, EjemploVisualizacion, AccesoGuiaPresentaciones, ConversacionBot, MensajeBot


@admin.register(ClaseResidente)
class ClaseResidenteAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'autor', 'fecha_clase', 'anios_dirigidos_display', 'visitas', 'es_destacada', 'activa']
    list_filter = ['categoria', 'es_destacada', 'activa', 'fecha_clase']
    search_fields = ['titulo', 'descripcion', 'tags', 'autor__username']
    readonly_fields = ['visitas', 'fecha_creacion', 'fecha_actualizacion']
    date_hierarchy = 'fecha_clase'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'descripcion', 'categoria', 'tags')
        }),
        ('Archivo', {
            'fields': ('archivo', 'archivo_thumbnail')
        }),
        ('Audiencia', {
            'fields': ('anios_dirigidos',)
        }),
        ('Autor y Fechas', {
            'fields': ('autor', 'fecha_clase', 'fecha_creacion', 'fecha_actualizacion')
        }),
        ('Estado', {
            'fields': ('activa', 'es_destacada', 'visitas')
        }),
    )
    
    def anios_dirigidos_display(self, obj):
        return obj.anios_dirigidos_display()
    anios_dirigidos_display.short_description = 'Años Dirigidos'


@admin.register(ComentarioClase)
class ComentarioClaseAdmin(admin.ModelAdmin):
    list_display = ['clase', 'autor', 'contenido_preview', 'fecha_creacion']
    list_filter = ['fecha_creacion']
    search_fields = ['contenido', 'autor__username', 'clase__titulo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    
    def contenido_preview(self, obj):
        return obj.contenido[:50] + '...' if len(obj.contenido) > 50 else obj.contenido
    contenido_preview.short_description = 'Contenido'


@admin.register(FavoritoClase)
class FavoritoClaseAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'clase', 'fecha_creacion']
    list_filter = ['fecha_creacion']
    search_fields = ['usuario__username', 'clase__titulo']
    readonly_fields = ['fecha_creacion']


@admin.register(EjemploVisualizacion)
class EjemploVisualizacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'categoria', 'orden', 'activo', 'fecha_creacion']
    list_filter = ['categoria', 'activo', 'fecha_creacion']
    search_fields = ['titulo', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    list_editable = ['orden', 'activo']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'descripcion', 'categoria')
        }),
        ('Imagen', {
            'fields': ('imagen',)
        }),
        ('Visualización', {
            'fields': ('orden', 'activo')
        }),
        ('Fechas', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AccesoGuiaPresentaciones)
class AccesoGuiaPresentacionesAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'fecha_acceso', 'user_agent_short']
    list_filter = ['fecha_acceso', 'usuario']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name', 'user_agent']
    readonly_fields = ['usuario', 'fecha_acceso', 'user_agent']
    date_hierarchy = 'fecha_acceso'
    
    def user_agent_short(self, obj):
        """Muestra solo los primeros 50 caracteres del user agent"""
        if obj.user_agent:
            return obj.user_agent[:50] + '...' if len(obj.user_agent) > 50 else obj.user_agent
        return '-'
    user_agent_short.short_description = 'Navegador'
    
    def has_add_permission(self, request):
        """No permitir agregar registros manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir editar registros"""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Agregar estadísticas al listado de accesos"""
        extra_context = extra_context or {}
        
        # Calcular estadísticas
        total_visitas = AccesoGuiaPresentaciones.objects.count()
        usuarios_unicos = AccesoGuiaPresentaciones.objects.values('usuario').distinct().count()
        
        # Visitas últimos 7 días
        fecha_limite = timezone.now() - timedelta(days=7)
        visitas_ultimos_7_dias = AccesoGuiaPresentaciones.objects.filter(
            fecha_acceso__gte=fecha_limite
        ).count()
        
        # Top 5 usuarios más activos
        top_usuarios = AccesoGuiaPresentaciones.objects.values(
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            total_accesos=Count('id')
        ).order_by('-total_accesos')[:5]
        
        extra_context['total_visitas'] = total_visitas
        extra_context['usuarios_unicos'] = usuarios_unicos
        extra_context['visitas_ultimos_7_dias'] = visitas_ultimos_7_dias
        extra_context['top_usuarios'] = top_usuarios
        extra_context['promedio_por_usuario'] = round(total_visitas / usuarios_unicos, 1) if usuarios_unicos > 0 else 0
        
        return super().changelist_view(request, extra_context=extra_context)


class MensajeBotInline(admin.TabularInline):
    model = MensajeBot
    extra = 0
    readonly_fields = ['rol', 'contenido', 'timestamp', 'feedback']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ConversacionBot)
class ConversacionBotAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'fecha_inicio', 'fecha_actualizacion', 'total_mensajes', 'activa']
    list_filter = ['activa', 'fecha_inicio', 'usuario']
    search_fields = ['usuario__username', 'usuario__first_name', 'usuario__last_name']
    readonly_fields = ['usuario', 'fecha_inicio', 'fecha_actualizacion']
    date_hierarchy = 'fecha_inicio'
    inlines = [MensajeBotInline]
    
    def has_add_permission(self, request):
        """No permitir crear conversaciones manualmente"""
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Agregar estadísticas del bot"""
        extra_context = extra_context or {}
        
        # Estadísticas generales
        total_conversaciones = ConversacionBot.objects.count()
        conversaciones_activas = ConversacionBot.objects.filter(activa=True).count()
        total_mensajes = MensajeBot.objects.count()
        
        # Usuarios únicos que han usado el bot
        usuarios_unicos = ConversacionBot.objects.values('usuario').distinct().count()
        
        # Promedio de mensajes por conversación
        promedio_mensajes = total_mensajes / total_conversaciones if total_conversaciones > 0 else 0
        
        # Top 5 usuarios más activos
        top_usuarios = ConversacionBot.objects.values(
            'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            total_conversaciones=Count('id'),
            total_mensajes=Count('mensajes')
        ).order_by('-total_mensajes')[:5]
        
        extra_context['total_conversaciones'] = total_conversaciones
        extra_context['conversaciones_activas'] = conversaciones_activas
        extra_context['total_mensajes'] = total_mensajes
        extra_context['usuarios_unicos'] = usuarios_unicos
        extra_context['promedio_mensajes'] = round(promedio_mensajes, 1)
        extra_context['top_usuarios'] = top_usuarios
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(MensajeBot)
class MensajeBotAdmin(admin.ModelAdmin):
    list_display = ['conversacion', 'rol', 'contenido_preview', 'timestamp', 'feedback_display']
    list_filter = ['rol', 'timestamp', 'feedback']
    search_fields = ['contenido', 'conversacion__usuario__username']
    readonly_fields = ['conversacion', 'rol', 'contenido', 'timestamp', 'feedback']
    date_hierarchy = 'timestamp'
    
    def contenido_preview(self, obj):
        return obj.contenido[:100] + '...' if len(obj.contenido) > 100 else obj.contenido
    contenido_preview.short_description = 'Contenido'
    
    def feedback_display(self, obj):
        if obj.feedback == 'positivo':
            return '👍 Positivo'
        elif obj.feedback == 'negativo':
            return '👎 Negativo'
        return '- Sin valorar'
    feedback_display.short_description = 'Feedback'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Agregar estadísticas de feedback"""
        extra_context = extra_context or {}
        
        # Estadísticas de feedback
        total_respuestas = MensajeBot.objects.filter(rol='assistant').count()
        feedback_positivo = MensajeBot.objects.filter(rol='assistant', feedback='positivo').count()
        feedback_negativo = MensajeBot.objects.filter(rol='assistant', feedback='negativo').count()
        sin_feedback = total_respuestas - feedback_positivo - feedback_negativo
        
        # Porcentajes
        tasa_feedback = ((feedback_positivo + feedback_negativo) / total_respuestas * 100) if total_respuestas > 0 else 0
        satisfaccion = (feedback_positivo / (feedback_positivo + feedback_negativo) * 100) if (feedback_positivo + feedback_negativo) > 0 else 0
        
        extra_context['total_respuestas'] = total_respuestas
        extra_context['feedback_positivo'] = feedback_positivo
        extra_context['feedback_negativo'] = feedback_negativo
        extra_context['sin_feedback'] = sin_feedback
        extra_context['tasa_feedback'] = round(tasa_feedback, 1)
        extra_context['satisfaccion'] = round(satisfaccion, 1)
        
        return super().changelist_view(request, extra_context=extra_context)
