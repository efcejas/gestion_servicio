from django.db import models

class personal_medico (models.Model):
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    dni = models.IntegerField(unique=True)
    telefono = models.IntegerField()
    email = models.EmailField()
    matricula = models.IntegerField(unique=True)
    observaciones = models.TextField()

    class Meta:
        verbose_name = 'Personal Médico'
        verbose_name_plural = 'Personal Médico'

    def __str__(self):
        return self.nombre
