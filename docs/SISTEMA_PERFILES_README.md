# Sistema de Perfiles de Usuario - Implementación Completa

## 📋 Resumen de Cambios

Se implementó un sistema completo de perfiles por rol que permite:
- Registro simplificado (solo datos básicos)
- Completar perfil post-registro con selección de rol
- Control de acceso basado en roles
- Middleware que fuerza completar perfil antes de usar el sistema
- Acceso a protocolos para médicos residentes y técnicos

---

## 🎯 Nuevo Flujo de Usuario

### 1. Registro
- Usuario completa formulario con: username, email, nombre, apellido, password
- Se crea cuenta pero `perfil_completo = False`
- Redirige a login

### 2. Primer Login
- Usuario inicia sesión exitosamente
- Middleware detecta `perfil_completo = False`
- Redirige automáticamente a `/accounts/completar-perfil/`

### 3. Completar Perfil
- Usuario selecciona su **rol** (obligatorio):
  - Médico de Staff
  - Médico Residente ✨ *Ahora tiene acceso a protocolos*
  - Jefe de Servicio
  - Técnico Radiólogo ✨ *Ahora tiene acceso a protocolos*
  - Administrativo
  - Enfermería
  - Otro
- Opcionalmente completa: cargo específico, teléfono, preferencias
- Al guardar, se marca `perfil_completo = True` y `fecha_perfil_completado`

### 4. Acceso Completo
- Usuario ya puede acceder a todas las secciones según su rol
- Middleware ya no interrumpe la navegación

---

## 📁 Archivos Creados/Modificados

### Nuevos Archivos:
1. **`accounts/decorators.py`** - Decoradores para control de acceso
2. **`accounts/middleware.py`** - Middleware de verificación de perfil
3. **`templates/accounts/completar_perfil.html`** - Template del formulario
4. **`actualizar_usuarios.py`** - Script para migrar usuarios existentes

### Archivos Modificados:
1. **`accounts/models.py`**
   - Nuevos campos: `rol`, `perfil_completo`, `fecha_perfil_completado`, `recibir_notificaciones`
   - Métodos: `marcar_perfil_completo()`, `puede_acceder_protocolos()`, `es_medico()`, `es_residente()`
   - Simplificación de roles (de 10 cargos a 7 roles agrupados)

2. **`accounts/forms.py`**
   - `CustomUserCreationForm`: Simplificado (solo datos básicos)
   - `CompletarPerfilForm`: Nuevo formulario para completar perfil
   - `CustomUserChangeForm`: Actualizado para nuevos campos

3. **`accounts/views.py`**
   - `completar_perfil()`: Nueva vista para formulario de perfil

4. **`accounts/urls.py`**
   - Nueva ruta: `completar-perfil/`
   - Agregado `app_name = 'accounts'` para namespacing

5. **`protocolos/views.py`**
   - Cambiado `@login_required` por `@protocolos_access_required`
   - Ahora permite acceso a residentes y técnicos

6. **`gestion_estudios/settings.py`**
   - Agregado `ProfileRequiredMiddleware` al stack de middleware

### Migración:
- **`accounts/migrations/0004_customuser_fecha_perfil_completado_and_more.py`**

---

## 🔐 Decoradores Disponibles

### `@profile_required`
Requiere que el usuario tenga perfil completo. Si no, redirige a completar perfil.

```python
from accounts.decorators import profile_required

@profile_required
def mi_vista(request):
    # Solo accesible con perfil completo
    pass
```

### `@role_required(*roles)`
Requiere que el usuario tenga uno de los roles especificados.

```python
from accounts.decorators import role_required

@role_required('medico_staff', 'medico_residente')
def vista_medicos(request):
    # Solo para médicos
    pass
```

### `@medical_staff_required`
Atajo para personal médico (staff, residentes, jefes).

```python
from accounts.decorators import medical_staff_required

@medical_staff_required
def dictar_informe(request):
    pass
```

### `@protocolos_access_required`
Específico para protocolos (médicos + técnicos).

```python
from accounts.decorators import protocolos_access_required

@protocolos_access_required
def ver_protocolo(request):
    pass
```

---

## 🚀 Cómo Usar

### Para Migrar Usuarios Existentes:
```bash
python actualizar_usuarios.py
```

Este script:
- Mapea cargos antiguos → roles nuevos
- Marca perfiles como completos automáticamente
- Genera reporte de cambios

### Para Crear Nuevo Usuario:
1. Ir a `/accounts/register/`
2. Completar datos básicos
3. Login
4. Automáticamente redirige a completar perfil
5. Seleccionar rol
6. ¡Listo!

