# 💰 Costos y Límites del Sistema

> Actualizado: 13 de febrero de 2026

Esta guía explica todos los costos asociados al sistema de pedidos de estudios médicos, límites de las APIs gratuitas, y recomendaciones de escalado.

---

## 📋 Resumen Ejecutivo

| Servicio | Plan | Costo Mensual | Límites |
|----------|------|---------------|---------|
| Gmail API | Gratuito | **$0** | 1B unidades/día ✅ |
| Google Cloud Console | Gratuito | **$0** | Proyecto + OAuth |
| Windows Task Scheduler | Gratuito | **$0** | Desarrollo local |
| SendGrid (Free) | Gratuito | **$0** | 100 emails/día |
| Heroku Hobby Dyno | Pagado | **~$7 USD** | Producción |
| SendGrid Essentials | Pagado | **~$15 USD** | 40,000 emails/mes |

**Para un sanatorio con 50-200 pedidos/día:**
- **Desarrollo local**: $0/mes
- **Producción básica**: $7/mes
- **Alto volumen**: $22/mes

---

## 🔍 Análisis Detallado

### 1. Gmail API ✅ GRATUITO

**Cuota gratuita diaria**: 1,000,000,000 de unidades

#### Costo de Operaciones
| Operación | Unidades | Llamadas en ~1,000,000 |
|-----------|----------|------------------------|
| `gmail.users.messages.list` | 5 | 200,000,000 |
| `gmail.users.messages.get` | 5 | 200,000,000 |
| `gmail.users.messages.modify` | 5 | 200,000,000 |
| `gmail.users.messages.attachments.get` | 5 | 200,000,000 |

#### Tu Uso Estimado (Sanatorio Colegiales)

**Escenario conservador**: 100 emails/día
```
Operaciones por email:
- Listar emails nuevos:    5 unidades × 1 llamada  = 5
- Obtener email completo:   5 unidades × 1 llamada  = 5
- Descargar 2 adjuntos:     5 unidades × 2 llamadas = 10
- Marcar como leído:        5 unidades × 1 llamada  = 5
                                          TOTAL por email = 25 unidades

100 emails/día × 25 unidades = 2,500 unidades/día
```

**Escenario alto**: 500 emails/día
```
500 emails/día × 25 unidades = 12,500 unidades/día
```

**Tu margen de seguridad**: 
- Límite: 1,000,000,000 unidades/día
- Uso estimado: 2,500 - 12,500 unidades/día
- **Estás usando el 0.00125% del límite** ✅

#### Límites Adicionales
- **Requiere verificación de Google**: Solo si superas 100 usuarios
- **Refresh token válido**: 6 meses sin uso (se renueva automáticamente con uso)
- **Rate limiting**: 25,000 unidades/usuario/segundo (amplio para tu caso)

**Conclusión**: ✅ **Gmail API es 100% gratuito para tu uso**

---

### 2. Google Cloud Platform ✅ GRATUITO

#### Proyecto de Google Cloud
- **Costo**: $0
- **Límites**: 
  - Proyectos por cuenta: Ilimitados
  - APIs habilitadas por proyecto: Ilimitadas
  - Credenciales OAuth: 100 por proyecto

#### OAuth 2.0
- **Costo**: $0
- **Límites de autenticación**: Ninguno relevante
- **Verificación de app**: 
  - No requerida para uso interno (tipo "Externo" con usuarios de prueba)
  - Requerida solo si publicas la app para más de 100 usuarios

#### Almacenamiento
- Credenciales (`credentials.json`, `token.json`): Archivos locales, sin costo de Google

**Conclusión**: ✅ **Google Cloud es 100% gratuito para este proyecto**

---

### 3. Hosting y Ejecución

#### Opción A: Desarrollo Local (Windows) ✅ GRATUITO

**Windows Task Scheduler**:
- Costo: $0
- Límites: Ninguno
- Ventajas:
  - Sin costo adicional
  - Control total
  - Sin dependencias externas
- Desventajas:
  - PC debe estar encendida
  - No accesible remotamente
  - Backups manuales

**Recomendado para**: Testing, desarrollo, uso por tiempo limitado

#### Opción B: Heroku 💵 PAGADO

**Heroku Hobby Dyno**:
- Costo: **$7 USD/mes**
- Características:
  - Always-on (24/7)
  - 512 MB RAM
  - Sin límite de horas
  - Certificado SSL incluido
  
