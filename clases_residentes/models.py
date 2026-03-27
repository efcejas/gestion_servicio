from django.db import models
from django.conf import settings
from django.utils import timezone

from cloudinary.models import CloudinaryField
from .storages import S3MediaStorage


class ClaseResidente(models.Model):
    """
    Modelo para gestionar clases/presentaciones de residentes.
    Cada clase puede estar dirigida a años específicos de residencia.
    """

    def get_anios_display_list(self):
        """Devuelve los labels legibles de los años dirigidos (ej: 'R1 - Primer Año')"""
        if not self.anios_dirigidos:
            return []
        choices_dict = dict(self.ANIO_CHOICES)
        return [choices_dict.get(anio, anio) for anio in self.anios_dirigidos]
    
    # Opciones de años de residencia dirigidos
    ANIO_CHOICES = [
        ('R1', 'R1'),
        ('R2', 'R2'),
        ('R3', 'R3'),
        ('R4', 'R4'),
    ]
    
    # Categorías de clases
    CATEGORIA_CHOICES = [
        ('anatomia', 'Anatomía Radiológica'),
        ('fisica', 'Física de Imágenes'),
        ('protocolos', 'Protocolos de Estudio'),
        ('patologia', 'Patología por Imagen'),
        ('pediatria', 'Radiología Pediátrica'),
        ('intervencionismo', 'Intervencionismo'),
        ('us', 'Ultrasonido'),
        ('tc', 'Tomografía Computada'),
        ('rm', 'Resonancia Magnética'),
        ('caso_clinico', 'Caso Clínico'),
        ('revision', 'Revisión Bibliográfica'),
        ('otro', 'Otro'),
    ]
    
    # Información básica
    titulo = models.CharField(
        max_length=200,
        help_text='Título descriptivo de la clase'
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        help_text='Descripción detallada del contenido'
    )
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        help_text='Categoría temática de la clase'
    )
    
    # Archivos múltiples: Documentos en S3, Videos en Cloudinary
    archivo = models.FileField(
        storage=S3MediaStorage(),
        blank=True,
        null=True,
        upload_to='',  # Se guarda en la carpeta definida por location en el storage
        help_text='Archivo de presentación (PPT, PDF, etc.) - almacenado en S3'
    )
    archivo_video = CloudinaryField(
        'video',
        blank=True,
        null=True,
        folder='clases_residentes/videos',
        resource_type='video',
        help_text='Archivo de video (MP4, MOV, etc.) - almacenado en Cloudinary'
    )
    archivo_thumbnail = CloudinaryField(
        'thumbnail',
        blank=True,
        null=True,
        folder='clases_residentes/thumbnails',
        help_text='Miniatura de la presentación'
    )
    
    # Tipo de archivo (documento o video)
    TIPO_ARCHIVO_CHOICES = [
        ('documento', 'Documento (PPT, PDF, etc.)'),
        ('video', 'Video (MP4, MOV, etc.)'),
    ]
    tipo_archivo = models.CharField(
        max_length=20,
        choices=TIPO_ARCHIVO_CHOICES,
        default='documento',
        help_text='Tipo de archivo cargado'
    )
    
    # Clasificación por año de residencia (múltiple)
    anios_dirigidos = models.JSONField(
        default=list,
        help_text='Lista de años de residencia a los que va dirigida (ej: ["R1", "R2"])'
    )
    
    # Autor y fechas
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clases_creadas',
        help_text='Residente o médico que creó la clase'
    )
    fecha_clase = models.DateField(
        default=timezone.now,
        help_text='Fecha en que se dictó la clase'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # Metadata
    visitas = models.PositiveIntegerField(
        default=0,
        help_text='Número de veces que se ha visualizado'
    )
    es_destacada = models.BooleanField(
        default=False,
        help_text='Marcar como clase destacada'
    )
    activa = models.BooleanField(
        default=True,
        help_text='Si está activa y visible para los usuarios'
    )
    
    # Tags adicionales (opcional)
    tags = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text='Tags separados por comas (ej: tórax, covid, neumonía)'
    )
    
    class Meta:
        verbose_name = 'Clase de Residente'
        verbose_name_plural = 'Clases de Residentes'
        ordering = ['-fecha_clase', '-fecha_creacion']
        indexes = [
            models.Index(fields=['-fecha_clase']),
            models.Index(fields=['categoria']),
            models.Index(fields=['autor']),
        ]
    
    def __str__(self):
        return f"{self.titulo} - {self.get_categoria_display()}"
    
    def anios_dirigidos_display(self):
        """Retorna string legible de años dirigidos"""
        if not self.anios_dirigidos:
            return "Todos los años"
        return ", ".join(str(a) for a in self.anios_dirigidos)
    
    def get_archivo_url(self):
        """
        Retorna la URL del archivo principal (documento o video).
        Prioriza archivo_video si es tipo video, sino retorna archivo.
        """
        if self.tipo_archivo == 'video' and self.archivo_video:
            return self.archivo_video.url
        elif self.archivo:
            return self.archivo.url
        return None
    
    def tiene_archivo(self):
        """Verifica si la clase tiene algún archivo cargado"""
        return bool(self.archivo or self.archivo_video)
    
    def get_anios_list(self):
        """Retorna lista de años dirigidos para usar en templates"""
        if not self.anios_dirigidos:
            return []
        return self.anios_dirigidos if isinstance(self.anios_dirigidos, list) else []
    
    def puede_ver(self, usuario):
        """
        Verifica si un usuario puede ver esta clase.
        - Jefes e instructores pueden ver todas
        - Administrativos de Docencia pueden ver todas (solo lectura)
        - Residentes solo ven las de su año o inferiores
        """
        # Jefes, instructores y staff pueden ver todo
        if usuario.rol in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio', 'medico_staff']:
            return True

        # Administrativos de Docencia pueden ver todas las clases
        if usuario.groups.filter(name='Administrativo - Docencia').exists():
            return True

        # Si es para todos los años
        if not self.anios_dirigidos:
            return True

        # Si es residente, verificar su año
        if usuario.rol == 'medico_residente' and usuario.anio_residencia:
            return usuario.anio_residencia in self.anios_dirigidos

        return False
    
    def puede_editar(self, usuario):
        """
        Verifica si un usuario puede editar esta clase.
        - Autor puede editar su propia clase
        - Jefes e instructores pueden editar cualquier clase
        """
        if usuario == self.autor:
            return True
        
        if usuario.rol in ['jefe_residentes', 'instructor_residentes', 'jefe_servicio']:
            return True
        
        return usuario.is_superuser
    
    def incrementar_visitas(self):
        """Incrementa el contador de visitas"""
        self.visitas += 1
        self.save(update_fields=['visitas'])
    
    def get_tags_list(self):
        """Retorna lista de tags"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    def get_archivo_url_publico(self):
        """
        Obtiene la URL pública del archivo optimizada para visualización.
        Asegura que sea accesible por visualizadores externos como Office Online.
        """
        if not self.archivo:
            return None
        
        try:
            if hasattr(self.archivo, 'url'):
                url = str(self.archivo.url)
                # Forzar HTTPS
                if url.startswith('http://'):
                    url = url.replace('http://', 'https://')
                return url
        except Exception:
            pass
        
        return None
    
    def get_tipo_archivo_detectado(self):
        """
        Detecta automáticamente el tipo de archivo según su extensión.
        Útil para archivos cargados antes de agregar el campo tipo_archivo.
        """
        if not self.archivo:
            return 'documento'
        
        try:
            nombre_archivo = self.archivo.name.lower()
            extension = nombre_archivo.split('.')[-1] if '.' in nombre_archivo else ''
            
            EXTENSIONES_VIDEO = ['mp4', 'mov', 'avi', 'webm', 'mkv', 'm4v', 'flv', 'wmv']
            
            if extension in EXTENSIONES_VIDEO:
                return 'video'
            return 'documento'
        except Exception:
            return 'documento'
    
    def es_video(self):
        """
        Retorna True si el archivo es un video.
        Verifica tanto el campo tipo_archivo como la extensión real.
        """
        # Priorizar el campo tipo_archivo si está definido
        if self.tipo_archivo == 'video':
            return True
        # Fallback: detectar por extensión
        return self.get_tipo_archivo_detectado() == 'video'
    
    def get_mime_type(self):
        """
        Retorna el MIME type aproximado según el tipo y extensión del archivo.
        """
        if not self.archivo:
            return None
        
        try:
            extension = self.archivo.name.lower().split('.')[-1] if '.' in self.archivo.name else ''
            
            MIME_TYPES = {
                # Videos
                'mp4': 'video/mp4',
                'webm': 'video/webm',
                'mov': 'video/quicktime',
                'avi': 'video/x-msvideo',
                'mkv': 'video/x-matroska',
                'm4v': 'video/x-m4v',
                # Documentos
                'pdf': 'application/pdf',
                'ppt': 'application/vnd.ms-powerpoint',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'key': 'application/x-iwork-keynote-sffkey',
            }
            
            return MIME_TYPES.get(extension, 'application/octet-stream')
        except Exception:
            return 'application/octet-stream'


class ComentarioClase(models.Model):
    """
    Comentarios y feedback sobre las clases.
    """
    clase = models.ForeignKey(
        ClaseResidente,
        on_delete=models.CASCADE,
        related_name='comentarios'
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comentarios_clases'
    )
    contenido = models.TextField(
        help_text='Comentario o feedback sobre la clase'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Comentario de Clase'
        verbose_name_plural = 'Comentarios de Clases'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Comentario de {self.autor.username} en {self.clase.titulo}"


class FavoritoClase(models.Model):
    """
    Clases marcadas como favoritas por los usuarios.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clases_favoritas'
    )
    clase = models.ForeignKey(
        ClaseResidente,
        on_delete=models.CASCADE,
        related_name='favoritos'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Clase Favorita'
        verbose_name_plural = 'Clases Favoritas'
        unique_together = ['usuario', 'clase']
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.usuario.username} - {self.clase.titulo}"


