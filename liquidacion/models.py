from django.db import models
from django.utils import timezone

class Medico(models.Model):
    nombre = models.CharField(max_length=50, verbose_name='Nombre')
    apellido = models.CharField(max_length=50, verbose_name='Apellido')
    matricula = models.CharField(max_length=6, verbose_name='Matrícula', unique=True, blank=True, null=True)

    class Meta:
        verbose_name = 'Médico'
        verbose_name_plural = 'Médicos'

    def __str__(self):
        return f'{self.nombre} {self.apellido}'

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
    medico = models.ForeignKey(Medico, on_delete=models.CASCADE, verbose_name='Médico')
    nombre_paciente = models.CharField(max_length=50, verbose_name='Nombre del paciente')
    apellido_paciente = models.CharField(max_length=50, verbose_name='Apellido del paciente')
    dni_paciente = models.CharField(max_length=8, verbose_name='DNI del paciente')
    fecha_registro = models.DateTimeField(default=timezone.now, verbose_name='Fecha de registro')
    fecha_del_informe = models.DateField(verbose_name='Fecha del informe', blank=True, null=True)
    estudio = models.ManyToManyField(Estudios, verbose_name='Estudios')

    class Meta:
        verbose_name = 'Registro de estudio por médico'
        verbose_name_plural = 'Registros de estudios por médico'

    def __str__(self):
        return f'{self.medico} - {self.fecha_registro}'

    def total_regiones(self):
        """
        Calcula el total de regiones para los estudios asociados a este registro.
        """
        return sum(estudio.conteo_regiones for estudio in self.estudio.all())
