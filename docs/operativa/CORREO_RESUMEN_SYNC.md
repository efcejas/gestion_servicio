# Resumen de Correos - Operativa

Guia operativa para sincronizar correos institucionales y alimentar el panel Resumen de correos del dashboard administrativo.

## Objetivo

Leer la casilla institucional por IMAP, priorizar mensajes relevantes y mostrar un resumen ejecutivo en el dashboard.

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

## Seguridad

- No versionar la clave institucional.
- Si la clave fue expuesta en terminal o capturas, rotarla.
- Mantener IMAP sobre SSL/TLS con puerto 993.