class EjemploVisualizacion(models.Model):
    """
    Modelo para gestionar ejemplos visuales de buenas prácticas en presentaciones.
    Usado en la guía de presentaciones para residentes.
    """
    
    # Categorías de ejemplos
    CATEGORIA_CHOICES = [
        ('cita_imagen', 'Citación de Imágenes'),
        ('bibliografia', 'Formato de Bibliografía'),
        ('diseno', 'Diseño Visual'),
        ('presentacion', 'Presentación Oral'),
        ('estructura', 'Estructura de Contenido'),
    ]
    
    # Información básica
    titulo = models.CharField(
        max_length=200,
        help_text='Título descriptivo del ejemplo'
    )
    descripcion = models.TextField(
        help_text='Descripción detallada de qué muestra este ejemplo'
    )
    categoria = models.CharField(
        max_length=30,
        choices=CATEGORIA_CHOICES,
        help_text='Categoría del ejemplo'
    )
    
    # Imagen del ejemplo (almacenada en Cloudinary)
    imagen = CloudinaryField(
        'image',
        folder='clases_residentes/ejemplos_guia',
        help_text='Imagen que muestra el ejemplo visual'
    )
    
    # Control de visualización
    orden = models.PositiveIntegerField(
        default=0,
        help_text='Orden de visualización (menor número = primero)'
    )
    activo = models.BooleanField(
        default=True,
        help_text='Si está activo y visible en la guía'
    )
    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Ejemplo de Visualización'
        verbose_name_plural = 'Ejemplos de Visualización'
        ordering = ['orden', '-fecha_creacion']
        indexes = [
            models.Index(fields=['categoria', 'activo']),
            models.Index(fields=['orden']),
        ]
    
    def __str__(self):
        return f"{self.titulo} ({self.get_categoria_display()})"
    
    def get_imagen_url(self):
        """Retorna la URL de la imagen"""
        if self.imagen:
            return self.imagen.url
        return None


