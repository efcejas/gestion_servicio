# 🛠️ Scripts del Sistema

Este directorio contiene todos los scripts auxiliares del sistema organizados por categoría.

## 📂 Estructura

```
scripts/
├── maintenance/          # Scripts de mantenimiento del sistema
├── tests/               # Scripts de prueba y verificación
├── README.md           # Este archivo
└── [scripts de carga]  # Scripts de carga masiva de datos
```

## 🔧 Scripts de Mantenimiento (`maintenance/`)

Scripts para tareas administrativas y mantenimiento del sistema:

- **`actualizar_usuarios.py`** - Migración de usuarios al nuevo sistema de perfiles
  - Mapea campos antiguos (`cargo`) a nuevos roles (`rol`)
  - Ejecutar: `python manage.py shell < scripts/maintenance/actualizar_usuarios.py`

- **`auditoria_protocolos.py`** - Auditoría completa del sistema de protocolos
  - Verifica integridad de modalidades, regiones, tags y fases
  - Detecta inconsistencias y protocolos incompletos
  - Ejecutar: `python scripts/maintenance/auditoria_protocolos.py`

- **`limpiar_protocolos.py`** - Limpieza y corrección de base de datos de protocolos
  - Elimina duplicados y corrige relaciones
  - Ejecutar: `python scripts/maintenance/limpiar_protocolos.py`

## 🧪 Scripts de Prueba (`tests/`)

Scripts para testing y verificación del sistema:

### Tests de Funcionalidad
- **`test_email_simple.py`** - Prueba de envío de emails
- **`test_form_permissions.py`** - Validación de permisos en formularios
- **`test_funcionalidades_eventos.py`** - Tests del sistema de eventos
- **`test_navigation.py`** - Pruebas de navegación y rutas
- **`test_toast_view.py`** - Tests de notificaciones toast
- **`test_openai.py`** - Pruebas de integración con OpenAI

### Scripts de Verificación
- **`verificar_elegir_protocolo.py`** - Verifica flujo de selección de protocolos
- **`verificar_usuario_rol.py`** - Valida sistema de roles y permisos

**Ejecutar:** `python scripts/tests/[nombre_script].py`

## 📊 Scripts de Carga Masiva

Scripts para importación de datos desde Excel:

### Carga de Estudios
- **`cargar_ecografias_denise.py`** - Ecografías de médica específica
- **`cargar_estudios_denise.py`** - RX, TC y RM de médica específica

### Carga de Protocolos
- **`cargar_todos_protocolos.py`** - Carga masiva de todos los protocolos
- **`importar_protocolos_inteligente.py`** - Importación inteligente evitando duplicados
- **`exportar_protocolos.py`** - Exportación de protocolos a JSON/Excel

### Análisis y Verificación
- **`analizar_protocolos.py`** - Análisis estadístico de protocolos
- **`verificar_protocolos.py`** - Verificación de integridad de protocolos
- **`verificar_templates_auth.py`** - Verificación de templates de autenticación
- **`diagnosticar_templates_auth.py`** - Diagnóstico de problemas en templates

### Otros
- **`poblar_diccionario_medico.py`** - Carga de términos médicos al diccionario

## ▶️ Cómo Ejecutar

### Scripts Django (requieren manage.py)
```bash
python manage.py shell < scripts/[categoria]/[nombre_script].py
```

### Scripts standalone
```bash
python scripts/[categoria]/[nombre_script].py
```

## 🛡️ Notas Importantes

- **Backups**: Siempre haz backup de la base de datos antes de ejecutar scripts de mantenimiento
- **Entorno**: Asegúrate de tener el entorno virtual activado
- **Duplicados**: Los scripts de carga verifican duplicados automáticamente
- **Logs**: Revisa la salida de los scripts para verificar que todo se ejecutó correctamente

## 📝 Documentación Adicional

Ver documentación completa en:
- [RESUMEN_CARGA_PROTOCOLOS.md](RESUMEN_CARGA_PROTOCOLOS.md) - Detalle de carga de protocolos
- [MIGRACION_PROTOCOLOS_DUPLICADO_A_COLEGIALES.md](MIGRACION_PROTOCOLOS_DUPLICADO_A_COLEGIALES.md) - Migración entre bases de datos
- [../docs/README.md](../docs/README.md) - Documentación general del sistema

---

*Última actualización: Diciembre 2025*
