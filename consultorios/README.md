# 🏥 Consultorios - Guía de Inicio Rápido

## ✅ FASE 1 COMPLETADA

### ¿Qué puedes hacer ahora?

#### 1. Acceder al Panel de Administración
```
http://localhost:8000/admin/
```

#### 2. Gestionar Consultorios
- **Ruta:** Admin → Consultorios → Consultorios
- **Crear nuevo:** Clic en "Agregar Consultorio"
- **Campos obligatorios:** Nombre
- **Campos opcionales:** Ubicación, capacidad, observaciones

#### 3. Registrar Profesionales Externos
- **Ruta:** Admin → Consultorios → Profesionales Externos
- **Para qué:** Médicos que trabajan en tus consultorios pero no necesitan cuenta de usuario
- **Campos obligatorios:** Nombre, Apellido, Matrícula (única)
- **Campos opcionales:** Especialidad, teléfono, email

#### 4. Asignar Equipos a Consultorios
- **Ruta:** Admin → Consultorios → Asignaciones Equipo-Consultorio
- **Prerequisito:** Tener equipos creados en Admin → Equipos
- **Tipos de asignación:**
  - **Permanente:** Marca el checkbox "Es permanente"
  - **Temporal:** Deja desmarcado y especifica fecha_fin

#### 5. Crear Bloques Horarios
- **Ruta:** Admin → Consultorios → Bloques Horarios
- **Profesionales:**
  - **Interno:** Selecciona un usuario del sistema
  - **Externo:** Selecciona un profesional externo
  - ⚠️ **IMPORTANTE:** Solo puedes elegir UNO (interno O externo)
- **Horarios:** Día de semana + hora inicio/fin
- **Tipo de actividad:** Eco General, Doppler, Obstétrica, etc.
- **Estado:** Activo (por defecto)

---

## 🎯 Ejemplos de Uso

### Ejemplo 1: Consultorio Simple
```
1. Crear consultorio "Eco 1"
2. Asignar ecógrafo GE permanentemente
3. Crear bloque: Lunes 8:00-12:00, Dr. Interno (usuario del sistema)
```

### Ejemplo 2: Profesional Externo
```
1. Crear profesional externo: Dr. Juan Pérez, Mat. 12345
2. Crear bloque: Martes 14:00-18:00, Dr. Juan Pérez (externo)
```

### Ejemplo 3: Rotación de Equipos
```
1. Asignar ecógrafo temporalmente: del 16/01 al 31/01
2. Automáticamente se marca como no vigente después del 31/01
```

---

## 🔍 Características Implementadas

✅ **Consultorios:** CRUD completo, estado activo/inactivo  
✅ **Profesionales Externos:** Gestión de médicos sin cuenta de usuario  
✅ **Asignación de Equipos:** Permanente o temporal con fechas  
✅ **Bloques Horarios:** Franjas semanales con múltiples configuraciones  
✅ **Validaciones:** Horarios, profesionales, equipos  
✅ **Admin Personalizado:** Vistas visuales, filtros, búsquedas  
✅ **Tests:** 10 tests automatizados (100% aprobados)  

---

## 📚 Documentación Completa

Ver: `docs/SISTEMA_CONSULTORIOS.md`

---

## 🚀 Próximos Pasos

**Fase 2:** Detección de conflictos y lógica de disponibilidad  
**Fase 3:** Dashboard visual con calendario interactivo  
**Fase 4:** Automatizaciones y reportes  
**Fase 5:** Integración con otras apps del sistema  

---

## ⚠️ Notas Importantes

- **Validación estricta:** Un bloque requiere exactamente UN profesional
- **Equipos opcionales:** Puedes crear bloques sin especificar equipo
- **Vigencia:** Los bloques pueden tener vigencia indefinida
- **Estados:** Usa ACTIVO/PAUSADO/FINALIZADO según necesites

---

## 🐛 Problemas Comunes

### "Debe especificar un profesional interno O externo"
➡️ Asegúrate de seleccionar UN profesional (no dejes ambos vacíos)

### "No puede asignar ambos tipos de profesional"
➡️ Solo selecciona un profesional interno O un profesional externo, no ambos

### "Hora de inicio debe ser anterior a hora de fin"
➡️ Verifica que hora_inicio < hora_fin

### "El equipo no está asignado al consultorio"
➡️ Primero asigna el equipo al consultorio en "Asignaciones Equipo-Consultorio"

---

**Fecha:** 16 de enero de 2026  
**Versión:** Fase 1 - Modelos Base  
**Estado:** ✅ Producción Lista
