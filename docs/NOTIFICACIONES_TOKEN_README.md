# Sistema de Notificaciones con Token - Documentación

## ✅ Implementación Completada

### Funcionalidades Implementadas

1. **Token de Acceso para Médicos** ✓
   - Campo `token_acceso` agregado al modelo `MedicoGuardia`
   - Tokens únicos de 64 caracteres generados automáticamente
   - Método `get_url_acceso()` para generar URL con token

2. **Vista sin Login con Token** ✓
   - URL: `/pedidos/mis-estudios/<token>/`
   - Acceso sin autenticación usando token único
   - Muestra estudios filtrados por especialidad del médico
   - Botón "Realizado" funcional con token
   - Template compartido con vista con login (detección automática)

3. **Notificaciones Mejoradas** ✓
   - Emails personalizados para cada médico
   - Incluye botón "Ver Mis Estudios Pendientes" con enlace directo
   - Detecta médicos de guardia según especialidad del estudio
   - Envío individual a cada destinatario con su propio token

---

## 🔧 Archivos Modificados

### Modelos
- **pedidos_estudios/models.py**
  - Agregado campo `token_acceso` a `MedicoGuardia`
  - Método `save()` sobrescrito para generar token automáticamente
  - Método `get_url_acceso()` para generar URL completa

### Vistas
- **pedidos_estudios/views_medicos.py**
  - `mis_estudios_token(request, token)` - Vista sin login
  - `marcar_realizado_token(request, token, pedido_id)` - Acción sin login

### Notificador
- **pedidos_estudios/services/notificador.py**
  - `notificar_pedido()` modificado para enviar emails personalizados
  - `_obtener_destinatarios()` incluye médicos de guardia por especialidad
  - `_generar_contenido_html()` acepta parámetro `medico` para personalizar
  - Incluye botón de acceso con token en el email

### Templates
- **templates/pedidos_estudios/mis_estudios.html**
  - Soporta acceso con login Y con token
  - Detección automática vía flag `es_acceso_token`
  - URLs dinámicas según tipo de acceso
  - Indicador visual cuando se accede con token

- **templates/pedidos_estudios/token_invalido.html** (NUEVO)
  - Página de error para tokens inválidos

### URLs
- **pedidos_estudios/urls.py**
  - `/mis-estudios/<token>/` - Vista con token
  - `/estudios/<token>/<pedido_id>/marcar-realizado/` - Acción con token

### Configuración
- **gestion_estudios/settings.py**
  - Nueva variable `SITE_URL` para generar enlaces completos

---

## 🧪 Cómo Probar

### 1. Obtener URLs de Acceso
```bash
python manage.py shell -c "from pedidos_estudios.models import MedicoGuardia; [print(f'{m.nombre_completo}: {m.get_url_acceso()}') for m in MedicoGuardia.objects.all()]"
```

### 2. Probar Acceso con Token
Copiar una de las URLs y abrir en el navegador. Deberías ver:
- Header con nombre del médico y especialidad
- Indicador "Acceso con enlace directo"
- Lista de estudios filtrada por especialidad
- Botón "Realizado" funcional

### 3. Médicos Existentes

**Dr. Carlos Rodríguez** (Doppler y Ecocardio)
- Email: admin@colegiales.com
- Ve TODOS los estudios (Doppler + Ecocardio)
- Token: `mylMQsqe36GJ7X5pEe1gJ4-E2iE82bGGToe6RgvocRny1THzCrVNjduZcVFp-gzr`

**Dr. Juan Pérez** (Ecodoppler)
- Email: juan.perez@sanatoriocolegiales.com.ar
- Ve solo estudios de Doppler
- Token: `j_TfwXTi0UaaTIypwJG8u0qDd2vB1bz0oRh3IAKarD6qjytSFI_e0UeqtOLroyNQ`

**Dra. María González** (Ecocardiograma)
- Email: maria.gonzalez@sanatoriocolegiales.com.ar
- Ve solo estudios de Ecocardiograma
- Token: `yM1_MG0FZauL9QJ57BRlBgg6ULdnnwJ6kVc46PwPZBU7XXhk-LModPO7SgNOu91G`

### 4. Simular Notificación

Ejecutar script de prueba:
```bash
python manage.py shell < test_notificaciones_token.py
```

Esto mostrará:
- Pedido que se notificará
- Destinatarios que recibirán el email
- URLs con token para cada médico
- Preview del HTML del email

Para **enviar realmente** el email, editar `test_notificaciones_token.py` y descomentar:
```python
resultado = notificador.notificar_pedido(pedido)
```

### 5. Probar Marcar como Realizado

1. Acceder con token (usar una de las URLs de arriba)
2. Hacer clic en "Realizado" en cualquier estudio
3. Confirmar la acción
4. Verificar que el estudio desaparece de la lista

---

## 📧 Formato del Email

El email incluye:

### Header
- Título: "Nuevo Pedido de Estudio"
- Nombre personalizado del médico destinatario

### Contenido
- Badge de prioridad (color según urgencia)
- Datos del paciente (nombre, HC, habitación)
- Datos del estudio (tipo, descripción, indicación)
- Médico solicitante
- Fecha de solicitud

### Botón de Acceso (NUEVO)
- Botón azul: "📋 Ver Mis Estudios Pendientes"
- Enlace directo con token del médico
- Texto explicativo: "Haz clic para ver todos tus estudios pendientes"

### Footer
- Mensaje automático
- ID del pedido
- Firma: "Sanatorio de los Colegiales - Sistema de Gestión de Estudios"

---

## 🔐 Seguridad

- **Tokens únicos**: 64 caracteres generados con `secrets.token_urlsafe(48)`
- **Tokens persistentes**: Guardados en base de datos, no expiran (pueden regenerarse si es necesario)
- **Filtrado por especialidad**: Cada médico solo ve estudios que puede realizar
- **Validación**: Token inválido muestra página de error

---

## 🚀 Próximos Pasos (Opcionales)

- [ ] Comando para regenerar tokens de todos los médicos
- [ ] Expiración de tokens (opcional)
- [ ] Envío de emails reales desde procesador de emails
- [ ] WhatsApp notifications usando los tokens
- [ ] Dashboard de administrador con gestión de tokens
- [ ] Histórico de notificaciones enviadas

---

## 📝 Notas Técnicas

### Migración
- Archivo: `pedidos_estudios/migrations/0004_add_token_acceso_medicoguardia.py`
- Campo: `token_acceso` (CharField, 64 chars, unique, nullable)

### Compatibilidad
- El sistema sigue funcionando con login normal para médicos con cuenta de usuario
- Los médicos sin usuario del sistema pueden usar el token
- El template detecta automáticamente el tipo de acceso

### Base de Datos
- 3 médicos con tokens generados
- Tokens visibles en admin de Django
- Campo `token_acceso` indexado (unique constraint)

---

**Fecha de implementación**: 15/02/2026
**Estado**: ✅ Completado y listo para pruebas
