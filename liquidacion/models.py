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

class Estudio(models.Model):
    nombre = models.CharField(max_length=100)
    modalidad = models.CharField(
        max_length=50,
        choices=[
            ('TOMOGRAFIA', 'Tomografía'),
            ('RESONANCIA', 'Resonancia Magnética'),
            ('RADIOGRAFIA', 'Radiografía'),
            ('ECOGRAFIA', 'Ecografía'),
        ],
    )
    regiones = models.PositiveIntegerField(default=1)  # Regiones que representa
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    class Meta:
        verbose_name = "Estudio"
        verbose_name_plural = "Estudios"

    def __str__(self):
        return f"{self.nombre} ({self.modalidad}) - {self.regiones} regiones"

class Paciente(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    dni = models.CharField(max_length=8, unique=True, verbose_name="DNI")

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.dni})"


class RegistroDiario(models.Model):
    medico = models.ForeignKey(Medico, on_delete=models.CASCADE)
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, verbose_name="Paciente", null=True, blank=True)
    fecha = models.DateField(default=timezone.now)
    estudios = models.ManyToManyField(Estudio, through="DetalleRegistro")
    total_regiones = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        verbose_name = "Registro Diario"
        verbose_name_plural = "Registros Diarios"

    def calcular_total_regiones(self):
        total = sum(
            detalle.estudio.regiones * detalle.cantidad
            for detalle in self.detalleregistro_set.all()
        )
        self.total_regiones = total
        self.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.calcular_total_regiones()

    def __str__(self):
        return f"{self.fecha} - {self.medico} - {self.paciente} - {self.total_regiones} regiones"

class DetalleRegistro(models.Model):
    registro = models.ForeignKey(RegistroDiario, on_delete=models.CASCADE)
    estudio = models.ForeignKey(Estudio, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Detalle de Registro"
        verbose_name_plural = "Detalles de Registro"

    def __str__(self):
        return f"{self.estudio} x{self.cantidad}"

class TarifaEstudio(models.Model):
    modalidad = models.CharField(
        max_length=50,
        choices=[
            ('TOMOGRAFIA', 'Tomografía'),
            ('RESONANCIA', 'Resonancia Magnética'),
            ('RADIOGRAFIA', 'Radiografía'),
            ('ECOGRAFIA', 'Ecografía'),
        ],
    )
    valor_por_region = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Tarifa Estudio"
        verbose_name_plural = "Tarifas Estudios"

    def __str__(self):
        return f"{self.modalidad} - ${self.valor_por_region}"

