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

### 7. Cierre anual de la residencia

El ciclo termina el 31 de julio. Antes de esa fecha, en el admin de usuarios,
marcar **Repite año de residencia** solamente en quienes deban conservar su año.

El 1 de agosto (o en una tarea diaria/mensual) ejecutar:

```bash
python manage.py actualizar_anios_residencia
```

#### Ejecución automática en Heroku

Configurar un job en **Heroku Scheduler** con estos valores:

- Frecuencia: `Daily`
- Hora: `03:05 UTC` (equivale a `00:05` de Argentina)
- Comando: `python manage.py actualizar_anios_residencia`

Heroku Scheduler expresa los horarios diarios en UTC. El comando evalúa el cierre
con la zona `America/Argentina/Buenos_Aires`, por lo que no promociona antes de la
medianoche argentina. Ejecutarlo diariamente es seguro: cada cierre se registra y
no puede aplicarse dos veces. Si una ejecución se demora o se omite, la siguiente
ejecución diaria procesa el cierre pendiente.

Para crear o abrir el Scheduler:

```bash
heroku addons:create scheduler:standard
heroku addons:open scheduler
```

El comando es idempotente y realiza R1→R2, R2→R3, R3→R4 y R4→Egresado.
Los repetidores conservan el año y la marca de excepción se limpia. Los egresados
conservan su cuenta e historial, pero dejan de aparecer en guardias, coberturas y
funciones propias de residentes.

Para revisar anticipadamente el cierre 2026 sin guardar cambios:

```bash
python manage.py actualizar_anios_residencia --cierre 2026 --dry-run
```

### 8. Validaciones

#### En el Formulario de Completar Perfil
- Si selecciona "Médico Residente" → Campo de fecha es **obligatorio**
- Si selecciona otro rol → Campo de fecha se **oculta**

#### En el Formulario de Edición
- Residentes ven: Fecha de ingreso (editable) + Año (solo lectura)
- No residentes: Campos ocultos

### 9. Actualización Automática

El año inicial se calcula al completar el perfil. Los cambios posteriores se
procesan por ciclo académico con `actualizar_anios_residencia`.

### 10. Permisos y Accesos

Todos los médicos (staff, residentes, jefes, instructores) tienen acceso a:
- **Protocolos Radiológicos**: Sistema de decisión clínica
- **Gestión de Eventos**: Novedades del servicio
- **Editar Perfil**: Actualizar información personal

### 11. Próximos Pasos Sugeridos

1. **Tarea Programada**: ejecutar `actualizar_anios_residencia` diariamente o el 1 de agosto
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
