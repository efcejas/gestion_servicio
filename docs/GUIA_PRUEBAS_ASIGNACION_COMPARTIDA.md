# 🧪 Guía de Pruebas - Sistema de Asignación Compartida

## 📋 Datos de Prueba Creados

### 👥 Usuarios Disponibles

| Usuario | Contraseña | Rol | Nombre |
|---------|-----------|-----|--------|
| `test_residente1` | `test123` | Residente | Juan Pérez |
| `test_residente2` | `test123` | Residente | María González |
| `test_residente3` | `test123` | Residente | Carlos Rodríguez |
| `test_jefe1` | `test123` | Jefe de Residentes | Laura Martínez |
| `test_jefe2` | `test123` | Jefe de Residentes | Roberto Sánchez |
| `test_instructor1` | `test123` | Instructor | Ana López |
| `test_staff1` | `test123` | Staff | Pedro Fernández |

### 📝 Preinformes de Prueba

| Número | Estado | Tipo | Revisor | Notas |
|--------|--------|------|---------|-------|
| TEST-2026-001 | Borrador | Normal | - | Para editar |
| TEST-2026-002 | Borrador | Normal | - | Para editar |
| **TEST-2026-003** | **Pendiente** | **🟣 Compartido** | - | **En pool compartido** |
| **TEST-2026-004** | **Pendiente** | **🟣 Compartido** | - | **En pool compartido** |
| **TEST-2026-005** | **Pendiente** | **🟣 Compartido** | - | **En pool compartido** |
| TEST-2026-006 | Pendiente | Normal | Laura Martínez | Asignado específico |
| TEST-2026-007 | Pendiente | Normal | Pedro Fernández | Asignado específico |
| TEST-2026-008 | Pendiente | Normal | - | Sin asignar |
| TEST-2026-009 | En Revisión | Normal | Laura Martínez | Ya en revisión |
| TEST-2026-010 | Finalizado | Normal | Pedro Fernández | Revisado |

---

## 🎯 Escenarios de Prueba

### 1️⃣ Como Residente: Crear Preinforme con Asignación Compartida

1. **Login:** `test_residente1` / `test123`
2. **Ir a:** Dashboard de Preinformes → "Nuevo Preinforme"
3. **Completar datos:**
   - Número de estudio: `TEST-2026-011`
   - Tipo: Ecocardiograma Transtorácico
   - Región: Cardíaco
   - Datos del paciente
   - Contenido del informe
4. **Marcar checkbox:** ✅ "Pool compartido"
5. **Verificar:** El campo "Asignar a revisor" debe estar deshabilitado
6. **Guardar y enviar para revisión**

**Resultado esperado:** El preinforme queda en pool compartido (sin revisor asignado).

---

### 2️⃣ Como Jefe: Ver Pool Compartido

1. **Login:** `test_jefe1` / `test123`
2. **Ir a:** Lista de Revisión
3. **Click en tab:** "🟣 Pool Compartido"
4. **Verificar:** Debes ver 3 estudios (TEST-2026-003, 004, 005)
5. **Observar:** Badge "Compartido" en cada estudio

**Resultado esperado:** Lista de estudios compartidos disponibles para tomar.

---

### 3️⃣ Como Jefe: Tomar Estudio del Pool

1. **Login:** `test_jefe1` / `test123`
2. **Ir a:** Lista de Revisión → Tab "Pool Compartido"
3. **Seleccionar:** TEST-2026-003
4. **Click:** Botón "🤚 Tomar este estudio"
5. **Resultado:** Te redirige automáticamente a la vista de revisión del estudio

**Resultado esperado:** 
- El estudio se te asigna automáticamente
- Desaparece del pool compartido
- Aparece en tu lista de "Mis Asignados"

---

### 4️⃣ Como Otro Jefe: Verificar que No Ve el Estudio Tomado

1. **Login:** `test_jefe2` / `test123`
2. **Ir a:** Lista de Revisión → Tab "Pool Compartido"
3. **Verificar:** Ya NO ves TEST-2026-003 (lo tomó test_jefe1)
4. **Verificar:** Aún ves TEST-2026-004 y TEST-2026-005

**Resultado esperado:** Solo ves estudios aún disponibles en el pool.

---

### 5️⃣ Probar Race Condition (¡avanzado!)

