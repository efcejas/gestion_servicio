from django.contrib import admin
from .models import DicomFile

@admin.register(DicomFile)
class DicomFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre_subido', 'archivo', 'subido_en')
    search_fields = ('nombre_subido',)
