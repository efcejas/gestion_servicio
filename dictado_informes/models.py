from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import re

User = get_user_model()


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
    def procesar_comandos_voz(texto):
        """
        Procesa comandos de voz como 'nueva línea', 'punto', etc.
        También limpia artefactos de transcripción como "., " o ", ."
        
        Args:
            texto (str): Texto con comandos de voz
        
        Returns:
            str: Texto con comandos reemplazados por formato
        """
        if not texto:
            return texto
        
        # PASO 1: Reemplazar comandos de voz literales
        comandos = {
            # Saltos de línea (prioridad alta)
            r'\bnueva línea\b': '\n',
            r'\bnueva linea\b': '\n',
            r'\bsalto de línea\b': '\n',
            r'\bsalto de linea\b': '\n',
            r'\bpunto y aparte\b': '.\n\n',
            r'\bpárrafo nuevo\b': '\n\n',
            
            # Punto seguido (mantener en misma línea)
            r'\bpunto seguido\b': '. ',  # Punto + espacio, SIN salto
            r'\bseguido\b': '. ',        # Atajo: solo "seguido"
            
            # Puntuación básica
            r'\bpunto\b': '.',
            r'\bcoma\b': ',',
            r'\bdos puntos\b': ':',
            r'\bpunto y coma\b': ';',
            
            # Símbolos
            r'\bparéntesis abre\b': '(',
            r'\bparéntesis cierra\b': ')',
            r'\binterrogación abre\b': '¿',
            r'\binterrogación cierra\b': '?',
        }
        
        texto_procesado = texto
        for patron, reemplazo in comandos.items():
            texto_procesado = re.sub(patron, reemplazo, texto_procesado, flags=re.IGNORECASE)
        
        # PASO 2: CONVERSIÓN AUTOMÁTICA DE GRADOS A NÚMEROS ROMANOS
        # Convierte "grado 1/2/3/4" → "grado I/II/III/IV"
        conversiones_grado = {
            r'\bgrado\s+1\b': 'grado I',
            r'\bgrado\s+2\b': 'grado II',
            r'\bgrado\s+3\b': 'grado III',
            r'\bgrado\s+4\b': 'grado IV',
        }
        
        for patron, reemplazo in conversiones_grado.items():
            texto_procesado = re.sub(patron, reemplazo, texto_procesado, flags=re.IGNORECASE)
        
        # PASO 3: LIMPIAR ARTEFACTOS DE WHISPER
        # Cuando dices "nueva línea", Whisper puede transcribir como "., " o dejar espacios extra
        
        # 1. Limpiar combinaciones extrañas de puntuación
        texto_procesado = re.sub(r',\s*\.\s*,', '.\n', texto_procesado)  # ", ., " → ".\n"
        texto_procesado = re.sub(r'\.\s*,\s*\n', '.\n', texto_procesado)  # "., \n" → ".\n"
        texto_procesado = re.sub(r',\s*\.\s*\n', '.\n', texto_procesado)  # ", .\n" → ".\n"
        texto_procesado = re.sub(r',\s*\.\s*', '.\n', texto_procesado)    # ", ." → ".\n"
        texto_procesado = re.sub(r'\.\s*,\s*', '.\n', texto_procesado)    # "., " → ".\n"
        
        # 2. Doble punto → salto de línea
        texto_procesado = re.sub(r'\.\s*\.\s*', '.\n', texto_procesado)   # ".." → ".\n"
        
        # 3. Limpiar comas antes de saltos de línea
        texto_procesado = re.sub(r',\s*\n', '\n', texto_procesado)        # ",\n" → "\n"
        
        # 4. Limpiar espacios alrededor de saltos de línea
        texto_procesado = re.sub(r'\s+\n', '\n', texto_procesado)         # " \n" → "\n"
        texto_procesado = re.sub(r'\n\s+', '\n', texto_procesado)         # "\n " → "\n"
        
        # 5. Limitar saltos de línea consecutivos
        texto_procesado = re.sub(r'\n{3,}', '\n\n', texto_procesado)      # "\n\n\n..." → "\n\n"
        
        # 6. Capitalizar primera letra después de punto (con o sin salto)
        def capitalizar_despues_punto(match):
            return match.group(1) + match.group(2).upper()
        
        # Capitalizar después de punto + salto
        texto_procesado = re.sub(r'(\.\s*\n)([a-záéíóúñ])', capitalizar_despues_punto, texto_procesado)
        # Capitalizar después de punto + espacio (punto seguido)
        texto_procesado = re.sub(r'(\.\s+)([a-záéíóúñ])', capitalizar_despues_punto, texto_procesado)
        
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
        Calcula las diferencias entre texto_ia y texto_final
        Guarda en cambios_detectados
        """
        import difflib
        
        # Usar difflib para detectar cambios palabra por palabra
        palabras_ia = self.texto_ia.split()
        palabras_final = self.texto_final.split()
        
        matcher = difflib.SequenceMatcher(None, palabras_ia, palabras_final)
        cambios = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                cambios.append({
                    'tipo': 'reemplazo',
                    'de': ' '.join(palabras_ia[i1:i2]),
                    'a': ' '.join(palabras_final[j1:j2])
                })
            elif tag == 'delete':
                cambios.append({
                    'tipo': 'eliminado',
                    'texto': ' '.join(palabras_ia[i1:i2])
                })
            elif tag == 'insert':
                cambios.append({
                    'tipo': 'agregado',
                    'texto': ' '.join(palabras_final[j1:j2])
                })
        
        self.cambios_detectados = cambios
        return cambios
    
    def save(self, *args, **kwargs):
        """Al guardar, calcular diferencias automáticamente"""
        if not self.cambios_detectados:
            self.calcular_diferencias()
        super().save(*args, **kwargs)
    
    @staticmethod
    def obtener_ejemplos_aprendizaje(usuario=None, limite=10):
        """
        Obtiene los ejemplos de correcciones más recientes para entrenar la IA
        🚀 OPTIMIZADO: Con caché y solo campos necesarios
        
        Args:
            usuario: Usuario específico (opcional)
            limite: Número máximo de ejemplos
            
        Returns:
            str: Ejemplos formateados para incluir en el prompt
        """
        from django.core.cache import cache
        
        # 🚀 CACHÉ: Verificar si ya tenemos esto en caché
        cache_key = f'aprendizaje_ejemplos_{usuario.id if usuario else "global"}_{limite}'
        cached_ejemplos = cache.get(cache_key)
        if cached_ejemplos:
            return cached_ejemplos
        
        query = CorreccionAprendizaje.objects.all()
        
        if usuario:
            query = query.filter(usuario=usuario)
        
        # 🚀 OPTIMIZACIÓN: Solo traer campos necesarios
        correcciones = query.only('cambios_detectados')[:limite]
        
        if not correcciones:
            return ""
        
        ejemplos = []
        for corr in correcciones:
            if corr.cambios_detectados:
                # Formatear cada cambio detectado
                for cambio in corr.cambios_detectados:
                    if cambio['tipo'] == 'reemplazo':
                        ejemplos.append(f"❌ {cambio['de']} → ✅ {cambio['a']}")
                    elif cambio['tipo'] == 'agregado':
                        ejemplos.append(f"✅ Agregar: {cambio['texto']}")
        
        if not ejemplos:
            return ""
        
        # Limitar a los 20 ejemplos más relevantes
        ejemplos_unicos = list(dict.fromkeys(ejemplos))[:20]
        resultado = "\n".join(ejemplos_unicos)
        
        # 🚀 GUARDAR EN CACHÉ (5 minutos)
        cache.set(cache_key, resultado, timeout=300)
        
        return resultado
