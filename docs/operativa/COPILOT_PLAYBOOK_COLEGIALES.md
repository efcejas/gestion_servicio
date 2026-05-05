# Copilot Playbook Colegiales

Guia practica para sacarle el maximo redito a Copilot en este proyecto Django medico.

## 1) Que pieza usar en cada caso

### copilot-instructions.md (base estrategica)
- Archivo: .github/copilot-instructions.md
- Para que sirve: define tu perfil, prioridades clinicas, arquitectura y estilo de trabajo.
- Cuando impacta: en todas las conversaciones dentro del repo.
- Regla practica: aca va el marco general del proyecto, no decisiones ultra especificas de un modulo.

### instructions por modulo (reglas de precision)
- Carpeta: .github/instructions/
- Ejemplo actual: control_guardias.instructions.md (applyTo control_guardias/**/*.py)
- Para que sirve: reglas no negociables por modulo (restricciones de dominio, tests, convenciones criticas).
- Cuando usar: cuando una app tiene complejidad clinica u operativa alta.

### skills (conocimiento especializado reusable)
- Carpeta: .github/skills/
- Para que sirve: empaquetar conocimiento tecnico-clinico para tareas recurrentes.
- Diferencia vs instrucciones: la instruccion manda reglas; la skill aporta contexto experto y patrones de solucion.
- Cuando conviene crear una skill: si repetis una misma explicacion o checklist 3+ veces.

### agentes especializados (ejecucion profunda)
- Carpeta: .github/agents/
- Para que sirve: derivar tareas complejas a un especialista (ej. dictado_informes, preinformes).
- Cuando conviene: bugs complejos, refactors con multiples archivos, mejoras de flujo.

### prompts de arranque (plantillas de pedido)
- Carpeta: .github/prompts/
- Para que sirve: iniciar sesiones con contexto y formato de salida consistentes.
- Beneficio: menos friccion y menos olvidos al pedir tareas importantes.

## 2) Flujo recomendado de trabajo (alto rendimiento)

1. Definir objetivo clinico-operativo en una frase.
2. Clasificar tarea por impacto/riesgo/esfuerzo.
3. Elegir modo:
   - Bajo riesgo: implementar directo.
   - Riesgo medio/alto: Architect Mode primero, codigo despues.
4. Pedir siempre validacion final:
   - tests corridos
   - riesgos remanentes
   - plan de rollback breve si toca area critica

## 3) Matriz de decision rapida

| Situacion | Herramienta principal | Resultado esperado |
|---|---|---|
| Cambio global de estilo de asistencia | copilot-instructions.md | Comportamiento consistente en todo el repo |
| Regla dura de una app (ej. guardias) | instruction applyTo | Menos errores de dominio |
| Tarea repetida con logica estable | skill | Respuestas mas precisas y rapidas |
| Problema complejo de un modulo puntual | agente especializado | Analisis y ejecucion mas profunda |
| Inicio de sesion o handoff | prompt de arranque | Pedido completo y accionable |

## 4) Como pedirle trabajo a Copilot (ejemplos)

### A. Implementacion segura en modulo critico
"Trabajemos en liquidacion. Quiero Architect Mode primero: propuesta MVP, riesgos, tests minimos, luego implementacion incremental."

### B. Mejora UX + backend coherente
"Necesito redisenar el flujo de preinformes para residente y revisor. Primero mapa de flujo y trade-offs, despues cambios minimos en views/forms/templates."

### C. Refactor guiado por capas
"Quiero mover logica de views.py a services/selectors en control_stock sin cambiar comportamiento. Mostrame diff por etapas y cobertura de tests."

## 5) Setup recomendado (VS Code + Copilot)

- Mantener activo Copilot Chat con instrucciones de workspace.
- Usar prompts de .github/prompts para iniciar tareas repetidas.
- Usar agentes especializados para modulos complejos.
- Validar cambios con tests por app antes de commit.
- En areas criticas, pedir siempre resumen de riesgos y supuestos.

## 6) Gobernanza simple para que no se degrade

Cada vez que se detecte un error repetido:
1. decidir si era falta de regla (instructions) o falta de conocimiento reusable (skill)
2. actualizar un unico lugar
3. agregar un ejemplo real

Regla de oro:
- Instructions = reglas
- Skills = conocimiento
- Agents = ejecucion especializada
- Prompts = arranque rapido

## 7) Roadmap sugerido para vos (incremental)

### Fase 1 (hoy)
- Estandarizar prompts de arranque.
- Usar agentes especializados en dictado_informes y preinformes.

### Fase 2 (1-2 semanas)
- Crear skill dedicada para liquidacion critica.
- Crear instruction applyTo para preinformes y dictado_informes.

### Fase 3 (2-4 semanas)
- Armar ritual fijo de QA por PR: permisos, timezone, transacciones, N+1, tests criticos.
- Medir ahorro de tiempo por tipo de tarea (estimado simple por semana).
