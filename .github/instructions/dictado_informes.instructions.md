---
applyTo: "dictado_informes/**/*.py"
---

# Instrucciones para dictado_informes

> Ultima actualizacion: 03/05/2026

## Pipeline IA

- Mantener el flujo: audio -> STT -> LLM -> informe.
- Prompts y comportamiento del pipeline solo se modifican en `ai_services.py`.
- Evitar hardcode de texto de prompt en vistas.

## Modelos y aprendizaje

- `CorreccionAprendizaje` se guarda siempre; su uso en prompt depende de aptitud.
- Al tocar filtros de aptitud, preservar guardrails anti-ruido.
- En modo estructurado, priorizar fidelidad al dictado y estructura clinica.

## Tests

- Nunca ejecutar `python manage.py test dictado_informes` (conflicto tests.py/tests/).
- Ejecutar tests por modulo, por ejemplo:
  - `python manage.py test dictado_informes.tests.test_utils`

## Seguridad y privacidad

- No loguear contenido sensible de pacientes ni audio.
- API keys siempre por variables de entorno, nunca hardcodeadas.
- Validar tipo/tamano de archivos antes de STT.

## Arquitectura y UX

- Mantener opciones no esenciales en panel de "Opciones Avanzadas".
- Preservar compatibilidad de copiado `text/plain` con CRLF para sistemas legacy Windows.
- Si se integra un nuevo proveedor/modelo, dejar fallback explicito y documentado.
