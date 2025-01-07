from django.db import models

# Create your models here.
class Guardia(models.Model):
    DIA_SEMANA_CHOICES = [
        ('LUN', 'Lunes'),
        ('MAR', 'Martes'),
        ('MIE', 'Miércoles'),
        ('JUE', 'Jueves'),
        ('VIE', 'Viernes'),
        ('SAB', 'Sábado'),
        ('DOM', 'Domingo'),
    ]

    FRANJA_HORARIA_CHOICES = [
        ('NOCHE', '20:00 - 08:00'),
        ('DIA_COMPLETO', '24 horas'),
    ]

    dia_semana = models.CharField(max_length=3, choices=DIA_SEMANA_CHOICES)
    franja_horaria = models.CharField(max_length=12, choices=FRANJA_HORARIA_CHOICES)
    cubierta = models.BooleanField(default=False)
    medico = models.CharField(max_length=100, blank=True, null=True)
    fecha = models.DateField(default=None)

    def __str__(self):
        return f"{self.fecha.strftime('%A %d/%m/%y')} - {self.get_dia_semana_display()} - {self.get_franja_horaria_display()} - {'Cubierta' if self.cubierta else 'No cubierta'}"