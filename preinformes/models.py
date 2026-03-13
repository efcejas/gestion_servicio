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


def normalize_html_content_soft(content: str, br_threshold: int = 3) -> str:
    """
    Versión "soft" de normalización HTML que RESPETA la estructura original del usuario.
    
    Esta función es menos agresiva que normalize_html_content() y preserva la estructura
    intencional creada por el usuario (por ejemplo, técnicas narrativas con 1-2 <br>,
    o separaciones verticales con <br><br>).
    
    Heurística de decisión:
    
    1. HTML con 2+ <p>: NO reestructurar (ya está bien formado)
       - Solo eliminar <p> vacíos (&nbsp;, <br>, espacios)
       - Preservar todos los <br> tal como están
       
    2. HTML con 0 <p> (texto plano): Convertir líneas por saltos \n
       - Interpretar como texto sin formatear
       - Crear <p> por cada línea
       
    3. HTML con 1 <p> y >= br_threshold <br>: Interpretar como "pegado sucio"
       - Probablemente viene de Word/otro editor
       - SÍ convertir <br> en nuevos <p>
       
    4. HTML con 1 <p> pero < br_threshold <br>: PRESERVAR
       - Probablemente es contenido intencional (técnica narrativa)
       - NO convertir <br> a <p>
       
    5. No tocar <br> dentro de <table>, <ul>, <ol>, <li>
       - Estructuras complejas se preservan intactas
    
    Args:
        content: HTML a normalizar
        br_threshold: Número mínimo de <br> para considerar "pegado sucio" (default: 3)
    
    Returns:
        HTML normalizado de forma respetuosa
    
    Ejemplos:
        >>> # Caso 1: Técnica narrativa (NO convertir)
        >>> html = '<p><strong>TÉCNICA:</strong></p><p>Linea 1<br>Linea 2</p>'
        >>> normalize_html_content_soft(html)
        '<p><strong>TÉCNICA:</strong></p><p>Linea 1<br>Linea 2</p>'
        
        >>> # Caso 2: Pegado sucio con muchos br (SÍ convertir)
        >>> html = '<p>L1<br>L2<br>L3<br>L4</p>'
        >>> normalize_html_content_soft(html)
        '<p>L1</p><p>L2</p><p>L3</p><p>L4</p>'
    """
    # Manejar None o vacío
    if not content:
        return ''
    
    content = content.strip()
    if not content:
        return ''
    
    # Paso 1: Contar <p> existentes (con o sin atributos)
    p_count = len(re.findall(r'<p(?:\s[^>]*)?>',  content, flags=re.IGNORECASE))
    
    # Paso 2: Si tiene 2+ <p>, asumir que está bien estructurado
    # Solo limpiar párrafos vacíos y devolver
    if p_count >= 2:
        # Eliminar <p> vacíos: <p>&nbsp;</p>, <p> </p>, <p><br></p>, <p></p>
        cleaned = re.sub(
            r'<p(?:\s[^>]*)?>(\s|&nbsp;|<br\s*/?>)*</p>',
            '',
            content,
            flags=re.IGNORECASE
        )
        
        # Eliminar múltiples <p></p> consecutivos que puedan quedar
        cleaned = re.sub(r'(</p>)\s*(<p(?:\s[^>]*)?>)\s*(?=\s*<p)', r'\1\2', cleaned)
        
        return cleaned.strip()
    
    # Paso 3: Si tiene 0 <p>, es texto plano con posibles \n
    if p_count == 0:
        # Convertir saltos de línea en párrafos
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if lines:
            return ''.join(f'<p>{line}</p>' for line in lines)
        # Si no hay líneas válidas, envolver en un <p>
        return f'<p>{content}</p>' if content else ''
    
    # Paso 4: Si tiene exactamente 1 <p>, analizar <br> dentro
    # Contar <br> fuera de estructuras complejas
    
    # Crear una copia sin tablas, listas, para contar <br> "peligrosos"
    # TODO: Mejorar esta heurística si se encuentran edge cases
    temp_content = content
    
    # Remover temporalmente contenido de tablas
    temp_content = re.sub(r'<table[^>]*>.*?</table>', '', temp_content, flags=re.IGNORECASE | re.DOTALL)
    # Remover temporalmente listas
    temp_content = re.sub(r'<[uo]l[^>]*>.*?</[uo]l>', '', temp_content, flags=re.IGNORECASE | re.DOTALL)
    
    # Contar <br> en el contenido filtrado
    br_count = len(re.findall(r'<br\s*/?>', temp_content, flags=re.IGNORECASE))
    
    # Si tiene >= br_threshold <br>, interpretar como pegado sucio
    if br_count >= br_threshold:
        # Convertir <br> a saltos de línea temporales
        content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
        
        # Eliminar párrafos vacíos
        content = re.sub(
            r'<p(?:\s[^>]*)?>(\s|&nbsp;|<br\s*/?>)*</p>',
            '',
            content,
            flags=re.IGNORECASE
        )
        
        # Extraer contenido de <p> y dividir por \n
        def process_p_tag(match):
            inner = match.group(1)
            # Dividir por saltos de línea y crear párrafos individuales
            lines = [line.strip() for line in inner.split('\n') if line.strip()]
            return ''.join(f'<p>{line}</p>' for line in lines)
        
        # Procesar el tag <p>
        result = re.sub(r'<p(?:\s[^>]*)?>(.*?)</p>', process_p_tag, content, flags=re.DOTALL | re.IGNORECASE)
        return result.strip()
    
    # Paso 5: Si tiene < br_threshold <br>, PRESERVAR estructura original
    # Solo eliminar párrafos vacíos obvios
    cleaned = re.sub(
        r'<p(?:\s[^>]*)?>(\s|&nbsp;)*</p>',
        '',
        content,
        flags=re.IGNORECASE
    )
    
    return cleaned.strip()


