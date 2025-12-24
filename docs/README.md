# 📚 Documentación del Sistema

Esta carpeta contiene toda la documentación técnica y funcional del Sistema de Gestión del Servicio de Diagnóstico por Imágenes.

## 📋 Documentación Activa

### Sistemas y Funcionalidades

- **[README_PROTOCOLOS.md](README_PROTOCOLOS.md)** - Sistema de protocolos radiológicos
  - Guía completa de modalidades, regiones anatómicas, tags y fases de adquisición
  - Flujo de selección inteligente de protocolos
  - Mantenimiento y actualización de protocolos

- **[SISTEMA_PERFILES_README.md](SISTEMA_PERFILES_README.md)** - Sistema de perfiles de usuario
  - Flujo de registro y completado de perfil
  - Roles y permisos por tipo de usuario
  - Validaciones y reglas de negocio

- **[SISTEMA_RESIDENTES_README.md](SISTEMA_RESIDENTES_README.md)** - Gestión de residentes
  - Cálculo automático de año de residencia (R1-R5)
  - Seguimiento de progreso académico
  - Permisos y accesos por año

### Despliegue y Configuración

- **[README_colegiales_deploy.md](README_colegiales_deploy.md)** - Guía de despliegue en Heroku
  - Configuración de aplicación gestion-colegiales
  - Variables de entorno necesarias
  - Base de datos PostgreSQL
  - Email con SendGrid
  - Proceso de deployment

### Seguridad y Pruebas

- **[SECURITY_IMPROVEMENTS.md](SECURITY_IMPROVEMENTS.md)** - Mejoras de seguridad implementadas
  - Configuración de email segura (App Passwords)
  - HTTPS y manejo de contraseñas
  - Mejores prácticas

- **[TESTS_README.md](TESTS_README.md)** - Guía de testing
  - Suite de tests del sistema
  - Cómo ejecutar tests
  - Cobertura de código

## 📦 Archivo Histórico

La carpeta [archive/](archive/) contiene documentación de implementaciones pasadas y reportes históricos:

- Migraciones completadas
- Correcciones visuales y de alineación
- Reportes de auditoría
- Cambios en templates y autenticación
- Verificaciones de permisos

**Nota:** Los documentos en archive/ son de referencia histórica. Para información actual, consulta la documentación activa listada arriba.

## 🔄 Mantenimiento

Al agregar nueva documentación:
1. Coloca documentos activos en la raíz de `docs/`
2. Archiva documentos históricos en `docs/archive/`
3. Actualiza este índice con la nueva documentación
4. Usa nombres descriptivos en MAYÚSCULAS para documentos importantes

---

*Última actualización: Diciembre 2025*
