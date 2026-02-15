# ⏰ Configuración de Procesamiento Automático

## 🪟 Windows (Desarrollo y Sanatorio Local)

### Opción 1: Task Scheduler (Recomendado)

**Crear tarea programada:**

1. Presiona `Win + R` → escribe `taskschd.msc` → Enter
2. Panel derecho → "Crear tarea básica"
3. Configuración:
   - **Nombre:** `Procesar Pedidos Estudios`
   - **Descripción:** `Procesa pedidos de estudios desde Gmail cada 5 minutos`
   - **Desencadenador:** Diariamente
   - **Repetir cada:** 5 minutos
   - **Duración:** Indefinidamente
   - **Acción:** Iniciar programa
   - **Programa:** `C:\Dev\GitHub\gestion_servicio\procesar_pedidos_auto.bat`
   - **Directorio de inicio:** `C:\Dev\GitHub\gestion_servicio`

4. **Configuración avanzada:**
   - ✅ Ejecutar aunque el usuario no haya iniciado sesión
   - ✅ Ejecutar con los privilegios más altos
   - ✅ Configurar para: Windows 10/11
   - ⏰ Si la tarea falla, reintentar cada: 1 minuto
   - 🔢 Intentar reinicio hasta: 3 veces

### Opción 2: Script de Monitoreo Continuo

```batch
REM Ejecutar en terminal administrativa
cd C:\Dev\GitHub\gestion_servicio
procesar_pedidos_loop.bat
```

---

## 🐧 Linux / Heroku (Producción)

### Cron Job

**1. Editar crontab:**
```bash
crontab -e
```

**2. Agregar línea para ejecutar cada 5 minutos:**
```bash
*/5 * * * * cd /app && python manage.py procesar_pedidos_auto --silent >> /var/log/procesar_pedidos.log 2>&1
```

**Ejemplos de frecuencias:**
```bash
# Cada 5 minutos
*/5 * * * * comando

# Cada 10 minutos
*/10 * * * * comando

# Cada hora
0 * * * * comando

# Cada día a las 8:00 AM
0 8 * * * comando

# Cada lunes a las 9:00 AM
0 9 * * 1 comando
```

### Heroku Scheduler

**1. Instalar addon:**
```bash
heroku addons:create scheduler:standard
```

**2. Configurar:**
```bash
heroku addons:open scheduler
```

**3. Agregar job:**
- **Comando:** `python manage.py procesar_pedidos_auto --silent`
- **Frecuencia:** Every 10 minutes
- **Dyno:** Standard-1X

---

## 📊 Monitoreo

### Ver logs en tiempo real:

**Windows:**
```batch
type logs\procesar_pedidos.log
```

**Linux/Heroku:**
```bash
tail -f /var/log/procesar_pedios.log

# O en Heroku
heroku logs --tail --app sanatorio-colegiales
```

### Verificar última ejecución:

```bash
python manage.py shell
>>> from pedidos_estudios.models import LogProcesamientoEmail
>>> LogProcesamientoEmail.objects.latest('fecha_procesamiento')
```

---

## 🔧 Ajustar Frecuencia

**Para entorno de pruebas:** Cada 10-15 minutos es suficiente  
**Para producción con mucho volumen:** Cada 3-5 minutos  
**Para sanatorio pequeño:** Cada 10-30 minutos  

**Modificar en Task Scheduler:**
1. Abrir Task Scheduler
2. Biblioteca → Buscar "Procesar Pedidos Estudios"
3. Clic derecho → Propiedades
4. Pestaña "Desencadenadores" → Editar
5. Cambiar "Repetir cada" a tu preferencia

---

## ⚠️ Importante

- El script automático **SÍ marca emails como leídos** (usa `procesar_pedidos_auto`)
- Para testing manual, usa `procesar_pedidos_email --no-marcar-leido`
- El sistema detecta duplicados automáticamente
- Los logs se guardan en `logs/procesar_pedidos.log`

---

## 🧪 Testing

**Probar ejecución manual:**
```batch
cd C:\Dev\GitHub\gestion_servicio
procesar_pedidos_auto.bat
```

**Verificar que funciona:**
1. Envía email de prueba a solicitudestudioscolegiales@gmail.com
2. Espera 5 minutos (o ejecuta manualmente)
3. Verifica en Django admin que se creó el pedido
4. El email debe aparecer como leído en Gmail
