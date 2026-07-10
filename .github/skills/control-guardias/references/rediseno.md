# Rediseño control_guardias - referencia funcional

Usar esta referencia solo para pedidos amplios de rediseño o evolucion funcional del modulo. Para cambios puntuales, priorizar `.github/instructions/control_guardias.instructions.md` y el `SKILL.md` principal.

## Objetivo del modulo

Planificar guardias de residentes con distribucion equitativa, trazabilidad operativa, resolucion de ausencias/cambios y calendario claro para residentes y gestores.

## Decisiones vigentes

- Acceso con login. No hay portal publico.
- No hay integracion con liquidacion por ahora.
- No existe R5: solo R1, R2, R3 y R4.
- `CustomUser` es la fuente para residentes y gestores; no crear un modelo paralelo de medico de guardia.
- Gestionan `jefe_residentes`, `instructor_residentes` y `superuser`.
- El sistema propone distribuciones; el humano valida/publica.
- FullCalendar es la UI de calendario.
- Las cuotas por anio son configurables por jefes/instructores.

## Capacidades principales

1. Configurar tipos de guardia, feriados y cuotas mensuales.
2. Generar distribucion automatica por mes/anio y tipos seleccionados.
3. Mantener borradores antes de publicar.
4. Mostrar calendario y lista personal de guardias.
5. Reportar y resolver ausencias.
6. Solicitar y revisar cambios entre residentes.
7. Notificar eventos relevantes.

## Reglas de distribucion esperadas

- Respetar cuota disponible por residente.
- Evitar dos guardias del mismo residente el mismo dia.
- Evitar dias consecutivos.
- Considerar feriados.
- Pre-cargar asignaciones existentes del periodo antes de crear nuevas.
- Si hay doble cobertura, representarla con tipos de guardia distintos para el mismo dia/horario.
- Registrar slots sin cubrir y advertencias en vez de fallar silenciosamente.

## Modelo de roles

| Rol | Puede hacer |
|---|---|
| Residente | Ver sus guardias, reportar ausencia, pedir cambio |
| Jefe/instructor | Configurar, generar, revisar, publicar, resolver ausencias/cambios |
| Superuser | Supervision total y soporte administrativo |

## Riesgos de rediseño

- Romper unicidad `unique_residente_fecha_tipo`.
- Reintroducir R5.
- Crear reglas en templates en vez de servicios.
- Hacer calculos de fecha con UTC que fallen en Argentina.
- Cambiar permisos solo en UI sin validar backend.
- Generar distribuciones sin considerar guardias ya existentes.

## Validacion minima

```bash
python manage.py test control_guardias --verbosity=1
python manage.py makemigrations --check --dry-run
```

Si el cambio es solo documental, no hace falta ejecutar tests Django.
