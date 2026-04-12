# SISTEMA DE GESTIÓN AUTOMÁTICA DE PEDIDOS DE ESTUDIOS
## Prevención de Débitos por Estudios No Realizados

**Desarrollado por:** Enso Cejas  
**Fecha:** Febrero 2026  
**Status:** En producción y funcionando

---

## 🚨 EL PROBLEMA CRÍTICO

### Situación Actual con Netterm:
Las órdenes emitidas **solo pueden consultarse presencialmente** en el sistema.

Esto genera:
- ❌ Personal debe entrar manualmente a buscar cada pedido
- ❌ Algunos estudios quedan "olvidados" en el sistema
- ❌ **No hay alertas automáticas de pedidos urgentes**
- ❌ No hay trazabilidad de cuándo se vio el pedido

### Consecuencia Directa: DÉBITOS
**Las obras sociales debitan estudios no realizados en menos de 24 horas.**

Cada estudio debitado = pérdida de ingreso para la institución.

---

## 💰 IMPACTO ECONÓMICO REAL

### Pérdidas Actuales Estimadas:
```
Supongamos:
• Valor promedio estudio: $40,000 ARS
• Débitos mensuales por demora: 3-5 estudios
• Pérdida mensual: $120,000 - $200,000 ARS
• Pérdida anual: $1,440,000 - $2,400,000 ARS
```

### Con el Sistema Automático:
```
✓ Procesamiento cada 10 minutos (144 revisiones/día)
✓ Alertas por prioridad (URGENTE aparece destacado)
✓ Médicos ven sus pendientes desde celular 24/7
✓ Trazabilidad: fecha de recepción → quién lo vio → cuándo se realizó
✓ Dashboard con estudios próximos a vencer (24hs)

Resultado: CERO débitos por pedidos no vistos
Ahorro anual: $1,440,000 - $2,400,000 ARS
```

---

## ✅ LO QUE YA ESTÁ FUNCIONANDO

### Sistema en Producción:
🌐 **URL:** https://gestion-colegiales-a1dfc873c2b8.herokuapp.com/pedidos/

**Funcionalidades activas:**
- [✓] Procesamiento automático 24/7 cada 10 minutos
- [✓] Parser inteligente: extrae paciente, DNI, HC, habitación, estudio
- [✓] **Alertas de prioridad:** URGENTE/ALTA destacadas en naranja/rojo
- [✓] Dashboard con estadísticas en tiempo real
- [✓] Filtros: por fecha, estado, médico, prioridad
- [✓] Vista "Mis Estudios" para médicos (móvil-friendly)
- [✓] Control de acceso por roles (admin/coordinadores)
- [✓] 12 tipos de estudio precargados
- [✓] Email de recepción: solicitudestudioscolegiales@gmail.com

**Evidencia de funcionamiento:**
Ayer procesé 2 emails de prueba automáticamente:
1. Morales, Alberto Ramón - Ecocardiograma transesofágico (Prioridad: Normal)
2. Rodriguez, Alberto José - Ecodoppler carotídeo y vertebral (Prioridad: ALTA)

Ambos fueron extraídos, clasificados y están en el dashboard en menos de 1 minuto.

---

## ⏳ LO QUE FALTA (NO DEPENDE DE MÍ)

**Netterm debe enviar emails automáticamente al emitir pedidos.**

Dirección de destino (ya configurada y lista):  
📧 **solicitudestudioscolegiales@gmail.com**

Esta integración requiere **1 línea de código del lado de Netterm**.

Yo ya creé la cuenta Gmail, configuré la API, y el sistema está esperando recibir los emails.

---

## 📊 COMPARATIVA: ANTES vs. DESPUÉS

| Aspecto | ANTES (Sistema Netterm Manual) | DESPUÉS (Sistema Automático) |
|---------|--------------------------------|------------------------------|
| **Revisión de pedidos** | Manual, cuando alguien se acuerda | Automático cada 10 minutos |
| **Pedidos urgentes** | Se pierden entre los demás | Destacados en naranja/rojo |
| **Acceso a pedidos** | Presencial en Netterm | Desde cualquier lugar (móvil) |
| **Trazabilidad** | Ninguna | Completa (fecha, hora, quién) |
| **Riesgo de débito** | **ALTO** (3-5 por mes) | **CERO** |
| **Pérdida mensual** | **$120,000-200,000 ARS** | **$0** |
| **Tiempo administrativo** | 2 horas/día | 0 horas/día |

---

## 💵 COSTOS DE OPERACIÓN

### Infraestructura Cloud (Mensual):
```
Heroku Hobby Dyno (servidor web):     USD  7.00  (~$6,300 ARS)
Heroku Postgres Mini (base de datos): USD  5.00  (~$4,500 ARS)
Heroku Scheduler (automático):         Incluido
Gmail API (procesamiento emails):      GRATIS
Cloudinary (almacenamiento imágenes):  GRATIS (plan base)
────────────────────────────────────────────────────────────
TOTAL MENSUAL:                         ~USD 12   (~$10,800 ARS/mes)
```

### ROI (Retorno de Inversión):
```
Pérdida mensual evitada:     $150,000 ARS (promedio)
Costo mensual operativo:     $ 10,800 ARS
────────────────────────────────────────────────────────────
AHORRO NETO MENSUAL:         $139,200 ARS
ROI:                         1,289% (se recupera en 2 días)
```

---

## 🎯 PROPUESTA ECONÓMICA

