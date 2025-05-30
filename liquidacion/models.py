from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings

class Estudios(models.Model):
    nombre = models.CharField(max_length=150, unique=True, verbose_name='Nombre del estudio')
    TIPO_ESTUDIO_CHOICES = (
        ('ECO', 'Ecografía'),
        ('RAD', 'Radiografía'),
        ('TOM', 'Tomografía'),
        ('RES', 'Resonancia Magnética'),
        )
    tipo = models.CharField(max_length=3, choices=TIPO_ESTUDIO_CHOICES, default='ECO', verbose_name='Tipo de estudio')
    conteo_regiones = models.IntegerField(verbose_name='Cantidad de regiones')

    class Meta:
        verbose_name = 'Estudio'
        verbose_name_plural = 'Estudios'

    def __str__(self):
        return f'{self.nombre}'

class RegistroEstudiosPorMedico(models.Model):
    medico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Médico')
    nombre_paciente = models.CharField(max_length=50, verbose_name='Nombre del paciente')
    apellido_paciente = models.CharField(max_length=50, verbose_name='Apellido del paciente')
    dni_paciente = models.CharField(verbose_name='DNI del paciente')
    fecha_registro = models.DateTimeField(default=timezone.now, verbose_name='Fecha de registro')
    fecha_del_informe = models.DateField(verbose_name='Fecha del informe')
    estudio = models.ManyToManyField(Estudios, verbose_name='Estudios')
    cantidad_estudio = models.PositiveIntegerField(default=1, blank=True, null=True, verbose_name='Cantidad por estudio')  # Nuevo campo

    class Meta:
        verbose_name = 'Registro de estudio por médico'
        verbose_name_plural = 'Registros de estudios por médico'

    def __str__(self):
        return f'{self.medico} - {self.fecha_registro}'

    def total_regiones(self):
        total = 0
        for estudio in self.estudio.all():
            cantidad = self.cantidad_estudio or 1  # Evitar problemas si es None
            total += estudio.conteo_regiones * cantidad
        return total
    
# Modelo para registrar que fue a la lista pero no tubo pacientes
class DiaSinPacientes(models.Model):
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Médico'
    )
    fecha = models.DateField(verbose_name='Fecha sin pacientes')
    observacion = models.TextField(
        blank=True,
        null=True,
        verbose_name='Observación (opcional)'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('medico', 'fecha')
        ordering = ['-fecha']
        verbose_name = 'Día sin pacientes'
        verbose_name_plural = 'Días sin pacientes'

    def __str__(self):
        return f"{self.medico.get_full_name()} - {self.fecha.strftime('%d/%m/%Y')}"

class RegistroProcedimientosIntervensionismo(models.Model):
    medico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Médico')
    nombre_paciente = models.CharField(max_length=50, verbose_name='Nombre del paciente')
    apellido_paciente = models.CharField(max_length=50, verbose_name='Apellido del paciente')
    dni_paciente = models.CharField(max_length=50, verbose_name='DNI del paciente', blank=True, null=True)
    fecha_registro = models.DateTimeField(default=timezone.now, verbose_name='Fecha de registro')
    fecha_del_procedimiento = models.DateField(verbose_name='Fecha del procedimiento', default=timezone.now)
    procedimiento = models.CharField(max_length=150, verbose_name='Procedimiento realizado')
    conteo_regiones = models.IntegerField(verbose_name='Cantidad de regiones', blank=True, null=True, default=0)
    notas = models.TextField(verbose_name='Notas', blank=True, null=True)

    class Meta:
        verbose_name = 'Registro de procedimiento de intervencionismo'
        verbose_name_plural = 'Registros de procedimientos de intervencionismo'

    def __str__(self):
        return f'{self.medico} - {self.fecha_registro}'