from django.db import models
from django.conf import settings
from django.utils import timezone
import re


class ImportBatch(models.Model):
    """
    Representa un lote de importación de datos EGES.
    Cada vez que se sube un Excel, se crea un batch.
    """
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='batches_eges')
    archivo_nombre = models.CharField(max_length=255)
    fecha_importacion = models.DateTimeField(default=timezone.now)
    total_filas = models.IntegerField(default=0)
    
    # Métricas calculadas
    total_ingresos_unicos = models.IntegerField(default=0)
    total_estudios_candidatos = models.IntegerField(default=0)  # No insumos
    total_estudios_finalizados = models.IntegerField(default=0)  # Estado = Informado
    
    # Contadores por modalidad
    total_tc = models.IntegerField(default=0)
    total_rm = models.IntegerField(default=0)
    total_rx = models.IntegerField(default=0)
    total_eco = models.IntegerField(default=0)
    total_otros = models.IntegerField(default=0)
    
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
        
        # Por modalidad (entre finalizados)
        self.total_tc = finalizados.filter(modalidad='TC').count()
        self.total_rm = finalizados.filter(modalidad='RM').count()
        self.total_rx = finalizados.filter(modalidad='RX').count()
        self.total_eco = finalizados.filter(modalidad='ECO').count()
        self.total_otros = finalizados.filter(modalidad='OTROS').count()
        
        self.save()


class EgesRow(models.Model):
    """
    Representa una fila cruda del Excel EGES.
    Almacenamos todos los campos tal cual vienen.
    
    IMPORTANTE: Usa unique_together para evitar duplicados.
    Si una fila con la misma combinación HC+Fecha+Hora+Centro+Práctica ya existe, se ignora.
    """
    MODALIDAD_CHOICES = [
        ('TC', 'Tomografía'),
        ('RM', 'Resonancia Magnética'),
        ('RX', 'Rayos X'),
        ('ECO', 'Ecografía'),
        ('OTROS', 'Otros'),
    ]
    
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='filas')
    
    # Identificación del turno/ingreso
    numero_turno = models.CharField(max_length=50, blank=True, null=True)
    fecha_turno = models.DateField(null=True, blank=True)
    hora_turno = models.TimeField(null=True, blank=True)
    centro_atencion = models.CharField(max_length=100, blank=True, null=True)
    
    # Paciente
    historia_clinica = models.CharField(max_length=50, blank=True, null=True)
    apellido_nombre = models.CharField(max_length=200, blank=True, null=True)
    
    # Estudio
    servicio = models.CharField(max_length=200, blank=True, null=True)
    equipo = models.CharField(max_length=100, blank=True, null=True)
    estado_turno = models.CharField(max_length=50, blank=True, null=True)
    
    # Clasificación
    es_insumo = models.BooleanField(default=False)
    modalidad = models.CharField(max_length=10, choices=MODALIDAD_CHOICES, default='OTROS')
    
    # Metadata
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['batch', 'fecha_turno', 'hora_turno']
        verbose_name = 'Fila EGES'
        verbose_name_plural = 'Filas EGES'
        indexes = [
            models.Index(fields=['batch', 'historia_clinica', 'fecha_turno']),
            models.Index(fields=['batch', 'modalidad', 'estado_turno']),
        ]
        # PROTECCIÓN CONTRA DUPLICADOS
        # Si una fila con esta combinación ya existe (en cualquier batch), se detecta como duplicada
        unique_together = [
            ('historia_clinica', 'fecha_turno', 'hora_turno', 'centro_atencion', 'servicio')
        ]
    
    def __str__(self):
        return f"HC {self.historia_clinica} - {self.servicio} ({self.fecha_turno})"
    
    def clasificar_modalidad(self):
        """
        Detecta la modalidad según el texto de servicio y equipo.
        Regla simple: buscar keywords en el texto.
        """
        texto = f"{self.servicio or ''} {self.equipo or ''}".upper()
        
        if any(kw in texto for kw in ['TOMOGRAF', 'TC ', ' TC', 'TAC', 'SCANNER']):
            return 'TC'
        elif any(kw in texto for kw in ['RESONANCIA', 'RM ', ' RM', 'RMN', 'MAGNÉTICA']):
            return 'RM'
        elif any(kw in texto for kw in ['RAYOS X', 'RX ', ' RX', 'RADIOGRAF']):
            return 'RX'
        elif any(kw in texto for kw in ['ECO', 'ECOGRAF', 'ULTRASON', 'DOPPLER']):
            return 'ECO'
        else:
            return 'OTROS'
    
    def clasificar_insumo(self):
        """
        Detecta si la fila es un insumo (contraste, medicación, etc.)
        y no un estudio real.
        """
        texto = f"{self.servicio or ''}".upper()
        
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
            
            # Material médico
            'INSUMO', 'MATERIAL', 'LLAVE DE 3 VIAS', 'CATETER',
            'EQUIPO DE VENOCLISIS', 'JELCO', 'AGUJA', 'JERINGA',
            'TUBO', 'SONDA', 'GUIA', 'VALVULA',
            
            # Equipamiento
            'BOMBA', 'INYECTOR', 'E-151', 'E-152', 'E-',
            
            # Otros consumibles
            'GUANTES', 'CAMPO', 'GASA', 'VENDAJE', 'TELA ADHESIVA'
        ]
        
        return any(kw in texto for kw in keywords_insumo)
    
    def save(self, *args, **kwargs):
        """
        Al guardar, clasificamos automáticamente modalidad e insumo.
        Solo clasifica en creación o si no se especifica update_fields.
        """
        update_fields = kwargs.get('update_fields', None)
        
        # Si es creación O no se está haciendo una actualización parcial
        if not self.pk or update_fields is None:
            # Solo reclasificar si no estamos actualizando campos específicos
            if update_fields is None:
                self.es_insumo = self.clasificar_insumo()
                self.modalidad = self.clasificar_modalidad()
        
        super().save(*args, **kwargs)
