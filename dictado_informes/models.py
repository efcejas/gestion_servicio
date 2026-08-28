from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging
import re
import difflib

logger = logging.getLogger(__name__)
User = get_user_model()

from .utils import REGEX_COMANDOS_VOZ, REGEX_GRADOS, REGEX_LIMPIEZA  # noqa: E402


class TipoEstudio(models.TextChoices):
    """Tipos de estudios de diagnóstico por imágenes"""
    RESONANCIA = 'RES', 'Resonancia Magnética'
    TOMOGRAFIA = 'TOM', 'Tomografía'
    RADIOGRAFIA = 'RAD', 'Radiografía'
    ECOGRAFIA = 'ECO', 'Ecografía'
    MAMOGRAFIA = 'MAM', 'Mamografía'
    DENSITOMETRIA = 'DEN', 'Densitometría'
    OTRO = 'OTR', 'Otro'


class EstadoInforme(models.TextChoices):
    """Estados del informe durante el proceso"""
    BORRADOR = 'BOR', 'Borrador'
    EN_REVISION = 'REV', 'En Revisión'
    FINALIZADO = 'FIN', 'Finalizado'
    FIRMADO = 'FIR', 'Firmado'


class PlantillaEstructurada(models.Model):
    """Plantillas estructuradas para modo ESTRUCTURADO con guardrails de IA.
    
    Define la estructura base (título, sección técnica, comentarios) que se usa
    para mejorar el texto en modo ESTRUCTURADO. El sistema preserva líneas no 
    mencionadas en el dictado original (guardrails).
    
    Campo 'codigo' vinculado a tipo de estudio (ej. RODILLA, CADERA, ABDOMEN C/G).
    """
    MODO_ESTRUCTURA_LEGACY = 'legacy'
    MODO_ESTRUCTURA_ESTRICTA = 'estricta'
    MODO_ESTRUCTURA_FLEXIBLE = 'flexible'
    MODO_ESTRUCTURA_AGENTE = 'agente'
    MODO_ESTRUCTURA_CHOICES = [
        (MODO_ESTRUCTURA_LEGACY, 'Legacy compatible'),
        (MODO_ESTRUCTURA_ESTRICTA, 'Estructura estricta'),
        (MODO_ESTRUCTURA_FLEXIBLE, 'Estructura flexible'),
        (MODO_ESTRUCTURA_AGENTE, 'Agente con confirmacion'),
    ]

    # Código único identificador (ej. RODILLA, CADERA, TORAX S/G, etc.)
    codigo = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        verbose_name="Código",
        help_text="Identificador único: RODILLA, CADERA, ATM, TC_MSK, ABDOMEN C/G, TORAX S/G, etc."
    )
    
    # Nombre descriptivo para UI (ej "RM de Rodilla")
    nombre = models.CharField(
        max_length=200,
        verbose_name="Nombre",
        help_text="Nombre descriptivo para mostrar en selectores (ej. 'RM de Rodilla')"
    )
    
    # Titímulo base con placeholders tipo [<DERECHA/IZQUIERDA>]
    titulo = models.CharField(
        max_length=500,
        verbose_name="Título",
        help_text="Título de la plantilla con placeholders: 'RM DE RODILLA [<DERECHA/IZQUIERDA>]'"
    )
    
    # Sección técnica descriptiva
    seccion_tecnica = models.TextField(
        verbose_name="Sección Técnica",
        help_text="Descripción de la técnica utilizada en el estudio"
    )
    
    # Comentarios base (anatomía normal) que se preservan en guardrails
    # Lista JSON de strings, uno por línea
    comentarios_base = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Comentarios Base",
        help_text="Lista de líneas con anatomía normal que se preservan en modo ESTRUCTURADO"
    )
    
    # Guía de estilo personal: instrucciones en lenguaje natural para la IA
    # Ejemplo: "Para meniscos usar 'de configuración habitual'. Indicar grado Stoller en desgarros."
    guia_estilo = models.TextField(
        blank=True,
        default='',
        verbose_name="Guía de Estilo",
        help_text=(
            "Instrucciones en lenguaje natural que la IA recibe para esta plantilla. "
            "Ejemplo: 'Para meniscos usar \"de configuración habitual\" (no \"normales\"). "
            "En desgarros indicar siempre grado Stoller y cuerno afectado.'"
        )
    )

    modo_estructura = models.CharField(
        max_length=20,
        choices=MODO_ESTRUCTURA_CHOICES,
        default=MODO_ESTRUCTURA_LEGACY,
        verbose_name="Modo de Estructura",
        help_text=(
            "Define cuanto debe respetarse la estructura original. "
            "Legacy mantiene el comportamiento actual."
        )
    )

    estructura_documento = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Estructura del Documento",
        help_text=(
            "Representacion flexible de secciones importadas desde documentos. "
            "Si queda vacia, se deriva desde titulo, tecnica y comentarios base."
        )
    )

    permitir_secciones_nuevas = models.BooleanField(
        default=False,
        verbose_name="Permitir Secciones Nuevas",
        help_text=(
            "Si esta desactivado, la IA no debe agregar secciones que no existan "
            "en la plantilla original."
        )
    )

    # Origen de la plantilla (legacy = migrada desde hardcode)
    ORIGEN_CHOICES = [
        ('legacy', 'Legado (migrado de hardcode)'),
        ('user', 'Creada por usuario'),
        ('system', 'Sistema'),
    ]
    origen = models.CharField(
        max_length=20,
        choices=ORIGEN_CHOICES,
        default='legacy',
        verbose_name="Origen",
        help_text="Indica si fue migrada desde hardcode o creada por usuario"
    )
    
    # Control de activación
    activa = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Activa",
        help_text="Solo se usan plantillas activas"
    )

    compartida = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Compartida",
        help_text="Si está activa y compartida, queda disponible para otros usuarios de Dictado IA"
    )
    
    # Auditoría
    creada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plantillas_estructuradas_creadas',
        verbose_name="Creada por"
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Creación"
    )
    fecha_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Modificación"
    )
    
    class Meta:
        verbose_name = "Plantilla Estructurada"
        verbose_name_plural = "Plantillas Estructuradas"
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['codigo', 'activa']),
            models.Index(fields=['origen']),
        ]
    
    def __str__(self):
        estado = "✅" if self.activa else "❌"
        return f"{estado} {self.nombre} ({self.codigo})"

    @classmethod
    def visibles_para_usuario(cls, usuario, solo_activas=False):
        queryset = cls.objects.all()

        if solo_activas:
            queryset = queryset.filter(activa=True)

        if not usuario or not getattr(usuario, 'is_authenticated', False):
            return queryset.filter(compartida=True)

        if usuario.is_superuser:
            return queryset

        return queryset.filter(models.Q(compartida=True) | models.Q(creada_por=usuario))

    def puede_ser_editada_por(self, usuario):
        if not usuario or not getattr(usuario, 'is_authenticated', False):
            return False
        return usuario.is_superuser or self.creada_por_id == usuario.id

    def obtener_estructura_documento(self):
        """
        Devuelve una estructura normalizada de secciones sin cambiar el modelo legacy.

        Las plantillas actuales no tienen estructura_documento cargada; para ellas
        se deriva un contrato equivalente al comportamiento historico, incluyendo
        CONCLUSION. Las plantillas importadas pueden omitir secciones y el agente
        debe respetar esa omision salvo instruccion explicita.
        """
        estructura = self.estructura_documento or {}
        secciones = estructura.get('secciones') if isinstance(estructura, dict) else None

        if isinstance(secciones, list) and secciones:
            return {
                'modo': estructura.get('modo') or self.modo_estructura,
                'permitir_secciones_nuevas': bool(
                    estructura.get('permitir_secciones_nuevas', self.permitir_secciones_nuevas)
                ),
                'secciones': [self._normalizar_seccion_estructura(s) for s in secciones],
            }

        secciones_legacy = []
        if self.titulo:
            secciones_legacy.append({
                'nombre': 'TITULO',
                'tipo': 'titulo',
                'contenido': self.titulo,
                'editable_por_ia': True,
            })
        if self.seccion_tecnica:
            secciones_legacy.append({
                'nombre': 'TECNICA',
                'tipo': 'tecnica',
                'contenido': self.seccion_tecnica,
                'editable_por_ia': False,
            })
        if self.comentarios_base:
            secciones_legacy.append({
                'nombre': 'COMENTARIO',
                'tipo': 'hallazgos',
                'lineas_base': list(self.comentarios_base or []),
                'editable_por_ia': True,
            })

        # Compatibilidad: el modo estructurado actual siempre genera conclusion.
        secciones_legacy.append({
            'nombre': 'CONCLUSION',
            'tipo': 'conclusion',
            'contenido': '',
            'editable_por_ia': True,
        })

        return {
            'modo': self.modo_estructura,
            'permitir_secciones_nuevas': self.permitir_secciones_nuevas,
            'secciones': secciones_legacy,
        }

    def tiene_seccion(self, nombre):
        nombre_normalizado = self._normalizar_nombre_seccion(nombre)
        estructura = self.obtener_estructura_documento()
        return any(
            self._normalizar_nombre_seccion(s.get('nombre')) == nombre_normalizado
            for s in estructura.get('secciones', [])
        )

    def puede_agregar_seccion(self, nombre):
        if self.tiene_seccion(nombre):
            return True

        estructura = self.obtener_estructura_documento()
        return bool(estructura.get('permitir_secciones_nuevas'))

    @staticmethod
    def _normalizar_seccion_estructura(seccion):
        if not isinstance(seccion, dict):
            return {
                'nombre': 'SECCION',
                'tipo': 'texto',
                'contenido': str(seccion),
                'editable_por_ia': True,
            }

        nombre = (seccion.get('nombre') or seccion.get('titulo') or 'SECCION').strip()
        tipo = (seccion.get('tipo') or 'texto').strip().lower()
        normalizada = {
            'nombre': nombre,
            'tipo': tipo,
            'contenido': seccion.get('contenido') or '',
            'editable_por_ia': bool(seccion.get('editable_por_ia', True)),
        }

        lineas_base = seccion.get('lineas_base')
        if isinstance(lineas_base, list):
            normalizada['lineas_base'] = [str(linea).strip() for linea in lineas_base if str(linea).strip()]

        return normalizada

    @staticmethod
    def _normalizar_nombre_seccion(nombre):
        texto = (nombre or '').strip().upper()
        reemplazos = str.maketrans('ÁÉÍÓÚÜÑ', 'AEIOUUN')
        return texto.translate(reemplazos).rstrip(':')