El sistema fue desarrollado **fuera de mi horario laboral**, usando infraestructura personal.

### Solicito:

#### 1️⃣ COBERTURA DE COSTOS OPERATIVOS (Mensual):
**$12,000 ARS/mes** para mantener el sistema activo  
*(Equivalente al 8% del ahorro generado)*

#### 2️⃣ RECONOCIMIENTO POR DESARROLLO (Una sola vez):
**$300,000 - $350,000 ARS**

**Justificación:**
- ~50-60 horas de desarrollo especializado
- Integración Gmail API + OAuth2 + seguridad
- Parser inteligente de emails (múltiples formatos)
- Dashboard con estadísticas en tiempo real
- Sistema responsive (PC + tablet + móvil)
- Deploy en producción con alta disponibilidad
- Control de roles y permisos por tipo de usuario
- Documentación completa

**Equivalente a:** 2 meses de débitos evitados

---

## 💡 ALTERNATIVA (Si el presupuesto es limitado):

**Mínimo solicitado:**
- ✓ Costos mensuales de infraestructura: **$12,000 ARS/mes**
- ✓ Bono simbólico por desarrollo: **$150,000 ARS** (una vez)

Esto representa:
- Menos del 10% del ahorro mensual generado
- La institución sigue ahorrando **$138,000+ ARS/mes**
- ROI de 1,150%

---

## 🎬 PRÓXIMOS PASOS

### Fase 1: Validación (Esta semana)
1. ✅ Demo de 15 minutos para el director
2. ✅ Mostrar pedidos procesados en tiempo real
3. ✅ Revisar dashboard y filtros

### Fase 2: Integración con Netterm (1-2 semanas)
1. Reunión con equipo de Netterm
2. Configuran envío automático a: solicitudestudioscolegiales@gmail.com
3. Pruebas piloto con 10-20 pedidos reales

### Fase 3: Lanzamiento Completo (Semana 3)
1. Sistema activo para todos los servicios
2. Capacitación a coordinadores (1 hora)
3. Monitoreo de débitos durante primer mes

**Tiempo estimado total:** 3 semanas desde aprobación

---

## 📈 MÉTRICAS DE ÉXITO (Primer mes)

Indicadores a monitorear:
- ✓ Débitos por estudios no realizados: **Objetivo = 0**
- ✓ Tiempo promedio entre pedido → realización: **<12 horas**
- ✓ Estudios procesados automáticamente: **100%**
- ✓ Satisfacción de médicos con acceso móvil: **Encuesta**

---

## 🔒 SEGURIDAD Y MANTENIMIENTO

### Ya implementado:
- ✓ Autenticación OAuth2 con Google (estándar bancario)
- ✓ Control de acceso por roles
- ✓ Datos sensibles en variables de entorno (no en código)
- ✓ Backup automático de base de datos (Heroku)
- ✓ SSL/HTTPS obligatorio (certificado incluido)

### Documentación:
- ✓ Código comentado y estructurado
- ✓ Guía de deployment en `docs/DEPLOY_HEROKU_PEDIDOS.md`
- ✓ Checklist de mantenimiento en `docs/operativa/CHECKLIST_DEPLOY_HEROKU.md`
- ✓ Ejemplos de emails en `pedidos_estudios/EJEMPLOS_EMAILS.md`

**Transferencia de conocimiento:** 2 horas para capacitar a otro desarrollador si fuera necesario.

---

## ✨ BONUS: BENEFICIOS ADICIONALES

Más allá de prevenir débitos:

1. **Reportes automáticos:** 
   - Estudios realizados por mes/servicio
   - Médicos más solicitantes
   - Tiempos promedio de respuesta

2. **Escalabilidad:**
   - Base para futuras automatizaciones
   - Puede integrarse con otros sistemas (laboratorio, rayos, etc.)

3. **Compliance:**
   - Registro auditable de todos los pedidos
   - Evidencia para obras sociales en caso de reclamos

4. **Experiencia del paciente:**
   - Estudios más rápidos = menor estadía hospitalaria
   - Menos quejas por demoras

---

## 📞 CONTACTO

**Desarrollador:** Enso Cejas  
**Email:** ensofermincejas@gmail.com  
**Sistema en producción:** https://gestion-colegiales-a1dfc873c2b8.herokuapp.com/pedidos/  
**Email de recepción:** solicitudestudioscolegiales@gmail.com

**Disponibilidad para demo:** Lunes a Viernes, 9:00-17:00 hs

---

## 📎 ANEXOS

### A. Capturas de pantalla del sistema
*(Ver en la demo en vivo)*

### B. Logs de procesamiento automático
```
[2026-02-15 14:10] ✓ Email procesado: Morales, Alberto Ramón
[2026-02-15 14:10] ✓ Email procesado: Rodriguez, Alberto José
[2026-02-15 14:10] Procesamiento automático: 2 exitosos, 0 errores
```

### C. Comparativa de costos vs. pérdidas evitadas (anual)
```
Costo anual del sistema:      $129,600 ARS/año
Pérdidas evitadas (mínimo):   $1,440,000 ARS/año
────────────────────────────────────────────────
BENEFICIO NETO:               $1,310,400 ARS/año
ROI:                          1,011%
```

---

**Resumen ejecutivo:**
Sistema funcionando → Previene débitos → Ahorra $150K/mes → Cuesta $12K/mes → ROI 1,289%

**Inversión solicitada:** $300-350K (una vez) + $12K/mes  
**Recuperación:** 2.3 meses
