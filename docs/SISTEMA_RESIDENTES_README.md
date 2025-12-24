# Sistema de Gestión de Residentes - Colegiales

## Nuevas Funcionalidades Implementadas

### 1. Roles Ampliados

Se agregaron nuevos roles específicos para el sistema de residencia:

- **Médico Residente** (`medico_residente`)
- **Jefe de Residentes** (`jefe_residentes`)
- **Instructor de Residentes** (`instructor_residentes`)
- **Médico de Staff** (`medico_staff`)
- **Jefe de Servicio** (`jefe_servicio`)

### 2. Cálculo Automático de Año de Residencia

#### Cómo Funciona

Cuando un usuario se registra como **Médico Residente**, debe ingresar su **fecha de ingreso a la residencia**. El sistema automáticamente:

1. Calcula el tiempo transcurrido desde la fecha de ingreso
2. Asigna el año de residencia correspondiente:
   - **Menos de 12 meses** → R1
   - **12-23 meses** → R2
   - **24-35 meses** → R3
   - **36-47 meses** → R4
   - **48-59 meses** → R5
   - **60+ meses** → R5+

#### Ejemplo Práctico

```
Fecha de ingreso: 1 de marzo de 2024
Fecha actual: 19 de diciembre de 2025
Meses transcurridos: 9 meses
Resultado: R1
```

### 3. Campos del Modelo CustomUser

#### Nuevos Campos

```python
# Específicos para residentes
fecha_ingreso_residencia = DateField (opcional)
anio_residencia = CharField (calculado automáticamente)
```

#### Métodos Útiles

```python
user.calcular_anio_residencia()  # Retorna 'R1', 'R2', etc.
user.actualizar_anio_residencia()  # Actualiza el campo en la BD
user.es_residente()  # True si el rol es medico_residente
```

### 4. Flujo de Registro para Residentes

1. **Registro básico**: Username, email, nombre, apellido, contraseña
2. **Completar perfil**:
   - Seleccionar rol: "Médico Residente"
   - Se muestra automáticamente el campo "Fecha de ingreso a la residencia"
   - Ingresar la fecha (obligatoria para residentes)
   - Completar campos opcionales (especialidad, teléfono)
3. **Al guardar**:
   - El sistema calcula automáticamente el año de residencia
   - Se muestra en el perfil: "R1", "R2", etc.

### 5. Edición de Perfil

Los residentes pueden:
- Ver su año de residencia actual (solo lectura)
- Actualizar su fecha de ingreso si fue incorrecta
- El año se recalcula automáticamente al guardar cambios

### 6. Visualización en el Sistema

#### En el Header (pantallas grandes)
```
Nombre Completo
email@example.com
🩺 Médico Residente - R2
```

#### En el Dropdown (móviles)
```
Nombre Completo
email@example.com
🩺 Médico Residente
```

### 7. Comando de Actualización Masiva

Para actualizar el año de todos los residentes existentes:

```bash
python manage.py actualizar_anios_residencia
```

Este comando:
- Busca todos los usuarios con rol `medico_residente`
- Recalcula el año según su fecha de ingreso
- Muestra un resumen de los cambios realizados

### 8. Validaciones

#### En el Formulario de Completar Perfil
- Si selecciona "Médico Residente" → Campo de fecha es **obligatorio**
- Si selecciona otro rol → Campo de fecha se **oculta**

#### En el Formulario de Edición
- Residentes ven: Fecha de ingreso (editable) + Año (solo lectura)
- No residentes: Campos ocultos

### 9. Actualización Automática

El año de residencia se actualiza automáticamente en:
- Registro inicial (al completar perfil)
- Edición de perfil (al cambiar fecha de ingreso)
- Comando manual: `actualizar_anios_residencia`

### 10. Permisos y Accesos

Todos los médicos (staff, residentes, jefes, instructores) tienen acceso a:
- **Protocolos Radiológicos**: Sistema de decisión clínica
- **Gestión de Eventos**: Novedades del servicio
- **Editar Perfil**: Actualizar información personal

### 11. Próximos Pasos Sugeridos

1. **Tarea Programada**: Crear un cronjob que ejecute `actualizar_anios_residencia` mensualmente
2. **Notificaciones**: Alertar cuando un residente cambia de año (R1→R2)
3. **Estadísticas**: Dashboard mostrando distribución de residentes por año
4. **Rotaciones**: Sistema para registrar rotaciones por servicio/modalidad

### 12. Migración de Datos Existentes

Si ya tienes usuarios registrados como residentes sin fecha de ingreso:

1. Contactar a cada residente para que actualice su perfil
2. O usar el admin de Django para ingresar las fechas manualmente
3. Luego ejecutar: `python manage.py actualizar_anios_residencia`

## Código de Ejemplo

### Ver año de residencia en templates
```django
{% if user.es_residente %}
    <span class="badge">{{ user.anio_residencia }}</span>
{% endif %}
```

### Filtrar residentes en views
```python
residentes_r1 = CustomUser.objects.filter(
    rol='medico_residente',
    anio_residencia='R1'
)
```

## Soporte

Para cualquier duda o problema:
1. Revisar esta documentación
2. Consultar el código en `accounts/models.py`
3. Ver ejemplos en las templates de completar/editar perfil
