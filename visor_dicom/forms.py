from django import forms
from .models import DicomFile

class DicomFileForm(forms.ModelForm):
    class Meta:
        model = DicomFile
        fields = ['archivo']