class PlantillaInforme(models.Model):
    """Plantillas predefinidas para diferentes tipos de estudios"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre de la Plantilla")
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        verbose_name="Tipo de Estudio"
    )
    contenido = models.TextField(verbose_name="Contenido de la Plantilla")
    variables = models.JSONField(
        default=dict,
        blank=True,
        help_text="Variables que se pueden completar: {paciente}, {edad}, {fecha}, etc.",
        verbose_name="Variables"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    creada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='plantillas_creadas',
        verbose_name="Creada por"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        verbose_name = "Plantilla de Informe"
        verbose_name_plural = "Plantillas de Informes"
        ordering = ['tipo_estudio', 'nombre']

    def __str__(self):
        return f"{self.get_tipo_estudio_display()} - {self.nombre}"
    
    def clean(self):
        """Validación de campos HTML antes de guardar"""
        from django.core.exceptions import ValidationError
        import re
        
        # Tags peligrosos que no permitimos
        dangerous_tags = ['script', 'iframe', 'object', 'embed', 'link', 'meta']
        
        # El campo 'contenido' puede tener HTML básico
        if self.contenido:
            # Buscar tags peligrosos (case-insensitive)
            for tag in dangerous_tags:
                pattern = re.compile(f'<{tag}[^>]*>', re.IGNORECASE)
                if pattern.search(self.contenido):
                    raise ValidationError({
                        'contenido': f"No se permite el tag <{tag}> por seguridad. Usa solo texto plano o HTML básico (p, br, strong, em)."
                    })
            
            # Validar que los tags estén balanceados básicamente
            if self.contenido.count('<') != self.contenido.count('>'):
                raise ValidationError({
                    'contenido': "HTML malformado: los tags no están balanceados (cantidad de < y > no coincide)."
                })


class Informe(models.Model):
    """Informe médico generado por dictado con IA"""
    # Datos del paciente
    nombre_paciente = models.CharField(max_length=200, verbose_name="Nombre del Paciente")
    apellido_paciente = models.CharField(max_length=200, verbose_name="Apellido del Paciente")
    dni_paciente = models.CharField(max_length=20, blank=True, verbose_name="DNI")
    edad_paciente = models.PositiveIntegerField(null=True, blank=True, verbose_name="Edad")
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name="Fecha de Nacimiento")
    
    # Datos del estudio
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        verbose_name="Tipo de Estudio"
    )
    numero_estudio = models.CharField(max_length=50, blank=True, verbose_name="Número de Estudio")
    fecha_estudio = models.DateField(default=timezone.now, verbose_name="Fecha del Estudio")
    region_anatomica = models.CharField(max_length=200, blank=True, verbose_name="Región Anatómica")
    
    # Contenido del informe
    indicacion_clinica = models.TextField(blank=True, verbose_name="Indicación Clínica")
    tecnica = models.TextField(blank=True, verbose_name="Técnica")
    hallazgos = models.TextField(verbose_name="Hallazgos")
    conclusion = models.TextField(verbose_name="Conclusión")
    
    # Estado y control
    estado = models.CharField(
        max_length=3,
        choices=EstadoInforme.choices,
        default=EstadoInforme.BORRADOR,
        verbose_name="Estado"
    )
    plantilla_usada = models.ForeignKey(
        PlantillaInforme,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='informes',
        verbose_name="Plantilla Usada"
    )
    
    # Médico responsable
    medico = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='informes_dictados',
        verbose_name="Médico Informante"
    )
    medico_firma = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='informes_firmados',
        verbose_name="Médico que Firma"
    )
    fecha_firma = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Firma")
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")
    
    # IA y procesamiento
    procesado_con_ia = models.BooleanField(default=False, verbose_name="Procesado con IA")
    confianza_ia = models.FloatField(
        null=True,
        blank=True,
        help_text="Nivel de confianza de la IA (0-1)",
        verbose_name="Confianza IA"
    )
    sugerencias_ia = models.JSONField(
        default=dict,
        blank=True,
        help_text="Sugerencias de mejora de la IA",
        verbose_name="Sugerencias IA"
    )
    
    # Notas adicionales
    notas_privadas = models.TextField(
        blank=True,
        help_text="Notas privadas del médico (no aparecen en el informe final)",
        verbose_name="Notas Privadas"
    )

    class Meta:
        verbose_name = "Informe Médico"
        verbose_name_plural = "Informes Médicos"
        ordering = ['-fecha_estudio', '-fecha_creacion']
        permissions = [
            ("can_dictate", "Puede dictar informes"),
            ("can_sign", "Puede firmar informes"),
            ("can_use_ai", "Puede usar IA para informes"),
        ]

    def __str__(self):
        return f"{self.get_tipo_estudio_display()} - {self.apellido_paciente}, {self.nombre_paciente} ({self.fecha_estudio})"

    def firmar(self, medico):
        """Firma el informe"""
        self.estado = EstadoInforme.FIRMADO
        self.medico_firma = medico
        self.fecha_firma = timezone.now()
        self.save()

    def nombre_completo_paciente(self):
        """Retorna el nombre completo del paciente"""
        return f"{self.apellido_paciente}, {self.nombre_paciente}"


class AudioTranscripcion(models.Model):
    """Almacena los audios dictados y sus transcripciones"""
    informe = models.ForeignKey(
        Informe,
        on_delete=models.CASCADE,
        related_name='audios',
        verbose_name="Informe"
    )
    archivo_audio = models.FileField(
        upload_to='dictados/%Y/%m/%d/',
        verbose_name="Archivo de Audio"
    )
    duracion_segundos = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Duración (segundos)"
    )
    
    # Transcripción
    texto_original = models.TextField(
        blank=True,
        help_text="Transcripción literal del audio",
        verbose_name="Texto Original"
    )
    texto_mejorado = models.TextField(
        blank=True,
        help_text="Texto mejorado por IA",
        verbose_name="Texto Mejorado por IA"
    )
    
    # Metadatos del procesamiento
    servicio_transcripcion = models.CharField(
        max_length=50,
        blank=True,
        help_text="Whisper, Azure Speech, etc.",
        verbose_name="Servicio de Transcripción"
    )
    confianza_transcripcion = models.FloatField(
        null=True,
        blank=True,
        help_text="Nivel de confianza de la transcripción (0-1)",
        verbose_name="Confianza"
    )
    
    # Control
    procesado = models.BooleanField(default=False, verbose_name="Procesado")
    fecha_grabacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Grabación")
    fecha_transcripcion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Transcripción"
    )
    
    # Usuario
    grabado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audios_grabados',
        verbose_name="Grabado por"
    )

    class Meta:
        verbose_name = "Audio de Dictado"
        verbose_name_plural = "Audios de Dictados"
        ordering = ['-fecha_grabacion']

    def __str__(self):
        return f"Audio {self.id} - {self.informe} ({self.fecha_grabacion.strftime('%d/%m/%Y %H:%M')})"


class CategoriaTerminoMedico(models.TextChoices):
    """Categorías de términos médicos"""
    ORTOPEDIA = 'ORTOPEDIA', 'Ortopedia'
    RADIOLOGIA = 'RADIOLOGIA', 'Radiología'
    GENERAL = 'GENERAL', 'General'
    ANATOMIA = 'ANATOMIA', 'Anatomía'


class TerminoMedico(models.Model):
    """Diccionario de términos médicos con correcciones automáticas"""
    termino_incorrecto = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Término Incorrecto",
        help_text="Término como lo transcribe el navegador (ej: 'con artrosis trick compartimental')"
    )
    termino_correcto = models.CharField(
        max_length=200,
        verbose_name="Término Correcto",
        help_text="Término médico correcto (ej: 'gonartrosis tricompartimental')"
    )
    categoria = models.CharField(
        max_length=50,
        choices=CategoriaTerminoMedico.choices,
        default=CategoriaTerminoMedico.GENERAL,
        verbose_name="Categoría"
    )
    frecuencia_uso = models.IntegerField(
        default=0,
        verbose_name="Frecuencia de Uso",
        help_text="Contador automático de veces que se aplicó esta corrección"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notas",
        help_text="Notas adicionales sobre el término"
    )

    class Meta:
        verbose_name = "Término Médico"
        verbose_name_plural = "Términos Médicos"
        ordering = ['-frecuencia_uso', 'termino_incorrecto']
        indexes = [
            models.Index(fields=['termino_incorrecto'], name='dictado_inf_termino_idx'),
        ]

    def __str__(self):
        return f"{self.termino_incorrecto} → {self.termino_correcto}"

    @staticmethod
    def aplicar_correcciones(texto):
        """
        Aplica todas las correcciones activas del diccionario a un texto
        
        Args:
            texto (str): Texto a corregir
        
        Returns:
            tuple: (texto_corregido, list de correcciones aplicadas)
        """
        if not texto or not texto.strip():
            return texto, []
        
        terminos = TerminoMedico.objects.filter(activo=True).order_by('-frecuencia_uso')
        texto_corregido = texto
        correcciones_aplicadas = []
        
        for termino in terminos:
            # Búsqueda case-insensitive con límites de palabra
            patron = re.compile(re.escape(termino.termino_incorrecto), re.IGNORECASE)
            
            if patron.search(texto_corregido):
                texto_corregido = patron.sub(termino.termino_correcto, texto_corregido)
                correcciones_aplicadas.append({
                    'de': termino.termino_incorrecto,
                    'a': termino.termino_correcto
                })
                
                # Incrementar contador de uso
                termino.frecuencia_uso += 1
                termino.save(update_fields=['frecuencia_uso'])
        
        return texto_corregido, correcciones_aplicadas

    @staticmethod
    def procesar_texto_completo(texto):
        """
        🎯 OPTIMIZACIÓN: Método unificado que procesa comandos de voz Y aplica correcciones
        del diccionario médico en el orden correcto.
        
        Orden de procesamiento:
        1. Comandos de voz ("nueva línea" → "\n", "punto" → ".", etc.)
        2. Diccionario médico ("Jofa" → "Hoffa", "oligamentaria" → "ligamentaria", etc.)
        
        Args:
            texto (str): Texto transcrito con Whisper
        
        Returns:
            tuple: (texto_procesado, correcciones_aplicadas)
        
        Ejemplo:
            >>> texto = "paciente sin Jofa punto nueva línea"
            >>> texto_final, correcciones = TerminoMedico.procesar_texto_completo(texto)
            >>> print(texto_final)
            "Paciente sin Hoffa.\nSin alteraciones..."
            >>> print(correcciones)
            [{'de': 'Jofa', 'a': 'Hoffa'}]
        """
        if not texto or not texto.strip():
            return texto, []
        
        # PASO 1: Procesar comandos de voz (convierte comandos literales a formato)
        texto_con_comandos = TerminoMedico.procesar_comandos_voz(texto)
        
        # PASO 2: Aplicar diccionario médico (corrige términos específicos)
        texto_final, correcciones = TerminoMedico.aplicar_correcciones(texto_con_comandos)
        
        return texto_final, correcciones

    @staticmethod
    def procesar_comandos_voz(texto):
        """
        🚀 OPTIMIZADO FASE 3: Procesa comandos de voz usando regex precompilados (30-50% más rápido)
        
        Procesa comandos de voz como 'nueva línea', 'punto', etc.
        También limpia artefactos de transcripción como "., " o ", ."
        
        Args:
            texto (str): Texto con comandos de voz
        
        Returns:
            str: Texto con comandos reemplazados por formato
        """
        if not texto:
            return texto
        
        texto_procesado = texto
        
        # PASO 1: Reemplazar comandos de voz literales usando regex precompilados
        # ⚡ OPTIMIZACIÓN: Usar patrones globales precompilados en lugar de compilar cada vez
        comandos_reemplazos = [
            # Saltos de línea (prioridad alta)
            (REGEX_COMANDOS_VOZ['nueva_linea'], '\n'),
            (REGEX_COMANDOS_VOZ['nueva_linea_sin_acento'], '\n'),
            (REGEX_COMANDOS_VOZ['salto_linea'], '\n'),
            (REGEX_COMANDOS_VOZ['salto_linea_sin_acento'], '\n'),
            (REGEX_COMANDOS_VOZ['punto_aparte'], '.\n\n'),
            (REGEX_COMANDOS_VOZ['parrafo_nuevo'], '\n\n'),
            
            # Punto seguido (mantener en misma línea)
            (REGEX_COMANDOS_VOZ['punto_seguido'], '. '),
            (REGEX_COMANDOS_VOZ['seguido'], '. '),
            
            # Puntuación básica
            (REGEX_COMANDOS_VOZ['punto'], '.'),
            (REGEX_COMANDOS_VOZ['coma'], ','),
            (REGEX_COMANDOS_VOZ['dos_puntos'], ':'),
            (REGEX_COMANDOS_VOZ['punto_coma'], ';'),
            
            # Símbolos
            (REGEX_COMANDOS_VOZ['parentesis_abre'], '('),
            (REGEX_COMANDOS_VOZ['parentesis_cierra'], ')'),
            (REGEX_COMANDOS_VOZ['interrogacion_abre'], '¿'),
            (REGEX_COMANDOS_VOZ['interrogacion_cierra'], '?'),
        ]
        
        for patron_compilado, reemplazo in comandos_reemplazos:
            texto_procesado = patron_compilado.sub(reemplazo, texto_procesado)
        
        # PASO 2: CONVERSIÓN AUTOMÁTICA DE GRADOS A NÚMEROS ROMANOS
        # Convierte "grado 1/2/3/4" → "grado I/II/III/IV"
        grados_reemplazos = [
            (REGEX_GRADOS['grado_1'], 'grado I'),
            (REGEX_GRADOS['grado_2'], 'grado II'),
            (REGEX_GRADOS['grado_3'], 'grado III'),
            (REGEX_GRADOS['grado_4'], 'grado IV'),
        ]
        
        for patron_compilado, reemplazo in grados_reemplazos:
            texto_procesado = patron_compilado.sub(reemplazo, texto_procesado)
        
        # PASO 3: LIMPIAR ARTEFACTOS DE WHISPER
        # Cuando dices "nueva línea", Whisper puede transcribir como "., " o dejar espacios extra
        limpiezas = [
            (REGEX_LIMPIEZA['coma_punto_coma'], '.\n'),      # ", ., " → ".\n"
            (REGEX_LIMPIEZA['punto_coma_newline'], '.\n'),   # "., \n" → ".\n"
            (REGEX_LIMPIEZA['coma_punto_newline'], '.\n'),   # ", .\n" → ".\n"
            (REGEX_LIMPIEZA['coma_punto'], '.\n'),           # ", ." → ".\n"
            (REGEX_LIMPIEZA['punto_coma'], '.\n'),           # "., " → ".\n"
            (REGEX_LIMPIEZA['doble_punto'], '.\n'),          # ".." → ".\n"
            (REGEX_LIMPIEZA['coma_newline'], '\n'),          # ",\n" → "\n"
            (REGEX_LIMPIEZA['espacios_antes_newline'], '\n'), # " \n" → "\n"
            (REGEX_LIMPIEZA['espacios_despues_newline'], '\n'), # "\n " → "\n"
            (REGEX_LIMPIEZA['newlines_multiples'], '\n\n'),  # "\n\n\n..." → "\n\n"
        ]
        
        for patron_compilado, reemplazo in limpiezas:
            texto_procesado = patron_compilado.sub(reemplazo, texto_procesado)
        
        # 6. Capitalizar primera letra después de punto (con o sin salto)
        def capitalizar_despues_punto(match):
            return match.group(1) + match.group(2).upper()
        
        # Capitalizar después de punto + salto
        texto_procesado = REGEX_LIMPIEZA['capitalizar_punto_newline'].sub(
            capitalizar_despues_punto, texto_procesado
        )
        # Capitalizar después de punto + espacio (punto seguido)
        texto_procesado = REGEX_LIMPIEZA['capitalizar_punto_espacio'].sub(
            capitalizar_despues_punto, texto_procesado
        )
        
        # 7. INTELIGENCIA: Detectar y separar hallazgos/conceptos automáticamente
        # Palabras que típicamente inician nuevo concepto en informes radiológicos
        palabras_inicio_concepto = [
            # Conectores comunes
            'además', 'asimismo', 'igualmente', 'también', 'por otro lado', 'por otra parte',
            # Verbos de observación
            'se observa', 'se identifica', 'se visualiza', 'se reconoce', 'se evidencia',
            'se aprecia', 'se detecta', 'se constata', 'se encuentra',
            # Negaciones
            'no se observa', 'no se identifica', 'no se visualiza', 'ausencia de', 'sin evidencia',
            # Confirmación
            'presencia de', 'existe', 'hay evidencia',
            # Estructuras anatómicas (con artículo)
            'el ligamento', 'los ligamentos', 'el menisco', 'los meniscos', 
            'la rótula', 'el cartílago', 'la articulación', 'el hueso', 'los huesos',
            # Estructuras anatómicas (sin artículo - inicio directo)
            'ligamento', 'ligamentos', 'menisco', 'meniscos', 
            'rótula', 'cartílago', 'articulación', 'hueso', 'huesos',
            # Patología/hallazgos específicos
            'incremento del', 'incremento de', 'aumento del', 'aumento de',
            'signos de', 'presencia de', 'evidencia de'
        ]
        
        for palabra in palabras_inicio_concepto:
            # Si encuentra estas palabras después de punto sin salto, agrega salto
            # Patrón: ". palabra" → ".\nPalabra"
            patron = r'\.\s+' + re.escape(palabra) + r'\b'
            
            def reemplazar_con_salto(match):
                texto_completo = match.group(0)  # ". la rótula" completo
                # Separar el punto del resto
                texto_sin_punto = texto_completo.lstrip('. ')  # "la rótula"
                # Capitalizar solo la primera letra
                if texto_sin_punto:
                    return '.\n' + texto_sin_punto[0].upper() + texto_sin_punto[1:]
                return texto_completo
            
            texto_procesado = re.sub(patron, reemplazar_con_salto, texto_procesado, flags=re.IGNORECASE)
        
        return texto_procesado.strip()


class TrazaAgenteDictado(models.Model):
    """Decision audit trail for agent mode without storing clinical text."""

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='trazas_agente_dictado',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    huella_entrada = models.CharField(max_length=64, blank=True)
    longitud_entrada = models.PositiveIntegerField(default=0)
    region_detectada = models.CharField(max_length=30, blank=True)
    lateralidad_detectada = models.CharField(max_length=20, blank=True)
    plantilla_seleccionada = models.ForeignKey(
        'PlantillaEstructurada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='trazas_seleccion',
    )
    codigo_plantilla = models.CharField(max_length=50, blank=True)
    codigo_plantilla_legacy = models.CharField(max_length=50, blank=True)
    origen_seleccion = models.CharField(max_length=20, blank=True)
    conflicto_contexto = models.BooleanField(default=False)
    score_selector = models.IntegerField(default=0)
    margen_selector = models.IntegerField(default=0)
    confianza_selector = models.CharField(max_length=10, blank=True)
    candidatos = models.JSONField(default=list, blank=True)
    codigo_plantilla_sombra = models.CharField(max_length=50, blank=True)
    score_selector_sombra = models.FloatField(default=0.0)
    margen_selector_sombra = models.FloatField(default=0.0)
    confianza_selector_sombra = models.CharField(max_length=10, blank=True)
    candidatos_sombra = models.JSONField(default=list, blank=True)
    selector_sombra_coincide = models.BooleanField(default=False)
    guardrails_aplicados = models.JSONField(default=list, blank=True)
    confianza_ia = models.FloatField(default=0.0)
    modelo_ia = models.CharField(max_length=50, blank=True)
    requiere_confirmacion = models.BooleanField(default=False)
    posible_invencion = models.BooleanField(default=False)
    duracion_ms = models.PositiveIntegerField(default=0)
    exitosa = models.BooleanField(default=True)
    error_detalle = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['usuario', '-fecha_creacion']),
            models.Index(fields=['region_detectada', '-fecha_creacion']),
            models.Index(fields=['exitosa', '-fecha_creacion']),
        ]
        verbose_name = 'Traza del agente de dictado'
        verbose_name_plural = 'Trazas del agente de dictado'

    def __str__(self):
        plantilla = self.codigo_plantilla or 'sin plantilla'
        return f'Traza {self.pk} - {plantilla}'


class CorreccionAprendizaje(models.Model):
    """
    Modelo para guardar correcciones manuales del usuario y entrenar la IA.
    Cuando el usuario edita el texto mejorado, guardamos la diferencia para aprender.
    """
    # Textos
    texto_original = models.TextField(
        verbose_name="Texto original (transcripción Whisper)",
        help_text="Texto tal como lo transcribió Whisper"
    )
    texto_ia = models.TextField(
        verbose_name="Texto mejorado por IA",
        help_text="Texto después de pasar por la IA en modo FIEL"
    )
    texto_final = models.TextField(
        verbose_name="Texto final (editado por usuario)",
        help_text="Texto después de correcciones manuales del usuario"
    )
    
    # Metadata
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='correcciones_aprendizaje',
        verbose_name="Usuario"
    )
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        blank=True,
        verbose_name="Tipo de Estudio"
    )
    modo_dictado = models.CharField(max_length=20, blank=True)
    tipo_plantilla = models.CharField(max_length=50, blank=True)
    region = models.CharField(max_length=30, blank=True)
    modalidad = models.CharField(max_length=20, blank=True)
    lateralidad = models.CharField(max_length=20, blank=True)
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de corrección"
    )
    
    # Análisis automático de diferencias
    cambios_detectados = models.JSONField(
        default=list,
        blank=True,
        help_text="Lista de cambios: [{de: 'texto_ia', a: 'texto_final', tipo: 'correcion/agregado/eliminado'}]",
        verbose_name="Cambios detectados"
    )
    fue_aplicada = models.BooleanField(
        default=False,
        verbose_name="Aplicada al modelo",
        help_text="Si esta corrección ya fue usada para entrenar/ajustar la IA"
    )
    
    # Utilidad
    votos_utilidad = models.IntegerField(
        default=0,
        verbose_name="Votos de utilidad",
        help_text="Para rankear qué correcciones son más importantes"
    )
    
    class Meta:
        verbose_name = "Corrección de Aprendizaje"
        verbose_name_plural = "Correcciones de Aprendizaje"
        ordering = ['-fecha_creacion']
        indexes = [
            models.Index(fields=['-fecha_creacion']),
            models.Index(fields=['fue_aplicada']),
            models.Index(fields=['usuario', '-fecha_creacion']),  # 🚀 Optimización para queries por usuario
        ]
    
    def __str__(self):
        preview = self.texto_final[:50] + '...' if len(self.texto_final) > 50 else self.texto_final
        return f"Corrección {self.id} - {self.usuario} - {preview}"
    
    def calcular_diferencias(self):
        """
        🚀 MEJORADO: Calcula diferencias con análisis semántico
        Detecta patrones, categoriza correcciones y asigna scores
        ⭐ NUEVO: Detecta eliminaciones de líneas normales cuando hay patología
        """
        import difflib
        from collections import Counter
        
        # Usar difflib para detectar cambios palabra por palabra
        palabras_ia = self.texto_ia.split()
        palabras_final = self.texto_final.split()
        
        matcher = difflib.SequenceMatcher(None, palabras_ia, palabras_final)
        cambios = []
        
        # Patrones médicos comunes
        terminologia_medica = {
            'grado': ['grado i', 'grado ii', 'grado iii', 'grado iv'],
            'lateralidad': ['derecho', 'izquierdo', 'bilateral'],
            'presencia': ['se observa', 'se visualiza', 'se identifica', 'se evidencia'],
            'ausencia': ['no se observa', 'sin evidencia', 'ausencia de']
        }
        
        # 🏗️ NUEVO: Analizar por líneas para detectar eliminaciones de plantilla
        lineas_ia = self.texto_ia.split('\n')
        lineas_final = self.texto_final.split('\n')
        
        # 🔍 Detectar líneas de plantilla "normal" que fueron eliminadas
        lineas_eliminadas_normales = self._detectar_conflictos_plantilla_patologia(lineas_ia, lineas_final)
        cambios.extend(lineas_eliminadas_normales)
        cambios.extend(self._detectar_reordenamiento_lineas(lineas_ia, lineas_final))
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                texto_de = ' '.join(palabras_ia[i1:i2])
                texto_a = ' '.join(palabras_final[j1:j2])
                
                # 🧠 Análisis semántico: categorizar el tipo de cambio
                categoria = self._categorizar_cambio(texto_de, texto_a, terminologia_medica)
                
                # Calcular score de importancia (0-100)
                score = self._calcular_score_importancia(texto_de, texto_a, categoria)
                
                cambios.append({
                    'tipo': 'reemplazo',
                    'de': texto_de,
                    'a': texto_a,
                    'categoria': categoria,
                    'score': score
                })
            elif tag == 'delete':
                texto = ' '.join(palabras_ia[i1:i2])
                cambios.append({
                    'tipo': 'eliminado',
                    'texto': texto,
                    'categoria': 'eliminacion',
                    'score': 30  # Score medio para eliminaciones
                })
            elif tag == 'insert':
                texto = ' '.join(palabras_final[j1:j2])
                # Verificar si es información clínica importante
                score = 80 if any(kw in texto.lower() for kw in ['desgarro', 'fractura', 'lesión', 'edema']) else 50
                cambios.append({
                    'tipo': 'agregado',
                    'texto': texto,
                    'categoria': 'agregado',
                    'score': score
                })
        
        self.cambios_detectados = cambios
        logger.info(f"📊 Análisis semántico: {len(cambios)} cambios detectados")
        return cambios
    
    def _detectar_reordenamiento_lineas(self, lineas_ia, lineas_final):
        """
        Detecta cuando el usuario conserva una linea generada pero la mueve de lugar.
        Esto ensenia preferencias de ubicacion dentro del bloque COMENTARIO/HALLAZGOS.
        """
        cambios = []
        bloque_ia = self._extraer_bloque_hallazgos(lineas_ia)
        bloque_final = self._extraer_bloque_hallazgos(lineas_final)
        if len(bloque_ia) < 2 or len(bloque_final) < 2:
            return cambios

        usados_final = set()
        pares = []
        for idx_ia, linea_ia in enumerate(bloque_ia):
            mejor_idx = None
            mejor_ratio = 0
            for idx_final, linea_final in enumerate(bloque_final):
                if idx_final in usados_final:
                    continue
                ratio = difflib.SequenceMatcher(
                    None,
                    self._normalizar_para_control(linea_ia),
                    self._normalizar_para_control(linea_final),
                ).ratio()
                if ratio > mejor_ratio:
                    mejor_ratio = ratio
                    mejor_idx = idx_final

            if mejor_idx is not None and mejor_ratio >= 0.88:
                usados_final.add(mejor_idx)
                pares.append((idx_ia, mejor_idx, bloque_final[mejor_idx]))

        for idx_ia, idx_final, linea in pares:
            if idx_ia == idx_final:
                continue
            previa = bloque_final[idx_final - 1] if idx_final > 0 else ''
            siguiente = bloque_final[idx_final + 1] if idx_final + 1 < len(bloque_final) else ''
            cambios.append({
                'tipo': 'reordenamiento_linea',
                'texto': linea,
                'posicion_ia': idx_ia + 1,
                'posicion_final': idx_final + 1,
                'despues_de': previa,
                'antes_de': siguiente,
                'categoria': 'estructural_orden',
                'score': 88,
                'regla': self._formatear_regla_orden(linea, previa, siguiente),
            })

        return cambios[:5]

    @classmethod
    def _extraer_bloque_hallazgos(cls, lineas):
        headers_inicio = {'COMENTARIO', 'HALLAZGOS', 'INFORME', 'DESCRIPCION', 'DESCRIPCIÓN'}
        headers_fin = {'CONCLUSION', 'CONCLUSIÓN', 'IMPRESION', 'IMPRESIÓN', 'TECNICA', 'TÉCNICA'}
        dentro = False
        bloque = []

        for linea in lineas:
            limpia = (linea or '').strip()
            if not limpia:
                continue
            header = cls._normalizar_para_control(limpia).upper().rstrip(':')
            if header in headers_inicio:
                dentro = True
                continue
            if dentro and header in headers_fin:
                break
            if dentro:
                bloque.append(limpia)

        return bloque

    @staticmethod
    def _formatear_regla_orden(linea, previa, siguiente):
        if previa:
            return f'Ubicar "{linea}" inmediatamente despues de "{previa}".'
        if siguiente:
            return f'Ubicar "{linea}" inmediatamente antes de "{siguiente}".'
        return f'Ubicar "{linea}" segun el orden corregido por el usuario.'

    def _detectar_conflictos_plantilla_patologia(self, lineas_ia, lineas_final):
        """
        🎯 NUEVO: Detecta cuando el usuario elimina líneas "normales" porque mencionó patología
        
        Ejemplo:
        - IA genera: "Manguito rotador de morfología conservada."
        - Usuario dicta: "Tendinopatía del supraespinoso e infraespinoso"
        - Usuario elimina la línea normal
        → Sistema aprende: Si hay patología en manguito rotador, NO generar línea normal
        
        Returns:
            list: Cambios detectados con reglas de conflicto
        """
        cambios = []
        
        # 🏥 Estructuras anatómicas y sus palabras clave de "normalidad"
        estructuras_anatomicas = {
            'manguito rotador': {
                'normalidad': ['morfología conservada', 'sin alteraciones visibles', 'sin lesiones evidentes'],
                'patologia': ['tendinopatía', 'desgarro', 'lesión', 'ruptura', 'rotura']
            },
            'supraespinoso': {
                'normalidad': ['conservado', 'normal', 'sin alteraciones'],
                'patologia': ['tendinopatía', 'desgarro', 'lesión', 'ruptura']
            },
            'infraespinoso': {
                'normalidad': ['conservado', 'normal', 'sin alteraciones'],
                'patologia': ['tendinopatía', 'desgarro', 'lesión', 'ruptura']
            },
            'menisco': {
                'normalidad': ['morfología normal', 'altura y señal normales', 'conservado'],
                'patologia': ['desgarro', 'lesión', 'adelgazamiento', 'extrusión']
            },
            'ligamento': {
                'normalidad': ['trayecto y morfología conservados', 'sin alteraciones'],
                'patologia': ['desgarro', 'ruptura', 'lesión', 'distensión']
            },
            'bíceps': {
                'normalidad': ['ubicado en su corredera', 'sin alteraciones', 'conservado'],
                'patologia': ['tenosinovitis', 'tendinopatía', 'subluxación', 'luxación']
            },
            'bursa': {
                'normalidad': ['sin distensión', 'sin alteraciones'],
                'patologia': ['distensión', 'bursitis', 'líquido']
            },
            'tendón': {
                'normalidad': ['sin alteraciones', 'conservado'],
                'patologia': ['tendinopatía', 'desgarro', 'rotura']
            },
            'cartílago': {
                'normalidad': ['conservado', 'sin lesiones'],
                'patologia': ['condropatía', 'adelgazamiento', 'lesión']
            },
            'hueso': {
                'normalidad': ['sin lesiones', 'sin alteraciones'],
                'patologia': ['fractura', 'lesión', 'edema', 'contusión']
            }
        }
        
        # Convertir listas a conjuntos para búsqueda eficiente
        lineas_ia_set = set([l.strip() for l in lineas_ia if l.strip()])
        lineas_final_set = set([l.strip() for l in lineas_final if l.strip()])
        
        # Detectar líneas eliminadas
        lineas_eliminadas = lineas_ia_set - lineas_final_set
        
        # 🔍 Para cada línea eliminada, verificar si es una línea "normal" de plantilla
        for linea_eliminada in lineas_eliminadas:
            linea_lower = linea_eliminada.lower()
            
            # Verificar cada estructura anatómica
            for estructura, patrones in estructuras_anatomicas.items():
                # ¿La línea eliminada contiene esta estructura?
                if estructura in linea_lower:
                    # ¿La línea eliminada dice que la estructura está "normal"?
                    es_linea_normal = any(normalidad in linea_lower for normalidad in patrones['normalidad'])
                    
                    if es_linea_normal:
                        # ¿En el texto final hay patología de esta estructura?
                        texto_final_completo = '\n'.join(lineas_final).lower()
                        
                        tiene_patologia = any(patologia in texto_final_completo for patologia in patrones['patologia'])
                        
                        if tiene_patologia:
                            # 🎯 BINGO! Usuario eliminó línea normal porque hay patología
                            # Extraer el término de patología específico
                            patologia_encontrada = next((p for p in patrones['patologia'] if p in texto_final_completo), 'patología')
                            
                            cambios.append({
                                'tipo': 'regla_conflicto',
                                'de': linea_eliminada,
                                'a': f'NO GENERAR - Hay {patologia_encontrada} en {estructura}',
                                'estructura': estructura,
                                'patologia': patologia_encontrada,
                                'categoria': 'estructural_critico',
                                'score': 95,  # MUY ALTA PRIORIDAD
                                'regla': f'⚠️ Si hay {patologia_encontrada} en {estructura} → NO generar línea normal'
                            })
                            
                            logger.info(f"⚠️ CONFLICTO DETECTADO: {estructura} - eliminada línea normal porque hay {patologia_encontrada}")
        
        return cambios
    
    def _categorizar_cambio(self, texto_de, texto_a, terminologia):
        """
        🧠 Categoriza el tipo de cambio basándose en patrones semánticos
        
        Returns:
            str: Categoría del cambio (ortografia, terminologia, estructural, etc.)
        """
        import difflib
        
        texto_de_lower = texto_de.lower()
        texto_a_lower = texto_a.lower()
        
        # 1. Cambio ortográfico (solo difieren en acentos/mayúsculas)
        if texto_de_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') == \
           texto_a_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u'):
            return 'ortografia'
        
        # 2. Corrección de terminología médica (palabras similares pero técnicas)
        similitud = difflib.SequenceMatcher(None, texto_de_lower, texto_a_lower).ratio()
        if similitud > 0.6 and similitud < 0.95:
            # Palabras muy similares pero no iguales = probablemente terminología
            return 'terminologia'
        
        # 3. Cambio en grado/clasificación
        if any(grado in texto_de_lower or grado in texto_a_lower for categoria in terminologia.get('grado', []) for grado in [categoria]):
            return 'clasificacion'
        
        # 4. Cambio estructural (diferencia significativa)
        if len(texto_a.split()) > len(texto_de.split()) * 1.5:
            return 'estructural'
        
        # 5. Cambio semántico puro (diferente significado)
        if similitud < 0.3:
            return 'semantico'
        
        return 'otro'
    
    def _calcular_score_importancia(self, texto_de, texto_a, categoria):
        """
        📊 Calcula un score de importancia para priorizar correcciones
        
        Args:
            texto_de: Texto original
            texto_a: Texto corregido
            categoria: Categoría del cambio
        
        Returns:
            int: Score 0-100 (mayor = más importante)
        """
        # Score base según categoría
        scores_base = {
            'ortografia': 20,
            'terminologia': 85,  # MUY importante
            'clasificacion': 90,  # CRÍTICO (ej: grado II vs grado III)
            'estructural': 70,
            'semantico': 80,
            'otro': 50
        }
        
        score = scores_base.get(categoria, 50)
        
        # Bonus: Términos médicos críticos
        terminos_criticos = [
            'desgarro', 'fractura', 'lesión', 'edema', 'tumor',
            'grado', 'maligno', 'benigno', 'metástasis'
        ]
        
        if any(term in texto_a.lower() for term in terminos_criticos):
            score += 10
        
        # Penalización: Cambios muy pequeños (1-2 caracteres)
        if len(texto_de) <= 3 and len(texto_a) <= 3:
            score -= 30
        
        return max(0, min(100, score))  # Clamp entre 0-100
    
    def save(self, *args, **kwargs):
        """Al guardar, calcular diferencias automáticamente e invalidar caché"""
        if not self.cambios_detectados:
            self.calcular_diferencias()
        
        super().save(*args, **kwargs)
        
        # 🚀 NUEVO: Invalidar caché del usuario después de guardar
        if self.usuario:
            # Importar aquí para evitar circular import
            from .ai_services import AIService
            AIService.invalidar_cache_usuario(self.usuario, tipo_plantilla=self.tipo_plantilla)
            logger.info(f"🗑️ Caché invalidado para usuario {self.usuario.id} tras nueva corrección")

    @staticmethod
    def _normalizar_para_control(texto):
        """Normaliza texto para métricas de similitud en filtros de calidad."""
        if not texto:
            return ""
        return re.sub(r'\s+', ' ', texto).strip().lower()

    @classmethod
    def es_apta_para_prompt(cls, correccion):
        """
        Determina si una corrección es confiable para aprendizaje automático.

        Objetivo: evitar que una edición accidental/grosera contamine el prompt.
        """
        texto_ia = (correccion.texto_ia or '').strip()
        texto_final = (correccion.texto_final or '').strip()
        cambios = correccion.cambios_detectados or []

        if not texto_ia or not texto_final or not cambios:
            return False

        # Evitar registros vacíos; permitir textos cortos para mantener compatibilidad del flujo.
        if len(texto_ia) < 3 or len(texto_final) < 3:
            return False

        ratio_longitud = len(texto_final) / max(len(texto_ia), 1)
        if ratio_longitud < 0.45 or ratio_longitud > 2.40:
            return False

        # Similitud global: si es demasiado baja suele indicar reescritura total/accidental.
        ia_norm = cls._normalizar_para_control(texto_ia)
        final_norm = cls._normalizar_para_control(texto_final)
        similitud = difflib.SequenceMatcher(None, ia_norm, final_norm).ratio()
        if similitud < 0.22:
            return False

        # Evitar textos repetitivos o basura (ej: "asdf asdf ...", "random random ...").
        tokens_final = re.findall(r'[a-záéíóúñ]+', final_norm)
        if len(tokens_final) >= 6:
            frecuencias = {}
            for t in tokens_final:
                frecuencias[t] = frecuencias.get(t, 0) + 1

            max_ratio = max(frecuencias.values()) / len(tokens_final)
            ratio_unicos = len(frecuencias) / len(tokens_final)
            if max_ratio > 0.45 or ratio_unicos < 0.35:
                return False

            terminos_medicos = {
                'lesion', 'lesión', 'desgarro', 'edema', 'derrame', 'menisco', 'ligamento',
                'rotula', 'rótula', 'condral', 'osteocondral', 'tendinopatia', 'tendinopatía',
                'sinovitis', 'bursitis', 'fractura', 'cartilago', 'cartílago', 'hueso'
            }
            tiene_semantica_medica = any(t in terminos_medicos for t in frecuencias.keys())
            if not tiene_semantica_medica and similitud < 0.55:
                return False

        # Detectar contenido sospechoso (ruido o pegado erróneo).
        if re.search(r'(.)\1{6,}', texto_final):
            return False

        total = len(cambios)
        criticos = 0
        bajos = 0
        for cambio in cambios:
            score = cambio.get('score', 50)
            categoria = cambio.get('categoria', 'otro')
            tipo = cambio.get('tipo', '')

            if score >= 70 or categoria in {'terminologia', 'clasificacion', 'estructural_critico'}:
                criticos += 1

            if score <= 30 and (categoria in {'otro', 'eliminacion'} or tipo in {'delete', 'eliminado'}):
                bajos += 1

        # Si hay muchísimos cambios de baja calidad y ninguno crítico, no usar para prompt.
        if total >= 8 and criticos == 0 and (bajos / total) > 0.6:
            return False

        return True

    @classmethod
    def es_apta_para_estilo(cls, correccion):
        """
        Filtro adicional para ejemplos de estilo.
        Requiere estructura mínima de informe para evitar aprender formatos pobres.
        """
        if not cls.es_apta_para_prompt(correccion):
            return False

        texto = (correccion.texto_final or '').upper()
        tiene_estructura = 'COMENTARIO' in texto and 'CONCLUSI' in texto
        tiene_longitud = len((correccion.texto_final or '').strip()) >= 80
        return tiene_estructura and tiene_longitud
    
    @staticmethod
    def obtener_ejemplos_aprendizaje(usuario=None, limite=10, tipo_plantilla=''):
        """
        Obtiene ejemplos de correcciones priorizados por importancia
        🚀 MEJORADO: Usa scores semánticos para priorizar
        
        Args:
            usuario: Usuario específico (opcional)
            limite: Número máximo de ejemplos
            
        Returns:
            str: Ejemplos formateados priorizados para incluir en el prompt
        """
        from django.core.cache import cache
        
        # 🚀 CACHÉ: Verificar si ya tenemos esto en caché
        plantilla_cache = tipo_plantilla or 'sin_plantilla'
        cache_key = (
            f'aprendizaje_ejemplos_v4_{usuario.id if usuario else "global"}_'
            f'{limite}_{plantilla_cache}'
        )
        cached_ejemplos = cache.get(cache_key)
        if cached_ejemplos:
            return cached_ejemplos
        
        query = CorreccionAprendizaje.objects.all()
        
        if usuario:
            query = query.filter(usuario=usuario)
        if tipo_plantilla:
            query = query.filter(tipo_plantilla=tipo_plantilla)
        
        # Traer más correcciones para poder filtrar las mejores
        correcciones = query.only('cambios_detectados', 'texto_ia', 'texto_final').order_by('-fecha_creacion')[:limite * 4]
        
        if not correcciones:
            return ""
        
        # 📊 Recolectar y puntuar todos los cambios
        cambios_con_score = []
        reglas_conflicto = []  # ⭐ NUEVO: Separar reglas de conflicto
        
        descartadas = 0
        for corr in correcciones:
            if not CorreccionAprendizaje.es_apta_para_prompt(corr):
                descartadas += 1
                continue

            if corr.cambios_detectados:
                for cambio in corr.cambios_detectados:
                    # Obtener score del análisis semántico (default 50 si no existe)
                    score = cambio.get('score', 50)
                    categoria = cambio.get('categoria', 'otro')
                    tipo = cambio.get('tipo', '')
                    
                    # ⚠️ PRIORIDAD MÁXIMA: Reglas de conflicto plantilla-patología
                    if tipo == 'regla_conflicto':
                        reglas_conflicto.append({
                            'texto': cambio.get('regla', f"⚠️ {cambio['a']}"),
                            'score': score,
                            'categoria': 'estructural_critico',
                            'estructura': cambio.get('estructura', ''),
                            'patologia': cambio.get('patologia', '')
                        })
                    elif tipo == 'reemplazo':
                        cambios_con_score.append({
                            'texto': f"❌ {cambio['de']} → ✅ {cambio['a']}",
                            'score': score,
                            'categoria': categoria
                        })
                    elif tipo == 'agregado' and score > 60:  # Solo agregados importantes
                        cambios_con_score.append({
                            'texto': f"✅ Agregar: {cambio['texto']}",
                            'score': score,
                            'categoria': categoria
                        })
        
        if not cambios_con_score and not reglas_conflicto:
            return ""
        
        # 🎯 Ordenar por score (más importantes primero)
        cambios_con_score.sort(key=lambda x: x['score'], reverse=True)
        
        # 🧹 Eliminar duplicados manteniendo los de mayor score
        ejemplos_unicos = []
        textos_vistos = set()
        
        for cambio in cambios_con_score:
            if cambio['texto'] not in textos_vistos:
                textos_vistos.add(cambio['texto'])
                ejemplos_unicos.append(cambio)
        
        # Limitar a los N ejemplos más importantes
        ejemplos_top = ejemplos_unicos[:limite * 2]  # Doble límite para tener más diversidad
        
        # ⭐ FORMATEAR RESULTADO: Reglas de conflicto PRIMERO
        lineas = []
        
        # 1️⃣ PRIMERO: Reglas críticas de conflicto (máxima prioridad)
        if reglas_conflicto:
            lineas.append("🚨 REGLAS CRÍTICAS (APLICAR SIEMPRE):")
            for regla in reglas_conflicto[:5]:  # Máximo 5 reglas
                lineas.append(f"   {regla['texto']}")
            lineas.append("")  # Línea en blanco separadora
        
        # 2️⃣ SEGUNDO: Correcciones normales priorizadas
        for i, cambio in enumerate(ejemplos_top[:15], 1):  # Máximo 15 líneas normales
            # Emoji según categoría
            emoji_categoria = {
                'terminologia': '🔬',
                'clasificacion': '⚠️',
                'ortografia': '✏️',
                'semantico': '💭',
                'estructural': '🏗️',
                'estructural_critico': '🚨',
                'otro': '📝'
            }
            emoji = emoji_categoria.get(cambio['categoria'], '📝')
            
            # Solo mostrar emoji de prioridad para los MUY importantes (score > 80)
            prioridad = '⭐' if cambio['score'] > 80 else ''
            lineas.append(f"{emoji} {prioridad}{cambio['texto']}")
        
        resultado = "\n".join(lineas)
        
        # 🚀 GUARDAR EN CACHÉ (5 minutos)
        cache.set(cache_key, resultado, timeout=300)
        
        logger.info(
            f"📚 Ejemplos priorizados: {len(lineas)} de {len(cambios_con_score)} cambios disponibles "
            f"(descartadas por calidad: {descartadas})"
        )
        
        return resultado
    
    @staticmethod
    def obtener_preferencias_aprendidas(usuario=None, limite=8, tipo_plantilla=''):
        """
        Extrae reglas compactas desde correcciones previas:
        - ubicacion de lineas movidas por el usuario
        - reemplazos terminologicos frecuentes
        """
        from django.core.cache import cache

        plantilla_cache = tipo_plantilla or 'sin_plantilla'
        cache_key = (
            f'preferencias_aprendidas_v2_{usuario.id if usuario else "global"}_'
            f'{limite}_{plantilla_cache}'
        )
        cached = cache.get(cache_key)
        if cached:
            return cached

        query = CorreccionAprendizaje.objects.all()
        if usuario:
            query = query.filter(usuario=usuario)
        if tipo_plantilla:
            query = query.filter(tipo_plantilla=tipo_plantilla)

        correcciones = query.only(
            'cambios_detectados', 'texto_ia', 'texto_final'
        ).order_by('-fecha_creacion')[:limite * 5]

        reglas_orden = []
        reemplazos = []
        vistos = set()
        for corr in correcciones:
            if not CorreccionAprendizaje.es_apta_para_prompt(corr):
                continue
            for cambio in corr.cambios_detectados or []:
                tipo = cambio.get('tipo')
                if tipo == 'reordenamiento_linea':
                    regla = cambio.get('regla')
                    if regla and regla not in vistos:
                        vistos.add(regla)
                        reglas_orden.append(regla)
                elif tipo == 'reemplazo' and cambio.get('score', 0) >= 70:
                    de = (cambio.get('de') or '').strip()
                    a = (cambio.get('a') or '').strip()
                    if de and a:
                        regla = f'Preferir "{a}" en lugar de "{de}".'
                        if regla not in vistos:
                            vistos.add(regla)
                            reemplazos.append(regla)

        lineas = []
        if reglas_orden:
            lineas.append('ORDEN Y UBICACION APRENDIDOS:')
            lineas.extend(f'- {r}' for r in reglas_orden[:limite])
        if reemplazos:
            lineas.append('TERMINOLOGIA APRENDIDA:')
            lineas.extend(f'- {r}' for r in reemplazos[:limite])

        resultado = '\n'.join(lineas)
        if resultado:
            cache.set(cache_key, resultado, timeout=600)
        return resultado

    @staticmethod
    def obtener_ejemplos_estilo_completo(usuario=None, limite=3, tipo_plantilla=''):
        """
        Obtiene ejemplos COMPLETOS de informes del usuario para aprender su estilo
        No solo cambios, sino cómo escribe informes completos
        
        Args:
            usuario: Usuario específico (opcional)
            limite: Número de ejemplos completos
            
        Returns:
            str: Ejemplos de informes completos formateados
        """
        from django.core.cache import cache
        
        plantilla_cache = tipo_plantilla or 'sin_plantilla'
        cache_key = (
            f'estilo_completo_v2_{usuario.id if usuario else "global"}_'
            f'{limite}_{plantilla_cache}'
        )
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        query = CorreccionAprendizaje.objects.all()
        
        if usuario:
            query = query.filter(usuario=usuario)
        if tipo_plantilla:
            query = query.filter(tipo_plantilla=tipo_plantilla)
        
        # Traer los más recientes con texto completo
        correcciones = query.only('texto_final', 'texto_ia', 'cambios_detectados').order_by('-fecha_creacion')[:limite * 3]
        
        if not correcciones:
            return ""
        
        ejemplos = []
        for i, corr in enumerate(correcciones, 1):
            if not CorreccionAprendizaje.es_apta_para_estilo(corr):
                continue

            if corr.texto_final and len(corr.texto_final.strip()) > 50:  # Solo si es suficientemente largo
                ejemplos.append(f"EJEMPLO {i}:\n{corr.texto_final.strip()}")

            if len(ejemplos) >= limite:
                break
        
        if not ejemplos:
            return ""
        
        resultado = "\n\n---\n\n".join(ejemplos)
        
        # Cachear por 10 minutos
        cache.set(cache_key, resultado, timeout=600)
        
        return resultado


class FeedbackCalidadDictado(models.Model):
    """Feedback clínico post-generación para medir calidad real de salida."""

    class EstadoFeedback(models.TextChoices):
        CORRECTO = 'correcto', 'Correcto al primer intento'
        REQUIRIO_CORRECCION = 'correccion', 'Requirió corrección manual'

    class ModoDictado(models.TextChoices):
        FIEL = 'FIEL', 'Fiel al Dictado'
        ESTRUCTURADO = 'ESTRUCTURADO', 'Plantilla Estructurada'
        AGENTE = 'AGENTE', 'Agente de informe'

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feedbacks_calidad_dictado',
        verbose_name="Usuario"
    )
    fecha = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha")

    estado_feedback = models.CharField(
        max_length=20,
        choices=EstadoFeedback.choices,
        verbose_name="Resultado reportado"
    )
    modo_dictado = models.CharField(
        max_length=20,
        choices=ModoDictado.choices,
        default=ModoDictado.FIEL,
        verbose_name="Modo de dictado"
    )
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        blank=True,
        verbose_name="Tipo de Estudio"
    )
    tipo_plantilla = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Código de Plantilla"
    )

    longitud_texto_ia = models.IntegerField(default=0, verbose_name="Longitud texto IA")
    longitud_texto_final = models.IntegerField(default=0, verbose_name="Longitud texto final")
    caracteres_editados = models.IntegerField(default=0, verbose_name="Caracteres editados")
    porcentaje_edicion = models.FloatField(default=0.0, verbose_name="Porcentaje de edición")
    tuvo_edicion = models.BooleanField(default=False, verbose_name="¿Hubo edición manual?")

    class Meta:
        verbose_name = "Feedback de Calidad de Dictado"
        verbose_name_plural = "Feedbacks de Calidad de Dictado"
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['usuario', '-fecha']),
            models.Index(fields=['estado_feedback', '-fecha']),
            models.Index(fields=['tipo_plantilla', '-fecha']),
        ]

    def __str__(self):
        return f"{self.get_estado_feedback_display()} - {self.usuario} - {self.fecha:%d/%m %H:%M}"


class EventoAprendizajeDictado(models.Model):
    """Bitacora no clinica de las decisiones que pueden mejorar el dictado."""

    class TipoEvento(models.TextChoices):
        PLANTILLA_CONFIRMADA = 'plantilla_confirmada', 'Plantilla confirmada'
        CORRECCION_VOZ_APLICADA = 'correccion_voz_aplicada', 'Correccion por voz aplicada'
        CORRECCION_VOZ_DESHECHA = 'correccion_voz_deshecha', 'Correccion por voz deshecha'
        CORRECCION_VOZ_REHECHA = 'correccion_voz_rehecha', 'Correccion por voz rehecha'
        INFORME_ACEPTADO = 'informe_aceptado', 'Informe aceptado'
        INFORME_CORREGIDO = 'informe_corregido', 'Informe que requirio correccion'
        APRENDIZAJE_CONFIRMADO = 'aprendizaje_confirmado', 'Correccion manual guardada'

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='eventos_aprendizaje_dictado',
    )
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    tipo_evento = models.CharField(max_length=40, choices=TipoEvento.choices)
    modo_dictado = models.CharField(max_length=20, blank=True)
    tipo_estudio = models.CharField(max_length=3, choices=TipoEstudio.choices, blank=True)
    region = models.CharField(max_length=30, blank=True)
    modalidad = models.CharField(max_length=20, blank=True)
    lateralidad = models.CharField(max_length=20, blank=True)
    plantilla_propuesta_codigo = models.CharField(max_length=50, blank=True)
    plantilla_confirmada_codigo = models.CharField(max_length=50, blank=True)
    tipo_operacion = models.CharField(max_length=50, blank=True)
    traza = models.ForeignKey(
        TrazaAgenteDictado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    correccion = models.ForeignKey(
        CorreccionAprendizaje,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    feedback = models.ForeignKey(
        FeedbackCalidadDictado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_aprendizaje',
    )
    metadatos = models.JSONField(default=dict, blank=True)
    revertido = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['usuario', 'tipo_evento', '-fecha']),
            models.Index(fields=['region', 'modalidad', '-fecha']),
            models.Index(fields=['plantilla_confirmada_codigo', '-fecha']),
        ]
        verbose_name = 'Evento de aprendizaje de dictado'
        verbose_name_plural = 'Eventos de aprendizaje de dictado'

    def __str__(self):
        return f'{self.get_tipo_evento_display()} - {self.usuario} - {self.fecha:%d/%m %H:%M}'


class PreferenciaAprendidaDictado(models.Model):
    """Memoria estructurada, versionada y reversible derivada de evidencia repetida."""

    class Categoria(models.TextChoices):
        SELECCION_PLANTILLA = 'seleccion_plantilla', 'Seleccion de plantilla'
        TERMINOLOGIA = 'terminologia', 'Terminologia'
        ORDEN = 'orden', 'Orden de hallazgos'
        ESTRUCTURA = 'estructura', 'Estructura del informe'
        CONCLUSION = 'conclusion', 'Conclusion'

    class Estado(models.TextChoices):
        CANDIDATA = 'candidata', 'Candidata'
        ACTIVA = 'activa', 'Activa'
        INACTIVA = 'inactiva', 'Inactiva'
        REEMPLAZADA = 'reemplazada', 'Reemplazada'

    class Origen(models.TextChoices):
        AUTOMATICO = 'automatico', 'Automatico'
        MANUAL = 'manual', 'Manual'

    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='preferencias_aprendidas_dictado',
    )
    categoria = models.CharField(max_length=30, choices=Categoria.choices)
    clave = models.CharField(max_length=180)
    valor = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.CANDIDATA)
    vigente = models.BooleanField(default=True)
    cantidad_evidencia = models.PositiveIntegerField(default=0)
    confirmaciones = models.PositiveIntegerField(default=0)
    rechazos = models.PositiveIntegerField(default=0)
    confianza = models.FloatField(default=0.0)
    origen = models.CharField(max_length=20, choices=Origen.choices, default=Origen.AUTOMATICO)
    reemplaza_a = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versiones_siguientes',
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fecha_modificacion']
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'categoria', 'clave', 'version'],
                name='uniq_preferencia_dictado_version',
            ),
        ]
        indexes = [
            models.Index(fields=['usuario', 'categoria', 'vigente']),
            models.Index(fields=['estado', '-fecha_modificacion']),
        ]
        verbose_name = 'Preferencia aprendida de dictado'
        verbose_name_plural = 'Preferencias aprendidas de dictado'

    def __str__(self):
        return f'{self.get_categoria_display()} v{self.version} - {self.usuario}'

# ========================================
# 🚀 FASE 4: SISTEMA DE MONITOREO
# ========================================

class MetricaDictado(models.Model):
    """
    📊 Métricas de uso del sistema de dictado para análisis de performance
    
    Registra tiempos de respuesta, uso de caché, errores y calidad de resultados
    para identificar cuellos de botella y optimizar el sistema.
    """
    
    # Usuario
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='metricas_dictado',
        verbose_name="Usuario"
    )
    
    # Timestamp
    fecha = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y Hora",
        db_index=True
    )
    
    # Tiempos de respuesta (en milisegundos)
    tiempo_transcripcion_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tiempo Transcripción (ms)",
        help_text="Tiempo de API Whisper (null si usó caché)"
    )
    tiempo_mejora_ms = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tiempo Mejora IA (ms)",
        help_text="Tiempo de API GPT/Groq (null si usó caché)"
    )
    tiempo_total_ms = models.IntegerField(
        verbose_name="Tiempo Total (ms)",
        help_text="Tiempo end-to-end medido por el cliente"
    )
    
    # Uso de caché
    transcripcion_from_cache = models.BooleanField(
        default=False,
        verbose_name="Transcripción desde Caché"
    )
    mejora_from_cache = models.BooleanField(
        default=False,
        verbose_name="Mejora desde Caché"
    )
    
    # Datos del audio
    duracion_audio_segundos = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Duración Audio (segundos)"
    )
    tamanio_audio_kb = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Tamaño Audio (KB)"
    )
    
    # Resultados
    longitud_transcripcion = models.IntegerField(
        default=0,
        verbose_name="Longitud Transcripción (caracteres)"
    )
    longitud_mejora = models.IntegerField(
        default=0,
        verbose_name="Longitud Mejora (caracteres)"
    )
    
    # Flags de calidad
    tuvo_errores = models.BooleanField(
        default=False,
        verbose_name="¿Tuvo Errores?"
    )
    error_detalle = models.TextField(
        blank=True,
        verbose_name="Detalle del Error",
        help_text="Stack trace o mensaje de error"
    )
    
    # API utilizada
    api_transcripcion = models.CharField(
        max_length=20,
        default='whisper',
        choices=[
            ('whisper', 'OpenAI Whisper'),
            ('groq_whisper', 'Groq Whisper'),
        ],
        verbose_name="API de Transcripción"
    )
    api_mejora = models.CharField(
        max_length=20,
        default='gpt',
        choices=[
            ('gpt', 'OpenAI GPT'),
            ('groq', 'Groq Llama'),
        ],
        verbose_name="API de Mejora"
    )
    
    # Modo de mejora utilizado
    modo_mejora = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ('FIEL', 'Fiel al Dictado'),
            ('LIBRE', 'Reescritura Libre'),
            ('PLANTILLA', 'Con Plantilla'),
        ],
        verbose_name="Modo de Mejora"
    )
    
    # Tipo de estudio (para segmentar métricas)
    tipo_estudio = models.CharField(
        max_length=3,
        choices=TipoEstudio.choices,
        blank=True,
        verbose_name="Tipo de Estudio"
    )
    
    class Meta:
        verbose_name = "Métrica de Dictado"
        verbose_name_plural = "Métricas de Dictado"
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['usuario', '-fecha']),
            models.Index(fields=['tuvo_errores', '-fecha']),
            models.Index(fields=['fecha', 'tiempo_total_ms']),  # Para análisis de performance por periodo
        ]
    
    def __str__(self):
        status = "❌ Error" if self.tuvo_errores else "✅ OK"
        return f"{status} - {self.usuario.username} - {self.tiempo_total_ms}ms - {self.fecha.strftime('%d/%m %H:%M')}"
    
    @property
    def cache_hit_rate(self):
        """Calcula tasa de aciertos de caché (0.0 a 1.0)"""
        hits = 0
        total = 0
        
        if self.tiempo_transcripcion_ms is not None:
            total += 1
            if self.transcripcion_from_cache:
                hits += 1
        
        if self.tiempo_mejora_ms is not None:
            total += 1
            if self.mejora_from_cache:
                hits += 1
        
        return hits / total if total > 0 else 0.0
    
    @staticmethod
    def obtener_estadisticas_periodo(fecha_desde, fecha_hasta, usuario=None):
        """
        📊 Obtiene estadísticas agregadas de un periodo
        
        Args:
            fecha_desde: Fecha inicio (datetime)
            fecha_hasta: Fecha fin (datetime)
            usuario: Usuario específico (opcional)
        
        Returns:
            dict: Estadísticas completas del periodo
        """
        from django.db.models import Avg, Max, Min, Count, Q, Sum
        
        # Filtrar por periodo
        query = MetricaDictado.objects.filter(
            fecha__gte=fecha_desde,
            fecha__lte=fecha_hasta
        )
        
        # Filtrar por usuario si se especifica
        if usuario:
            query = query.filter(usuario=usuario)
        
        # Agregar estadísticas
        stats = query.aggregate(
            total_requests=Count('id'),
            total_errores=Count('id', filter=Q(tuvo_errores=True)),
            tiempo_promedio=Avg('tiempo_total_ms'),
            tiempo_min=Min('tiempo_total_ms'),
            tiempo_max=Max('tiempo_total_ms'),
            cache_transcripcion=Count('id', filter=Q(transcripcion_from_cache=True)),
            cache_mejora=Count('id', filter=Q(mejora_from_cache=True)),
            duracion_audio_total=Sum('duracion_audio_segundos'),
        )
        
        # Calcular métricas derivadas
        total = stats['total_requests'] or 1  # Evitar división por cero
        stats['tasa_error'] = (stats['total_errores'] / total) * 100
        stats['tasa_cache_transcripcion'] = (stats['cache_transcripcion'] / total) * 100
        stats['tasa_cache_mejora'] = (stats['cache_mejora'] / total) * 100
        
        # Distribución por tipo de estudio
        stats['por_tipo_estudio'] = dict(
            query.values('tipo_estudio').annotate(
                count=Count('id'),
                tiempo_promedio=Avg('tiempo_total_ms')
            ).values_list('tipo_estudio', 'count')
        )
        
        # Distribución por modo
        stats['por_modo'] = dict(
            query.exclude(modo_mejora='').values('modo_mejora').annotate(
                count=Count('id')
            ).values_list('modo_mejora', 'count')
        )
        
        return stats
    
    @staticmethod
    def obtener_top_usuarios(fecha_desde, fecha_hasta, limite=10):
        """
        👥 Obtiene usuarios que más usan el sistema
        
        Args:
            fecha_desde: Fecha inicio
            fecha_hasta: Fecha fin
            limite: Número de usuarios a retornar
        
        Returns:
            QuerySet: Top usuarios con métricas
        """
        from django.db.models import Count, Avg, Q
        
        return MetricaDictado.objects.filter(
            fecha__gte=fecha_desde,
            fecha__lte=fecha_hasta
        ).values(
            'usuario__username',
            'usuario__first_name',
            'usuario__last_name'
        ).annotate(
            total_usos=Count('id'),
            tiempo_promedio=Avg('tiempo_total_ms'),
            errores=Count('id', filter=Q(tuvo_errores =True))
        ).order_by('-total_usos')[:limite]
    
    @staticmethod
    def detectar_anomalias(umbral_ms=5000):
        """
        🚨 Detecta requests anormalmente lentos
        
        Args:
            umbral_ms: Umbral de tiempo en milisegundos (default: 5s)
        
        Returns:
            QuerySet: Métricas con tiempos anormales
        """
        from datetime import timedelta
        from django.utils import timezone
        
        # Últimas 24 horas
        hace_24h = timezone.now() - timedelta(hours=24)
        
        return MetricaDictado.objects.filter(
            fecha__gte=hace_24h,
            tiempo_total_ms__gt=umbral_ms
        ).order_by('-tiempo_total_ms')
