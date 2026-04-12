# 📚 Documentación del Sistema

Índice operativo de la documentación del Sistema de Gestión del Servicio de Diagnóstico por Imágenes.

## Punto de entrada recomendado

### Operación y despliegue

- **[README_colegiales_deploy.md](README_colegiales_deploy.md)** - Guía principal de deploy en Heroku.
- **[CHECKLIST_DEPLOY_HEROKU.md](CHECKLIST_DEPLOY_HEROKU.md)** - Checklist corto antes y después del deploy.
- **[CONFIGURAR_SCHEDULER.md](CONFIGURAR_SCHEDULER.md)** - Configuración del scheduler local para pedidos.
- **[HEROKU_CONFIG_VARS.md](HEROKU_CONFIG_VARS.md)** - Variables de entorno útiles para producción.

### Sistemas activos

- **[README_PROTOCOLOS.md](README_PROTOCOLOS.md)** - Navegación del sistema de protocolos.
- **[SISTEMA_PERFILES_README.md](SISTEMA_PERFILES_README.md)** - Roles, perfiles y flujo de usuario.
- **[SISTEMA_RESIDENTES_README.md](SISTEMA_RESIDENTES_README.md)** - Módulo de residentes.
- **[SISTEMA_CLASES_RESIDENTES.md](SISTEMA_CLASES_RESIDENTES.md)** - Sistema educativo de residentes.
- **[SISTEMA_CONSULTORIOS.md](SISTEMA_CONSULTORIOS.md)** - Consultorios y equipamiento.
- **[SISTEMA_LIQUIDACION_COLEGIALES_V2.md](SISTEMA_LIQUIDACION_COLEGIALES_V2.md)** - Referencia funcional de liquidación.

### IA y dictado

- **[CONFIGURACION_APIS_IA.md](CONFIGURACION_APIS_IA.md)** - Configuración de APIs para IA.
- **[PLAN_ACCION_DICTADO_IA.md](PLAN_ACCION_DICTADO_IA.md)** - Documento vivo de roadmap y estado del sistema de dictado.
- **[ARQUITECTURA_SISTEMA_DICTADO_IA.md](ARQUITECTURA_SISTEMA_DICTADO_IA.md)** - Arquitectura del sistema de dictado.
- **[RELEVAMIENTO_SISTEMA_DICTADO_IA.md](RELEVAMIENTO_SISTEMA_DICTADO_IA.md)** - Relevamiento funcional/técnico actual.

### Calidad y seguridad

- **[TESTS_README.md](TESTS_README.md)** - Ejecución y alcance de tests.
- **[SECURITY_IMPROVEMENTS.md](SECURITY_IMPROVEMENTS.md)** - Resumen de mejoras de seguridad.
- **[security/SECURITY_README.md](security/SECURITY_README.md)** - Índice detallado de documentos de seguridad.

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
