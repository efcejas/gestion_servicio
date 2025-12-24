# 📧 Paso 2: Configurar Gmail para Desarrollo

## ✅ Checklist Rápido

- [ ] Verificación en 2 pasos activada en Gmail
- [ ] App Password generada
- [ ] Archivo .env actualizado
- [ ] Test realizado

---

## 🔐 Obtener App Password de Gmail

### Opción A: Link Directo (Más Rápido) ⚡

**1. Ir directamente a App Passwords:**
   - 🔗 https://myaccount.google.com/apppasswords

**2. Si NO funciona ese link** (te pide verificación en 2 pasos):
   - 🔗 https://myaccount.google.com/security
   - Activa "Verificación en 2 pasos"
   - Luego vuelve al link de arriba

**3. Generar la contraseña:**
   - App: Selecciona "Mail"
   - Device: Selecciona "Windows Computer"
   - Click "Generate"
   - **COPIA** los 16 caracteres (ej: `abcd efgh ijkl mnop`)

---

## 📝 Actualizar tu archivo .env

Abre tu archivo `.env` y reemplaza estas líneas:

```env
# ========================================
# EMAIL - GMAIL REAL (Desarrollo)
# ========================================
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST_USER=tu_email@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
DEFAULT_FROM_EMAIL=tu_email@gmail.com
```

**⚠️ IMPORTANTE:**
- Reemplaza `tu_email@gmail.com` con tu email real
- Reemplaza `abcdefghijklmnop` con tu App Password (los 16 caracteres SIN espacios)
- NO uses tu contraseña normal de Gmail, usa la App Password

---

## 🧪 Probar que funciona

### Test 1: Script Simple

```bash
python test_email_simple.py
```

Esto intentará enviar un email real.

### Test 2: Flujo de Recuperación

1. Iniciar servidor:
   ```bash
   python manage.py runserver
   ```

2. Ir a: http://127.0.0.1:8000/password_reset/

3. Ingresar tu email (el de un usuario que exista)

4. Revisar tu bandeja de entrada (y spam)

5. Click en el enlace → cambiar contraseña

---

## 🐛 Solución de Problemas

### Error: "SMTPAuthenticationError"

**Causa:** Usuario o contraseña incorrectos

**Solución:**
1. Verifica que usaste tu App Password (16 caracteres)
2. Asegúrate de que NO hay espacios en la contraseña
3. Verifica que el email es correcto
4. Regenera la App Password si es necesario

### Error: "SMTPServerDisconnected"

**Causa:** Conexión bloqueada o configuración incorrecta

**Solución:**
1. Verifica tu conexión a internet
2. Algunos ISP o firewalls bloquean puerto 587
3. Intenta con WiFi diferente
4. Verifica que EMAIL_PORT=587 y EMAIL_USE_TLS=True

### Email no llega

**Solución:**
1. Revisa la carpeta de SPAM
2. Espera 1-2 minutos (a veces demora)
3. Verifica que el destinatario es un usuario válido en tu BD
4. Chequea los logs del servidor

### Error: "Less secure app access"

**Causa:** Gmail detectó intento sospechoso

**Solución:**
1. Usa App Password (no tu contraseña normal)
2. Si usas contraseña normal: https://myaccount.google.com/lesssecureapps
3. ⚠️ Mejor usar App Password (más seguro)

---

## 💡 Consejos

### Para Desarrollo:
- ✅ Usa tu email personal de Gmail
- ✅ Límite: 500 emails/día (más que suficiente)
- ✅ Gratis siempre

### Para Producción:
- ❌ NO usar Gmail (poco confiable en producción)
- ✅ Mejor usar SendGrid, Mailgun, o similar
- ✅ Más profesional y escalable

---

## 🎓 Conceptos Aprendidos

1. **EMAIL_BACKEND**
   - `console` → Muestra en terminal (testing)
   - `smtp` → Envía emails reales (producción)

2. **SMTP (Simple Mail Transfer Protocol)**
   - Es el protocolo estándar para enviar emails
   - Puerto 587 con TLS (conexión segura)

3. **App Password vs Contraseña Normal**
   - App Password: segura, solo para tu app
   - Contraseña normal: acceso completo a tu cuenta

4. **TLS (Transport Layer Security)**
   - Encripta la comunicación
   - Evita que alguien lea tus emails en tránsito

---

## 📊 Comparación de Backends

| Backend | Uso | Emails Reales | Necesita Config |
|---------|-----|---------------|-----------------|
| `console` | Testing | ❌ No | ❌ No |
| `filebased` | Testing | ❌ No | ⚠️ Ruta archivo |
| `smtp` | Producción | ✅ Sí | ✅ Sí |

---

## ✅ Siguiente Paso

Una vez que Gmail funcione en desarrollo:
- Paso 3: Configurar SendGrid para producción
- Paso 4: Desplegar a Heroku con email funcional

¿Listo para probar?
