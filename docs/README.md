# 📚 Documentación del Sistema

Índice operativo de la documentación del Sistema de Gestión del Servicio de Diagnóstico por Imágenes.

## Punto de entrada recomendado

### Operación y despliegue

- **[operativa/README.md](operativa/README.md)** - Índice de documentación operativa.
- **[operativa/README_colegiales_deploy.md](operativa/README_colegiales_deploy.md)** - Guía principal de deploy en Heroku.
- **[operativa/CHECKLIST_DEPLOY_HEROKU.md](operativa/CHECKLIST_DEPLOY_HEROKU.md)** - Checklist corto antes y después del deploy.
- **[operativa/CONFIGURAR_SCHEDULER.md](operativa/CONFIGURAR_SCHEDULER.md)** - Configuración del scheduler local para pedidos.
- **[operativa/HEROKU_CONFIG_VARS.md](operativa/HEROKU_CONFIG_VARS.md)** - Variables de entorno útiles para producción.

### Sistemas activos

- **[producto/README.md](producto/README.md)** - Índice de documentación funcional.
- **[producto/README_PROTOCOLOS.md](producto/README_PROTOCOLOS.md)** - Navegación del sistema de protocolos.
- **[producto/SISTEMA_PERFILES_README.md](producto/SISTEMA_PERFILES_README.md)** - Roles, perfiles y flujo de usuario.
- **[producto/SISTEMA_RESIDENTES_README.md](producto/SISTEMA_RESIDENTES_README.md)** - Módulo de residentes.
- **[producto/SISTEMA_CLASES_RESIDENTES.md](producto/SISTEMA_CLASES_RESIDENTES.md)** - Sistema educativo de residentes.
- **[producto/SISTEMA_CONSULTORIOS.md](producto/SISTEMA_CONSULTORIOS.md)** - Consultorios y equipamiento.
- **[producto/SISTEMA_LIQUIDACION_COLEGIALES_V2.md](producto/SISTEMA_LIQUIDACION_COLEGIALES_V2.md)** - Referencia funcional de liquidación.

### IA y dictado

- **[arquitectura/README.md](arquitectura/README.md)** - Índice de documentación técnica.
- **[arquitectura/CONFIGURACION_APIS_IA.md](arquitectura/CONFIGURACION_APIS_IA.md)** - Configuración de APIs para IA.
- **[arquitectura/PLAN_ACCION_DICTADO_IA.md](arquitectura/PLAN_ACCION_DICTADO_IA.md)** - Documento vivo de roadmap y estado del sistema de dictado.
- **[arquitectura/ARQUITECTURA_SISTEMA_DICTADO_IA.md](arquitectura/ARQUITECTURA_SISTEMA_DICTADO_IA.md)** - Arquitectura del sistema de dictado.
- **[arquitectura/RELEVAMIENTO_SISTEMA_DICTADO_IA.md](arquitectura/RELEVAMIENTO_SISTEMA_DICTADO_IA.md)** - Relevamiento funcional/técnico actual.

### Calidad y seguridad

- **[operativa/TESTS_README.md](operativa/TESTS_README.md)** - Ejecución y alcance de tests.
- **[SECURITY_IMPROVEMENTS.md](SECURITY_IMPROVEMENTS.md)** - Resumen de mejoras de seguridad.
- **[security/SECURITY_README.md](security/SECURITY_README.md)** - Índice detallado de documentos de seguridad.

## Estructura activa

- **[operativa/README.md](operativa/README.md)** - Deploy, scheduler, variables de entorno, testing y procedimientos.
- **[producto/README.md](producto/README.md)** - Documentación funcional de módulos y flujos de negocio.
- **[arquitectura/README.md](arquitectura/README.md)** - Roadmaps, relevamientos y documentos técnicos de diseño.

## Documentación histórica

- **[archive/](archive/)** - Archivo histórico general.
- **[archive/dictado_ia/](archive/dictado_ia/)** - Fases cerradas del proyecto de dictado IA.

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
