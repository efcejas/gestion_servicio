# 📧 Guía de Comandos - Procesamiento de Emails

## 🧪 Desarrollo / Testing

Usa este comando cuando estés probando o desarrollando:

```bash
python manage.py procesar_pedidos_email --max-emails=5 --no-marcar-leido
```

**Características:**
- ❌ **NO marca** emails como leídos
- 🔄 Permite reprocesar los mismos emails
- 📊 Muestra output detallado
- ✅ Perfecto para testing y desarrollo

---

## 🚀 Producción / Automatizado

Usa este comando para la ejecución automática (Task Scheduler/Cron):

```bash
python manage.py procesar_pedidos_auto --max-emails=10
```

**Características:**
- ✅ **SÍ marca** emails como leídos automáticamente
- 🚫 Previene duplicados
- 📝 Logging estructurado para monitoreo
- 🔕 Output resumido (--silent para modo silencioso)
- 🎯 Optimizado para scheduler

---

## 📋 Comparación

| Característica | procesar_pedidos_email | procesar_pedidos_auto |
|----------------|------------------------|------------------------|
| **Marcar como leído** | Solo con flag explícito | ✅ Siempre |
| **Uso recomendado** | Desarrollo, testing | Producción, cron |
| **Output** | Detallado | Resumido |
| **Logging** | Console | Structured logs |
| **Duplicados** | Detecta pero no marca | Detecta y marca |

---

## 🔍 Verificar Estado de Emails

### Ver emails sin procesar:
```python
python manage.py shell

from pedidos_estudios.services.gmail_service import GmailService
gmail = GmailService()
emails = gmail.obtener_emails_nuevos(query='is:unread', max_results=10)
print(f"Emails sin leer: {len(emails)}")
```

### Ver último procesamiento:
```python
python manage.py shell

from pedidos_estudios.models import LogProcesamientoEmail
ultimo = LogProcesamientoEmail.objects.latest('fecha_procesamiento')
print(f"Último: {ultimo.fecha_procesamiento}")
print(f"Exitoso: {ultimo.exitoso}")
```

---

## ⚙️ Flags Disponibles

### procesar_pedidos_email:
- `--max-emails N`: Procesar máximo N emails (default: 10)
- `--no-marcar-leido`: NO marcar como leídos (útil para testing)
- `--desde-fecha YYYY-MM-DD`: Procesar desde fecha específica

### procesar_pedidos_auto:
- `--max-emails N`: Procesar máximo N emails (default: 10)
- `--silent`: Modo silencioso (solo errores)

---

## 🎯 Casos de Uso

**Durante desarrollo:**
```bash
# Procesar sin marcar como leído (puedes reprocesar)
python manage.py procesar_pedidos_email --max-emails=1 --no-marcar-leido
```

**Testing de producción:**
```bash
# Procesar marcando como leído
python manage.py procesar_pedidos_email --max-emails=5
```

**Configuración automática (Task Scheduler):**
```bash
# Ejecutar cada 5 minutos via scheduler
python manage.py procesar_pedidos_auto --max-emails=10
```

**Monitoreo silencioso:**
```bash
# Para cron jobs que solo registran errores
python manage.py procesar_pedidos_auto --max-emails=20 --silent
```

**Procesar emails antiguos:**
```bash
# Desde una fecha específica
python manage.py procesar_pedidos_email --desde-fecha 2026-02-01
```

---

## 🚨 Importante

⚠️ **En producción, SIEMPRE usa `procesar_pedidos_auto`**  
Esto asegura que:
- Los emails procesados se marcan como leídos
- No se crean duplicados innecesarios
- El sistema mantiene el estado consistente

⚠️ **Para testing, usa `--no-marcar-leido`**  
Evita tener que reenviar emails para testing.