### Para Verificar Rol en Templates:
```django
{% if user.es_residente %}
    <p>Eres residente</p>
{% endif %}

{% if user.puede_acceder_protocolos %}
    <a href="{% url 'protocolos:elegir' %}">Ver Protocolos</a>
{% endif %}
```

### Para Verificar Rol en Vistas:
```python
def mi_vista(request):
    if request.user.es_medico():
        # Lógica para médicos
        pass
    
    if request.user.puede_acceder_protocolos():
        # Mostrar protocolos
        pass
```

---

## ⚙️ Configuración del Middleware

El middleware está configurado para **NO** requerir perfil completo en:
- `/accounts/completar-perfil/`
- `/accounts/login/`
- `/accounts/logout/`
- `/accounts/register/`
- `/accounts/password_reset/`
- `/static/` y `/media/`
- `/admin/` (para superusuarios)

Para agregar más excepciones, editar `accounts/middleware.py`:

```python
EXEMPT_URLS = [
    '/accounts/completar-perfil/',
    # ... agregar aquí
]
```

---

## 🎨 Roles y Permisos

| Rol | Acceso a Protocolos | Dictar Informes | Gestión | Observaciones |
|-----|---------------------|-----------------|---------|---------------|
| **Médico Staff** | ✅ | ✅ | ✅ | Acceso completo |
| **Médico Residente** | ✅ | ✅ | ❌ | ✨ **Nuevo acceso a protocolos** |
| **Jefe Servicio** | ✅ | ✅ | ✅ | Acceso administrativo |
| **Técnico** | ✅ | ❌ | ❌ | ✨ **Nuevo acceso a protocolos** |
| **Administrativo** | ❌ | ❌ | ✅ | Gestión sin clínica |
| **Enfermería** | ❌ | ❌ | ⚠️ | Acceso limitado |
| **Otro** | ❌ | ❌ | ❌ | Rol genérico |
| **Superusuario** | ✅ | ✅ | ✅ | Sin restricciones |

---

## 🐛 Troubleshooting

### "Usuario no puede acceder a protocolos"
- Verificar que el rol sea: `medico_staff`, `medico_residente`, `jefe_servicio` o `tecnico`
- Verificar que `perfil_completo = True`

### "Bucle infinito en completar perfil"
- Verificar que la URL `/accounts/completar-perfil/` está en `EXEMPT_URLS` del middleware
- Verificar que existe el namespace `accounts:completar_perfil` en URLs

### "Usuarios existentes no pueden acceder"
- Ejecutar script de migración: `python actualizar_usuarios.py`
- O manualmente marcar perfiles completos en admin

---

## 📊 Migración de Base de Datos

La migración `0004` agrega:
- Campo `rol` (CharField con choices)
- Campo `perfil_completo` (Boolean, default=False)
- Campo `fecha_perfil_completado` (DateTime, nullable)
- Campo `recibir_notificaciones` (Boolean, default=True)
- Modifica campo `cargo` (ahora opcional, para especializaciones)

**Es compatible hacia atrás**: usuarios existentes pueden seguir usando el sistema pero serán redirigidos a completar perfil.

---

## ✅ Testing Checklist

- [ ] Nuevo usuario puede registrarse
- [ ] Después de login, redirige a completar perfil
- [ ] Formulario de perfil muestra roles correctamente
- [ ] Al completar perfil, redirige a home
- [ ] Usuario con perfil completo puede acceder a todo
- [ ] Residente puede acceder a protocolos
- [ ] Técnico puede acceder a protocolos
- [ ] Administrativo NO puede acceder a protocolos
- [ ] Superusuarios no necesitan completar perfil
- [ ] Script de migración actualiza usuarios existentes

---

## 🔄 Próximos Pasos Sugeridos

1. **Personalización por Rol**: Crear dashboards específicos según rol
2. **Sistema de Permisos Granular**: Agregar permisos específicos por funcionalidad
3. **Grupos de Django**: Migrar a grupos nativos de Django para mejor escalabilidad
4. **Auditoría**: Registrar cambios de perfil y permisos
5. **Onboarding**: Tour guiado según rol del usuario
6. **Notificaciones**: Sistema de notificaciones diferenciado por rol

---

## 📝 Notas Importantes

- Los superusuarios **siempre** tienen acceso completo sin restricciones
- El campo `cargo` ahora es opcional y se usa para especializaciones
- El campo `rol` es el que determina los permisos
- El middleware se ejecuta **después** de `AuthenticationMiddleware`
- Usuarios sin perfil completo solo pueden: logout, completar perfil, y ver páginas públicas

---

*Implementado: 16 de diciembre de 2025*
*Versión: 1.0*
