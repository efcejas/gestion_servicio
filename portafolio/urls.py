from django.urls import path

from . import views


app_name = 'portafolio'

urlpatterns = [
    path('', views.mi_portafolio, name='mi_portafolio'),
    path('residentes/', views.seguimiento_residentes, name='seguimiento'),
    path('residentes/<int:pk>/', views.detalle_residente, name='detalle_residente'),
]
