from django.db import models
from django.conf import settings

class Region(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    peso = models.PositiveIntegerField(default=1)  # Número de regiones que representa

    class Meta:
        verbose_name = "Región"
        verbose_name_plural = "Regiones"

    def __str__(self):
        return f"{self.nombre} ({self.peso} regiones)"


class Estudio(models.Model):
    MODALIDAD_CHOICES = [
        ('RM', 'Resonancia Magnética'),
        ('TC', 'Tomografía Computada'),
        ('RX', 'Radiografía'),
    ]
    nombre = models.CharField(max_length=100, unique=True)
    modalidad = models.CharField(max_length=2, choices=MODALIDAD_CHOICES, default='RX')
    regiones = models.ManyToManyField(Region, related_name="estudios")

    class Meta:
        verbose_name = "Estudio"
        verbose_name_plural = "Estudios"

    def __str__(self):
        return f"{self.nombre} ({self.get_modalidad_display()})"


class RegistroEstudio(models.Model):
    medico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    paciente_nombre = models.CharField(max_length=100)
    paciente_dni = models.CharField(max_length=15)
    fecha_estudio = models.DateField()
    estudios = models.ManyToManyField(Estudio, through="RegistroEstudioDetalle")
    total_regiones = models.PositiveIntegerField(default=0)

    def calcular_total_regiones(self):
        """Calcula automáticamente el total de regiones."""
        total = 0
        for detalle in self.registroestudiodetalle_set.all():
            total += detalle.cantidad * detalle.estudio.regiones.aggregate(models.Sum('peso'))['peso__sum']
        self.total_regiones = total
        self.save()

    def save(self, *args, **kwargs):
        self.calcular_total_regiones()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Registro: {self.paciente_nombre} ({self.medico})"


class RegistroEstudioDetalle(models.Model):
    registro = models.ForeignKey(RegistroEstudio, on_delete=models.CASCADE)
    estudio = models.ForeignKey(Estudio, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)  # Veces que se realizó el estudio

    class Meta:
        verbose_name = "Detalle de Registro de Estudio"
        verbose_name_plural = "Detalles de Registro de Estudio"

    def __str__(self):
        return f"{self.estudio} x{self.cantidad}"
