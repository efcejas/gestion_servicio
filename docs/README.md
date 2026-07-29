# 📚 Documentación del Sistema

Índice operativo de la documentación del Sistema de Gestión del Servicio de Diagnóstico por Imágenes.

## Punto de entrada recomendado

### Operación y despliegue

- **[operativa/README.md](operativa/README.md)** - Índice de documentación operativa.
- **[operativa/README_colegiales_deploy.md](operativa/README_colegiales_deploy.md)** - Guía principal de deploy en Heroku.
- **[operativa/CHECKLIST_DEPLOY_HEROKU.md](operativa/CHECKLIST_DEPLOY_HEROKU.md)** - Checklist corto antes y después del deploy.
- **[operativa/CONFIGURAR_SCHEDULER.md](operativa/CONFIGURAR_SCHEDULER.md)** - Configuración del scheduler local para pedidos.
- **[operativa/HEROKU_CONFIG_VARS.md](operativa/HEROKU_CONFIG_VARS.md)** - Variables de entorno útiles para producción.
- **[operativa/DEPLOY_HEROKU_PEDIDOS.md](operativa/DEPLOY_HEROKU_PEDIDOS.md)** - Deploy específico del sistema de pedidos.
- **[operativa/DEPLOY_ACTUALIZACION_SEGURIDAD.md](operativa/DEPLOY_ACTUALIZACION_SEGURIDAD.md)** - Procedimiento de actualización de seguridad.
- **[operativa/AUDITORIA_USO_LIQUIDACION.md](operativa/AUDITORIA_USO_LIQUIDACION.md)** - Checklist para validar uso real del módulo de liquidación.
- **[operativa/COMANDO_IMPORTAR_ESTUDIOS.md](operativa/COMANDO_IMPORTAR_ESTUDIOS.md)** - Referencia del comando de importación de estudios desde EGES.
- **[operativa/FRONTEND_TAILWIND_WORKFLOW.md](operativa/FRONTEND_TAILWIND_WORKFLOW.md)** - Flujo operativo de Tailwind + IntelliSense en VS Code.

### Sistemas activos

- **[producto/README.md](producto/README.md)** - Índice de documentación funcional.
- **[producto/CONTROL_GUARDIAS.md](producto/CONTROL_GUARDIAS.md)** - Fuente funcional principal del módulo de guardias.
- **[producto/README_PROTOCOLOS.md](producto/README_PROTOCOLOS.md)** - Navegación del sistema de protocolos.
- **[producto/SISTEMA_PERFILES_README.md](producto/SISTEMA_PERFILES_README.md)** - Roles, perfiles y flujo de usuario.
- **[producto/SISTEMA_RESIDENTES_README.md](producto/SISTEMA_RESIDENTES_README.md)** - Módulo de residentes.
- **[producto/SISTEMA_CLASES_RESIDENTES.md](producto/SISTEMA_CLASES_RESIDENTES.md)** - Sistema educativo de residentes.
- **[producto/SISTEMA_CONSULTORIOS.md](producto/SISTEMA_CONSULTORIOS.md)** - Consultorios y equipamiento.
- **[producto/SISTEMA_LIQUIDACION_COLEGIALES_V2.md](producto/SISTEMA_LIQUIDACION_COLEGIALES_V2.md)** - Referencia funcional de liquidación.
- **[producto/RESUMEN_LOGICA_REGISTRO_ESTUDIOS.md](producto/RESUMEN_LOGICA_REGISTRO_ESTUDIOS.md)** - Resumen funcional/técnico del registro de estudios.
- **[producto/NOTIFICACIONES_TOKEN_README.md](producto/NOTIFICACIONES_TOKEN_README.md)** - Acceso por token y notificaciones para médicos.
- **[producto/PREINFORMES_FORMATO_WORD.md](producto/PREINFORMES_FORMATO_WORD.md)** - Compatibilidad de preinformes con Word y EGES.
- **[producto/PREINFORMES_REVISION_STAFF.md](producto/PREINFORMES_REVISION_STAFF.md)** - Circuito vigente de revision staff de preinformes.

- **[liquidacion/reglas-descuento-residencia.md](liquidacion/reglas-descuento-residencia.md)** - Reglas vigentes de descuento residencia, B2/B3, diagnostico de recalculo, preparacion RRHH y checklist de cierre.

