---
description: "Analiza y aterriza decisiones funcionales del modulo liquidacion segun rol, estado de sesion y riesgo operativo"
name: "Liquidacion Decision Funcional"
argument-hint: "Opcional: describe caso concreto (rol, estado, accion, problema actual)"
agent: "agent"
---

Actua en Architect Mode para decisiones funcionales de `liquidacion`.

Contexto fijo:
- Sistema Django en produccion para gestion medica.
- Modulo critico de facturacion (impacta dinero real).
- Hay multiples perfiles con permisos diferentes.
- Necesitamos decisiones simples, aplicables y auditables.

Tu tarea:
1. Evaluar la decision funcional propuesta por rol y estado de sesion.
2. Detectar riesgos de seguridad, facturacion y operacion.
3. Proponer regla final clara (quien puede que, cuando y con que trazabilidad).
4. Traducir la decision a backlog tecnico minimo viable.

Criterios obligatorios:
- Impacto clinico/operativo.
- Riesgo (permisos, dinero, auditoria).
- Esfuerzo de implementacion.
- Compatibilidad con reglas actuales del modulo.

Salida esperada (en este orden):
1. Decision recomendada (1-3 lineas)
2. Matriz rol x accion x estado
3. Cambios minimos en codigo (archivos objetivo)
4. Tests minimos de regresion
5. Riesgos remanentes y mitigacion

Formato:
- Breve resumen narrativo + tabla accionable.
- Evitar sobreingenieria.
- No saltar a rediseno total.
