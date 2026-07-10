---
applyTo: "**"
---

# Colegiales - instrucciones globales

Sistema Django medico en produccion para gestion de diagnostico por imagenes.
El usuario es jefe medico con perfil tecnico autodidacta: responder como socio tecnico senior, con explicacion breve del por que y pasos accionables.

## Regla de oro

Antes de cambiar codigo, clasificar el pedido:

1. **Regla fija del proyecto o modulo** -> leer `.github/instructions/*.instructions.md`.
2. **Procedimiento reusable o dominio fragil** -> leer `.github/skills/*/SKILL.md`.
3. **Tarea profunda multiarchivo** -> usar/agregar contexto de `.github/agents/*.agent.md`.
4. **Pedido repetido o arranque de sesion** -> usar `.github/prompts/*.prompt.md`.

No duplicar reglas entre archivos. La instruccion global solo orienta; el detalle vive en el modulo.

## Stack y comandos

- Backend: Django 5.1.4, Python 3.13.
- Frontend: Tailwind CSS + Flowbite, Alpine.js cuando aplique.
- DB: SQLite en desarrollo, PostgreSQL en produccion Heroku.

Comandos frecuentes:

```bash
python manage.py runserver
npm run tailwind:watch
python manage.py test <app>
python manage.py makemigrations --check --dry-run
```

Caso especial:

```bash
# No ejecutar el modulo completo: hay conflicto tests.py/tests/
python manage.py test dictado_informes.tests.test_utils
```

## Arquitectura esperada

- Mantener views delgadas.
- Poner logica de negocio en `services.py` cuando exista el patron.
- Usar `selectors.py` para consultas reutilizables.
- Usar excepciones tipadas en modulos que ya tengan `exceptions.py`.
- No mover reglas sensibles a templates.
- Usar `timezone.now()` / `timezone.localtime()`. Evitar `datetime.now()` y `date.today()` en codigo Django.
- Evitar N+1 con `select_related()` / `prefetch_related()` cuando haya listados.

## Modulos criticos y fuentes

Leer la fuente especifica antes de tocar cada modulo:

- `liquidacion/`: `.github/instructions/liquidacion.instructions.md` y `.github/skills/liquidacion-operativo/SKILL.md`.
- `control_guardias/`: `.github/instructions/control_guardias.instructions.md` y `.github/skills/control-guardias/SKILL.md`.
- `dictado_informes/`: `.github/instructions/dictado_informes.instructions.md` y `.github/agents/dictado-informes.agent.md` si toca IA/prompts/STT/LLM.
- `preinformes/`: `.github/instructions/preinformes.instructions.md` y `.github/agents/preinformes-mejoras.agent.md`.
- `consultorios/`: `.github/agents/consultorios-ecografia.agent.md`.

## Areas de alto riesgo

- `liquidacion/`: afecta dinero real, estados contables, snapshots y auditoria.
- `accounts/decorators.py` y permisos por rol: pueden exponer datos sensibles.
- Management commands de integracion EGES: afectan datos importados.
- Migraciones ya aplicadas: no modificarlas; crear nuevas migraciones.
- Envio de emails reales: no activarlo salvo aprobacion explicita.

## Convenciones Django

- Orden de imports: stdlib, Django, third-party, local.
- Modelos: fields, `Meta`, `__str__`, `clean/save`, metodos, properties.
- Validar permisos en backend, no solo en templates.
- Para navbar, no tocar `includes/_nav.html`; editar `accounts/context_processors.py`.
- Templates: guardar en UTF-8. Si aparecen `Ã³` o `Ã¡`, revisar encoding del archivo.

## Frontend

- Base portal/light: `base_tailwind.html`.
- Base superuser/dark: `base_with_sidebar.html`.
- Contenedor operativo estandar:

```html
<div class="max-w-full px-4 sm:px-6 lg:px-10 py-4">
```

- Preferir cambios incrementales de UX. Evitar redisenos grandes si el pedido es focal.
- Usar el componente de avatar:

```django
{% include 'components/user_avatar.html' with user_obj=user size="sm" %}
```

## Testing

- Prioridad de tests: liquidacion, permisos, guardias, validaciones de forms y flujos clinicos.
- Elegir tests focales antes que suites largas cuando el riesgo este acotado.
- Si se toca modelo, correr `python manage.py makemigrations --check --dry-run`.

## Forma de respuesta esperada

Para tareas no triviales:

1. Diagnostico corto.
2. Plan MVP por impacto operativo, riesgo y esfuerzo.
3. Implementacion incremental.
4. Validacion ejecutada.
5. Riesgos remanentes y siguiente paso concreto.