**Heroku Scheduler (add-on)**:
- Costo: **$0** (incluido con dyno pagado)
- Límites:
  - Jobs programados: Ilimitados
  - Frecuencia mínima: Cada 10 minutos

**Costo total Heroku**: ~$7 USD/mes

**Recomendado para**: Producción, uso continuo, acceso remoto

#### Opción C: VPS (DigitalOcean, AWS, Azure)
- Costo: desde $5-10 USD/mes
- Mayor control y recursos
- Requiere más configuración

---

### 4. Notificaciones por Email

#### SendGrid Free ✅ GRATUITO

**Límites del plan gratuito**:
- **100 emails/día** (3,000/mes)
- Validación de dominio opcional
- No caduca

**Tu uso estimado**:
```
Escenario conservador: 50 pedidos/día
- 1 notificación por pedido = 50 emails/día
✅ Dentro del límite gratuito

Escenario alto: 100 pedidos/día
- 1 notificación inicial + 1 de cambio estado = 200 emails/día
❌ Excede límite gratuito
```

#### SendGrid Essentials 💵 PAGADO

Si necesitas más de 100 emails/día:
- Costo: **$14.95 USD/mes**
- Límites: 40,000 emails/mes (~1,333/día)
- Soporte técnico incluido

#### Alternativas Gratuitas
1. **Mailgun**: 5,000 emails/mes gratuitos (válido 3 meses)
2. **Gmail SMTP directo**: 500 emails/día (tu cuenta de Gmail)
3. **Amazon SES**: $0.10 por 1,000 emails (muy barato)

**Recomendación**: 
- Empezar con SendGrid Free
- Monitorear uso
- Escalar a Essentials si es necesario

---

### 5. Base de Datos

#### SQLite (Local) ✅ GRATUITO
- Incluida en Python
- Sin límites para este uso
- Archivos locales

#### PostgreSQL (Heroku) ✅ GRATUITO (con límites)
- Heroku Postgres Hobby Dev: **$0**
- Límites:
  - 10,000 filas
  - Sin backups automáticos
  - Conexiones limitadas

**Si superas 10,000 pedidos**:
- Heroku Postgres Hobby Basic: **$9 USD/mes**
  - 10,000,000 filas
  - Backups automáticos

---

## 📊 Escenarios Reales para Sanatorio Colegiales

### Escenario 1: Período de Prueba (1-3 meses)
```
Objetivo: Probar el sistema, ajustar parser, entrenar al personal

Configuración:
✅ Gmail API (gratuito)
✅ Google Cloud (gratuito)
✅ Desarrollo local con Task Scheduler (gratuito)
✅ SendGrid Free - 100 emails/día (gratuito)
✅ SQLite (gratuito)

Costo total: $0/mes

Limitaciones:
- PC debe estar encendida
- Hasta 100 notificaciones/día
- No accesible remotamente
```

### Escenario 2: Producción Básica
```
Objetivo: Sistema en producción, accesible 24/7

Configuración:
✅ Gmail API (gratuito)
✅ Google Cloud (gratuito)
💵 Heroku Hobby Dyno ($7/mes)
✅ SendGrid Free - 100 emails/día (gratuito)
✅ Heroku Postgres Hobby Dev (gratuito, <10k pedidos)

Costo total: ~$7 USD/mes

Limitaciones:
- Hasta 100 notificaciones/día
- Hasta 10,000 pedidos totales en DB
```

### Escenario 3: Alto Volumen
```
Objetivo: Más de 100 notificaciones/día, backups automáticos

Configuración:
✅ Gmail API (gratuito)
✅ Google Cloud (gratuito)
💵 Heroku Hobby Dyno ($7/mes)
💵 SendGrid Essentials ($15/mes)
💵 Heroku Postgres Hobby Basic ($9/mes)

Costo total: ~$31 USD/mes

Sin limitaciones relevantes para sanatorio mediano
```

---

## 📈 Proyección de Costos por Volumen

| Pedidos/Día | Notificaciones/Día | Config Recomendada | Costo/Mes |
|-------------|-------------------|-------------------|-----------|
| 10-30 | 10-60 | Local + SendGrid Free | **$0** |
| 30-80 | 60-160 | Heroku + SendGrid Free | **$7** |
| 80-200 | 160-400 | Heroku + SendGrid Essentials | **$22** |
| 200-500 | 400-1000 | Heroku + SendGrid + Postgres | **$31** |
| 500+ | 1000+ | Escalar a Professional | **$50+** |

---

## 🎯 Recomendación Final

