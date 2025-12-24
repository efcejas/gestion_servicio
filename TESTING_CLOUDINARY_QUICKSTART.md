# 🧪 GUÍA RÁPIDA: Testing y Configuración Cloudinary

## ✅ PASO 1: Testing Manual (5 minutos)

El servidor ya está corriendo en: **http://localhost:8000/clases/**

### 1.1 Acceso al Sistema
1. ✅ Abre: http://localhost:8000/clases/
2. Si no estás logueado, te redirigirá a login
3. Inicia sesión con tu usuario médico/residente

### 1.2 Verificar Navegación
- ✅ Busca el enlace "Clases" en la barra de navegación (ícono 🎓)
- ✅ Haz clic y verás la lista de clases

### 1.3 Crear una Clase de Prueba SIN Cloudinary
1. Clic en **"Nueva Clase"**
2. Completa el formulario:
   - **Título:** "TEST - Anatomía Básica para R1"
   - **Descripción:** "Clase de prueba del sistema"
   - **Categoría:** Anatomía
   - **Fecha:** (hoy por defecto)
   - **Años dirigidos:** Marca ✓ R1
   - **Archivo:** ⚠️ DÉJALO VACÍO POR AHORA (sin Cloudinary no funcionará)
   - **Tags:** "test, anatomía, r1"
3. Clic en **"Publicar Clase"**
4. ✅ Debería crearse y redirigir a la lista

### 1.4 Verificar la Clase Creada
- ✅ Deberías ver la clase en la lista
- ✅ Haz clic en la clase para ver detalles
- ✅ Prueba agregar un comentario
- ✅ Prueba marcar como favorito (estrella amarilla)

### 1.5 Verificar "Mis Clases"
- ✅ Clic en "Mis Clases" (card morado)
- ✅ Deberías ver tu clase con estadísticas

### 1.6 Verificar "Favoritos"
- ✅ Clic en "Favoritos" (card amarillo)
- ✅ Deberías ver las clases que marcaste

---

## 🌩️ PASO 2: Configurar Cloudinary (10 minutos)

### 2.1 Crear Cuenta Gratis
1. Ve a: https://cloudinary.com/users/register_free
2. Completa el formulario:
   - Email: tu@email.com
   - First Name: Tu nombre
   - Last Name: Tu apellido
   - Password: (contraseña segura)
3. ✓ Acepta términos
4. Clic en **"Sign Up"**
5. Verifica tu email (revisa spam)
6. Haz clic en el enlace de verificación

### 2.2 Obtener Credenciales
1. Inicia sesión en Cloudinary
2. Serás redirigido al **Dashboard**
3. En la sección "Product Environment Credentials" verás:

```
Cloud name:     dxxxxxxxxxxxxx
API Key:        123456789012345
API Secret:     abcdefghijklmnopqrstuvwxyz
Secure URL:     ✓
```

**⚠️ IMPORTANTE:** 
- NO compartas el API Secret con nadie
- Copia estos 3 valores exactamente como aparecen

### 2.3 Configurar Variables de Entorno

1. **Busca el archivo `.env`** en la raíz del proyecto:
   ```
   C:\Dev\GitHub\gestion_servicio\.env
   ```

2. **Abre `.env` con un editor de texto**

3. **Agrega estas 3 líneas al FINAL del archivo:**
   ```bash
   # Cloudinary Configuration
   CLOUDINARY_CLOUD_NAME=dxxxxxxxxxxxxx
   CLOUDINARY_API_KEY=123456789012345
   CLOUDINARY_API_SECRET=abcdefghijklmnopqrstuvwxyz
   ```

4. **Reemplaza con tus valores reales** (los que copiaste del Dashboard)

5. **Guarda el archivo** (Ctrl+S)

### 2.4 Reiniciar el Servidor

1. En la terminal donde corre el servidor, presiona **Ctrl+C**
2. Vuelve a iniciar:
   ```bash
   python manage.py runserver
   ```
3. Ahora deberías ver:
   ```
   ✓ Cloudinary configurado correctamente
   ```
   En lugar de:
   ```
   ⚠ Cloudinary NO configurado - usando almacenamiento local
   ```

---

## 📤 PASO 3: Testing con Cloudinary (5 minutos)

### 3.1 Crear Clase con Archivo

1. Ve a: http://localhost:8000/clases/
2. Clic en **"Nueva Clase"**
3. Completa el formulario:
   - **Título:** "TEST - Radiología de Tórax"
   - **Descripción:** "Clase con archivo PPT de prueba"
   - **Categoría:** Radiología Simple
   - **Años dirigidos:** R1, R2
   - **Archivo:** 📎 **AHORA SÍ sube un archivo**
     * Soporta: .ppt, .pptx, .pdf
     * Máximo: 50 MB
   - **Tags:** "tórax, radiología, r1, r2"
4. Clic en **"Publicar Clase"**

### 3.2 Verificar Upload Exitoso

✅ Si Cloudinary está bien configurado:
- La clase se crea sin errores
- Puedes ver el archivo subido
- El enlace del archivo funciona
- Aparece un thumbnail (si subiste imagen)

