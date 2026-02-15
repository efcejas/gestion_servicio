# Guía Rápida de Inicio

## Sistema de Pedidos de Ecodoppler y Ecocardiogramas

Este sistema está diseñado para procesar automáticamente pedidos de:
- **Ecocardiogramas** (transtorácico, transesofágico)
- **Ecodoppler vascular** (carotídeo, renal, MMSS, MMII, arterial, venoso)

## Próximos pasos después de la instalación

### 1. Configurar credenciales de Gmail

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un proyecto nuevo
3. Habilita Gmail API
4. Crea credenciales OAuth 2.0 (aplicación de escritorio)
5. Descarga `credentials.json` y guárdalo en la raíz del proyecto

### 2. Probar la conexión

```bash
python manage.py shell
```

```python
from pedidos_estudios.services.gmail_service import verificar_configuracion_gmail
exito, mensaje = verificar_configuracion_gmail()
print(mensaje)
```

La primera vez se abrirá el navegador para autorizar. Se creará `token.json`.

### 3. Cargar tipos de estudio iniciales

**Opción A: Automático (Recomendado)**

Ejecuta el comando que carga 12 tipos de estudio predefinidos:

```bash
python manage.py cargar_tipos_estudio_inicial
```

Esto crea automáticamente:
- ✅ 3 tipos de ecocardiograma (TT, TE, Doppler color)
- ✅ 9 tipos de ecodoppler vascular (MMII, MMSS, carotídeo, renal, aorta, testicular, peneano)

Luego solo necesitas asignar médicos responsables desde: `/admin/pedidos_estudios/tipoestudio/`

**Opción B: Manual**

Si prefieres crear manualmente, accede al admin: `/admin/pedidos_estudios/tipoestudio/`

#### Ecocardiogramas:
- **Ecocardiograma Transtorácico**
  - Modalidad: US (Ecografía)
  - Tiempo estimado: 45 minutos
  - Requiere preparación: No
  
- **Ecocardiograma Transesofágico (TEE)**
  - Modalidad: US (Ecografía)
  - Tiempo estimado: 60 minutos
  - Requiere preparación: Sí (ayuno 6 horas)

#### Ecodoppler Vascular:
- **Ecodoppler Carotídeo** (tiempo: 30 min)
- **Ecodoppler de Miembros Inferiores** (tiempo: 40 min)
- **Ecodoppler de Miembros Superiores** (tiempo: 30 min)
- **Ecodoppler Arterial** (tiempo: 30 min)
- **Ecodoppler Venoso** (tiempo: 30 min)
- **Ecodoppler Renal** (tiempo: 30 min)

Asigna médicos responsables a cada tipo.

### 4. Ajustar el parser

Cuando recibas el **primer email real** de pedido de ecodoppler/ecocardio:

1. Cópialo completo (incluyendo headers si es posible)
2. Edita `services/email_parser.py`
3. Ajusta los patrones regex en `PATRONES` para que coincidan con tu formato

Ejemplo de texto esperado:
```
Paciente: Juan Pérez
DNI: 12345678
Habitación: 302A
Cama: 1
Estudio solicitado: Ecodoppler carotídeo bilateral
Médico: Dr. García
Indicación: Control post ACV
```
4. Prueba el parser:

```python
from pedidos_estudios.services.email_parser import extraer_informacion_basica

texto = """
# Pega aquí el contenido del email real
"""

datos = extraer_informacion_basica(texto)
print(datos)
```

### 5. Probar el procesamiento

```bash
# Modo prueba (no marca como leído)
python manage.py procesar_pedidos_email --no-marcar-leido --no-notificar

# Producción
python manage.py procesar_pedidos_email
```

### 6. Revisar resultados

- Ve al admin: `/admin/pedidos_estudios/`
- Revisa "Pedidos de Estudios" - deberían aparecer los nuevos
- Revisa "Logs de Procesamiento" - verás el detalle de cada email procesado

### 7. Configurar automatización

**Opción A: Cron** (simple)

```bash
crontab -e
```

Agregar:
```
*/15 * * * * cd /path/to/gestion_servicio && source gestion_env/bin/activate && python manage.py procesar_pedidos_email
```

**Opción B: Celery** (recomendado)

Ya tienes la estructura, solo necesitas configurar Celery Beat en tu proyecto.

---

## Troubleshooting Común

### Error: "Google API libraries not installed"

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Error: "credentials.json not found"

Asegúrate de tener el archivo en la ruta correcta especificada en `GMAIL_CONFIG['CREDENTIALS_FILE']`

### Error: "Invalid grant" o token expirado

Elimina `token.json` y vuelve a autenticar:

```bash
rm token.json
python manage.py shell
# ... ejecuta verificar_configuracion_gmail() de nuevo
```

### Los emails no se procesan correctamente

1. Revisa los logs: `/admin/pedidos_estudios/logprocesamientoemail/`
2. Mira el campo `errores` de cada log
3. Ajusta los patrones regex según los errores que veas

### Las notificaciones no llegan

1. Verifica que `DEFAULT_FROM_EMAIL` esté configurado
2. Verifica que los tipos de estudio tengan médicos o emails asignados
3. Revisa los logs de Django para errores de email

---

## Workflow típico

1. **Email llega** a `solicitudestudioscolegiales@gmail.com`
2. **Cron/Celery ejecuta** el comando cada 15 minutos
3. **Sistema procesa**:
   - Lee emails no leídos
   - Extrae información con regex
   - Crea/actualiza paciente
   - Crea pedido de estudio
   - Descarga adjuntos
   - Envía notificación al médico responsable
   - Marca email como leído
4. **Médico recibe** notificación con todos los datos
5. **Staff revisa** en el admin si necesita correcciones
6. **Sistema trackea** todo el ciclo de vida del pedido

---

¿Dudas? Revisa el [README.md](README.md) completo.
