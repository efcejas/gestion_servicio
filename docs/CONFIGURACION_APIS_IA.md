# 🔑 Configuración de APIs de IA para Sistema de Dictado

Este documento explica cómo configurar las APIs de inteligencia artificial necesarias para el sistema de dictado de informes médicos.

---

## 📋 Resumen

El sistema utiliza **2 APIs de IA**:
1. **OpenAI Whisper** - Transcripción de audio (Speech-to-Text)
2. **OpenAI GPT-4o-mini** - Mejora de texto con IA (Language Model)

**Fallback gratuito:** Groq (Llama 3.3-70b) está disponible como alternativa gratuita para la mejora de texto.

---

## 💰 Costos Estimados

### OpenAI (Recomendado - Mejor Calidad)
- **Whisper (STT):** $0.006 por minuto de audio
- **GPT-4o-mini (LLM):**
  - Input: $0.15 por 1M tokens
  - Output: $0.60 por 1M tokens
  
**Ejemplo de uso típico:**
```
1 informe promedio:
├─ Audio: 2 minutos → $0.012
├─ Mejora texto: ~1000 tokens → $0.0003
└─ Total: ~$0.012 USD por informe

30 informes/día (volumen alto):
├─ Mensual: ~$11 USD
└─ Con $5 gratis iniciales → primeros 400 informes gratis
```

### Groq (Alternativa Gratuita)
- **LLM:** GRATIS
- **Límites:**
  - 14,400 requests/día
  - 30 requests/minuto
  - 20,000 tokens/minuto

> ⚠️ **Nota:** Groq NO tiene Whisper. Necesitás OpenAI obligatoriamente para transcripción de audio.

---

## 🚀 Setup Paso a Paso

### Opción A: Solo OpenAI (Recomendado para producción)

#### 1. Crear cuenta en OpenAI

Ve a https://platform.openai.com/signup y crea una cuenta.

#### 2. Obtener API Key

1. Accede a https://platform.openai.com/api-keys
2. Click en "Create new secret key"
3. Copiá la key (empieza con `sk-proj-...`)
4. ⚠️ **Importante:** Guardala en un lugar seguro, solo se muestra una vez

#### 3. Agregar créditos (si no tenés saldo gratuito)

1. Ve a https://platform.openai.com/account/billing
2. Click en "Add payment method"
3. Agrega método de pago
4. (Opcional) Configura límite de gasto mensual para evitar sorpresas

> 💡 **Tip:** Las cuentas nuevas reciben $5 USD de crédito gratuito (válido 3 meses)

#### 4. Configurar en el proyecto

Edita tu archivo `.env` (en la raíz del proyecto):

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

#### 5. Verificar configuración

```bash
python manage.py shell
```

```python
from dictado_informes.ai_services import AIService

ai = AIService()
print(ai.get_api_info())
# Debería mostrar:
# {
#   'provider': 'openai',
#   'model': 'gpt-4o-mini',
#   'enabled': True,
#   'fallback': None
# }
```

---

### Opción B: OpenAI + Groq (Máximo ahorro)

Usa OpenAI para Whisper (transcripción) y Groq GRATIS para mejora de texto.

#### 1. Crear cuenta en Groq

Ve a https://console.groq.com/playground y crea cuenta.

#### 2. Obtener API Key de Groq

1. Click en tu perfil → "API Keys"
2. "Create API Key"  
3. Copiá la key (empieza con `gsk_...`)

#### 3. Configurar ambas APIs

Edita tu `.env`:

```bash
# OpenAI (solo Whisper para transcripción)
OPENAI_API_KEY=sk-proj-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Groq (gratis para mejora de texto)
GROQ_API_KEY=gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

#### 4. Verificar configuración

```python
from dictado_informes.ai_services import AIService

ai = AIService()
info = ai.get_api_info()
print(f"Provider: {info['provider']}")  # Debería ser 'openai' (prioritario)
print(f"Fallback: {info['fallback']}")  # Debería ser 'Groq (gratis)'
```

> ✅ **Ventaja:** Si OpenAI falla o se queda sin créditos, el sistema automáticamente usa Groq para mejora de texto.

---

### Opción C: Solo Groq (Solo para pruebas)

⚠️ **Limitación:** NO funciona la transcripción de audio. Solo útil para probar mejora de texto manualmente.

```bash
# Solo Groq (transcripción deshabilitada)
GROQ_API_KEY=gsk_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

---

## 🧪 Testing de Configuración

### Test 1: Transcripción de Audio

```python
from dictado_informes.ai_services import AIService
from django.core.files.base import ContentFile

ai = AIService()

# Crear audio de prueba (mínimo 500 bytes)
with open('test_audio.webm', 'rb') as f:
    audio_file = ContentFile(f.read(), name='test.webm')
    
result = ai.transcribe_audio(audio_file)
print(result)
# Debería retornar: {'text': '...', 'confidence': 0.95, ...}
```

