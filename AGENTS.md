# Instrucciones para agentes

Este repositorio es un sistema Django medico en produccion. Antes de analizar o modificar codigo, leer `.github/copilot-instructions.md`, que contiene las reglas globales del proyecto.

## Coordinacion entre agentes

- Tratar los archivos del repositorio, especialmente `AGENTS.md`, `.github/copilot-instructions.md` y la documentacion del modulo, como la fuente compartida de contexto.
- Revisar los cambios existentes en el worktree antes de editar y no sobrescribir trabajo de otro agente.
- Para cambios grandes, dejar el codigo en un estado ejecutable y resumir archivos modificados, decisiones y validaciones realizadas.
- Para cambios pequenos, mantener el alcance focal y ejecutar una validacion rapida antes de terminar.

## Seleccion de reglas

- Cambios de frontend o UX: leer `docs/ux/guia-estilo.md` y respetar los patrones compartidos antes de crear nuevos componentes o estilos.
- `liquidacion/`: leer `.github/instructions/liquidacion.instructions.md` y `.github/skills/liquidacion-operativo/SKILL.md`.
- `control_guardias/`: leer `.github/instructions/control_guardias.instructions.md` y `.github/skills/control-guardias/SKILL.md`.
- `dictado_informes/`: leer `.github/instructions/dictado_informes.instructions.md` y `.github/agents/dictado-informes.agent.md` cuando el cambio toque IA, STT o LLM.
- `preinformes/`: leer `.github/instructions/preinformes.instructions.md` y `.github/agents/preinformes-mejoras.agent.md`.
- `consultorios/`: leer `.github/agents/consultorios-ecografia.agent.md`.

## Validacion minima

- Priorizar tests focalizados sobre suites completas cuando el cambio sea acotado.
- Si se tocan modelos, ejecutar `python manage.py makemigrations --check --dry-run`.
- No modificar migraciones ya aplicadas.
- No tocar credenciales, tokens, `db.sqlite3` ni `gestion_env/`.