def strip_html_tags(text):
    """Remueve tags HTML y devuelve solo el texto"""
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()


class EtiquetaPreinforme(models.Model):
    """Etiquetas clínicas para clasificar preinformes (ej: Apendicitis, Dolor abdominal)"""
    nombre = models.CharField(max_length=100, unique=True)
    color = models.CharField(
        max_length=7, 
        default='#3B82F6',
        help_text="Color en formato hexadecimal (ej: #3B82F6)"
    )
    creada_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='etiquetas_creadas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Etiqueta de Preinforme"
        verbose_name_plural = "Etiquetas de Preinformes"
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


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
    
    # Nueva propiedad para determinar si es compartida
    @property
    def compartida(self):
        """Retorna True si la plantilla es pública"""
        return self.estado == 'publica'
    
    class Meta:
        verbose_name = "Plantilla de Preinforme"
        verbose_name_plural = "Plantillas de Preinformes"
        ordering = ['tipo_estudio__nombre', 'region__nombre', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'tipo_estudio', 'region', 'sistema_destino'],
                condition=models.Q(estado='publica'),
                name='unique_plantilla_publica'
            )
        ]
    
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
        blank=True
    )
    edad_paciente = models.PositiveIntegerField(null=True, blank=True)
    sexo_paciente = models.CharField(
        max_length=1, 
        choices=[('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')],
        null=True,
        blank=True
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
    asignacion_compartida = models.BooleanField(
        default=False,
        verbose_name="Asignación compartida",
        help_text="Si está activado, el estudio estará en el pool compartido para jefes/instructores"
    )
    
    # Etiquetas clínicas para clasificación y búsqueda
    etiquetas = models.ManyToManyField(
        EtiquetaPreinforme,
        blank=True,
        related_name='preinformes',
        verbose_name="Etiquetas clínicas"
    )
    
    # Sistema de bloqueo/coordinación para evitar ediciones simultáneas
    en_edicion_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preinformes_editando',
        verbose_name="En edición por"
    )
    ultima_actividad_edicion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Última actividad de edición"
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
    
    def marcar_en_edicion(self, usuario):
        """Marca el preinforme como en edición por un usuario"""
        self.en_edicion_por = usuario
        self.ultima_actividad_edicion = timezone.now()
        self.save(update_fields=['en_edicion_por', 'ultima_actividad_edicion'])
    
    def liberar_edicion(self):
        """Libera el preinforme de edición"""
        self.en_edicion_por = None
        self.ultima_actividad_edicion = None
        self.save(update_fields=['en_edicion_por', 'ultima_actividad_edicion'])
    
    def esta_siendo_editado(self):
        """Verifica si el preinforme está siendo editado actualmente"""
        if not self.en_edicion_por or not self.ultima_actividad_edicion:
            return False
        
        # Considerar abandonado después de 15 minutos sin actividad
        tiempo_limite = timezone.now() - timezone.timedelta(minutes=15)
        return self.ultima_actividad_edicion > tiempo_limite
    
    def puede_editar(self, usuario):
        """Verifica si un usuario puede editar el preinforme"""
        # Si nadie lo está editando, puede editar
        if not self.esta_siendo_editado():
            return True
        
        # Si el mismo usuario lo está editando, puede continuar
        return self.en_edicion_por == usuario
    
    def puede_ser_tomado_por(self, usuario):
        """Verifica si un estudio en pool compartido puede ser tomado por el usuario"""
        if not self.asignacion_compartida:
            return False
        
        # Solo disponible si no tiene revisor asignado
        if self.revisor is not None:
            return False
        
        # Solo jefes e instructores pueden tomar estudios compartidos
        if usuario.rol not in ['jefe_residentes', 'instructor_residentes']:
            return False
        
        # Debe estar en estado pendiente o en revisión
        if self.estado not in ['pendiente_revision', 'en_revision']:
            return False
        
        return True


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
            # IMPORTANTE: Normalizar el HTML de forma RESPETUOSA para CKEditor (preserva estructura original)
            self.informe_final_html = normalize_html_content_soft(contenido_base)
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


