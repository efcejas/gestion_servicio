from django.shortcuts import render, redirect, get_object_or_404
from .forms import DicomFileForm
from .models import DicomFile

def subir_dicom(request):
    if request.method == 'POST':
        form = DicomFileForm(request.POST, request.FILES)
        if form.is_valid():
            dicom = form.save()
            return redirect('visor_dicom:ver_dicom', pk=dicom.pk)
    else:
        form = DicomFileForm()
    return render(request, 'visor_dicom/subir.html', {'form': form})

def ver_dicom(request, pk):
    dicom = get_object_or_404(DicomFile, pk=pk)
    return render(request, 'visor_dicom/ver.html', {'dicom': dicom})