### Test 2: Mejora de Texto

```python
ai = AIService()

result = ai.improve_medical_text(
    texto_original="menisco roto, rodila derecha",
    tipo_estudio="RES",
    contexto={'modo': 'FIEL'}
)

print(result['texto_mejorado'])
# Debería corregir: "menisco roto, rodilla derecha"
```

---

## 🔧 Troubleshooting

### Error: "Insufficient Quota" (OpenAI)

**Causa:** Se agotaron los créditos.

**Solución:**
1. Ve a https://platform.openai.com/account/billing
2. Agrega método de pago
3. Recarga créditos ($10 mínimo recomendado)

---

### Error: "Rate Limit Exceeded" (Groq)

**Causa:** Superaste 30 requests/minuto.

**Solución:**
- El sistema reintentará automáticamente después de 1 minuto
- Si es frecuente, considera usar OpenAI que no tiene este límite

---

### Error: "API Key Invalid"

**Causa:** La API key es incorrecta o expiró.

**Solución:**
1. Verifica que copiaste la key completa (sin espacios)
2. Genera una nueva key si es necesaria
3. Actualiza el `.env` y reinicia el servidor:
   ```bash
   python manage.py runserver
   ```

---

### Whisper no funciona (Error 404 o "model_not_found")

**Causa:** Tu cuenta OpenAI no tiene acceso a Whisper o la key es inválida.

**Solución:**
1. Verifica que usás una API key de **plataforma** (no de ChatGPT Plus)
2. Confirma que tenés créditos disponibles
3. Prueba con:
   ```python
   import openai
   client = openai.OpenAI(api_key="tu_key")
   client.models.list()  # Debería listar "whisper-1"
   ```

---

### El sistema usa Groq en lugar de OpenAI

**Causa:** La variable `OPENAI_API_KEY` no está configurada o es inválida.

**Comportamiento:** El sistema prioriza OpenAI, pero si no está disponible usa Groq.

**Verificación:**
```python
from dictado_informes.ai_services import AIService
ai = AIService()
print(ai.llm_provider)  # Debería ser 'openai' (deseado)
```

---

## 📊 Monitoreo de Uso

### Ver costos en OpenAI

1. https://platform.openai.com/usage
2. Filtra por fecha y modelo
3. Exporta CSV para análisis detallado

### Ver requests de Groq

1. https://console.groq.com/usage
2. Dashboard muestra requests/día y límites

### Ver métricas internas del sistema

```python
from dictado_informes.models import MetricaDictado

# Total de transcripciones este mes
count = MetricaDictado.objects.filter(
    fecha_creacion__month=3,
    api_transcripcion='whisper'
).count()

print(f"Transcripciones este mes: {count}")
```

---

## 🔐 Seguridad

### ✅ Buenas Prácticas

1. **Nunca commitear el .env:**
   - Asegurate que `.env` esté en `.gitignore`
   - Usa variables de entorno en producción

2. **Rotar keys periódicamente:**
   - Regenera las API keys cada 3-6 meses
   - Si sospechás que se filtraron, regeneralas inmediatamente

3. **Limitar scope de keys:**
   - OpenAI: Usa "project keys" en lugar de "user keys"
   - Configura permisos mínimos necesarios

4. **Configurar límites de gasto:**
   - OpenAI: Set "hard limit" mensual en billing
   - Groq: No tiene costos, pero monitorea rate limits

### ⚠️ Qué NO hacer

- ❌ Pushear `.env` a GitHub
- ❌ Compartir API keys por email/chat
- ❌ Hardcodear keys en el código
- ❌ Usar la misma key en dev y producción

---

## 🌐 Deploys (Heroku / Render / AWS)

### Configurar variables de entorno

#### Heroku
```bash
heroku config:set OPENAI_API_KEY=sk-proj-xxx
heroku config:set GROQ_API_KEY=gsk_xxx
```

#### Render
1. Dashboard → Environment
2. Add environment variable:
   - Key: `OPENAI_API_KEY`
   - Value: `sk-proj-xxx`

#### AWS Elastic Beanstalk
```bash
eb setenv OPENAI_API_KEY=sk-proj-xxx GROQ_API_KEY=gsk_xxx
```

---

## 🆘 Soporte

### Recursos Oficiales

- **OpenAI Docs:** https://platform.openai.com/docs
- **Groq Docs:** https://console.groq.com/docs
- **OpenAI Community:** https://community.openai.com

### Contacto Interno

Si tenés problemas técnicos con el sistema:
1. Revisá los logs: `logs/debug.log`
2. Verificá métricas en `/admin/dictado_informes/metricadictado/`
3. Contacta al equipo de desarrollo

---

## 📝 Changelog

- **2026-03-19:** Documento inicial creado (Fase 1 - Quick Wins)
