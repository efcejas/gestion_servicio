# 📹 Sistema Híbrido de Carga de Archivos - Documentación

## 🎯 Objetivo

Resolver el error **H28 "Client Connection Idle"** de Heroku implementando un sistema híbrido de carga de archivos que evita timeouts para videos grandes.

## 🏗️ Arquitectura Implementada

### Sistema Híbrido (Documentos + Videos)

```
┌─────────────────────────────────────────────────────────────┐
│                    CLASES DE RESIDENTES                      │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────┐     ┌──────────────────────────┐
│   DOCUMENTOS (S3/MinIO)  │     │   VIDEOS (Cloudinary)    │
│                          │     │                          │
│  • PPT, PDF, KEY         │     │  • MP4, MOV, AVI, WMV    │
│  • Hasta 50 MB           │     │  • Hasta 1 GB            │
│  • Subida tradicional    │     │  • Subida directa        │
│  • A través de Django    │     │  • Sin pasar por Django  │
│  • Sin timeout           │     │  • Con barra de progreso │
└──────────────────────────┘     └──────────────────────────┘
```

### Flujo de Subida

**Documentos (tradicional):**
```
Navegador → Django → S3/MinIO → Guardado
          (5-10 seg)           (OK, sin timeout)
```

**Videos (subida directa):**
```
Navegador → Cloudinary (directo) → Guardado
          (90+ seg, sin timeout)
          │
          └→ Django recibe solo public_id (instantáneo)
```

## 📋 Cambios Implementados

### 1. Modelo `ClaseResidente`

**Nuevo campo agregado:**
```python
archivo_video = CloudinaryField(
    'video',
    blank=True,
    null=True,
    folder='clases_residentes/videos',
    resource_type='video'
)
```

**Campos actuales (sin cambios):**
- `archivo` → S3/MinIO (documentos)
- `archivo_thumbnail` → Cloudinary (imágenes)

### 2. Formulario `ClaseResidenteForm`

**Lógica implementada:**
- Detecta tipo de archivo automát icamente
- Campo oculto `archivo_video_public_id` para guardar ID de Cloudinary
- Validación separada para documentos y videos
- Al subir un tipo, limpia el otro automáticamente

### 3. Templates

**Interfaz con tabs:**
- Tab "Documento": Input file tradicional (PPT/PDF)
- Tab "Video": Botón que abre widget de Cloudinary
- Barra de progreso en tiempo real
- Preview del video subido

### 4. JavaScript

**Widget de Cloudinary (`cloudinary_upload_widget.js`):**
- Upload directo desde navegador
- Progreso en tiempo real
- Chunk upload automático para archivos grandes
- Manejo de errores y cancelación

## 🚀 Pasos para Deploy

### 1. Ejecutar Migración (SEGURA, no borra datos)

```bash
python manage.py migrate clases_residentes
```

### 2. Configurar Upload Preset en Cloudinary

**Pasos en Cloudinary Dashboard:**

1. Ir a **Settings** → **Upload** → **Upload presets**
2. Clic en **Add upload preset**
3. Configurar:
   - **Preset name:** `clases_residentes_unsigned`
   - **Signing Mode:** `Unsigned` ⚠️ IMPORTANTE
   - **Folder:** `clases_residentes/videos`
   - **Resource type:** `Video`
   - **Max file size:** `1000000000` (1 GB)
   - **Max video duration:** `3600` (60 minutos)
   - **Allowed formats:** `mp4,mov,avi,wmv,flv,mkv,m4v,webm`
4. Guardar

**¿Por qué "Unsigned"?**
- Permite subida directa desde el navegador sin firma backend
- Más rápido y simple
- El folder y configuraciones limitan lo que se puede subir

### 3. Verificar Variables de Entorno en Heroku

```bash
heroku config:get CLOUDINARY_CLOUD_NAME --app gestion-colegiales
heroku config:get CLOUDINARY_API_KEY --app gestion-colegiales
heroku config:get CLOUDINARY_API_SECRET --app gestion-colegiales
```

Si no están configuradas:
```bash
heroku config:set CLOUDINARY_CLOUD_NAME=tu_cloud_name --app gestion-colegiales
heroku config:set CLOUDINARY_API_KEY=tu_api_key --app gestion-colegiales
heroku config:set CLOUDINARY_API_SECRET=tu_api_secret --app gestion-colegiales
```

### 4. Deploy a Heroku

```bash
git add .
git commit -m "Implementar sistema híbrido de carga de archivos (S3 + Cloudinary)"
git push heroku feature/colegiales:main
```

### 5. Verificar Logs

```bash
heroku logs --tail --app gestion-colegiales
```

## 📊 Datos Existentes (100% Preservados)

**✅ Garantía:** Todos los archivos actuales en S3 se mantienen intactos.