# ======================================================================
# ASISTENTE IA PARA ELABORACIÓN DE PREINFORMES
# ======================================================================

class ConversacionAsistentePreinforme(models.Model):
    """
    Conversación entre un residente y el asistente IA Radiólogo Mentor
    durante la elaboración de un preinforme.
    """
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversaciones_asistente_preinforme',
        help_text='Residente que mantiene la conversación'
    )
    preinforme = models.ForeignKey(
        Preinforme,
        on_delete=models.CASCADE,
        related_name='conversaciones_asistente',
        null=True,
        blank=True,
        help_text='Preinforme asociado a la conversación (null si aún no fue guardado)'
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activa = models.BooleanField(default=True)

    # Scoring / evaluación de la sesión
    evaluacion_ia = models.JSONField(
        default=dict,
        blank=True,
        help_text='Evaluación de la sesión: {razonamiento_clinico, terminologia, autonomia, receptividad, comentario}'
    )
    puntuacion_global = models.FloatField(
        null=True,
        blank=True,
        help_text='Puntaje global de la sesión (0–10)'
    )
    evaluada = models.BooleanField(
        default=False,
        help_text='Si la conversación fue evaluada por la IA'
    )
    evaluacion_publicada = models.BooleanField(
        default=False,
        help_text='Si el docente habilitó que el residente vea su evaluación'
    )

    class Meta:
        verbose_name = 'Conversación con Asistente de Preinforme'
        verbose_name_plural = 'Conversaciones con Asistente de Preinforme'
        ordering = ['-fecha_actualizacion']
        indexes = [
            models.Index(fields=['-fecha_actualizacion']),
            models.Index(fields=['usuario', '-fecha_actualizacion']),
        ]

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        return f"Conversación de {nombre} — {self.fecha_inicio.strftime('%d/%m/%Y %H:%M')}"

    def total_mensajes(self):
        return self.mensajes_asistente.count()


class MensajeAsistentePreinforme(models.Model):
    """
    Mensaje individual dentro de una conversación con el asistente IA.
    """
    ROLES = [
        ('user', 'Residente'),
        ('assistant', 'Asistente IA'),
    ]

    FEEDBACK_CHOICES = [
        ('positivo', 'Positivo 👍'),
        ('negativo', 'Negativo 👎'),
    ]

    conversacion = models.ForeignKey(
        ConversacionAsistentePreinforme,
        on_delete=models.CASCADE,
        related_name='mensajes_asistente',
        help_text='Conversación a la que pertenece este mensaje'
    )
    rol = models.CharField(max_length=10, choices=ROLES)
    contenido = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    feedback = models.CharField(
        max_length=10,
        choices=FEEDBACK_CHOICES,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Mensaje del Asistente de Preinforme'
        verbose_name_plural = 'Mensajes del Asistente de Preinforme'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['conversacion', 'timestamp']),
        ]

    def __str__(self):
        preview = self.contenido[:50] + '...' if len(self.contenido) > 50 else self.contenido
        return f"{self.get_rol_display()}: {preview}"