❌ Si hay error:
- Revisa que las credenciales sean correctas
- Verifica que no haya espacios extra en `.env`
- Asegúrate de haber reiniciado el servidor

### 3.3 Verificar en Cloudinary Dashboard

1. Ve a tu Dashboard de Cloudinary
2. En el menú lateral: **Media Library** → **Assets**
3. Deberías ver tu archivo en la carpeta:
   ```
   clases_residentes/archivos/
   ```

---

## 🐛 TROUBLESHOOTING

### Problema 1: "No module named 'cloudinary'"
**Solución:**
```bash
pip install cloudinary django-cloudinary-storage
```

### Problema 2: "Cloudinary NO configurado"
**Causas:**
- Credenciales incorrectas en `.env`
- Espacios extra en los valores
- No reiniciaste el servidor

**Solución:**
1. Verifica `.env` línea por línea
2. NO uses comillas en los valores:
   ```bash
   ❌ CLOUDINARY_CLOUD_NAME="dxxxxx"    # MAL
   ✅ CLOUDINARY_CLOUD_NAME=dxxxxx      # BIEN
   ```
3. Reinicia: Ctrl+C → `python manage.py runserver`

### Problema 3: Error 401 al subir archivo
**Causa:** API Secret incorrecto

**Solución:**
1. Ve al Dashboard de Cloudinary
2. Copia nuevamente el API Secret
3. Actualiza `.env`
4. Reinicia servidor

### Problema 4: No puedo crear clases
**Causa:** Usuario sin permisos

**Solución:**
1. Ve al Django Admin: http://localhost:8000/admin/
2. Busca tu usuario en "Usuarios"
3. Edita y asegúrate que:
   - `rol` = "medico_residente" (o superior)
   - `anio_residencia` = "R1" (si eres residente)
4. Guarda cambios

### Problema 5: No veo ninguna clase
**Causa:** Filtrado por año de residencia

**Solución:**
- Si eres R1, solo verás clases dirigidas a R1
- Las clases sin años dirigidos son visibles para todos
- Jefes/Instructores ven TODAS las clases

---

## ✅ CHECKLIST FINAL

### Sin Cloudinary (Almacenamiento Local)
- [ ] Servidor corriendo sin errores
- [ ] Puedo acceder a /clases/
- [ ] Puedo crear clase (sin archivo)
- [ ] Puedo agregar comentarios
- [ ] Puedo marcar favoritos
- [ ] Veo "Mis Clases"
- [ ] Veo "Favoritos"

### Con Cloudinary (Producción)
- [ ] Cuenta Cloudinary creada
- [ ] Credenciales copiadas del Dashboard
- [ ] Variables agregadas a `.env`
- [ ] Servidor reiniciado
- [ ] Mensaje "✓ Cloudinary configurado"
- [ ] Puedo subir archivo PPT/PDF
- [ ] Archivo aparece en Cloudinary Media Library
- [ ] Puedo descargar el archivo desde la clase

---

## 📊 COMANDOS ÚTILES

### Ver logs en tiempo real:
```bash
# En la terminal donde corre el servidor
# Verás cada request y posibles errores
```

### Crear usuario de prueba:
```bash
python manage.py createsuperuser
```

### Verificar migraciones:
```bash
python manage.py showmigrations clases_residentes
```

### Verificar datos en DB:
```bash
python manage.py shell
>>> from clases_residentes.models import ClaseResidente
>>> ClaseResidente.objects.count()  # Ver cuántas clases hay
>>> ClaseResidente.objects.all()    # Ver todas las clases
```

---

## 🎯 RESULTADOS ESPERADOS

### Después de Testing Básico:
- ✅ 1-2 clases de prueba creadas
- ✅ Sistema de navegación funcionando
- ✅ Comentarios y favoritos operativos

### Después de Configurar Cloudinary:
- ✅ Archivos subidos a la nube
- ✅ URLs de archivos seguras (https://)
- ✅ Thumbnails generados automáticamente
- ✅ Sistema listo para producción

---

## 📞 ¿Necesitas Ayuda?

Si algo no funciona:

1. **Revisa la terminal:** Los errores aparecen ahí
2. **Verifica el navegador:** Abre la consola (F12) → Console
3. **Revisa el checklist:** ¿Completaste todos los pasos?
4. **Lee el error completo:** No solo la última línea

---

## 🚀 Próximos Pasos

Una vez que todo funcione:

1. **Eliminar clases de prueba:**
   - Ve a Django Admin
   - Busca "Clases de Residentes"
   - Elimina las clases TEST

2. **Crear clases reales:**
   - Sube PPTs reales
   - Organiza por categorías
   - Asigna años correctamente

3. **Capacitar usuarios:**
   - Muestra el sistema a residentes
   - Explica cómo subir clases
   - Fomenta el uso de comentarios

4. **Deploy (opcional):**
   - Sigue las instrucciones en SETUP_CLASES_RESIDENTES.md
   - Configura Cloudinary en Heroku
   - Ejecuta migraciones en producción

---

**¡Sistema listo! 🎉**
