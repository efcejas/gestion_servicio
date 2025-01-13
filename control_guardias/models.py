from django.db import models

class MedicoGuardia(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=8, unique=True, blank=True, null=True)
    matricula = models.CharField(max_length=6, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "Médico"
        verbose_name_plural = "Médicos"

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

class Guardia(models.Model):
    FRANJA_HORARIA_CHOICES = [
        ('NOCHE', '20:00 - 08:00'),
        ('DIA_COMPLETO', '24 horas'),
        ('DIA', '08:00 - 20:00'),
        ('NOCHE_FIN_SEMANA', '20:00 - 08:00 (SA-DO-FE)'),
        ('DIA_FIN_SEMANA', '08:00 - 20:00 (SA-DO-FE)'),
    ]

    franja_horaria = models.CharField(max_length=25, choices=FRANJA_HORARIA_CHOICES)
    cubierta = models.BooleanField(default=False)
    medico = models.ForeignKey(
        'MedicoGuardia',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Médico"
    )
    fecha = models.DateField()

    def __str__(self):
        return f"{self.fecha.strftime('%A %d/%m/%y')} - {self.get_franja_horaria_display()} - {'Cubierta' if self.cubierta else 'No cubierta'}"
