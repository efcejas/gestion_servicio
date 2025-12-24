import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from accounts.models import CustomUser

user = CustomUser.objects.first()
print(f'Username: {user.username}')
print(f'Full name: {user.get_full_name()}')
print(f'First name: {user.first_name}')
print(f'Last name: {user.last_name}')
print(f'Rol (raw): {repr(user.rol)}')
print(f'Rol (display): {user.get_rol_display() if user.rol else "Sin rol"}')
print(f'Perfil completo: {user.perfil_completo}')
print(f'Email: {user.email}')
