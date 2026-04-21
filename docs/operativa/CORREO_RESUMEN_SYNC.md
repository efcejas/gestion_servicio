# Resumen de Correos - Operativa

Guia operativa para sincronizar correos institucionales y alimentar el panel Resumen de correos del dashboard administrativo.

## Objetivo

Leer la casilla institucional por IMAP, priorizar mensajes relevantes, agrupar conversaciones en hilos y mostrar un resumen operativo en el dashboard.

## Estado actual del flujo

El modulo ya cubre tres capas de uso:

1. Sincronizacion de correos individuales priorizados.
2. Agrupacion automatica en hilos usando asunto normalizado.
3. Gestion operativa del hilo desde dashboard y vista detalle.

Estados disponibles del hilo:

- pendiente: requiere seguimiento visible en la bandeja del dashboard.
- en_curso: ya se esta trabajando, pero sigue abierto.
- resuelto: deja de aparecer en Atencion Hoy.

Regla practica: usar el hilo como unidad de trabajo. Los cambios de estado del hilo se propagan a los correos asociados para mantener consistencia.

## Configuracion requerida

Completar en .env:

```env
CORREO_RESUMEN_ENABLED=True
CORREO_RESUMEN_PROVIDER=imap
CORREO_RESUMEN_IMAP_HOST=mail.sanatoriocolegiales.com.ar
CORREO_RESUMEN_IMAP_PORT=993
CORREO_RESUMEN_IMAP_USERNAME=<casilla institucional>
CORREO_RESUMEN_IMAP_PASSWORD=<clave de la casilla>
CORREO_RESUMEN_IMAP_FOLDER=INBOX
CORREO_RESUMEN_SEARCH_CRITERIA=UNSEEN
CORREO_RESUMEN_MAX_EMAILS_PER_RUN=20
CORREO_RESUMEN_ENABLE_AI_SUMMARY=False
```

Reglas iniciales ajustables:

```env
CORREO_RESUMEN_PRIORITY_SENDERS=calidad@sanatoriocolegiales.com.ar,auditoria@sanatoriocolegiales.com.ar,soporte@sanatoriocolegiales.com.ar
CORREO_RESUMEN_URGENT_KEYWORDS=urgente,importante,auditoria,guardia,falla,reclamo
CORREO_RESUMEN_ACTION_KEYWORDS=responder,confirmar,coordinar,pendiente,resolver
```

## Primera puesta en marcha

1. Aplicar migraciones del modulo:

```powershell
python manage.py migrate correo_resumen
```

2. Ejecutar una sincronizacion manual de prueba:

```powershell
python manage.py sincronizar_correos_resumen --max-emails 10
```

3. Verificar el estado del ultimo proceso:

```powershell
python manage.py shell -c "from correo_resumen.models import CorreoSincronizacion; s=CorreoSincronizacion.objects.order_by('-iniciado_en').first(); print(s.estado, s.correos_leidos, s.correos_nuevos, s.mensaje)"
```

4. Abrir el dashboard administrativo y validar estas zonas:

- Resumen de correos
- Atencion Hoy por hilos
- Resumen ejecutivo del dia

Si la sincronizacion encontro mensajes relevantes, la tarjeta Atencion Hoy por hilos debe mostrar conversaciones agrupadas con estado, participantes y fecha del ultimo intercambio.

## Uso operativo diario

### Desde el dashboard

La tarjeta Atencion Hoy por hilos funciona como bandeja compacta.

- Click sobre la tarjeta: abre el detalle completo del hilo.
- Boton En curso: marca el hilo como tomado, sin sacarlo de la bandeja.
- Boton Resuelto: cierra el hilo y lo remueve de Atencion Hoy.
- Filtros rapidos: Todos, Pendientes, En curso y Urgentes para cambiar la vista sin salir del dashboard.
- Badge Seguimiento: muestra la proxima fecha operativa definida para el hilo.
- Agenda de seguimiento: separa hilos con seguimiento vencido de los proximos, para usar el dashboard como bandeja + agenda.

### Desde el detalle del hilo

La vista de detalle permite revisar toda la conversacion agrupada y cambiar el estado con mas contexto.

- Pendiente: vuelve a poner el hilo en seguimiento activo.
- En curso: deja registro de trabajo en marcha.
- Marcar resuelto: cierra la conversacion operativa.
- Proximo seguimiento: permite programar un recordatorio operativo con fecha y hora.
- Limpiar seguimiento: elimina el recordatorio cuando deja de ser necesario.

Regla actual: si se programa seguimiento sobre un hilo resuelto, el hilo vuelve automaticamente a pendiente para que reaparezca en la bandeja operativa.

Ruta actual:

```text
/dashboard/correos/hilo/<id>/
```

## Validacion tecnica recomendada

Checks minimos despues de cambios en el modulo:

```powershell
python manage.py check
python manage.py test correo_resumen
python manage.py test correo_resumen.tests_hilo
```

Cobertura agregada en esta etapa:

- filtros por estado y urgencia en la bandeja de hilos
- inclusion de fecha_seguimiento en la logica de Atencion Hoy
- cambio de estado y programacion de seguimiento via POST
- agenda resumida de seguimientos vencidos y proximos en el dashboard

## Automatizacion en Windows

Scripts disponibles en la raiz del proyecto:

- sincronizar_correos_resumen_auto.bat
- configurar_task_scheduler_correo_resumen.ps1

Para crear la tarea programada:

```powershell
PowerShell -ExecutionPolicy Bypass -File .\configurar_task_scheduler_correo_resumen.ps1
```

Frecuencia sugerida: cada 15 minutos.

## Logs

```powershell
Get-Content logs\sincronizar_correos_resumen.log -Tail 20
Get-Content logs\sincronizar_correos_resumen.log -Wait
```

## Problemas frecuentes

### no such table: correo_resumen_correosincronizacion

Faltan migraciones del modulo.

```powershell
python manage.py migrate correo_resumen
```

### 0 correo(s) nuevos priorizados

No necesariamente es error.

- Si SEARCH_CRITERIA=UNSEEN, puede que no haya mensajes sin leer.
- Para auditoria puntual, cambiar temporalmente a ALL y luego volver a UNSEEN.

### No aparecen correos en las tarjetas

Puede pasar si el correo fue sincronizado pero no alcanzo score suficiente para bloques de urgentes o importantes no leidos. Ajustar remitentes prioritarios y keywords en .env.

### Aparece el hilo pero no cambia al hacer click en un boton

Verificar que el servidor activo sea el correcto. En Windows es facil quedar con multiples runserver levantados y ver codigo viejo.

- Cerrar procesos runserver duplicados.
- Levantar nuevamente el servidor.
- Repetir la accion desde el dashboard.

### Un mismo asunto no genera dos hilos separados

Es el comportamiento esperado actual. El agrupamiento usa asunto normalizado y una restriccion unica por cuenta + asunto_normalizado.

Trade-off: simplifica la bandeja operativa y evita duplicados, pero no separa conversaciones historicas con el mismo asunto.

## Seguridad

- No versionar la clave institucional.
- Si la clave fue expuesta en terminal o capturas, rotarla.
- Mantener IMAP sobre SSL/TLS con puerto 993.
