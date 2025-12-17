"""
Script de migración de datos: Actualizar usuarios existentes al nuevo sistema de perfiles.

Este script mapea los valores antiguos del campo 'cargo' al nuevo campo 'rol'.

Ejecutar con:
    python manage.py shell < actualizar_usuarios.py
"""

from accounts.models import CustomUser

# Mapeo de cargos antiguos a roles nuevos
MAPEO_ROLES = {
    'jefe': 'jefe_servicio',
    'jefe tecnico': 'jefe_servicio',
    'jefe administrativo': 'jefe_servicio',
    'médico': 'medico_staff',
    'médico residente': 'medico_residente',
    'técnico radiólogo': 'tecnico',
    'administrativo': 'administrativo',
    'enfermero/a': 'enfermeria',
    'jefe de enfermería': 'enfermeria',
    'otro': 'otro',
}

def migrar_usuarios():
    """Migra usuarios del sistema antiguo al nuevo."""
    usuarios_actualizados = 0
    usuarios_sin_cambios = 0
    
    print("\n" + "="*60)
    print("MIGRACIÓN DE USUARIOS AL NUEVO SISTEMA DE PERFILES")
    print("="*60 + "\n")
    
    for user in CustomUser.objects.all():
        # Saltar superusuarios
        if user.is_superuser:
            user.perfil_completo = True
            user.save(update_fields=['perfil_completo'])
            print(f"✓ Superusuario: {user.username} - Perfil marcado como completo")
            usuarios_actualizados += 1
            continue
        
        # Mapear cargo antiguo a rol nuevo
        if user.cargo and user.cargo in MAPEO_ROLES:
            user.rol = MAPEO_ROLES[user.cargo]
            user.perfil_completo = True  # Marcar como completo si ya tenía cargo
            user.save(update_fields=['rol', 'perfil_completo'])
            print(f"✓ Usuario: {user.username}")
            print(f"  Cargo antiguo: '{user.cargo}' → Rol nuevo: '{user.rol}'")
            print(f"  Perfil marcado como completo")
            usuarios_actualizados += 1
        else:
            # Usuario sin cargo asignado - deberá completar perfil
            print(f"⚠ Usuario: {user.username} - Sin cargo. Deberá completar perfil.")
            usuarios_sin_cambios += 1
    
    print("\n" + "="*60)
    print(f"RESUMEN:")
    print(f"  - Usuarios actualizados: {usuarios_actualizados}")
    print(f"  - Usuarios sin cambios: {usuarios_sin_cambios}")
    print(f"  - Total procesados: {CustomUser.objects.count()}")
    print("="*60 + "\n")

if __name__ == '__main__':
    migrar_usuarios()
