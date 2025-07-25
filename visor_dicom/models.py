from django.db import models

class DicomFile(models.Model):
    archivo = models.FileField(upload_to='dicoms/')
    nombre_subido = models.CharField(max_length=200, blank=True)
    subido_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre_subido or f"DICOM #{self.id}"