**Migración segura:**
- Solo agrega el campo `archivo_video` (nullable)
- No modifica ni borra datos existentes
- Campo `archivo` permanece igual

## 🎨 Uso en la Interfaz

### Para Documentos (PPT/PDF):
1. Ir a "Crear Clase" o "Editar Clase"
2. Seleccionar tab **"Documento (PPT/PDF)"**
3. Usar el input file tradicional
4. Guardar normalmente

### Para Videos:
1. Ir a "Crear Clase" o "Editar Clase"
2. Seleccionar tab **"Video"**
3. Clic en **"Subir Video"**
4. Se abre widget de Cloudinary
5. Seleccionar video
6. Ver progreso en tiempo real
7. Una vez completado, guardar el formulario

## 📈 Mejores Prácticas

### Para  Videos en Premiere Pro

**Configuración recomendada:**
- Formato: **H.264**
- Preset: **YouTube 1080p HD**
- **Target Bitrate:** 3-5 Mbps (ajustar según contenido)
- **Maximum Bitrate:** 8-10 Mbps
- Resolución: 1920x1080 o 1280x720
- Audio Codec: **AAC**
- Audio Bitrate: **128 kbps**

**Resultado esperado (40 minutos de video):**
- Con 5 Mbps: ~1.5 GB
- Con 3 Mbps: ~900 MB

### Límites

**S3/MinIO (Documentos):**
- Tamaño recomendado: hasta 50 MB
- Sin timeout (subida rápida)
- Costo: bajo (Stackhero)

**Cloudinary (Videos):**
- Tamaño máximo: 1 GB por archivo
- Duración máxima: 60 minutos
- Plan gratuito: 10 GB almacenamiento total
- Monitorear uso mensual

## 🐛 Troubleshooting

### Error: "Upload preset not found"

**Solución:**
1. Verificar que el preset `clases_residentes_unsigned` existe en Cloudinary
2. Verificar que está configurado como "Unsigned"
3. Limpiar caché del navegador
4. Verificar en JavaScript que `CLOUDINARY_CLOUD_NAME` está definido

### Error: "Invalid signature"

**Solución:**
- Asegurarse de que el preset está en modo "Unsigned"
- NO usar signed uploads para este caso

### Video no se guarda al enviar formulario

**Solución:**
1. Abrir DevTools → Console
2. Verificar que `id_archivo_video_public_id` tiene valor
3. Verificar que el campo hidden `id_archivo_video` tiene el valor correcto
4. Enviar el formulario y verificar en logs de Django

### Timeout persiste

**Causas posibles:**
1. Estás usando el tab "Documento" con un video (usar tab "Video")
2. El archivo es demasiado grande (> 1 GB) - comprimir más
3. El upload preset no está configurado correctamente

## 📞 Soporte

**Si encuentras problemas:**

1. Revisar logs de Heroku:
   ```bash
   heroku logs --tail --app gestion-colegiales
   ```

2. Revisar logs de Cloudinary:
   - Dashboard → Media Library → Activity Log

3. Verificar en navegador (DevTools):
   - Console para errores de JavaScript
   - Network para ver peticiones a Cloudinary

## 🎓 Conceptos Aprendidos

### ¿Por qué este enfoque?

**Problema:** Heroku tiene un timeout de 30 segundos para peticiones HTTP.

**Solución tradicional (no funciona):**
```
Cliente → [90 seg subiendo] → Django → Storage
                                ↑
                            TIMEOUT!
```

**Nuestra solución (funciona):**
```
Cliente → Storage (directo)
       → Django solo recibe metadata (instantáneo)
```

### Ventajas de Cloudinary para Videos

1. **CDN Global:** Streaming rápido desde cualquier parte del mundo
2. **Transcodificación:** Convierte automáticamente a formatos web-optimizados
3. **Thumbnails:** Genera previews automáticos
4. **Adaptive Streaming:** Ajusta calidad según conexión del usuario
5. **Chunk Upload:** Sube archivos grandes en pedazos (manejo de fallos)

### ¿Por qué NO migrar documentos a Cloudinary?

1. **Costo:** Cloudinary es más caro para almacenamiento
2. **No es necesario:** Los PPT/PDF se suben rápido (5-10 seg)
3. **Ya funciona:** S3/MinIO está configurado y funcionando bien

## ✅ Checklist Post-Deploy

- [ ] Migración ejecutada sin errores
- [ ] Upload preset creado en Cloudinary
- [ ] Variables de entorno configuradas
- [ ] Probado subida de documento (PPT/PDF)
- [ ] Probado subida de video (MP4)
- [ ] Verificado que no hay errores H28
- [ ] Documentos existentes siguen accesibles
- [ ] Barra de progreso funciona correctamente

---

**Fecha de implementación:** 6 de marzo de 2026  
**Versión:** 1.0  
**Estado:** ✅ Listo para producción
