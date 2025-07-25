from django.urls import path
from . import views

app_name = 'visor_dicom'

urlpatterns = [
    path('subir/', views.subir_dicom, name='subir_dicom'),
    path('ver/<int:pk>/', views.ver_dicom, name='ver_dicom'),
]
