# Protección contra Duplicados en Carga Masiva EGES

## Problema Detectado

### Fecha: 30 de diciembre de 2025

### Descripción
Se detectó un problema de duplicación de registros en la funcionalidad de carga masiva de estudios desde archivos Excel EGES. Cuando se realizaba una carga masiva y luego se recargaba la página, los datos se duplicaban.

### Causas Identificadas

1. **Error de URL (NoReverseMatch)**
   - **Ubicación**: `liquidacion/views.py` línea 1073 (CargaMasivaView.confirmar_carga)
   - **Error**: `return redirect('carga-masiva')`
   - **Problema**: Faltaba el namespace `liquidacion:` en el nombre de la URL
   - **Impacto**: El redirect fallaba con error 500, pero los datos ya se habían guardado en la base de datos
   - **Log Heroku**: 
     ```
     django.urls.exceptions.NoReverseMatch: Reverse for 'carga-masiva' not found. 
     'carga-masiva' is not a valid view function or pattern name.
     ```

2. **Falta de Protección contra Duplicados**
   - La función `confirmar_carga` no verificaba si un registro ya existía antes de crearlo
   - Cada vez que se enviaba el formulario de confirmación, se insertaban TODOS los registros nuevamente
   - No había ningún mecanismo similar al que existe en `RegistroEstudiosPorMedicoCreateView` (líneas 111-139)

3. **Flujo del Problema**
   ```
   1. Usuario sube archivo Excel → Preview OK
   2. Usuario confirma carga → Registros se guardan en BD
   3. Intenta redirect → Falla con error 500
   4. Usuario ve error → Recarga la página manualmente
   5. Usuario confirma nuevamente → Registros duplicados se guardan otra vez
   ```

## Solución Implementada

### 1. Corrección de URL con Namespace
```python
# ANTES
return redirect('carga-masiva')

# DESPUÉS
return redirect('liquidacion:carga-masiva')
```

También se corrigió en `success_url`:
```python
# ANTES
success_url = reverse_lazy('carga-masiva')

# DESPUÉS
success_url = reverse_lazy('liquidacion:carga-masiva')
```

### 2. Protección contra Duplicados Recientes

Se implementó un sistema de protección similar al usado en la carga individual:

```python
from django.utils import timezone
from datetime import timedelta

hace_5_minutos = timezone.now() - timedelta(minutes=5)

# Verificar si ya existe un registro duplicado reciente
registro_existente = RegistroEstudiosPorMedico.objects.filter(
    medico=medico,
    dni_paciente=item['dni'],
    fecha_del_informe=item['fecha'],
    fecha_registro__gte=hace_5_minutos
).filter(
    estudio=estudio
).exists()

if registro_existente:
    duplicados += 1
    continue
```

### 3. Mejora en Mensajes al Usuario

Se implementaron tres tipos de mensajes para mayor claridad:

- **Success** (verde): Registros cargados exitosamente
- **Warning** (amarillo): Duplicados omitidos (protección activada)
- **Error** (rojo): Registros con errores que no se pudieron procesar

```python
if cargados > 0:
    messages.success(request, f"✅ Se cargaron correctamente {cargados} registros.")
if duplicados > 0:
    messages.warning(request, f"⚠️ Se omitieron {duplicados} registros duplicados (ya cargados en los últimos 5 minutos).")
if errores > 0:
    messages.error(request, f"❌ {errores} registros con errores no se pudieron cargar.")
```

## Características de la Protección

### Ventana de Tiempo: 5 minutos
- Evita doble envío accidental del formulario
- Permite registros legítimos posteriores del mismo paciente/estudio
- Mismo criterio usado en carga individual para consistencia

### Criterios de Duplicación
Un registro se considera duplicado si cumple TODAS estas condiciones:
1. Mismo médico
2. Mismo DNI de paciente
3. Misma fecha de informe
4. Mismo estudio
5. Creado en los últimos 5 minutos

## Impacto para los Usuarios

### Usuario: Denise Buleter (ID: 100)
- **Fecha**: 30 de diciembre de 2025, ~15:38 y 15:46 UTC
- **Registros afectados**: Carga masiva de diciembre 2025
- **Situación**: Se duplicaron sus registros por el bug antes de la corrección

### Recomendaciones Post-Fix

1. **Revisar registros duplicados**:
   ```python
   # Script para identificar duplicados
   from liquidacion.models import RegistroEstudiosPorMedico
   from datetime import date
   
   # Buscar registros del 30 de diciembre de 2025
   registros = RegistroEstudiosPorMedico.objects.filter(
       fecha_registro__date=date(2025, 12, 30),
       medico_id=100  # Denise Buleter
   ).order_by('dni_paciente', 'fecha_del_informe', 'fecha_registro')
   ```

2. **Eliminar duplicados si existen**:
   - Revisar registros con mismo DNI + fecha_del_informe
   - Mantener el registro más antiguo (primer registro creado)
   - Eliminar registros posteriores con mismos datos

## Testing

### Casos de Prueba
1. ✅ Carga masiva normal - debe funcionar sin errores
2. ✅ Doble click en confirmar - debe omitir duplicados
3. ✅ Recargar página después de carga - debe omitir duplicados
4. ✅ Carga legítima posterior (>5 min) - debe permitirse
5. ✅ Redirect después de confirmación - debe funcionar correctamente

### Verificación en Producción
- Desplegar cambios a Heroku
- Monitorear logs para confirmar ausencia de NoReverseMatch
- Verificar que los mensajes de duplicados aparecen correctamente

## Archivos Modificados

- ✅ `liquidacion/views.py`:
  - Clase `CargaMasivaView`, línea 971 (success_url)
  - Método `confirmar_carga`, líneas 1041-1113
  
## Estado

- [x] Bug identificado en logs de Heroku
- [x] Causa raíz encontrada (URL + falta de protección)
- [x] Solución implementada
- [ ] Desplegar a Heroku
- [ ] Verificar en producción
- [ ] Limpiar duplicados existentes si es necesario

## Notas Técnicas

### Diferencia con Protección en Carga Individual

La protección en `RegistroEstudiosPorMedicoCreateView` también verifica que los estudios seleccionados sean los mismos:

```python
# Buscar registros con estudios idénticos
for registro_reciente in registros_recientes:
    estudios_existentes = set(registro_reciente.estudio.all())
    if estudios_existentes == estudios_seleccionados:
        # Es duplicado
```

En la carga masiva, cada registro tiene solo un estudio, por lo que la verificación es más simple.

### Consideraciones Futuras

1. **Base de datos más robusta**: Considerar agregar un índice único compuesto en:
   - `(medico, dni_paciente, fecha_del_informe, estudio)`
   - Ventaja: Prevención a nivel de BD
   - Desventaja: No permite registros legítimos posteriores

2. **Log de auditoría**: Guardar información sobre duplicados omitidos para análisis

3. **Ventana de tiempo configurable**: Hacer la ventana de 5 minutos configurable por settings

## Referencias

- Issue en Heroku: Logs de 30/12/2025 15:38 y 15:46 UTC
- Usuario afectado: Denise Buleter (ID: 100)
- Rama: feature/colegiales
- App Heroku: mi-gestion-servicio
