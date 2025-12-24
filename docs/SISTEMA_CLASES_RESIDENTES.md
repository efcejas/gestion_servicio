# 🎓 Sistema de Clases para Residentes

Sistema completo para gestión de clases y material educativo dirigido a residentes de diagnóstico por imágenes.

## 📋 Características

### 🎯 Para Residentes
- ✅ Subir presentaciones (PPT, PDF, Keynote)
- ✅ Clasificar por categoría (Anatomía, Protocolos, Casos Clínicos, etc.)
- ✅ Dirigir clases a años específicos (R1, R2, etc.)
- ✅ Agregar tags para búsqueda
- ✅ Ver solo clases de su año
- ✅ Marcar clases como favoritas
- ✅ Comentar y dar feedback

### 👨‍⚕️ Para Jefes e Instructores
- ✅ Ver todas las clases
- ✅ Gestionar y redistribuir clases
- ✅ Activar/desactivar clases
- ✅ Marcar clases como destacadas
- ✅ Estadísticas de uso

### 🔐 Sistema de Permisos

**Visualización de Clases:**
- **R1**: Ve clases para R1 y "Todos"
- **R2**: Ve clases para R1, R2 y "Todos"
- **R3-R5**: Similar lógica
- **Jefes/Instructores**: Ven todas las clases

**Edición:**
- Autor puede editar su propia clase
- Jefes e instructores pueden editar cualquier clase

## 🗂️ Estructura de Modelos

### ClaseResidente
```python
- titulo: CharField (200)
- descripcion: TextField
- categoria: CharField (choices)
- archivo: CloudinaryField
- archivo_thumbnail: CloudinaryField (opcional)
- anios_dirigidos: JSONField (lista de años)
- autor: ForeignKey(CustomUser)
- fecha_clase: DateField
- visitas: PositiveIntegerField
- es_destacada: BooleanField
- activa: BooleanField
- tags: CharField
```

### ComentarioClase
```python
- clase: ForeignKey(ClaseResidente)
- autor: ForeignKey(CustomUser)
- contenido: TextField
- fecha_creacion: DateTimeField
```

### FavoritoClase
```python
- usuario: ForeignKey(CustomUser)
- clase: ForeignKey(ClaseResidente)
- fecha_creacion: DateTimeField
```

## 📂 Categorías Disponibles

1. **Anatomía Radiológica** - Bases anatómicas
2. **Física de Imágenes** - Física y tecnología
3. **Protocolos de Estudio** - Protocolos técnicos
4. **Patología por Imagen** - Patrones y hallazgos
5. **Radiología Pediátrica** - Casos pediátricos
6. **Intervencionismo** - Procedimientos
7. **Ultrasonido** - Ecografía
8. **Tomografía Computada** - TC específico
9. **Resonancia Magnética** - RM específico
10. **Caso Clínico** - Casos para discusión
11. **Revisión Bibliográfica** - Review de literatura
12. **Otro** - Otros temas

## 🌐 URLs Disponibles

```
/clases/                          # Lista de clases
/clases/crear/                    # Crear nueva clase
/clases/<id>/                     # Detalle de clase
/clases/<id>/editar/             # Editar clase
/clases/<id>/eliminar/           # Eliminar clase
/clases/<id>/comentario/         # Agregar comentario (AJAX)
/clases/<id>/favorito/           # Toggle favorito (AJAX)
/clases/mis-clases/              # Mis clases creadas
/clases/favoritos/               # Mis clases favoritas
/clases/gestionar/               # Gestión (jefes/instructores)
/clases/<id>/cambiar-estado/    # Activar/desactivar (AJAX)
```

## 🔧 Configuración

### 1. Instalar Dependencias

```bash
pip install django-cloudinary-storage
```

### 2. Configurar Cloudinary en settings.py

```python
# Agregar a INSTALLED_APPS
INSTALLED_APPS = [
    ...
    'cloudinary_storage',
    'cloudinary',
    'clases_residentes',
]

# Configuración de Cloudinary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': env('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': env('CLOUDINARY_API_KEY'),
    'API_SECRET': env('CLOUDINARY_API_SECRET')
}

# Usar Cloudinary para media files
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
```

### 3. Variables de Entorno (.env)

```env
# Cloudinary (obtener de https://cloudinary.com/console)
CLOUDINARY_CLOUD_NAME=tu_cloud_name
CLOUDINARY_API_KEY=tu_api_key
CLOUDINARY_API_SECRET=tu_api_secret
```

### 4. Agregar URLs en gestion_estudios/urls.py

```python
urlpatterns = [
    ...
    path('clases/', include('clases_residentes.urls')),
]
```

### 5. Ejecutar Migraciones

```bash
python manage.py makemigrations clases_residentes
python manage.py migrate
```

## 🎨 Templates Necesarios

Crear en `templates/clases_residentes/`:

1. **lista_clases.html** - Lista principal con búsqueda y filtros
2. **detalle_clase.html** - Vista detallada con comentarios
3. **crear_clase.html** - Formulario de creación
4. **editar_clase.html** - Formulario de edición
5. **eliminar_clase.html** - Confirmación de eliminación
6. **mis_clases.html** - Clases del usuario
7. **favoritos.html** - Clases favoritas
8. **gestionar_clases.html** - Panel de gestión (jefes)

## 📊 Uso

### Crear una Clase

```python
from clases_residentes.models import ClaseResidente

clase = ClaseResidente.objects.create(
    titulo="Protocolo de TC de Tórax",
    descripcion="Protocolo completo para TC de tórax",
    categoria="protocolos",
    anios_dirigidos=["R1", "R2"],  # Solo para R1 y R2
    autor=usuario,
    archivo=archivo_cloudinary,
    tags="tórax, tc, protocolo"
)
```

### Verificar Permisos

```python
# ¿Puede ver esta clase?
if clase.puede_ver(usuario):
    # Mostrar clase
    
# ¿Puede editar esta clase?
if clase.puede_editar(usuario):
    # Mostrar botón editar
```

## 🔒 Seguridad

- ✅ LoginRequiredMixin en todas las vistas
- ✅ Verificación de permisos con `puede_ver()` y `puede_editar()`
- ✅ Filtrado automático por año de residencia
- ✅ UserPassesTestMixin para edición/eliminación
- ✅ Validación de roles en gestión administrativa

## 📈 Estadísticas

El sistema rastrea:
- Número de visitas por clase
- Número de comentarios
- Clases favoritas por usuario
- Clases por categoría
- Clases por año de residencia

## 🚀 Próximas Mejoras (Opcional)

- [ ] Sistema de calificación (rating) por clase
- [ ] Notificaciones cuando se sube nueva clase
- [ ] Generación automática de thumbnails
- [ ] Conversión automática PPT → PDF
- [ ] Sistema de quizzes/evaluaciones
- [ ] Estadísticas avanzadas de uso
- [ ] Exportar colección de clases
- [ ] Versioning de archivos

## 📝 Notas Importantes

1. **Cloudinary es esencial** - Los archivos se almacenan en Cloudinary, no en el servidor
2. **JSONField para años** - Permite selección múltiple flexible
3. **Soft delete** - Campo `activa` permite desactivar sin eliminar
4. **Índices en DB** - Optimizado para búsquedas por fecha, categoría y autor

---

*Implementado: Diciembre 2025*
*Django 5.1.4 - Python 3.13 - Cloudinary*
