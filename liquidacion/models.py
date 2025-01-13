from django.db import models
from django.utils import timezone

class Medico(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=8, unique=True, blank=True, null=True)
    matricula = models.CharField(max_length=6, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

class Paciente(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    dni = models.CharField(max_length=8, unique=True, verbose_name="DNI")

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.dni})"

class Estudio(models.Model):
    nombre = models.CharField(max_length=100)
    regiones = models.PositiveIntegerField()  # Número de regiones que ocupa este estudio

    def __str__(self):
        return f"{self.nombre} ({self.regiones} regiones)"

class RegistroDiario(models.Model):
    medico = models.ForeignKey('Medico', on_delete=models.CASCADE, verbose_name="Médico")
    paciente = models.ForeignKey('Paciente', on_delete=models.CASCADE, null=True, blank=True)
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha del Estudio")
    total_regiones = models.PositiveIntegerField(default=0)

    def calcular_total_regiones(self):
        total = sum(detalle.estudio.regiones * detalle.cantidad for detalle in self.detalles.all())
        self.total_regiones = total
        self.save()

    def __str__(self):
        return f"Registro: {self.medico} - {self.paciente} - {self.fecha}"


class DetalleRegistro(models.Model):
    registro = models.ForeignKey(RegistroDiario, related_name="detalles", on_delete=models.CASCADE)
    estudio = models.ForeignKey(Estudio, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.registro} - {self.estudio} ({self.cantidad})"
