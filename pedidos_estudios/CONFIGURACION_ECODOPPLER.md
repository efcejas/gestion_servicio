# Configuración Específica para Ecodoppler y Ecocardiogramas

## 🎯 Enfoque del Sistema

Este sistema está **específicamente diseñado** para procesar pedidos de:

### Ecocardiogramas
- Ecocardiograma Transtorácico (ETT)
- Ecocardiograma Transesofágico (ETE/TEE)
- Ecocardiograma con Doppler Color

### Ecodoppler Vascular
- **Miembros**: MMII, MMSS (arterial y venoso)
- **Carotídeo**: Arterias carótidas y vertebrales
- **Renal**: Arterias renales
- **Aorta**: Aorta abdominal
- **Otros**: Testicular, peneano

## 🔧 Configuración Realizada

### 1. Parser Optimizado

El parser en `services/email_parser.py` está configurado para detectar:

**Palabras clave para Ecocardiograma:**
- ecocardio, eco cardio, ecocardiograma
- transtorácico, transesofágico, TEE
- doppler cardiaco, doppler color

**Palabras clave para Ecodoppler:**
- doppler, ecodoppler, eco doppler
- mmii, mmss (miembros inferiores/superiores)
- carotídeo/carotideo, carótidas
- arterial, venoso, vascular
- renal, testicular, peneano

### 2. Tipos de Estudio Precargados

Ejecuta este comando para cargar 12 tipos predefinidos:

```bash
python manage.py cargar_tipos_estudio_inicial
```

**Incluye:**
1. Ecocardiograma Transtorácico (45 min)
2. Ecocardiograma Transesofágico (60 min, requiere preparación)
3. Ecocardiograma Doppler Color (45 min)
4. Ecodoppler de Miembros Inferiores (40 min)
5. Ecodoppler de Miembros Superiores (30 min)
6. Ecodoppler Carotídeo y Vertebral (30 min)
7. Ecodoppler Arterial de MMII (35 min)
8. Ecodoppler Venoso de MMII (35 min)
9. Ecodoppler Renal (30 min)
10. Ecodoppler de Aorta Abdominal (30 min)
11. Ecodoppler Testicular (20 min)
12. Ecodoppler Peneano (30 min)

### 3. Modalidad de Estudios

Todos los estudios usan modalidad **"US" (Ecografía/Ultrasonido)**

### 4. Preparación Especial

Solo requieren preparación:
- **Ecocardiograma Transesofágico**: Ayuno 6 horas
- **Ecodoppler Peneano**: Requiere preparación específica

## 📧 Formato de Emails Esperado

Ver archivo [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md) con 8 ejemplos diferentes de formatos.

### Datos mínimos requeridos:
- ✅ Nombre del paciente
- ✅ Habitación o Historia Clínica
- ✅ Tipo de estudio (descripción)
- ⚠️ DNI (opcional pero recomendado)
- ⚠️ Médico solicitante (opcional)

### Ejemplo básico:
```
Paciente: Juan Pérez
DNI: 12345678
Habitación: 302A
Estudio: Ecodoppler carotídeo bilateral
Médico: Dr. García
```

## 🚀 Workflow Típico

1. **Email llega** a `solicitudestudioscolegiales@gmail.com`
2. **Cron ejecuta** cada 15 minutos: `python manage.py procesar_pedidos_email`
3. **Sistema detecta** tipo de estudio (ecocardio o doppler)
4. **Extrae** datos del paciente y ubicación
5. **Crea pedido** con prioridad detectada
6. **Notifica** al médico responsable del tipo de estudio
7. **Staff revisa** en admin si necesita ajustes

## 🔍 Casos Especiales

### Urgencias
El sistema detecta automáticamente como URGENTE si encuentra:
- Palabra "URGENTE" en asunto o cuerpo
- "STAT", "EMERGENCIA"
- Signos de prioridad alta

### TEE (Transesofágico)
- Marca automáticamente `requiere_preparacion = True`
- Tiempo estimado: 60 minutos
- Notifica sobre necesidad de consentimiento y ayuno

### TVP (Trombosis Venosa Profunda)
Si la indicación menciona "TVP" o "trombosis":
- Sugiere Ecodoppler Venoso de MMII
- Puede marcar como prioridad ALTA

## 🎨 Personalización

### Agregar nuevos tipos de estudio

1. Desde el admin: `/admin/pedidos_estudios/tipoestudio/add/`
2. Completa:
   - Nombre del estudio
   - Modalidad: US
   - Tiempo estimado en minutos
   - Médico responsable
   - Email de notificación (opcional)
   - Si requiere preparación

### Ajustar patrones de extracción

Edita `services/email_parser.py`, sección `PATRONES`:

```python
PATRONES = {
    'estudio': [
        r'estudio\s*solicitado\s*:?\s*([^\n]+)',
        r'tipo\s*de\s*estudio\s*:?\s*([^\n]+)',
        # Agrega tu patrón personalizado aquí
    ],
}
```

### Modificar clasificación de estudios

En `services/email_parser.py`, función `_clasificar_tipo_estudio()`:

```python
clasificaciones = {
    'ecocardiograma': [
        'ecocardio', 'eco cardio',
        # Agrega más palabras clave
    ],
}
```

## 📊 Métricas y Monitoreo

### Ver logs de procesamiento

Admin → Logs de Procesamiento: `/admin/pedidos_estudios/logprocesamientoemail/`

### Estadísticas útiles

```python
from pedidos_estudios.models import PedidoEstudio

# Pedidos por tipo de estudio
PedidoEstudio.objects.values('tipo_estudio__nombre').annotate(total=Count('id'))

# Pedidos urgentes pendientes
PedidoEstudio.objects.filter(prioridad='URGENTE', estado='PENDIENTE').count()

# Pedidos de ecocardiograma este mes
from django.utils import timezone
inicio_mes = timezone.now().replace(day=1)
PedidoEstudio.objects.filter(
    tipo_estudio__nombre__icontains='ecocardiograma',
    fecha_solicitud__gte=inicio_mes
).count()
```

## 🆘 Problemas Comunes

### El parser no detecta el tipo de estudio

**Solución**: Revisa que la descripción contenga palabras clave:
- Para ecocardio: "ecocardio", "doppler cardiaco", "transtorácico"
- Para doppler: "doppler", "mmii", "carotídeo", "arterial", "venoso"

Si el formato es diferente, agrega patrones en `email_parser.py`

### No asigna médico responsable

**Solución**: 
1. Ve al admin: `/admin/pedidos_estudios/tipoestudio/`
2. Edita cada tipo de estudio
3. Asigna un médico responsable o un email de notificación

### Los emails no se procesan

**Solución**:
1. Verifica Gmail API: `python manage.py shell` → `verificar_configuracion_gmail()`
2. Revisa que el cron esté ejecutándose
3. Mira los logs: `/admin/pedidos_estudios/logprocesamientoemail/`

## 📚 Referencias

- [README.md](README.md) - Documentación técnica completa
- [QUICKSTART.md](QUICKSTART.md) - Guía rápida de inicio
- [EJEMPLOS_EMAILS.md](EJEMPLOS_EMAILS.md) - Ejemplos de formatos de email
- Gmail API Docs: https://developers.google.com/gmail/api

---

**💡 Tip**: Cuando recibas el primer email real, cópialo completo y úsalo para probar el parser. Ajusta los patrones hasta que extraiga correctamente todos los datos.
