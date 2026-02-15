# ✅ Checklist de Instalación Gmail API

Usa esta lista para verificar cada paso de la instalación del sistema de pedidos de estudios.

---

## 📦 Parte 1: Instalación de Librerías

- [ ] Instalar `google-auth`
- [ ] Instalar `google-auth-oauthlib`
- [ ] Instalar `google-auth-httplib2`
- [ ] Instalar `google-api-python-client`
- [ ] Instalar `beautifulsoup4`

**Comando completo:**
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client beautifulsoup4
```

---

## ☁️ Parte 2: Google Cloud Console

### Crear Proyecto

- [ ] Ir a https://console.cloud.google.com/
- [ ] Clic en selector de proyectos (arriba)
- [ ] Clic en "NUEVO PROYECTO"
- [ ] Nombre: `Sanatorio Colegiales - Pedidos Estudios`
- [ ] Clic en "CREAR"
- [ ] Esperar notificación de proyecto creado

### Habilitar Gmail API

- [ ] Abrir menú ☰
- [ ] Ir a: APIs y servicios > Biblioteca
- [ ] Buscar: `gmail`
- [ ] Clic en "Gmail API"
- [ ] Clic en "HABILITAR"
- [ ] Verificar mensaje: "API habilitada"

### Configurar Pantalla de Consentimiento OAuth

- [ ] Ir a: APIs y servicios > Pantalla de consentimiento de OAuth
- [ ] Seleccionar tipo: **Externo**
- [ ] Clic en "CREAR"

**Paso 1 - Información de la app:**
- [ ] Nombre: `Sistema de Pedidos - Sanatorio Colegiales`
- [ ] Email de asistencia: `<tu_email>` (ej: ecejas@sanatoriocolegiales.com.ar)
- [ ] Email del desarrollador: `<tu_email>`
- [ ] Clic en "GUARDAR Y CONTINUAR"

**Paso 2 - Alcances:**
- [ ] Clic en "AGREGAR O QUITAR ALCANCES"
- [ ] Buscar: `gmail`
- [ ] Marcar: ☑ `.../auth/gmail.readonly`
- [ ] Marcar: ☑ `.../auth/gmail.modify`
- [ ] Clic en "ACTUALIZAR"
- [ ] Clic en "GUARDAR Y CONTINUAR"

**Paso 3 - Usuarios de prueba:**
- [ ] Clic en "+ AGREGAR USUARIOS"
- [ ] Email: `solicitudestudioscolegiales@gmail.com`
- [ ] Clic en "AGREGAR"
- [ ] Clic en "GUARDAR Y CONTINUAR"

**Paso 4 - Resumen:**
- [ ] Revisar información
- [ ] Clic en "VOLVER AL PANEL"

### Crear Credenciales OAuth

- [ ] Ir a: APIs y servicios > Credenciales
- [ ] Clic en "+ CREAR CREDENCIALES"
- [ ] Seleccionar: "ID de cliente de OAuth"
- [ ] Tipo de aplicación: **Aplicación de escritorio**
- [ ] Nombre: `Cliente Desktop - Pedidos Estudios`
- [ ] Clic en "CREAR"
- [ ] Clic en "DESCARGAR JSON"
- [ ] Guardar archivo como: `credentials.json`
- [ ] Mover a: `C:\Dev\GitHub\gestion_servicio\credentials.json`

---

## ⚙️ Parte 3: Configuración Django

### Crear settings_local.py

- [ ] Crear archivo: `gestion_estudios/settings_local.py`
- [ ] Copiar configuración completa (ver guía)
- [ ] Verificar ruta del `credentials.json`

### Actualizar .gitignore

- [ ] Abrir: `.gitignore`
- [ ] Agregar líneas:
  ```
  # Gmail API
  credentials.json
  token.json
  gestion_estudios/settings_local.py
  ```
- [ ] Guardar archivo

### Actualizar settings.py

- [ ] Abrir: `gestion_estudios/settings.py`
- [ ] Agregar al final:
  ```python
  # Importar configuración local
  try:
      from .settings_local import *
  except ImportError:
      pass
  ```
- [ ] Verificar `'pedidos_estudios'` en `INSTALLED_APPS`
- [ ] Guardar archivo

### Actualizar urls.py

- [ ] Abrir: `gestion_estudios/urls.py`
- [ ] Agregar a `urlpatterns`:
  ```python
  path('pedidos/', include('pedidos_estudios.urls')),
  ```
- [ ] Guardar archivo

---

## 🗄️ Parte 4: Base de Datos

- [ ] Ejecutar: `python manage.py makemigrations pedidos_estudios`
- [ ] Verificar archivos de migración creados
- [ ] Ejecutar: `python manage.py migrate`
- [ ] Verificar tablas creadas
- [ ] Ejecutar: `python manage.py cargar_tipos_estudio_inicial`
- [ ] Verificar: "12 tipos de estudio cargados"

---

## 🔐 Parte 5: Primera Autenticación

### Desde Django Shell

- [ ] Ejecutar: `python manage.py shell`
- [ ] Importar función:
  ```python
  from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail
  ```
- [ ] Ejecutar:
  ```python
  exito, mensaje = verificar_configuracion_gmail()
  ```
- [ ] Navegador se abre automáticamente

### En el Navegador

- [ ] Seleccionar cuenta: `solicitudestudioscolegiales@gmail.com`
- [ ] Clic en "Avanzado"
- [ ] Clic en "Ir a Sistema de Pedidos (no seguro)"
- [ ] Revisar permisos:
  - ☑ Ver mensajes de correo
  - ☑ Modificar metadatos de Gmail
- [ ] Clic en "Permitir"
- [ ] Verificar mensaje: "Authentication flow has completed"
- [ ] Cerrar pestaña del navegador

### De vuelta en Django Shell

- [ ] Verificar en shell:
  ```python
  print(f"Éxito: {exito}")
  print(f"Mensaje: {mensaje}")
  ```
- [ ] Output esperado:
  ```
  Éxito: True
  Mensaje: Conectado a solicitudestudioscolegiales@gmail.com - XXXX mensajes
  ```
- [ ] Verificar archivo creado: `token.json` en directorio raíz

---

## 🧪 Parte 6: Pruebas

### Test 1: Verificación en Admin

- [ ] Ejecutar: `python manage.py runserver`
- [ ] Ir a: http://localhost:8000/admin/
- [ ] Login con tu usuario admin
- [ ] Ir a: "Tipos de Estudios"
- [ ] Verificar 12 tipos:
  - 3 Ecocardiogramas
  - 9 Ecodoppler
- [ ] Asignar médico responsable a cada tipo
- [ ] Agregar email de notificación a cada tipo

### Test 2: Procesamiento Manual (Modo Test)

- [ ] Ejecutar en terminal:
  ```bash
  python manage.py procesar_pedidos_email --max-emails=5 --no-marcar-leido
  ```
- [ ] Verificar output:
  ```
  ✓ Emails procesados: X
  ✓ Pedidos creados: X
  ⚠ Errores: X
  ```
- [ ] Si hay errores, revisar logs

### Test 3: Ver Logs

- [ ] Ir al admin: "Logs de Procesamiento"
- [ ] Verificar entradas con:
  - Fecha/hora
  - Email procesado
  - Estado (éxito/error)
  - Datos extraídos
  - Errores (si los hay)

### Test 4: Revisar Pedidos

- [ ] Ir al admin: "Pedidos de Estudios"
- [ ] Verificar pedidos creados
- [ ] Campo "Requiere revisión" debería estar en ✓ (inicialmente)
- [ ] Verificar datos del paciente
- [ ] Verificar tipo de estudio asignado
- [ ] Verificar prioridad detectada

---

## 🔧 Parte 7: Ajuste del Parser

- [ ] Abrir Django shell: `python manage.py shell`
- [ ] Importar parser:
  ```python
  from pedidos_estudios.services.email_parser import EmailParser
  ```
- [ ] Tomar texto de un email real
- [ ] Probar extracción:
  ```python
  parser = EmailParser()
  datos = parser.extraer_informacion_basica("texto del email aquí")
  print(datos)
  ```
- [ ] Identificar campos faltantes o incorrectos
- [ ] Abrir: `pedidos_estudios/services/email_parser.py`
- [ ] Actualizar patrones en diccionario `PATRONES`
- [ ] Re-probar extracción
- [ ] Repetir hasta que extracción sea correcta

**Prueba con EJEMPLOS_EMAILS.md:**
- [ ] Abrir: `EJEMPLOS_EMAILS.md`
- [ ] Copiar ejemplo 1 (simple)
- [ ] Probar en shell
- [ ] Copiar ejemplo 2 (urgente)
- [ ] Probar en shell
- [ ] Continuar con los 8 ejemplos
- [ ] Verificar detección correcta en cada caso

---

## ⚙️ Parte 8: Automatización

### Opción A: Windows Task Scheduler (Desarrollo Local)

- [ ] Abrir: Programador de Tareas
- [ ] Crear Tarea Básica
- [ ] Nombre: `Procesar Pedidos Estudios`
- [ ] Disparador: **Diariamente**
- [ ] Repetir cada: **15 minutos**
- [ ] Durante: **Indefinidamente**
- [ ] Acción: **Iniciar un programa**
- [ ] Programa: Ruta completa a Python (ej: `C:\Python311\python.exe`)
- [ ] Argumentos: 
  ```
  manage.py procesar_pedidos_email --max-emails=20
  ```
- [ ] Directorio de inicio:
  ```
  C:\Dev\GitHub\gestion_servicio
  ```
- [ ] Guardar tarea
- [ ] Ejecutar manualmente para probar
- [ ] Verificar en "Historial" que se ejecutó correctamente

### Opción B: Heroku Scheduler (Producción)

- [ ] Heroku Dashboard > App > Resources
- [ ] Buscar add-on: "Heroku Scheduler"
- [ ] Instalar add-on (plan gratuito)
- [ ] Abrir "Heroku Scheduler"
- [ ] Clic en "Add Job"
- [ ] Comando:
  ```bash
  python manage.py procesar_pedidos_email --max-emails=20
  ```
- [ ] Frecuencia: **Every 10 minutes**
- [ ] Guardar job
- [ ] Monitorear logs: `heroku logs --tail --app tu-app`

**Configurar Config Vars en Heroku:**
- [ ] Settings > Config Vars
- [ ] Agregar:
  ```
  GMAIL_CREDENTIALS_JSON = {contenido completo del credentials.json}
  GMAIL_TOKEN_JSON = {contenido del token.json después de autenticar localmente}
  ```
- [ ] En `settings_local.py` agregar lógica para leer de `os.environ` en producción

---

## 🔒 Parte 9: Seguridad

- [ ] Verificar `.gitignore` contiene:
  - `credentials.json`
  - `token.json`
  - `settings_local.py`
- [ ] **NUNCA** hacer commit de estas credenciales
- [ ] En producción, usar variables de entorno o secretos de Heroku
- [ ] Limitar alcances de OAuth a solo lo necesario
- [ ] Mantener usuarios de prueba actualizados
- [ ] Revisar periódicamente la actividad de OAuth en Google Cloud Console

---

## 📊 Parte 10: Monitoreo y Mantenimiento

### Monitoreo Diario

- [ ] Revisar logs de procesamiento en admin
- [ ] Verificar pedidos marcados "Requiere revisión"
- [ ] Corregir manualmente errores de parsing
- [ ] Notificar a médicos de pedidos urgentes

### Monitoreo Semanal

- [ ] Estadísticas de procesamiento:
  ```python
  from pedidos_estudios.models import PedidoEstudio, LogProcesamientoEmail
  from django.utils import timezone
  from datetime import timedelta
  
  hace_7_dias = timezone.now() - timedelta(days=7)
  
  total = PedidoEstudio.objects.filter(fecha_recepcion__gte=hace_7_dias).count()
  automaticos = PedidoEstudio.objects.filter(
      fecha_recepcion__gte=hace_7_dias,
      procesado_automaticamente=True
  ).count()
  errores = LogProcesamientoEmail.objects.filter(
      fecha_procesamiento__gte=hace_7_dias,
      resultado='error'
  ).count()
  
  print(f"Últimos 7 días:")
  print(f"  Total procesados: {total}")
  print(f"  Procesados automáticamente: {automaticos}")
  print(f"  Errores: {errores}")
  print(f"  Tasa de éxito: {(automaticos/total*100):.1f}%")
  ```
- [ ] Revisar patrones de errores comunes
- [ ] Actualizar parser según sea necesario

### Monitoreo Mensual

- [ ] Revisar cuota de Gmail API en Google Cloud Console
- [ ] Verificar renovación de token (refresh_token debe funcionar)
- [ ] Actualizar tipos de estudio si hay nuevos
- [ ] Backup de base de datos

---

## ✅ Verificación Final

- [ ] ✓ Librerías de Google instaladas
- [ ] ✓ Proyecto en Google Cloud Console creado
- [ ] ✓ Gmail API habilitada
- [ ] ✓ Pantalla de consentimiento configurada
- [ ] ✓ Credenciales OAuth creadas y descargadas
- [ ] ✓ `credentials.json` en lugar correcto
- [ ] ✓ `settings_local.py` configurado
- [ ] ✓ `.gitignore` actualizado
- [ ] ✓ Migraciones aplicadas
- [ ] ✓ 12 tipos de estudio cargados
- [ ] ✓ Primera autenticación completada
- [ ] ✓ `token.json` creado
- [ ] ✓ Conexión a Gmail verificada
- [ ] ✓ Procesamiento de emails funciona
- [ ] ✓ Parser ajustado con emails reales
- [ ] ✓ Automatización configurada
- [ ] ✓ Sistema en producción

---

## 📝 Notas

- **Fecha de instalación**: _______________
- **Cuenta Gmail configurada**: _______________
- **ID del proyecto Google Cloud**: _______________
- **Frecuencia de automatización**: _______________
- **Médicos responsables asignados**: _______________

---

## 🆘 Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError: No module named 'google'` | Instalar librerías de Google |
| `FileNotFoundError: credentials.json` | Verificar ruta del archivo |
| `invalid_grant` | Borrar `token.json` y re-autenticar |
| `access_blocked` | Agregar usuario a la lista de prueba |
| No se crean pedidos | Revisar logs de procesamiento en admin |
| Parser no extrae datos | Ajustar patrones en `email_parser.py` |

---

**Última actualización**: 2026-02-13

Para más detalles, consultar:
- [INSTALACION_GMAIL_API.md](INSTALACION_GMAIL_API.md)
- [GUIA_VISUAL_GOOGLE_CLOUD.md](GUIA_VISUAL_GOOGLE_CLOUD.md)
- [QUICKSTART.md](QUICKSTART.md)
