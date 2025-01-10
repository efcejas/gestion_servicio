from django.db import models

class personal_medico (models.Model):
    nombre = models.CharField(max_length=50, verbose_name='Nombre')
    apellido = models.CharField(max_length=50, verbose_name='Apellido')
    dni = models.IntegerField(unique=True, blank=True, null=True, verbose_name='DNI')
    telefono = models.IntegerField(blank=True, null=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, null=True, verbose_name='Email')
    matricula = models.IntegerField(unique=True, blank=True, null=True, verbose_name='Matrícula')
    observaciones = models.TextField(blank=True, null=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Personal Médico'
        verbose_name_plural = 'Personal Médico'

    def __str__(self):
        return self.nombre
