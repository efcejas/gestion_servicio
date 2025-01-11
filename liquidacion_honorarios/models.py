from django.db import models

# Create your models here.
class Medicos(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    dni = models.CharField(max_length=8, blank=True, null=True, verbose_name="DNI")
    matricula = models.CharField(max_length=6, blank=True, null=True, verbose_name="Matrícula")
    email = models.EmailField(blank=True, null=True, verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=100, blank=True, null=True, verbose_name="Teléfono")

    class Meta:
        verbose_name_plural = "Médicos"
        verbose_name = "Médico"

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.especialidad}"