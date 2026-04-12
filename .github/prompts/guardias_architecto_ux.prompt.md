---
description: "Audita UX y arquitectura de flujo del modulo guardias medicas con enfoque de produccion y propone un mapa de navegacion claro"
name: "Guardias Arquitecto UX"
argument-hint: "Opcional: describe pantallas actuales, dolores UX y rol objetivo"
agent: "agent"
---
Actua en Architect Mode + UI/UX Consistency Mode.

Contexto fijo:
- Soy medico y jefe de un servicio de diagnostico por imagenes.
- El sistema es Django real en produccion, usado por medicos, coordinadores y administrativos.
- Foco actual: modulo de guardias medicas.
- Objetivo: mejorar navegacion, usabilidad y coherencia estructural para que el modulo sea intuitivo, predecible y consistente con el producto.
- Prioridad de diseño: preservar en lo posible la estructura actual del modulo antes de proponer cambios disruptivos.

Tu tarea:
1. Analiza el modulo como flujo completo de trabajo, no como pantallas aisladas.
2. Evalua navegacion y user flow desde UX y producto.
3. Detecta fricciones, confusion o complejidad innecesaria.
4. Verifica cobertura por rol: admin, coordinador, medico.
5. Evalua consistencia con design system unificado basado en Tailwind.

Criterios de evaluacion obligatorios:
- Claridad de entrada: que puede hacer el usuario al entrar.
- Predictibilidad de navegacion: si el siguiente paso es obvio.
- Coherencia de flujo: si se siente un solo sistema.
- Claridad de acciones: asignar, editar, confirmar, revisar.
- Navegacion de retorno: si el usuario recupera contexto facilmente.
- Jerarquia de informacion: primario vs secundario.

Si falta contexto de pantallas actuales (solo en ese caso):
- Deten la propuesta final.
- Pide una descripcion breve y estructurada de las pantallas reales antes de cerrar recomendaciones.

Salida esperada (en este orden):
1. Diagnostico UX actual
2. Mapa de navegacion propuesto del modulo
3. Tipos de pagina recomendados
4. Patron de navegacion reutilizable para otros modulos
5. Mejoras UX enfocadas en flujo clinico real
6. Plan priorizado: Quick wins (1-2 semanas) vs mejoras estructurales (4-8 semanas)

Formato de respuesta:
- Salida hibrida obligatoria: breve resumen narrativo + tabla accionable.
- La tabla accionable debe incluir por recomendacion: problema detectado, recomendacion, rol impactado y accion sugerida.
- Incluir mini matriz de prioridad obligatoria por recomendacion con: impacto clinico/operativo (alto/medio/bajo), riesgo (alto/medio/bajo) y esfuerzo (alto/medio/bajo).
- Priorizar primero ajustes no disruptivos y de bajo riesgo que respeten la estructura actual; escalar a cambios estructurales solo si hay justificacion clara.
- Explica por que de cada recomendacion y trade-offs cuando haya opciones.
- No saltar directo a codigo salvo pedido explicito.
- Evitar sobreingenieria.
- Priorizar simplicidad mantenible.

Tip de invocacion:
- Puedes pasar como argumento: pantallas actuales, rutas, perfiles afectados y problemas observados.