### IA y dictado

- **[arquitectura/README.md](arquitectura/README.md)** - Índice de documentación técnica.
- **[arquitectura/CONFIGURACION_APIS_IA.md](arquitectura/CONFIGURACION_APIS_IA.md)** - Configuración de APIs para IA.
- **[arquitectura/ARQUITECTURA_SISTEMA_DICTADO_IA.md](arquitectura/ARQUITECTURA_SISTEMA_DICTADO_IA.md)** - Arquitectura del sistema de dictado.
- **[arquitectura/RELEVAMIENTO_SISTEMA_DICTADO_IA.md](arquitectura/RELEVAMIENTO_SISTEMA_DICTADO_IA.md)** - Relevamiento funcional/técnico actual.
- **[arquitectura/CAMBIOS_NORMALIZE_SOFT_2026.md](arquitectura/CAMBIOS_NORMALIZE_SOFT_2026.md)** - Cambio técnico de normalización HTML en preinformes.
- **[arquitectura/REFACTOR_REVISION_STAFF.md](arquitectura/REFACTOR_REVISION_STAFF.md)** - Refactor de la revisión de staff en preinformes.
- **[arquitectura/SISTEMA_CARGA_ARCHIVOS_HIBRIDO.md](arquitectura/SISTEMA_CARGA_ARCHIVOS_HIBRIDO.md)** - Arquitectura de carga híbrida para clases de residentes.
- **[arquitectura/SISTEMA_DISENO_DARK_MODE.md](arquitectura/SISTEMA_DISENO_DARK_MODE.md)** - Sistema visual unificado para dark mode en dictado IA.
- **[arquitectura/NORMAS_UI_OPERATIVAS.md](arquitectura/NORMAS_UI_OPERATIVAS.md)** - Normas UI para bandejas, estados y acciones operativas.

### Calidad y seguridad

- **[operativa/TESTS_README.md](operativa/TESTS_README.md)** - Ejecución y alcance de tests.
- **[operativa/CONTROL_GUARDIAS_DISTRIBUCION_MEJORAS.md](operativa/CONTROL_GUARDIAS_DISTRIBUCION_MEJORAS.md)** - Reglas y mejoras de distribución de guardias.
- **[operativa/CONTROL_GUARDIAS_NOTIFICACIONES_EMAIL.md](operativa/CONTROL_GUARDIAS_NOTIFICACIONES_EMAIL.md)** - Matriz operativa de notificaciones del módulo.
- **[security/SECURITY_README.md](security/SECURITY_README.md)** - Índice detallado de documentos de seguridad.
- **[security/DASHBOARD_ADMIN_SEGURIDAD.md](security/DASHBOARD_ADMIN_SEGURIDAD.md)** - Restricciones de acceso del dashboard administrativo.

## Estructura activa

- **[operativa/README.md](operativa/README.md)** - Deploy, scheduler, variables de entorno, testing y procedimientos.
- **[producto/README.md](producto/README.md)** - Documentación funcional de módulos y flujos de negocio.
- **[arquitectura/README.md](arquitectura/README.md)** - Roadmaps, relevamientos y documentos técnicos de diseño.

## Documentación histórica

- **[archive/](archive/)** - Archivo histórico general.
- **[archive/dictado_ia/](archive/dictado_ia/)** - Fases cerradas del proyecto de dictado IA.
- **[archive/dictado_ia/PLAN_ACCION_DICTADO_IA.md](archive/dictado_ia/PLAN_ACCION_DICTADO_IA.md)** - Plan de optimización ya ejecutado (histórico).
- **[archive/producto/PROPUESTA_DIRECTOR_PEDIDOS.md](archive/producto/PROPUESTA_DIRECTOR_PEDIDOS.md)** - Propuesta funcional/económica de pedidos (histórico).

Usar `archive/` para:
- fases completadas
- relevamientos cerrados
- reportes de auditoría antiguos
- documentación que ya no sea la fuente principal de verdad

## Criterio de orden

1. La raíz de `docs/` debe contener solo documentación vigente o de consulta frecuente.
2. `docs/archive/` debe contener material histórico o cerrado.
3. Si un documento deja de ser el principal, no borrarlo: moverlo a `archive/` y actualizar enlaces.

---

*Última actualización: Abril 2026*
