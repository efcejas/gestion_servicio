from django.contrib import admin
from .models import personal_medico

class PersonalMedicoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'dni', 'telefono', 'email', 'matricula')
    search_fields = ('nombre', 'apellido', 'dni', 'matricula')

admin.site.register(personal_medico, PersonalMedicoAdmin)