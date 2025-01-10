from django.db import models

class Guardia(models.Model):
    FRANJA_HORARIA_CHOICES = [
        ('NOCHE', '20:00 - 08:00'),
        ('DIA_COMPLETO', '24 horas'),
    ]

    franja_horaria = models.CharField(max_length=12, choices=FRANJA_HORARIA_CHOICES)
    cubierta = models.BooleanField(default=False)
    medico = models.CharField(max_length=100, blank=True, null=True)
    fecha = models.DateField()

    def __str__(self):
        return f"{self.fecha.strftime('%A %d/%m/%y')} - {self.get_franja_horaria_display()} - {'Cubierta' if self.cubierta else 'No cubierta'}"