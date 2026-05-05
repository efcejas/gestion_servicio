---
name: copilot-workflow-operativo
description: "Skill para elegir y aplicar correctamente instrucciones, skills, agentes y prompts en gestion_servicio. Usar cuando el usuario pida optimizar flujo de trabajo con Copilot, retomar proyecto, planificar tareas complejas o estandarizar forma de pedir cambios."
---

# Skill: Copilot Workflow Operativo (Colegiales)

## Objetivo
Ayudar a decidir rapidamente que mecanismo usar (instructions, skill, agente o prompt) para obtener mejores resultados con menor friccion.

## Regla de decision

1. Si es una regla fija del proyecto o de una app -> instructions.
2. Si es conocimiento experto reusable -> skill.
3. Si es una tarea profunda multiarchivo -> agente especializado.
4. Si es inicio de sesion o pedido repetido -> prompt.

## Protocolo de respuesta recomendado

1. Diagnostico corto del pedido.
2. Seleccion de mecanismo y por que.
3. Plan MVP (primero impacto clinico/operativo, luego riesgo, luego esfuerzo).
4. Ejecucion incremental.
5. Validacion final (tests, riesgos remanentes, siguientes pasos).

## Antipatrones a evitar

- Empezar por codigo sin definir flujo ni riesgos en tareas no triviales.
- Crear instrucciones gigantes para cosas que en realidad son skills.
- Usar agentes para tareas simples de 1 archivo.
- Repetir prompts manualmente en cada sesion en lugar de guardarlos.

## Checklist rapido antes de implementar

- Permisos por rol estan claros.
- Impacto en datos y migraciones evaluado.
- Tests minimos definidos.
- Riesgo en modulos criticos identificado.
- Plan de rollback simple disponible si aplica.
