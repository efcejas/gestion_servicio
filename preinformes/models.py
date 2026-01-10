from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django_ckeditor_5.fields import CKEditor5Field
import re
import html

User = get_user_model()


def has_real_text(html_content):
    """
    Detecta si hay texto real en el contenido HTML.
    Considera vacío: <p>&nbsp;</p>, <p><br></p>, <p></p>, <p> </p>
    """
    if not html_content:
        return False
    
    # Convertir entidades HTML
    text = html.unescape(html_content)
    
    # Remover tags HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # Convertir &nbsp; a espacios
    text = text.replace('&nbsp;', ' ')
    text = text.replace('\xa0', ' ')  # non-breaking space
    
    # Remover espacios y saltos de línea
    text = text.strip()
    
    return len(text) > 0


def sanitize_center_alignment(html_content):
    """
    Elimina alineación centrada del HTML.
    - Remueve <center> tags
    - Remueve style="text-align:center"
    - Remueve class="text-center" o similares
    """
    if not html_content:
        return html_content
    
    # Remover tags <center>
    html_content = re.sub(r'<center[^>]*>', '', html_content, flags=re.IGNORECASE)
    html_content = re.sub(r'</center>', '', html_content, flags=re.IGNORECASE)
    
    # Remover style="text-align:center" y variantes
    html_content = re.sub(r'style\s*=\s*["\']([^"\']*?)text-align\s*:\s*center\s*;?([^"\']*?)["\']', 
                          r'style="\1\2"', html_content, flags=re.IGNORECASE)
    
    # Limpiar styles vacíos resultantes
    html_content = re.sub(r'style\s*=\s*["\']["\']', '', html_content)
    html_content = re.sub(r'style\s*=\s*["\']\s*["\']', '', html_content)
    
    # Remover classes que contengan text-center
    html_content = re.sub(r'class\s*=\s*["\']([^"\']*?)text-center([^"\']*?)["\']',
                          r'class="\1\2"', html_content, flags=re.IGNORECASE)
    
    return html_content


def normalize_html_content(content):
    """
    Normaliza contenido para asegurar que tenga formato HTML con párrafos separados.
    - Convierte <br> y <br/> a separadores de párrafos
    - Convierte \n a separadores de párrafos
    - Elimina párrafos vacíos (<p>&nbsp;</p>, <p></p>, etc.)
    - Extrae contenido de <p> único con breaks y crea múltiples <p>
    """
    if not content:
        return ''
    
    content = content.strip()
    
    # Paso 1: Si tiene <br> tags, convertirlos a saltos de línea temporales
    # Esto incluye <br>, <br/>, <br />, <BR>, etc.
    content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
    
    # Paso 2: Eliminar párrafos vacíos ANTES de procesar
    # Esto incluye <p>&nbsp;</p>, <p> </p>, <p></p>, <p><br></p>
    content = re.sub(r'<p[^>]*>(\s|&nbsp;|<br\s*/?>)*</p>', '', content, flags=re.IGNORECASE)
    
    # Paso 3: Contar párrafos existentes
    p_count = content.count('<p>') + content.count('<p ')
    
    # Paso 4: Si tiene un párrafo con saltos de línea, convertir a múltiples párrafos
    if p_count >= 1 and '\n' in content:
        # Extraer todo el contenido de los párrafos
        # Puede haber múltiples <p> con \n dentro
        def process_p_tag(match):
            inner = match.group(1)
            # Dividir por saltos de línea y crear párrafos individuales
            lines = [line.strip() for line in inner.split('\n') if line.strip()]
            return ''.join(f'<p>{line}</p>' for line in lines)
        
        # Procesar todos los tags <p>
        content = re.sub(r'<p[^>]*>(.*?)</p>', process_p_tag, content, flags=re.DOTALL)
        return content
    
    # Paso 5: Si ya tiene múltiples párrafos sin \n, devolver tal cual
    if p_count > 1:
        return content
    
    # Paso 6: Si tiene saltos de línea pero no tags <p>
    if '\n' in content:
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if lines:
            return ''.join(f'<p>{line}</p>' for line in lines)
    
    # Paso 7: Si es un solo párrafo sin problemas o texto plano, envolverlo
    if not content.startswith('<p'):
        return f'<p>{content}</p>'
    
    return content


def strip_html_tags(text):
    """Remueve tags HTML y devuelve solo el texto"""
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()