**Objetivo:** Verificar que dos jefes no pueden tomar el mismo estudio simultáneamente.

1. **Abrir dos navegadores/pestañas**
2. **Login simultáneo:** 
   - Navegador 1: `test_jefe1` / `test123`
   - Navegador 2: `test_jefe2` / `test123`
3. **Ambos:** Ir a Pool Compartido
4. **Ambos:** Ver TEST-2026-004
5. **Hacer click casi al mismo tiempo:** Botón "Tomar" en TEST-2026-004

**Resultado esperado:** 
- Uno lo toma exitosamente
- El otro recibe mensaje: "Este estudio no está disponible para tomar"

---

### 6️⃣ Como Residente: Intentar Asignar Revisor + Pool Compartido

1. **Login:** `test_residente1` / `test123`
2. **Crear nuevo preinforme**
3. **Intentar:** 
   - Seleccionar revisor específico
   - Marcar checkbox "Pool compartido"
4. **Enviar formulario**

**Resultado esperado:** Error de validación:
> "No puedes asignar a un revisor específico si el estudio está en pool compartido."

---

### 7️⃣ Como Staff: Verificar que NO Ve Estudios Compartidos

**Objetivo:** Confirmar que el staff médico no puede ver estudios del pool compartido.

1. **Login:** `test_staff1` / `test123`
2. **Ir a:** Lista de Revisión
3. **Verificar tabs disponibles:**
   - ✅ "Mis Asignados" (visible)
   - ✅ "Sin Asignar" (visible)
   - ❌ "Pool Compartido" (NO debe aparecer)
   - ✅ "Todos" (visible)
   
4. **Click en "Todos"**
5. **Verificar:** NO debes ver TEST-2026-003, 004, ni 005 (estudios compartidos)
6. **Verificar:** SÍ ves TEST-2026-007 (asignado a ti) y TEST-2026-008 (sin asignar, no compartido)

**Resultado esperado:** 
- Staff no tiene acceso al tab "Pool Compartido"
- Staff no ve estudios compartidos en ningún filtro
- Staff solo ve: estudios asignados a él + estudios sin asignar tradicionales

---

## 🔍 Verificaciones Adicionales

### Ver estudios como Residente
- **Login:** `test_residente1`
- **Ir a:** "Mis Preinformes"
- **Verificar:** Ves tus propios preinformes con diferentes estados

### Ver estudios asignados normalmente
- **Login:** `test_jefe1`
- **Tab:** "Mis Asignados"
- **Verificar:** TEST-2026-006 (asignado directamente) y cualquier otro que hayas tomado

### Ver estudios sin asignar (tradicional)
- **Login:** `test_staff1`
- **Tab:** "Sin Asignar"
- **Verificar:** TEST-2026-008 (no compartido, sin revisor) aparece aquí
- **NO debe aparecer:** TEST-2026-003, 004, 005 (son compartidos, exclusivos para jefes/instructores)

### Verificar aislamiento del pool compartido
- **Login:** `test_staff1`
- **Tab:** "Todos"
- **Verificar:** Solo ves estudios asignados a ti + estudios sin asignar NO compartidos
- **NO debes ver:** Ningún estudio con badge "🟣 Compartido"

---

## 🧹 Limpiar Datos de Prueba

Si quieres resetear los datos de prueba:

```bash
python manage.py crear_datos_prueba_asignacion --reset
```

Esto eliminará todos los usuarios y preinformes de prueba, y los volverá a crear desde cero.

---

## 🐛 Problemas Comunes

### "No veo el tab Pool Compartido"
- Solo es visible para usuarios con rol `jefe_residentes` o `instructor_residentes`
- Verifica que estás logueado con `test_jefe1` o `test_instructor1`

### "El checkbox Pool Compartido no deshabilita el campo Revisor"
- Asegúrate de que JavaScript está habilitado en tu navegador
- Revisa la consola del navegador por errores de JS

### "Puedo ver estudios que ya fueron tomados"
- Refresca la página (F5)
- Verifica que estás en el tab correcto

---

## 📊 Estados de Preinformes

- **Borrador:** Aún no enviado para revisión
- **Pendiente Revisión:** Enviado, esperando que alguien lo tome
- **En Revisión:** Un revisor lo está trabajando
- **Finalizado:** Revisión completada

---

¡Listo para probar! 🚀