### Fase 1: Implementación (Mes 1-2)
**Costo**: $0/mes
- Desarrollo local
- Ajustar parser con emails reales
- Entrenar al personal
- Validar precisión

### Fase 2: Producción Inicial (Mes 3-6)
**Costo**: $7/mes
- Heroku Hobby
- SendGrid Free (si <100 notif/día)
- Monitorear uso y precisión

### Fase 3: Escalar Según Necesidad
- Si superas 100 emails/día → SendGrid Essentials (+$15/mes)
- Si superas 10k pedidos → Postgres Basic (+$9/mes)
- Si necesitas más recursos → Heroku Standard (+$25-50/mes)

---

## 🔔 Alertas y Monitoreo

### Configurar Alertas en Google Cloud Console

1. **Ir a**: APIs y servicios > Panel de control
2. **Seleccionar**: Gmail API
3. **Ver**: Cuotas y límites
4. **Configurar alerta**: Si uso > 50% del límite diario

### Monitorear SendGrid

En el dashboard de SendGrid:
- Ver emails enviados/día
- Ver tasa de entrega
- Alertas si te acercas al límite del plan

### Queries para Estadísticas

```python
# Django shell
from pedidos_estudios.models import PedidoEstudio, LogProcesamientoEmail
from django.utils import timezone
from datetime import timedelta

# Pedidos del último mes
ultimo_mes = timezone.now() - timedelta(days=30)
pedidos_mes = PedidoEstudio.objects.filter(fecha_recepcion__gte=ultimo_mes).count()
print(f"Pedidos procesados (último mes): {pedidos_mes}")
print(f"Promedio diario: {pedidos_mes/30:.1f}")

# Notificaciones enviadas
notificaciones = PedidoEstudio.objects.filter(
    fecha_recepcion__gte=ultimo_mes,
    notificacion_enviada=True
).count()
print(f"Notificaciones enviadas: {notificaciones}")
print(f"Promedio diario: {notificaciones/30:.1f}")

# Proyección de costos
if notificaciones/30 > 100:
    print("⚠️ Considerar SendGrid Essentials ($15/mes)")
if pedidos_mes > 8000:
    print("⚠️ Pronto superarás 10k pedidos, considerar Postgres Basic ($9/mes)")
```

---

## ❓ FAQ sobre Costos

### ¿Gmail API realmente es gratis?
**Sí**, para tu volumen de uso. Los límites gratuitos son extremadamente generosos. Solo pagarías si fueras una empresa procesando millones de emails/día.

### ¿Qué pasa si supero los límites gratuitos?
- **Gmail API**: Muy difícil de superar. Si lo haces, Google te contactará.
- **SendGrid Free**: Los emails adicionales simplemente no se envían. Necesitas upgrade.

### ¿Puedo usar solo componentes gratuitos?
**Sí**, absolutamente. Si ejecutas en local con Task Scheduler y envías <100 notificaciones/día, todo es gratuito.

### ¿Heroku es obligatorio?
**No**. Heroku es solo una opción para hosting 24/7. Puedes usar:
- PC local con Task Scheduler (gratis)
- VPS propio (desde $5/mes)
- Servidor del sanatorio (si tienen)

### ¿Hay cargos ocultos?
**No**. Los únicos costos son:
1. Hosting (opcional: Heroku $7/mes o VPS $5-10/mes)
2. Notificaciones si >100/día (SendGrid $15/mes)
3. Base de datos si >10k pedidos (Heroku Postgres $9/mes)

### ¿Qué pasa con el costo de mi internet/PC?
Esos son costos de infraestructura que ya tienes. El sistema usa recursos mínimos:
- CPU: <1% cuando no procesa
- RAM: ~50-100 MB
- Ancho de banda: ~1-5 MB/día

---

## 📞 Soporte y Recursos

### Documentación Oficial
- [Gmail API Pricing](https://developers.google.com/gmail/api/v1/reference/quota)
- [Heroku Pricing](https://www.heroku.com/pricing)
- [SendGrid Pricing](https://sendgrid.com/pricing/)

### Contacto
- **Desarrollador**: Eduardo Cejas
- **Email**: ecejas@sanatoriocolegiales.com.ar

---

**Última actualización**: 13 de febrero de 2026

**Resumen**: Para Sanatorio Colegiales con volumen normal de estudios, el costo será de **$0-7 USD/mes** dependiendo si usas hosting local o en la nube. Gmail API y Google Cloud son 100% gratuitos para este uso.
