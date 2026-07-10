# Flujo de trabajo IA: Codex + Copilot

Esta guia resume como usar las instrucciones, skills, agentes y prompts del repo sin gastar contexto de mas.

## Idea central

No todo debe estar en memoria global. La informacion se organiza por frecuencia y riesgo:

| Recurso | Para que sirve | Cuando usarlo |
|---|---|---|
| `.github/copilot-instructions.md` | Router global liviano | Siempre; reglas minimas del proyecto |
| `.github/instructions/*.instructions.md` | Reglas duras por modulo | Cuando se toca codigo de ese modulo |
| `.github/skills/*/SKILL.md` | Procedimiento reusable | Cuando el dominio es fragil o repetible |
| `.github/agents/*.agent.md` | Rol especializado | Tareas profundas multiarchivo |
| `.github/prompts/*.prompt.md` | Pedido reusable | Arranque, review, roadmap, decisiones |

## Regla practica

- Si es una regla estable: `instructions`.
- Si es una receta de trabajo: `skill`.
- Si requiere criterio especializado durante una tarea grande: `agent`.
- Si es una forma de pedir algo: `prompt`.

## Como pedirme cosas a mi, Codex

Para tareas de implementacion:

```text
Usa las instrucciones del repo. Quiero cambiar <modulo/flujo>. Primero identifica riesgos, despues implementa el MVP y valida con tests focales.
```

Para revisar cambios:

```text
Revisa el diff con foco en bugs, permisos, datos, timezone, N+1 y tests faltantes. Usa las instrucciones del modulo si aplica.
```

Para liquidacion:

```text
Usa .github/skills/liquidacion-operativo/SKILL.md antes de tocar codigo. No recalcules masivamente ni toques migraciones aplicadas.
```

Para guardias:

```text
Usa .github/skills/control-guardias/SKILL.md. Cuidar R1-R4, distribucion, permisos y calendario local UTC-3.
```

## Como usar Copilot sin gastar de mas

Usar Copilot inline para completar codigo local y repetitivo:

- forms simples;
- mappers;
- validaciones pequenas;
- tests siguiendo un patron existente;
- nombres e imports.

Evitar Copilot Chat para investigacion amplia. Si el pedido requiere leer varios archivos, decidir arquitectura o tocar flujos criticos, conviene usar Codex.

## Prompts utiles existentes

- `.github/prompts/colegiales_arranque_sesion.prompt.md`: iniciar una tarea no trivial.
- `.github/prompts/colegiales_review_critico.prompt.md`: revisar bugs/regresiones.
- `.github/prompts/liquidacion_decision_funcional.prompt.md`: decidir comportamiento de liquidacion.
- `.github/prompts/roadmap_ia_clinica_residentes.prompt.md`: planificar producto/roadmap.

## Mantenimiento recomendado

Cada mes o despues de features grandes:

1. Quitar reglas obsoletas.
2. Mover detalles largos desde `copilot-instructions.md` a `instructions` o `skills`.
3. Revisar contradicciones entre `instructions`, `skills` y agentes.
4. Corregir encoding si aparecen `Ã³`, `Ã¡`, `â` o caracteres raros.
5. Preferir archivos cortos, accionables y con fuentes de verdad claras.

## Checklist para crear una nueva skill

Crear una skill solo si se cumple al menos una condicion:

- repetis el mismo procedimiento varias veces;
- el dominio tiene riesgos reales;
- hay fuentes de verdad que el agente debe leer siempre;
- hay comandos de validacion especificos;
- hay errores historicos que conviene prevenir.

Una buena skill debe responder:

1. Cuando se usa.
2. Que archivos leer primero.
3. Que invariantes preservar.
4. Que comandos ejecutar.
5. Que riesgos declarar al final.
