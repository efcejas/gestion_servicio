from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    CARGO = [
        ('jefe', 'Jefe de servicio'),
        ('jefe tecnico', 'Jefe técnico'),
        ('jefe administrativo', 'Jefe administrativo'),
        ('médico', 'Médico'),
        ('médico residente', 'Médico residente'),
        ('técnico radiólogo', 'Técnico radiólogo'),
        ('administrativo', 'Administrativo'),
        ('otro', 'Otro'),
    ]

    cargo = models.CharField(max_length=50, choices=CARGO, blank=True, null=True)  # Se agrega 'choices'
    telefono = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.username} - {self.get_cargo_display() if self.cargo else 'Sin cargo'}"


