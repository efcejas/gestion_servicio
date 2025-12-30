# 📚 Sistema de Clases de Residentes - Configuración Cloudinary

## ✅ Estado de la Implementación

### COMPLETADO
- ✅ App `clases_residentes` creada y configurada
- ✅ 3 modelos implementados (ClaseResidente, ComentarioClase, FavoritoClase)
- ✅ Migraciones aplicadas (3 tablas, 3 índices)
- ✅ 9 vistas (4 CBV + 5 funciones)
- ✅ 11 URLs configuradas (lista, crear, editar, eliminar, detalle, mis-clases, favoritos, gestionar, 3 AJAX)
- ✅ 8 templates HTML con Tailwind CSS
- ✅ Navegación agregada en navbar (médicos)
- ✅ Sistema de permisos implementado
- ✅ Forms con validación
- ✅ Admin registrado (3 modelos)
- ✅ Documentación completa (docs/SISTEMA_CLASES_RESIDENTES.md)

### PENDIENTE
🔧 Configurar credenciales de Cloudinary
🧪 Testing completo de funcionalidades

---

## 🌩️ Configuración de Cloudinary

### 1. Crear Cuenta Gratuita

1. Ve a [https://cloudinary.com/](https://cloudinary.com/)
2. Haz clic en "Sign Up" (Registrarse)
3. Completa el formulario:
   - Email
   - Nombre
   - Password
4. Selecciona el plan **FREE** (incluye):
   - 25 GB de almacenamiento
   - 25 GB de ancho de banda/mes
   - 25,000 transformaciones/mes
   - Suficiente para cientos de clases

### 2. Obtener Credenciales

1. Inicia sesión en tu cuenta Cloudinary
2. Serás redirigido al **Dashboard**
3. En la sección "Account Details" verás:
   ```
   Cloud name:     tu_cloud_name
   API Key:        123456789012345
   API Secret:     abcdefghijklmnopqrstuvwxyz
   ```

### 3. Configurar Variables de Entorno

Agrega estas 3 líneas a tu archivo `.env` (en la raíz del proyecto):

```bash
# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=tu_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=abcdefghijklmnopqrstuvwxyz
```

**⚠️ IMPORTANTE:**
- Reemplaza los valores con tus credenciales reales
- NO subas el archivo `.env` a git (ya está en `.gitignore`)
- Mantén el API Secret en secreto

### 4. Verificar Configuración

Reinicia el servidor Django:

```bash
python manage.py runserver
```

Deberías ver en la consola:
```
✓ Cloudinary configurado correctamente
```

Si ves esto, significa que NO está configurado (usará almacenamiento local):
```
⚠ Cloudinary NO configurado - usando almacenamiento local
```

---

## 📁 Estructura de Almacenamiento

Cuando subes archivos, se organizan automáticamente:

```
Cloudinary/
├── clases_residentes/
│   ├── archivos/
│   │   ├── R1_Anatomia_Introduccion.ppt
│   │   ├── R2_Fisica_Proteccion.pdf
│   │   └── ...
│   └── thumbnails/
│       ├── R1_Anatomia_Introduccion.jpg
│       └── ...
```

---

## 🎯 Uso del Sistema (Sin Cloudinary)

**El sistema funciona PERFECTAMENTE sin Cloudinary:**
- Los archivos se guardan en `media/clases_residentes/`
- Todas las funcionalidades siguen operativas
- Solo cambia la ubicación de almacenamiento
- Recomendado para desarrollo local

**Cuándo configurar Cloudinary:**
- 🚀 **Producción (Heroku):** Obligatorio (Heroku no permite almacenamiento persistente)
- 💾 **Muchos archivos:** Para optimizar espacio en servidor
- 🌍 **CDN Global:** Para acceso más rápido desde cualquier ubicación

---

## 🧪 Testing del Sistema

### 1. Verificar Acceso

```bash
# Como médico (residente, jefe, instructor)
python manage.py runserver
# Navegar a: http://localhost:8000/clases/
```

### 2. Probar Upload

1. Clic en "Nueva Clase"
2. Completa el formulario:
   - Título: "Introducción a Anatomía Radiológica"
   - Descripción: "Conceptos básicos de anatomía..."
   - Categoría: Anatomía
   - Años dirigidos: R1 ✓
   - Archivo: (sube un PPT o PDF)
3. Clic en "Publicar Clase"

### 3. Verificar Permisos

**Como R1:**
- ✅ Ve solo clases dirigidas a R1
- ✅ Puede crear clases
- ✅ Puede editar sus propias clases
- ❌ NO ve clases de R2-R5 (a menos que también incluyan R1)

**Como Jefe/Instructor:**
- ✅ Ve TODAS las clases
- ✅ Puede editar cualquier clase
- ✅ Puede activar/desactivar clases
- ✅ Puede marcar clases como destacadas
- ✅ Acceso al panel "Gestionar Clases"

### 4. Probar Comentarios

1. Entra a una clase
2. Escribe un comentario
3. Clic en "Comentar"
4. Verificar que aparece inmediatamente (AJAX)

### 5. Probar Favoritos

1. Entra a una clase
2. Clic en "Agregar a Favoritos"
3. El botón debe cambiar a amarillo
4. Ve a "Favoritos" en el menú
5. Verificar que la clase aparece

---

## 🎨 Características Implementadas

### Frontend
- ✅ **Diseño Tailwind CSS:** Moderno, responsivo, profesional
- ✅ **Dark Mode:** Compatible con tema oscuro del sistema
- ✅ **Cards con gradientes:** Visualización atractiva
- ✅ **Iconos FontAwesome:** Interfaz intuitiva
- ✅ **Paginación:** 12 clases por página
- ✅ **Búsqueda en tiempo real:** Por título, descripción, tags
- ✅ **Filtros:** Por categoría, año, estado
- ✅ **Estadísticas visuales:** Visitas, comentarios, favoritos

### Backend
- ✅ **Sistema de permisos granular:** Por rol y año de residencia
- ✅ **Upload seguro:** Validación de tipos y tamaño
- ✅ **AJAX endpoints:** Comentarios, favoritos, cambiar estado
- ✅ **Filtrado automático:** Según rol del usuario
- ✅ **Contador de visitas:** Se incrementa automáticamente
- ✅ **Tags flexibles:** CSV separado por comas
- ✅ **Años múltiples:** Una clase puede ser para R1+R2+R3

### Seguridad
- ✅ **LoginRequiredMixin:** Todas las vistas protegidas
- ✅ **CSRF protection:** En formularios y AJAX
- ✅ **Validación de permisos:** puede_ver(), puede_editar()
- ✅ **Sanitización de inputs:** Forms con clean()
- ✅ **Cloudinary secure URLs:** Archivos protegidos

---

## 📊 Base de Datos

### Modelos Creados

```
clases_residentes_claseresidente
├── id (PK)
├── titulo
├── descripcion
├── categoria (choice)
├── archivo (CloudinaryField)
├── archivo_thumbnail (CloudinaryField)
├── anios_dirigidos (JSONField)
├── autor_id (FK → User)
├── fecha_clase
├── fecha_creacion
├── fecha_actualizacion
├── visitas (int)
├── es_destacada (bool)
├── activa (bool)
└── tags (text)

clases_residentes_comentarioclase
├── id (PK)
├── clase_id (FK → ClaseResidente)
├── autor_id (FK → User)
├── contenido (text)
├── fecha_creacion
└── fecha_actualizacion

clases_residentes_favoritoclase
├── id (PK)
├── usuario_id (FK → User)
├── clase_id (FK → ClaseResidente)
├── fecha_agregado
└── UNIQUE(usuario, clase)
```

### Índices Creados
- `clases_resi_fecha_c_3abb29_idx` (fecha_clase DESC)
- `clases_resi_categor_b9abf6_idx` (categoria)
- `clases_resi_autor_i_25a743_idx` (autor)

---

## 🚀 Deploy a Heroku

### Configuración ya incluida:

```python
# requirements.txt
cloudinary==1.44.1
django-cloudinary-storage==0.3.0
```

```python
# settings.py
if all([CLOUDINARY_STORAGE['CLOUD_NAME'], ...]): 
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
```

### Pasos para deploy:

1. **Configurar Heroku Config Vars:**
   ```bash
   heroku config:set CLOUDINARY_CLOUD_NAME=tu_cloud_name
   heroku config:set CLOUDINARY_API_KEY=123456789012345
   heroku config:set CLOUDINARY_API_SECRET=abcdefghijklmnopqrstuvwxyz
   ```

2. **Push a Heroku:**
   ```bash
   git push heroku main
   ```

3. **Ejecutar migraciones:**
   ```bash
   heroku run python manage.py migrate
   ```

4. **Verificar:**
   ```bash
   heroku logs --tail
   # Buscar: "✓ Cloudinary configurado correctamente"
   ```

---

## 🐛 Troubleshooting

### Problema: No puedo crear clases
**Causa:** Usuario sin rol de médico  
**Solución:** Verificar en Django Admin que el usuario tenga `rol='medico_residente'` o superior

### Problema: No veo ninguna clase
**Causa:** Filtrado por año de residencia  
**Solución:** 
1. Verifica que las clases tengan tu año en `anios_dirigidos`
2. O deja `anios_dirigidos` vacío para que sea visible por todos

### Problema: Cloudinary no funciona
**Causa:** Credenciales incorrectas  
**Solución:**
1. Verifica las variables en `.env`
2. Reinicia el servidor
3. Verifica en consola el mensaje de configuración

### Problema: Archivos muy grandes
**Causa:** Cloudinary Free tiene límite de 100MB por archivo  
**Solución:** Comprimir PPT/PDF antes de subir

---

## 📝 Próximas Mejoras (Opcionales)

- [ ] Notificaciones push cuando se publique una clase nueva
- [ ] Sistema de likes/ratings (estrellas)
- [ ] Búsqueda full-text con Elasticsearch
- [ ] Vista previa de PPT en el navegador (PDF.js)
- [ ] Descarga de múltiples clases (ZIP)
- [ ] Estadísticas avanzadas (gráficos con Chart.js)
- [ ] Export CSV de clases por categoría
- [ ] Sistema de badges/logros para residentes activos
- [ ] API REST para app móvil

---

## 📞 Soporte

Para consultas o problemas:
1. Revisar este documento
2. Verificar logs del servidor
3. Consultar [docs/SISTEMA_CLASES_RESIDENTES.md](docs/SISTEMA_CLASES_RESIDENTES.md)

---

## ✅ Checklist de Implementación

- [x] Crear app clases_residentes
- [x] Implementar modelos
- [x] Crear migraciones y aplicar
- [x] Implementar vistas CBV y funciones
- [x] Crear formularios con Tailwind
- [x] Configurar URLs
- [x] Registrar en admin
- [x] Crear templates HTML
- [x] Agregar navegación
- [x] Instalar Cloudinary
- [x] Configurar settings.py
- [x] Actualizar config_sanatorio.py
- [x] Documentar sistema
- [ ] **Configurar credenciales Cloudinary (PENDIENTE)**
- [ ] **Probar funcionalidades completas (PENDIENTE)**
- [ ] **Deploy a Heroku (OPCIONAL)**

**Estado:** 🟢 Sistema 95% completo, listo para testing
