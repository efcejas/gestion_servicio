---
name: liquidacion-operativo
description: "Skill para evolucionar el modulo liquidacion con foco en reglas por rol, trazabilidad, cierre mensual, calculo economico y seguridad operativa. Usar cuando: se cambien permisos de carga/edicion/borrado, se ajusten reglas por estado de sesion, se modifique calcular_monto/bonus, se agreguen validaciones de cierre, se optimicen listados globales, o se escriban tests criticos del modulo."
---

# Skill: Liquidacion Operativa

> Ultima actualizacion: 13/05/2026

## Objetivo

Mejorar `liquidacion/` con enfoque de produccion clinica: exactitud de facturacion, control por rol, trazabilidad y bajo riesgo de regresion.

## Principios de trabajo

1. Impacto clinico/operativo primero.
2. Seguridad y trazabilidad antes que conveniencia.
3. Cambios pequenos, testeables y reversibles.
4. Nada de sobreingenieria.

## Matriz funcional base (resumen)

- Medicos: operan sobre registros propios en `ABIERTA/REVISION`.
- Jefe/instructor: igual que medicos para visibilidad personal.
- Vista global: `administrativo`, `jefe_servicio`, `superuser`.
- Correcciones en `CERRADA/FACTURADA`: perfiles operativos con trazabilidad fuerte.
- `PAGADA`: bloqueada.

## Checklist tecnico obligatorio

- Permisos en backend (`dispatch`, `test_func`, queryset restringido).
- Calculo centralizado en modelo/servicio (`calcular_monto`).
- `transaction.atomic` en escrituras compuestas.
- N+1 controlado en reportes.
- Tests por rol + estado + calculo.

## Riesgos frecuentes

- Duplicar reglas de calculo entre vista y modelo.
- Permisos solo en frontend (sin enforcement backend).
- Ediciones sin `modificado_por`/`fecha_modificacion`/`motivo_modificacion`.
- Cambios de comportamiento en cierres sin test por estado.

## Flujo recomendado de implementacion

1. Definir regla de negocio y rol afectado.
2. Ajustar validacion backend.
3. Ajustar vista/template.
4. Escribir test de regresion.
5. Verificar lista completa `python manage.py test liquidacion`.

## Salida esperada del skill

- Diagnostico corto del problema.
- Cambios puntuales aplicados en backend/frontend/tests.
- Riesgos mitigados y pendientes.
- Pasos de validacion funcional para administrativo y medico.