class AccesoGuiaPresentaciones(models.Model):
    """
    Modelo para trackear accesos a la guía de presentaciones.
    Permite al administrador ver qué residentes consultan la sección y con qué frecuencia.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='accesos_guia_presentaciones',
        help_text='Usuario que accedió a la guía'
    )
    fecha_acceso = models.DateTimeField(
        auto_now_add=True,
        help_text='Fecha y hora del acceso'
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text='User agent del navegador (para análisis de dispositivos)'
    )
    
    class Meta:
        verbose_name = 'Acceso a Guía de Presentaciones'
        verbose_name_plural = 'Accesos a Guía de Presentaciones'
        ordering = ['-fecha_acceso']
        indexes = [
            models.Index(fields=['-fecha_acceso']),
            models.Index(fields=['usuario', '-fecha_acceso']),
        ]
    
    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} - {self.fecha_acceso.strftime('%d/%m/%Y %H:%M')}"


class ConversacionBot(models.Model):
    """
    Modelo para gestionar conversaciones del bot de asistencia en presentaciones.
    Cada usuario puede tener múltiples conversaciones.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversaciones_bot',
        help_text='Usuario que mantiene la conversación'
    )
    fecha_inicio = models.DateTimeField(
        auto_now_add=True,
        help_text='Fecha y hora de inicio de la conversación'
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        help_text='Última actividad en esta conversación'
    )
    activa = models.BooleanField(
        default=True,
        help_text='Si la conversación está activa'
    )
    
    class Meta:
        verbose_name = 'Conversación con Bot'
        verbose_name_plural = 'Conversaciones con Bot'
        ordering = ['-fecha_actualizacion']
        indexes = [
            models.Index(fields=['-fecha_actualizacion']),
            models.Index(fields=['usuario', '-fecha_actualizacion']),
        ]
    
    def __str__(self):
        return f"Conversación de {self.usuario.get_full_name() or self.usuario.username} - {self.fecha_inicio.strftime('%d/%m/%Y %H:%M')}"
    
    def total_mensajes(self):
        """Retorna el total de mensajes en esta conversación"""
        return self.mensajes.count()