class TipoEstudio(models.Model):
    """Tipo de estudio radiológico (RX, TC, RM, ECO, etc.)"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Tipo de Estudio"
        verbose_name_plural = "Tipos de Estudios"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Region(models.Model):
    """Región anatómica del estudio"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Región"
        verbose_name_plural = "Regiones"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class PlantillaPreinforme(models.Model):
    """Plantillas precargadas para preinformes"""
    ESTADO_CHOICES = [
        ('borrador', 'Borrador (Solo yo)'),
        ('publica', 'Pública (Todos)'),
    ]
    
    SISTEMA_CHOICES = [
        ('eges', 'EGES (con acentos y ñ)'),
        ('netterm', 'Netterm (sin acentos ni ñ)'),
        ('universal', 'Universal (ambos sistemas)'),
    ]
    
    nombre = models.CharField(max_length=200)
    tipo_estudio = models.ForeignKey(TipoEstudio, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    sistema_destino = models.CharField(
        max_length=20, 
        choices=SISTEMA_CHOICES, 
        default='universal',
        verbose_name="Sistema destino",
        help_text="Sistema para el que está diseñada esta plantilla"
    )
    
    # Campo único de contenido completo (enfoque simplificado)
    contenido = CKEditor5Field(
        config_name='default',
        verbose_name="Contenido de la Plantilla",
        help_text="Contenido completo de la plantilla con formato. Pega directamente desde Word.",
        blank=True
    )
    
    # DEPRECATED: Campos legacy separados (mantener para migración)
    tecnica_template = CKEditor5Field(
        config_name='default',
        verbose_name="[LEGACY] Plantilla de Técnica",
        help_text="Campo legacy - usar 'contenido' en su lugar",
        blank=True,
        null=True
    )
    hallazgos_template = CKEditor5Field(
        config_name='default', 
        verbose_name="[LEGACY] Plantilla de Hallazgos",
        help_text="Campo legacy - usar 'contenido' en su lugar",
        blank=True,
        null=True
    )
    conclusion_template = CKEditor5Field(
        config_name='default',
        verbose_name="[LEGACY] Plantilla de Conclusión", 
        help_text="Campo legacy - usar 'contenido' en su lugar",
        blank=True,
        null=True
    )
    
    activa = models.BooleanField(default=True)
    creada_por = models.ForeignKey(User, on_delete=models.CASCADE)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Plantilla de Preinforme"
        verbose_name_plural = "Plantillas de Preinformes"
        unique_together = ['nombre', 'tipo_estudio', 'region']
        ordering = ['tipo_estudio__nombre', 'region__nombre', 'nombre']
    
    def __str__(self):
        return f"{self.tipo_estudio.nombre} - {self.region.nombre} - {self.nombre}"


class Preinforme(models.Model):
    """Preinforme realizado por un residente"""
    
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente_revision', 'Pendiente de Revisión'),
        ('en_revision', 'En Revisión'),
        ('revisado', 'Revisado'),
        ('finalizado', 'Finalizado'),
    ]
    
    SISTEMA_CHOICES = [
        ('eges', 'EGES'),
        ('netterm', 'Netterm'),
    ]
    
    # Identificación del estudio
    residente = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='preinformes_realizados'
    )
    numero_estudio = models.CharField(
        max_length=50, 
        help_text="Número del estudio en el sistema EGES"
    )
    tipo_estudio = models.ForeignKey(TipoEstudio, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    sistema_destino = models.CharField(
        max_length=20,
        choices=SISTEMA_CHOICES,
        default='eges',
        verbose_name="Sistema destino",
        help_text="Sistema donde se cargará este informe"
    )
    plantilla_utilizada = models.ForeignKey(
        PlantillaPreinforme, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Datos del paciente
    apellido_paciente = models.CharField(max_length=100)
    nombre_paciente = models.CharField(max_length=100)
    dni_paciente = models.CharField(
        max_length=20, 
        help_text="DNI o documento de identidad del paciente",
        null=True,
        blank=True,
        default='00000000'
    )
    edad_paciente = models.PositiveIntegerField()
    sexo_paciente = models.CharField(
        max_length=1, 
        choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')]
    )
    
    # Contenido del preinforme - Campo único simplificado
    informe_html = CKEditor5Field(
        config_name='default',
        verbose_name="Contenido del Preinforme",
        help_text="Informe completo con formato. Incluye técnica, hallazgos y conclusión.",
        blank=True,
        null=True
    )
    
    # DEPRECATED: Campos legacy separados (mantener para migración y compatibilidad)
    tecnica = CKEditor5Field(
        config_name='default',
        verbose_name="[LEGACY] Técnica",
        help_text="Campo legacy - usar 'informe_html' en su lugar",
        blank=True,
        null=True
    )
    hallazgos = CKEditor5Field(
        config_name='default',
        verbose_name="[LEGACY] Hallazgos",
        help_text="Campo legacy - usar 'informe_html' en su lugar",
        blank=True,
        null=True
    )
    conclusion = CKEditor5Field(
        config_name='default',
        verbose_name="[LEGACY] Conclusión",
        help_text="Campo legacy - usar 'informe_html' en su lugar",
        blank=True,
        null=True
    )
    
    # Estado y revisión
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='borrador')
    revisor = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='preinformes_revisados'
    )
    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    fecha_envio_revision = models.DateTimeField(null=True, blank=True)
    fecha_inicio_revision = models.DateTimeField(null=True, blank=True)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Preinforme"
        verbose_name_plural = "Preinformes"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.numero_estudio} - {self.apellido_paciente}, {self.nombre_paciente} ({self.residente.username})"
    
    def get_informe_html_or_legacy(self) -> str:
        """Fuente única: si existe informe_html, usarlo. Si no, armar desde legacy."""
        if self.informe_html:
            return self.informe_html
        
        # Fallback: construir desde campos legacy
        parts = []
        
        # Título basado en plantilla o tipo de estudio
        if self.plantilla_utilizada:
            titulo = self.plantilla_utilizada.nombre
        else:
            titulo = self.tipo_estudio.nombre
        parts.append(f'<p><strong>{titulo.upper()}</strong></p>')
        
        # Técnica
        if self.tecnica:
            parts.append(self.tecnica)
        
        # Hallazgos
        if self.hallazgos:
            parts.append(self.hallazgos)
        
        # Conclusión (solo si tiene contenido real)
        if self.conclusion and has_real_text(self.conclusion):
            parts.append('<p><strong>CONCLUSIÓN</strong></p>')
            parts.append(self.conclusion)
        
        return ''.join(parts)
    
    def enviar_a_revision(self):
        """Envía el preinforme para revisión"""
        self.estado = 'pendiente_revision'
        self.fecha_envio_revision = timezone.now()
        self.save()
    
    def iniciar_revision(self, revisor):
        """Inicia la revisión por parte del staff"""
        self.estado = 'en_revision'
        self.revisor = revisor
        self.fecha_inicio_revision = timezone.now()
        self.save()
    
    def finalizar_revision(self):
        """Finaliza la revisión"""
        self.estado = 'finalizado'
        self.fecha_finalizacion = timezone.now()
        self.save()


