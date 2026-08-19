import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class ImportBatch(models.Model):
    """
    Representa un lote de importación de datos EGES.
    Cada vez que se sube un Excel, se crea un batch.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='batches_eges')
    archivo_nombre = models.CharField(max_length=255)
    archivo_sha256 = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        verbose_name='Huella SHA-256 del archivo',
        help_text='Permite rechazar reimportaciones exactas sin alterar lotes históricos.',
    )
    fecha_importacion = models.DateTimeField(default=timezone.now)
    total_filas = models.IntegerField(default=0)

    # Métricas calculadas
    total_ingresos_unicos = models.IntegerField(default=0)
    total_estudios_candidatos = models.IntegerField(default=0)  # No insumos
    total_estudios_finalizados = models.IntegerField(default=0)  # Estado = Informado

    # Contadores por modalidad (finalizados = Informado)
    total_tc = models.IntegerField(default=0)
    total_rm = models.IntegerField(default=0)
    total_rx = models.IntegerField(default=0)
    total_dx = models.IntegerField(default=0)
    total_mam = models.IntegerField(default=0)
    total_eco = models.IntegerField(default=0)
    total_serie = models.IntegerField(default=0)
    total_otros = models.IntegerField(default=0)

    # Contadores de estados especiales
    total_rx_sin_informe = models.IntegerField(default=0)  # Estado = Entregado Sin Informe

    class Meta:
        ordering = ['-fecha_importacion']
        verbose_name = 'Lote de importación EGES'
        verbose_name_plural = 'Lotes de importación EGES'

    def __str__(self):
        return f"Batch {self.id} - {self.archivo_nombre} ({self.fecha_importacion.strftime('%d/%m/%Y %H:%M')})"

    def calcular_metricas(self):
        """
        Calcula todas las métricas del batch basándose en las filas importadas.
        """
        filas = self.filas.all()
        self.total_filas = filas.count()

        # Ingresos únicos: agrupamos por HC + fecha + hora + centro
        ingresos_unicos = filas.values(
            'historia_clinica', 'fecha_turno', 'hora_turno', 'centro_atencion'
        ).distinct().count()
        self.total_ingresos_unicos = ingresos_unicos

        # Estudios candidatos (no insumos)
        estudios = filas.filter(es_insumo=False)
        self.total_estudios_candidatos = estudios.count()

        # Estudios finalizados (Estado = Informado)
        finalizados = estudios.filter(estado_turno__iexact='Informado')
        self.total_estudios_finalizados = finalizados.count()

        # Por modalidad (entre finalizados = Informado)
        self.total_tc = finalizados.filter(modalidad='TC').count()
        self.total_rm = finalizados.filter(modalidad='RM').count()
        self.total_rx = finalizados.filter(modalidad='RX').count()
        self.total_dx = finalizados.filter(modalidad='DX').count()
        self.total_mam = finalizados.filter(modalidad='MAM').count()
        self.total_eco = finalizados.filter(modalidad='ECO').count()
        self.total_serie = finalizados.filter(modalidad='SERIE').count()
        self.total_otros = finalizados.filter(modalidad='OTROS').count()

        # Estados especiales (RX entregado sin informe: cerrado pero sin reporte médico)
        self.total_rx_sin_informe = estudios.filter(
            modalidad='RX',
            estado_turno__iexact='Entregado Sin Informe',
        ).count()

        self.save()


class EgesRow(models.Model):
    """
    Representa una fila cruda del Excel EGES.

    IMPORTANTE: Usa unique_together para evitar duplicados.
    Si una fila con la misma combinación HC+Fecha+Hora+Centro+Práctica ya existe, se ignora.
    """
    MODALIDAD_CHOICES = [
        ('TC', 'Tomografía Computada'),
        ('RM', 'Resonancia Magnética'),
        ('RX', 'Rayos X / Radiología'),
        ('DX', 'Densitometría'),
        ('MAM', 'Mamografía'),
        ('ECO', 'Ecografía'),
        ('SERIE', 'Seriografía'),
        ('OTROS', 'Otros'),
    ]

    # Sub-modalidades para ECO (también se usa como choices en formularios/admin)
    SUB_MODALIDAD_ECO_CHOICES = [
        ('ECOCARDIO', 'Ecocardiograma'),
        ('DOPPLER', 'Doppler / Dúplex'),
        ('ECO_MAMA', 'Ecografía Mamaria'),
        ('ECO_TIROIDES', 'Ecografía Tiroidea'),
        ('ECO_OBSTETRICA', 'Ecografía Obstétrica'),
        ('ECO_PELVIS', 'Ecografía Pelviana'),
        ('ECO_ABDOMINAL', 'Ecografía Abdominal'),
        ('ECO_NEONATAL', 'Ecografía Neonatal'),
        ('ECO_PARTES_BLANDAS', 'Ecografía Partes Blandas'),
    ]

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='filas')

    # Identificación del turno/ingreso
    numero_turno = models.CharField(max_length=50, blank=True, null=True)
    protocolo = models.CharField(max_length=80, blank=True, null=True, db_index=True)
    fecha_turno = models.DateField(null=True, blank=True)
    hora_turno = models.TimeField(null=True, blank=True)
    hora_hasta = models.TimeField(null=True, blank=True)
    centro_atencion = models.CharField(max_length=100, blank=True, null=True)
    tipo_atencion = models.CharField(max_length=50, blank=True, null=True)

    # Paciente
    dni_paciente = models.CharField(max_length=20, blank=True, null=True)
    historia_clinica = models.CharField(max_length=50, blank=True, null=True)
    numero_afiliado = models.CharField(max_length=50, blank=True, null=True)
    apellido_nombre = models.CharField(max_length=200, blank=True, null=True)

    # Estudio
    servicio = models.CharField(max_length=200, blank=True, null=True)
    equipo = models.CharField(max_length=100, blank=True, null=True)
    estado_turno = models.CharField(max_length=50, blank=True, null=True)
    estado_informe = models.CharField(max_length=50, blank=True, null=True)
    tipo_turno = models.CharField(max_length=50, blank=True, null=True)
    tipo_paciente = models.CharField(max_length=50, blank=True, null=True)
    region_informe = models.CharField(max_length=100, blank=True, null=True)

    # Práctica específica: nomenclador EGES — más específico que 'servicio'
    practica = models.CharField(max_length=300, blank=True, null=True)
    codigo_practica = models.CharField(max_length=30, blank=True, null=True)
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, default=1)

    # Cobertura / obra social
    obra_social = models.CharField(max_length=200, blank=True, null=True)
    codigo_obra_social = models.CharField(max_length=20, blank=True, null=True)

    # Médico informante (capturado desde la columna del Excel si existe)
    medico_informante = models.CharField(max_length=200, blank=True, null=True)
    medico_actuante = models.CharField(max_length=200, blank=True, null=True)
    tecnico = models.CharField(max_length=200, blank=True, null=True)

    # Datos operativos disponibles en el reporte "Atendidos" de EGES
    duracion_minutos = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    contraste_eges = models.CharField(max_length=30, blank=True, null=True)
    anestesia_eges = models.CharField(max_length=30, blank=True, null=True)
    aplicacion_origen = models.CharField(max_length=80, blank=True, null=True)

    # Clasificación principal
    es_insumo = models.BooleanField(default=False)
    modalidad = models.CharField(max_length=10, choices=MODALIDAD_CHOICES, default='OTROS')

    # Sub-clasificación: solo se popula cuando modalidad == 'ECO'
    sub_modalidad = models.CharField(
        max_length=30,
        choices=SUB_MODALIDAD_ECO_CHOICES,
        blank=True,
        null=True,
    )

    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['batch', 'fecha_turno', 'hora_turno']
        verbose_name = 'Fila EGES'
        verbose_name_plural = 'Filas EGES'
        indexes = [
            models.Index(fields=['batch', 'historia_clinica', 'fecha_turno']),
            models.Index(fields=['batch', 'modalidad', 'estado_turno']),
            models.Index(fields=['fecha_turno', 'modalidad']),
            models.Index(fields=['medico_informante', 'fecha_turno']),
            models.Index(fields=['medico_actuante', 'fecha_turno']),
            models.Index(fields=['dni_paciente', 'fecha_turno']),
            models.Index(fields=['tipo_atencion', 'fecha_turno']),
            models.Index(fields=['obra_social', 'fecha_turno']),
            models.Index(fields=['codigo_practica']),
        ]
        unique_together = [
            # Usamos practica (específica) en lugar de servicio (genérico) para deduplicar
            # correctamente cuando un paciente tiene múltiples prácticas en el mismo turno
            ('historia_clinica', 'fecha_turno', 'hora_turno', 'centro_atencion', 'practica')
        ]

    def __str__(self):
        nombre_estudio = self.practica or self.servicio or 'Sin práctica'
        return f"HC {self.historia_clinica} - {nombre_estudio} ({self.fecha_turno})"

    def clasificar_modalidad(self):
        """
        Detecta la modalidad. Usa 'practica' como fuente primaria (más específica),
        con 'servicio' y 'equipo' como fallback.
        Prioridad: TC > RM > MAM > DX > ECO > RX > OTROS
        """
        texto = f"{self.practica or ''} {self.servicio or ''} {self.equipo or ''}".upper()

        if any(kw in texto for kw in ['TOMOGRAF', 'TC ', ' TC', 'TAC ', ' TAC', 'SCANNER']):
            return 'TC'
        if any(kw in texto for kw in ['RESONANCIA', ' RM ', 'RMN', 'MAGNÉT']):
            return 'RM'
        if any(kw in texto for kw in ['MAMOGRAF', 'MAMOTOM', 'BIOPSIA MAMA', 'MAMMOGRAF']):
            return 'MAM'
        if any(kw in texto for kw in ['DENSITOMETR', 'DENSITO', 'OSTEODENSITO', 'DXA ']):
            return 'DX'
        if any(kw in texto for kw in ['ECO', 'ECOGRAF', 'ULTRASON', 'DOPPLER', 'DÚPLEX', 'DUPLEX',
                                       'ECODOPPLER']):
            return 'ECO'
        # Seriografía: debe ir ANTES de RX para evitar que caiga en OTROS
        # Cubre: seriógrafos digitales/CR, histerosalpingografías, salpingografías, series digestivas
        if any(kw in texto for kw in ['SERIOGRAF', 'HISTEROSALPINGOGRAF', 'SALPINGOGRAF',
                                       'SERIOGR', 'SERIOSCOP', 'SERIADA',
                                       'TRANSITO DE INTESTINO', 'TRÁNSITO DE INTESTINO']):
            return 'SERIE'
        if any(kw in texto for kw in ['RAYOS X', 'RX.', ' RX ', 'RX ', 'RX-',
                                       'RADIOGRAF', 'RADIOLOG',
                                       'PLACA', 'TELE DE TORAX',
                                       'TELERRADIOGRAF', 'COLUMNA', 'CADERA', 'PELVIS AP']):
            return 'RX'
        return 'OTROS'

    def clasificar_sub_modalidad(self):
        """
        Detecta la sub-modalidad dentro de ECO.
        Prioridad: ECOCARDIO > ECO_TIROIDES > ECO_MAMA > ECO_OBSTETRICA >
                   ECO_PELVIS > DOPPLER (restante) > ECO_ABDOMINAL >
                   ECO_NEONATAL > ECO_PARTES_BLANDAS (fallback)

        Los estudios órgano-específicos (CARDIACO, TIROIDES, MAMA) tienen
        prioridad sobre la técnica genérica (DOPPLER) para que
        "ECODOPPLER CARDIACO" → ECOCARDIO y "ECODOPPLER TIROIDES" → ECO_TIROIDES.
        """
        texto = f"{self.practica or ''} {self.servicio or ''} {self.equipo or ''}".upper()

        # 1. Corazón
        if any(kw in texto for kw in ['ECOCARDIOGRAMA', 'ECOCARDIO', 'ECO CARDIACA',
                                       'ECO CARDIAC', 'CARDIACO', 'CARDIACA',
                                       'ECOESTRESS', 'TRANSESOFAGICA', 'TRANSESOFAG']):
            return 'ECOCARDIO'
        # 2. Tiroides — antes que DOPPLER para capturar ECODOPPLER TIROIDES
        if any(kw in texto for kw in ['TIROIDES', 'TIROIDE']):
            return 'ECO_TIROIDES'
        # 3. Mama — antes que DOPPLER para capturar ECODOPPLER MAMARIO
        if any(kw in texto for kw in ['MAMARIA', 'ECO MAMA', 'ECOGRAFIA MAMARIA']):
            return 'ECO_MAMA'
        # 4. Obstétrica
        if any(kw in texto for kw in ['OBSTETR', 'EMBARAZO', 'FETAL', 'MORFOL', 'GESTACI']):
            return 'ECO_OBSTETRICA'
        # 5. Pelvis / ginecológica
        if any(kw in texto for kw in ['PELVIS', 'TRANSVAGINAL', 'PELVIANA', 'TOCOGINECOL']):
            return 'ECO_PELVIS'
        # 6. DOPPLER genérico (todos los ECODOPPLER vasculares restantes)
        if any(kw in texto for kw in ['DOPPLER', 'DÚPLEX', 'DUPLEX', 'ECODOPPLER']):
            return 'DOPPLER'
        # 7. Abdominal / renal / urológica
        if any(kw in texto for kw in ['ABDOMINAL', 'ABDOMEN', 'HÍGADO', 'HIGADO',
                                       'HEPATICA', 'HEPÁTICA', 'RENAL', 'VESICULAR',
                                       'VEJIGA', 'PROSTATA', 'BILIAR']):
            return 'ECO_ABDOMINAL'
        # 8. Neonatal / cerebral
        if any(kw in texto for kw in ['NEONATAL', 'NEONAT', 'CEREBRAL', 'FONTANELA']):
            return 'ECO_NEONATAL'
        # 9. Fallback
        return 'ECO_PARTES_BLANDAS'

    def clasificar_insumo(self):
        """
        Detecta si la fila es un insumo (contraste, medicación, consumible, etc.)
        Usa 'codigo_practica' como primera señal (códigos 3XXXXXXX = insumos externos)
        y luego 'practica'/'servicio' para detección por descripción.
        """
        import re
        # Detección por código: en el nomenclador EGES los códigos que comienzan
        # con 3 y tienen 7+ dígitos corresponden a insumos/materiales
        codigo = str(self.codigo_practica or '').strip()
        if re.match(r'^3\d{6}', codigo):
            return True

        texto = f"{self.practica or ''} {self.servicio or ''}".upper()

        keywords_insumo = [
            # Contrastes
            'CONTRASTE', 'GADOLINIO', 'IODO', 'XENETIX', 'OMNIPAQUE',
            'OPTIRAY', 'VISIPAQUE', 'ULTRAVIST', 'DOTAREM',
            # Medicamentos
            'MEDICACI', 'SEDACI', 'ANESTESI',
            'DIFENHIDRAMINA', 'DEXAMETASONA', 'MIDAZOLAM', 'FENTANILO',
            'PROPOFOL', 'KETAMINA', 'DORMICUM', 'DIAZEPAM',
            # Soluciones y expansores
            'SOL. FISIOLOGICA', 'SOLUCION FISIOLOGICA', 'SUERO FISIOLOGICO',
            'EXPANSION', 'NEBULIZAR', 'SOLUCIÓN', 'SUERO',
            # Material médico descartable
            'INSUMO', 'MATERIAL', 'LLAVE DE 3 VIAS', 'CATETER',
            'EQUIPO DE VENOCLISIS', 'JELCO', 'AGUJA', 'JERINGA',
            'TUBO', 'SONDA', 'GUIA', 'VALVULA',
            # Descartables específicos
            'ABBOCATH', 'PERFUS', 'ELECTRODOS', 'JER.',
            # Equipamiento / descartable quirúrgico
            'BOMBA', 'INYECTOR', 'E-151', 'E-152', 'E-',
            # Ropa y elementos de cirugía/procedimiento
            'GUANTE', 'CAMPO', 'GASA', 'VENDAJE', 'TELA ADHESIVA',
            'CAMISOLIN', 'CAMISOLÍN', 'COFIA', 'BATA',
        ]

        return any(kw in texto for kw in keywords_insumo)

    def save(self, *args, **kwargs):
        """
        Al guardar, clasificamos automáticamente modalidad, sub_modalidad e insumo.
        Solo clasifica en creación o si no se especifica update_fields.
        """
        update_fields = kwargs.get('update_fields', None)

        if not self.pk or update_fields is None:
            if update_fields is None:
                self.es_insumo = self.clasificar_insumo()
                self.modalidad = self.clasificar_modalidad()
                if self.modalidad == 'ECO':
                    self.sub_modalidad = self.clasificar_sub_modalidad()
                else:
                    self.sub_modalidad = None

        super().save(*args, **kwargs)


class DirectorToken(models.Model):
    """
    Token de acceso para el portal del director.
    Un token UUID en la URL otorga acceso de solo-lectura sin login.
    """
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nombre_etiqueta = models.CharField(
        max_length=100,
        default='Director',
        help_text='Etiqueta descriptiva para identificar este token (ej: "Director 2026")',
    )
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_ultimo_acceso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Token de Director'
        verbose_name_plural = 'Tokens de Director'
        ordering = ['-fecha_creacion']

    def __str__(self):
        estado = 'activo' if self.activo else 'inactivo'
        return f"{self.nombre_etiqueta} ({estado})"

    def registrar_acceso(self):
        self.fecha_ultimo_acceso = timezone.now()
        self.save(update_fields=['fecha_ultimo_acceso'])


class NombreObraSocial(models.Model):
    """
    Tabla de lookup: código RNOS → nombre legible de la obra social.
    Se auto-completa al importar un Excel que tenga columna 'Nombre OS'.
    También se puede cargar/editar manualmente desde el admin.
    """
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código RNOS')
    nombre = models.CharField(max_length=200, verbose_name='Nombre')

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Nombre Obra Social'
        verbose_name_plural = 'Nombres Obras Sociales'

    def __str__(self):
        return f"{self.codigo} – {self.nombre}"
