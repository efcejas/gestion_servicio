from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now

class Paciente(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    dni = models.CharField(max_length=15, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

    def clean(self):
        if self.fecha_nacimiento and self.fecha_nacimiento > now().date():
            raise ValidationError("La fecha de nacimiento no puede ser en el futuro.")

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.dni})"


class Estudio(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Estudio"
        verbose_name_plural = "Estudios"

    def __str__(self):
        return self.nombre


class OrdenMedica(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    estudios = models.ManyToManyField(Estudio)  # Relación ManyToMany con los estudios
    archivo = models.FileField(upload_to='ordenes_medicas/', null=True, blank=True)
    fecha_emision = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Orden Médica"
        verbose_name_plural = "Órdenes médicas"

    def __str__(self):
        return f"Orden de {self.paciente} - {self.fecha_emision}"


class RegistroAtencion(models.Model):
    medico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    ordenes_medicas = models.ManyToManyField(OrdenMedica, blank=True)  # Relación ManyToMany
    fecha_atencion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de atención"
        verbose_name_plural = "Registros de atención"

    def __str__(self):
        return f"Atención: {self.paciente} por {self.medico} - {self.fecha_atencion.strftime('%Y-%m-%d')}"