class RevisionPreinforme(models.Model):
    """Revisión y correcciones realizadas por el staff"""
    preinforme = models.OneToOneField(
        Preinforme, 
        on_delete=models.CASCADE, 
        related_name='revision'
    )
    revisor = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Snapshot del informe original del residente (para comparaciones futuras)
    informe_residente_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot del informe completo del residente al momento de la revisión"
    )
    
    # Informe final editado por el staff (HTML único)
    informe_final_html = CKEditor5Field(
        config_name='default',
        verbose_name="Informe Final (Staff)",
        help_text="Informe final editado por el staff - se inicializa con el contenido del residente",
        blank=True
    )
    
    # Comentarios generales
    comentarios_generales = models.TextField(
        blank=True, 
        null=True,
        help_text="Comentarios y sugerencias para el residente"
    )
    
    # Puntuación opcional
    puntuacion = models.PositiveIntegerField(
        null=True, 
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Puntuación del 1 al 10 (opcional)"
    )
    

    
    # Timestamps
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Revisión de Preinforme"
        verbose_name_plural = "Revisiones de Preinformes"
    
    def __str__(self):
        return f"Revisión de {self.preinforme.numero_estudio} por {self.revisor.username}"
    
    def generar_informe_original_residente(self):
        """
        Genera el informe completo del residente.
        Usa el método helper del modelo para obtener el HTML correcto.
        """
        return self.preinforme.get_informe_html_or_legacy()
    
    def crear_snapshot_residente(self):
        """Crea un snapshot del informe original del residente"""
        if not self.informe_residente_snapshot:
            self.informe_residente_snapshot = self.generar_informe_original_residente()
            self.save()
    
    def inicializar_informe_final(self, save=True):
        """Inicializa el informe final del staff con el contenido del residente"""
        if not self.informe_final_html:
            # Preferir snapshot si existe, sino generar
            contenido_base = self.informe_residente_snapshot or self.generar_informe_original_residente()
            # IMPORTANTE: Normalizar el HTML para que CKEditor muestre párrafos separados
            self.informe_final_html = normalize_html_content(contenido_base)
            if save:
                self.save()
    
    def inicializar_revision(self, save=True):
        """Inicializa la revisión creando snapshot y preparando informe final"""
        self.crear_snapshot_residente()
        self.inicializar_informe_final(save=save)
        return self.informe_final_html


class HistorialEstudios(models.Model):
    """Estadísticas y historial de estudios por residente"""
    residente = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='historial_estudios'
    )
    total_preinformes = models.PositiveIntegerField(default=0)
    preinformes_finalizados = models.PositiveIntegerField(default=0)
    promedio_puntuacion = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        null=True, 
        blank=True
    )
    fecha_ultimo_preinforme = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Historial de Estudios"
        verbose_name_plural = "Historiales de Estudios"
    
    def __str__(self):
        return f"Historial de {self.residente.username}"
    
    def actualizar_estadisticas(self):
        """Actualiza las estadísticas del residente"""
        preinformes = Preinforme.objects.filter(residente=self.residente)
        self.total_preinformes = preinformes.count()
        self.preinformes_finalizados = preinformes.filter(estado='finalizado').count()
        
        if self.total_preinformes > 0:
            self.fecha_ultimo_preinforme = preinformes.latest('fecha_creacion').fecha_creacion
        
        # Calcular promedio de puntuaciones
        puntuaciones = preinformes.filter(
            revision__puntuacion__isnull=False
        ).values_list('revision__puntuacion', flat=True)
        
        if puntuaciones:
            self.promedio_puntuacion = sum(puntuaciones) / len(puntuaciones)
        
        self.save()