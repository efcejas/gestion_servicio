from django.db import models

class personal_medico(models.Model):
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
        return f"{self.nombre} {self.apellido}"

class FranjaHoraria(models.Model):
    nombre = models.CharField(max_length=50, verbose_name='Nombre de la Franja')
    hora_inicio = models.TimeField(verbose_name='Hora de Inicio')
    hora_fin = models.TimeField(verbose_name='Hora de Fin')

    class Meta:
        verbose_name = 'Franja Horaria'
        verbose_name_plural = 'Franjas Horarias'

    def __str__(self):
        return f"{self.nombre} ({self.hora_inicio} - {self.hora_fin})"

class Disponibilidad(models.Model):
    medico = models.ForeignKey(personal_medico, on_delete=models.CASCADE, verbose_name='Médico')
    dia_semana = models.CharField(max_length=10, choices=[
        ('LUN', 'Lunes'),
        ('MAR', 'Martes'),
        ('MIE', 'Miércoles'),
        ('JUE', 'Jueves'),
        ('VIE', 'Viernes'),
        ('SAB', 'Sábado'),
        ('DOM', 'Domingo'),
    ], verbose_name='Día de la Semana')
    franja_horaria = models.ForeignKey(FranjaHoraria, on_delete=models.CASCADE, verbose_name='Franja Horaria')
    servicio = models.CharField(max_length=50, choices=[
        ('INFORMES', 'Informes'),
        ('ECOGRAFIAS', 'Ecografías'),
    ], verbose_name='Servicio', default='INFORMES')
    modalidad = models.CharField(max_length=50, choices=[
        ('PRESENCIAL', 'Presencial'),
        ('DISTANCIA', 'A Distancia'),
    ], verbose_name='Modalidad', default='PRESENCIAL')

    class Meta:
        verbose_name = 'Disponibilidad'
        verbose_name_plural = 'Disponibilidades'

    def __str__(self):
        return f"{self.medico} - {self.get_dia_semana_display()} - {self.franja_horaria}"