class MensajeBot(models.Model):
    """
    Modelo para mensajes individuales dentro de una conversación con el bot.
    """
    ROLES = [
        ('user', 'Usuario'),
        ('assistant', 'Bot'),
    ]
    
    FEEDBACK_CHOICES = [
        ('positivo', 'Positivo 👍'),
        ('negativo', 'Negativo 👎'),
    ]
    
    conversacion = models.ForeignKey(
        ConversacionBot,
        on_delete=models.CASCADE,
        related_name='mensajes',
        help_text='Conversación a la que pertenece este mensaje'
    )
    rol = models.CharField(
        max_length=10,
        choices=ROLES,
        help_text='Quién envió el mensaje'
    )
    contenido = models.TextField(
        help_text='Contenido del mensaje'
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text='Fecha y hora del mensaje'
    )
    feedback = models.CharField(
        max_length=10,
        choices=FEEDBACK_CHOICES,
        null=True,
        blank=True,
        help_text='Valoración del usuario sobre la respuesta del bot'
    )
    
    class Meta:
        verbose_name = 'Mensaje de Bot'
        verbose_name_plural = 'Mensajes de Bot'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversacion', 'timestamp']),
        ]
    
    def __str__(self):
        preview = self.contenido[:50] + '...' if len(self.contenido) > 50 else self.contenido
        return f"{self.get_rol_display()}: {preview}"
