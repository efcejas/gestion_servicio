# ✅ Checklist de Despliegue - Sistema de Pedidos de Estudios

## ANTES DE DESPLEGAR

### 1. Archivos Protegidos
- [x] `.gitignore` configurado con archivos sensibles
- [ ] Verificar que NO estén en Git:
  ```bash
  git status | grep -E "token.json|credentials.json|.env|settings_local.py"
  # No debe mostrar nada
  ```

### 2. Generar Token de Gmail (LOCAL)

**CRÍTICO:** Este paso DEBE hacerse en tu máquina local antes de desplegar.

```bash
# 1. Asegúrate de tener credentials.json
ls credentials.json

# 2. Genera el token
python manage.py shell -c "from pedidos_estudios.services.gmail_service import GmailService; g = GmailService()"

# 3. Se abrirá el navegador - acepta los permisos
# 4. Verifica que se creó token.json
ls token.json
```

### 3. Preparar Token para Heroku

```bash
# Ejecuta el script helper
python pedidos_estudios/scripts/prepare_gmail_for_heroku.py

# Esto generará .local/gmail/token_for_heroku.txt con el valor para copiar
```

### 4. Variables de Entorno en Heroku

En **Heroku Dashboard → Settings → Config Vars**, agrega:

```env
# Django básico
SECRET_KEY=<genera uno nuevo para producción>
DEBUG=False
ALLOWED_HOSTS=<tu-app>.herokuapp.com

# Gmail (CRÍTICO)
GMAIL_TOKEN_JSON=<copia el contenido de .local/gmail/token_for_heroku.txt>
GMAIL_EMAIL=solicitudestudioscolegiales@gmail.com
GMAIL_PEDIDOS_QUERY=is:unread

# Notificaciones
PEDIDOS_EMAIL_DEFAULT=ecejas@sanatoriocolegiales.com.ar
SITE_URL=https://<tu-app>.herokuapp.com

# Email SMTP (para enviar notificaciones)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=<email>@gmail.com
EMAIL_HOST_PASSWORD=<app_password>

# Sanatorio
SANATORIO_NOMBRE=Sanatorio Colegiales
SANATORIO_MODO=Colegiales
```

### 5. Addons de Heroku

```bash
# Base de datos (si no existe)
heroku addons:create heroku-postgresql:mini

# Scheduler para procesamiento automático
heroku addons:create scheduler:standard
```

---

## DURANTE EL DESPLIEGUE

### 1. Push a Heroku

```bash
# Push del branch actual
git push heroku feature/colegiales:main

# Ver el build y release
heroku logs --tail
```

### 2. Ejecutar Migraciones (si no se ejecutaron auto)

```bash
heroku run python manage.py migrate
```

### 3. Crear Superusuario

```bash
heroku run python manage.py createsuperuser
```

### 4. Configurar Heroku Scheduler

```bash
# Abrir dashboard del scheduler
heroku addons:open scheduler

# Agregar job con frecuencia: Every 10 minutes
# Comando: python manage.py procesar_pedidos_auto --max-emails=20 --silent
```

---

## DESPUÉS DEL DESPLIEGUE

### 1. Verificar Gmail API

```bash
heroku run python manage.py shell -c "from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail; print(verificar_configuracion_gmail())"
```

**Resultado esperado:**
```
(True, 'Configuración de Gmail OK. Email: solicitudestudioscolegiales@gmail.com')
```

### 2. Probar Procesamiento Manual

```bash
heroku run python manage.py procesar_pedidos_auto --max-emails=3
```

**Resultado esperado:**
```
✓ Procesados: 2/3
```

### 3. Verificar Dashboard

```bash
# Abrir app en navegador
heroku open

# Ir a /pedidos/
# Login como superuser o administrativo
# Verificar que se ven los pedidos procesados
```

### 4. Monitorear Scheduler

```bash
# Ver logs en tiempo real
heroku logs --tail | grep "procesamiento"

# Esperar 10 minutos y verificar que ejecuta
# Debe aparecer: "Procesamiento automático: procesados=X, exitosos=Y"
```

### 5. Verificar Permisos por Rol

- [ ] Superuser puede ver dashboard completo
- [ ] Administrativo puede ver dashboard y procesar emails
- [ ] Jefes/Instructores pueden ver dashboard (sin botón procesar)
- [ ] Médicos NO ven dashboard (próximamente "Mis Estudios")

---

## TROUBLESHOOTING COMÚN

### ❌ "Token not found" o "Invalid credentials"

**Causa:** GMAIL_TOKEN_JSON no configurado o inválido

**Solución:**
```bash
# Verificar configuración
heroku config | grep GMAIL

# Si falta, volver a paso 3 "Preparar Token para Heroku"
heroku config:set GMAIL_TOKEN_JSON="<contenido de .local/gmail/token_for_heroku.txt>"
```

### ❌ "No se pueden procesar emails"

**Causa:** Permisos de API o query incorrecta

**Solución:**
```bash
# Verificar query
heroku config:get GMAIL_PEDIDOS_QUERY
# Debe mostrar: is:unread

# Verificar permisos en Google Cloud Console:
# - Gmail API habilitada
# - OAuth consent screen configurado
# - Scopes correctos agregados
```

### ❌ "Scheduler no ejecuta"

**Causa:** Job mal configurado o dyno dormido

**Solución:**
```bash
# Ver logs del scheduler
heroku logs --tail --dyno=scheduler

# Verificar que el job esté habilitado en el dashboard
heroku addons:open scheduler

# En plan gratuito, el dyno se duerme después de 30 min sin actividad
# Considera usar un pinger externo o upgrade a paid plan
```

### ❌ "Emails se procesan pero no se marcan como leídos"

**Causa:** Falta scope de modificación

**Solución:**
Verificar que en Google Cloud Console el scope incluye:
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.modify` ← ESTE

Regenerar token si falta scope.

---

## MANTENIMIENTO

### Renovar Token (si expira)

El token se renueva automáticamente, pero si falla:

```bash
# 1. En local, regenerar token
rm token.json
python manage.py shell -c "from pedidos_estudios.services.gmail_service import GmailService; g = GmailService()"

# 2. Preparar para Heroku
python pedidos_estudios/scripts/prepare_gmail_for_heroku.py

# 3. Actualizar en Heroku
heroku config:set GMAIL_TOKEN_JSON="<nuevo valor>"
```

### Ver Estadísticas

```bash
# Ver últimos 100 logs de procesamiento
heroku run python manage.py shell -c "from pedidos_estudios.models import LogProcesamientoEmail; logs = LogProcesamientoEmail.objects.all()[:10]; [print(f'{log.fecha_procesamiento} - {log.exitoso} - {log.tipo_estudio}') for log in logs]"

# Ver pedidos creados hoy
heroku run python manage.py shell -c "from pedidos_estudios.models import PedidoEstudio; from django.utils import timezone; hoy = timezone.now().date(); print(f'Pedidos hoy: {PedidoEstudio.objects.filter(fecha_creacion__date=hoy).count()}')"
```

---

## 📞 CONTACTO DE EMERGENCIA

Si algo falla crítico en producción:

1. **Ver logs:** `heroku logs --tail --app <tu-app>`
2. **Pausar scheduler:** Heroku Dashboard → Scheduler → Disable job
3. **Rollback:** `heroku releases` → `heroku rollback vXX`
4. **Modo mantenimiento:** `heroku maintenance:on`

---

**Última actualización:** 15/02/2026  
**Versión del sistema:** 1.0 - Pedidos de Estudios
