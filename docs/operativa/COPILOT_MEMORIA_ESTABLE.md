# Copilot Memoria Estable entre Sesiones

Guia practica para reducir perdida de contexto entre sesiones en VS Code + Copilot.

## 1) Que persiste de forma mas estable

### A. Contexto persistente en archivos del repo (recomendado)
- Guardar decisiones en docs versionados.
- Ventaja: trazable, auditable y compartible.
- En este proyecto usar:
  - `docs/operativa/`
  - `.github/instructions/`
  - `.github/skills/`
  - `.github/prompts/`

### B. Memoria de usuario (persistente entre conversaciones)
- Guardar preferencias estables tuyas (estilo, prioridades, flujo).
- Es util para no repetir siempre el mismo contexto personal.
- Debe ser breve y de alto valor (no logs largos).

### C. Memoria de repo
- Guardar hechos tecnicos estables de arquitectura y convenciones.
- Ideal para reglas de dominio y decisiones recurrentes por modulo.

## 2) Lo que NO conviene usar como memoria principal

- Confiar solo en el historial del chat de una sesion.
- Dejar decisiones criticas solo en mensajes sueltos sin archivo fuente.
- Guardar contexto importante unicamente en notas locales no versionadas.

## 3) Protocolo recomendado de continuidad

### Al inicio de sesion
1. Definir objetivo del dia en 1 linea.
2. Invocar prompt de arranque.
3. Confirmar restricciones del modulo (instructions aplicables).

### Durante la sesion
1. Registrar decisiones de arquitectura en docs cortos.
2. Si aparece un error repetido, promoverlo a instruction o skill.

### Al cierre de sesion
1. Guardar resumen en un archivo de handoff (que se commitea).
2. Incluir:
   - que se hizo
   - que falta
   - riesgos
   - siguiente paso recomendado

## 4) Plantilla minima de handoff (copiar/pegar)

## Resumen
- Cambios realizados:
- Estado actual:

## Riesgos / Supuestos
- Riesgo 1:
- Riesgo 2:

## Siguiente paso sugerido
- Paso unico recomendado para retomar rapido.

## 5) Estrategia concreta para este repo

- Mantener reglas globales en `.github/copilot-instructions.md`.
- Reglas por modulo en `.github/instructions/*.instructions.md`.
- Conocimiento reusable en `.github/skills/*/SKILL.md`.
- Arranques estandarizados en `.github/prompts/*.prompt.md`.
- Decisiones operativas y runbooks en `docs/operativa/`.

Con este esquema, aunque cambie la sesion, el contexto clave queda anclado en fuentes persistentes y reutilizables.
