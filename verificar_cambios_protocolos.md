# Resumen de Cambios - Sistema de Protocolos

## 1. Restricciones de Acceso

### Vistas Restringidas a Superusuarios
- **ProtocoloListView**: Solo superusuarios pueden ver/editar todos los protocolos
- **ProtocoloDetailView**: Solo superusuarios pueden ver detalles y editar protocolos

### Vista Accesible para Personal Médico
- **elegir_protocolo**: Accesible para médicos staff, residentes, jefes de servicio y técnicos

## 2. Mejoras de Navegación

### En elegir_protocolo.html
- Botón "Gestionar Protocolos" (solo visible para superusuarios)
- Lleva a la lista completa de protocolos

### En lista_protocolos.html
- Botón "Elegir Protocolo" - vuelve a la página de decisión clínica
- Botón "Nuevo Protocolo" - solo visible para usuarios con permisos (superusuarios)

### En detalle_protocolo.html
- Botón "Elegir Protocolo" - vuelve a la página de decisión
- Botón "Ver Lista" - vuelve a la lista de protocolos
- Botón "Editar" - solo visible para usuarios con permisos (superusuarios)

## 3. Flujo de Navegación

```
[Home] 
  └─> [Protocolos] (navbar - visible para médicos/técnicos)
       └─> [Elegir Protocolo] (decisión clínica)
            ├─> [Gestionar Protocolos] (solo superusuario)
            │    └─> [Lista de Protocolos]
            │         ├─> [Detalle Protocolo]
            │         └─> [Nuevo Protocolo] (admin)
            └─> Selección de escenario clínico
```

## 4. Permisos Implementados

| Vista/Acción | Acceso |
|--------------|--------|
| Elegir Protocolo | Médicos staff, residentes, jefes, técnicos |
| Ver Lista Completa | Solo superusuarios |
| Ver Detalle | Solo superusuarios |
| Agregar Protocolo | Solo superusuarios (via admin) |
| Editar Protocolo | Solo superusuarios (via admin) |

## 5. Verificación

Para verificar que todo funciona:
1. Como superusuario: deberías ver botón "Gestionar Protocolos"
2. Como médico/residente: solo ves "¿Qué protocolo elegir?"
3. En lista: superusuarios ven "Nuevo Protocolo" y "Elegir Protocolo"
4. En detalle: superusuarios ven "Editar", "Elegir Protocolo" y "Ver Lista"
