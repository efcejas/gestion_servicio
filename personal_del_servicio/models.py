from django.db import models

class personal_medico (models.Model):
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    dni = models.IntegerField(unique=True, blank=True, null=True)
    telefono = models.IntegerField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    matricula = models.IntegerField(unique=True, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Personal Médico'
        verbose_name_plural = 'Personal Médico'

    def __str__(self):
        return self.nombre
