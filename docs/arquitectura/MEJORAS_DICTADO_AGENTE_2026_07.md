# Mejoras Dictado IA: plantillas flexibles, modo agente y aprendizaje

Fecha: 2026-07-09

Este documento resume el bloque de mejoras implementadas para evolucionar el dictado inteligente desde un generador con plantillas hacia un agente asistido por voz, manteniendo fallback seguro al flujo de plantilla estructurada.

## Objetivo

El objetivo funcional fue permitir que el medico pueda dictar en lenguaje natural, por ejemplo:

```text
Paciente con gonalgia derecha y desgarro del ligamento cruzado anterior.
```

y que el sistema:

- seleccione la plantilla mas compatible;
- complete lateralidad e informacion clinica;
- respete la estructura original de la plantilla del usuario;
- reemplace lineas normales contradichas por hallazgos patologicos;
- ordene hallazgos nuevos cerca de la estructura anatomica correspondiente;
- evite inventar hallazgos;
- aprenda de correcciones manuales de texto, terminologia y ubicacion de lineas.

## Flujo actual

1. El usuario dicta o pega texto en Dictado Rapido.
2. El backend transcribe con Whisper cuando corresponde.
3. En modo `AGENTE`, el sistema analiza el dictado y extrae contexto clinico.
4. El selector deterministico busca la plantilla visible mas compatible para el usuario.
5. `AIService.improve_medical_text(...)` genera el informe con prompt estructurado.
6. Se aplican guardrails post-IA.
7. Si el usuario corrige el resultado y confirma aprendizaje al copiar, se guarda `CorreccionAprendizaje`.
8. Las siguientes generaciones reciben ejemplos y preferencias aprendidas del usuario.

## Importacion de plantillas

Se agrego importacion desde documento y texto pegado para que el usuario no tenga que cargar tantos campos manualmente.

Formatos soportados:

- `.docx`
- `.doc` basado en RTF
- `.txt`
- `.md` / `.markdown`
- `.rtf`
- `.html` / `.htm`
- texto pegado desde portapapeles

Archivo principal:

```text
dictado_informes/template_importer.py
```

La importacion:

- extrae parrafos;
- detecta encabezados como `TECNICA`, `HALLAZGOS`, `COMENTARIO`, `INFORME`, `CONCLUSION`;
- infiere tecnica si no hay encabezado explicito;
- separa hallazgos/comentarios base en lineas;
- genera `estructura_documento` en JSON;
- crea vista previa editable antes de guardar.

Tambien se agrego la opcion `Estructurar con IA`, que intenta clasificar el texto libre en:

```text
TITULO
INFORMACION CLINICA
TECNICA
COMENTARIO / HALLAZGOS
CONCLUSION
```

Si la IA falla o no esta configurada, el sistema cae al analisis local.

## Plantillas flexibles

Se agregaron campos para representar la estructura original de cada plantilla:

- `modo_estructura`
- `permitir_secciones_nuevas`
- `estructura_documento`

Migracion:

```text
dictado_informes/migrations/0016_plantilla_estructura_flexible.py
```

Modos disponibles:

- `legacy`: comportamiento historico, basado en titulo, tecnica y comentarios base.
- `estricta`: respeta exactamente las secciones importadas.
- `flexible`: respeta la estructura, pero permite mas adaptacion.
- `agente`: reservado para evolucion futura con confirmacion asistida.

La regla importante: si una plantilla importada no tiene conclusion, el agente no debe crear una conclusion salvo que la estructura lo permita.

## Modo agente

El modo agente se activa desde Dictado Rapido con `modo: AGENTE`.

Vista:

```text
dictado_informes/views.py
```

Servicio IA:

```text
dictado_informes/ai_services.py
```

El modo agente:

- extrae contexto clinico del dictado;
- sugiere plantilla;
- convierte el modo interno a `ESTRUCTURADO`;
- pasa `tipo_plantilla` y `contexto_clinico` a `AIService`;
- devuelve al frontend la plantilla sugerida y guardrails aplicados.

## Selector de plantilla

Funcion principal:

```text
sugerir_plantilla_para_dictado(...)
```

El selector analiza:

- tokens del dictado;
- codigo, nombre, titulo, tecnica y comentarios de cada plantilla;
- coincidencia por region anatomica;
- prioridad de plantillas del usuario;
- incompatibilidad entre regiones.

Regiones actualmente detectadas:

- `RODILLA`
- `HOMBRO`
- `CODO`
- `MANO`
- `MUNECA`
- `TOBILLO`
- `CADERA`
- `CEREBRO`
- `COLUMNA`

Correcciones importantes:

- Si el dictado detecta `CADERA`, una plantilla de `COLUMNA` no puede ganar.
- Si el dictado detecta `MANO`, una plantilla de `COLUMNA` no puede ganar.
- Se agregaron terminos como `pulgar`, `metacarpiano`, `risartrosis`, `trapeciometacarpiana` para evitar mezclar mano con columna.

## Contexto clinico y lateralidad

Funcion:

```text
extraer_contexto_clinico_dictado(...)
```

Extrae:

- `region`
- `lateralidad`
- `lado_tecnica`
- `titulo_lateralidad`
- `frase_lateralidad`
- `indicacion_clinica`

Ejemplos:

```text
gonalgia derecha
```

produce:

```json
{
  "region": "RODILLA",
  "lateralidad": "DERECHA",
  "lado_tecnica": "derecha",
  "indicacion_clinica": "Gonalgia derecha."
}
```

```text
coxalgia de ambas caderas
```

produce:

```json
{
  "region": "CADERA",
  "lateralidad": "BILATERAL",
  "titulo_lateralidad": "AMBAS CADERAS",
  "frase_lateralidad": "ambas caderas",
  "indicacion_clinica": "Coxalgia bilateral."
}
```

Guardrail agregado:

- Si el estudio es cadera bilateral, normaliza titulos como `RM DE CADERA BILATERAL` a `RM DE AMBAS CADERAS`.

## Guardrails post-IA

Los guardrails son defensas despues de la respuesta del modelo.

### Restauracion controlada de lineas normales

Funcion:

```text
_aplicar_guardrails_estructurado(...)
```

Responsabilidades:

- conservar lineas normales no mencionadas;
- no restaurar lineas normales contradichas por patologia;
- limpiar numeracion tipo `[1]`, `[2]`;
- insertar frases residuales debajo del hallazgo patologico relacionado;
- evitar duplicar lineas normales equivalentes.

Ejemplo:

Dictado:

```text
Desgarro del menisco interno.
```

Plantilla:

```text
Meniscos de altura y senal normales.
```

Salida esperada:

```text
Desgarro del menisco interno.
Menisco externo de altura y senal conservadas.
```

### Compatibilidad de region

Funcion:

```text
_plantilla_compatible_con_contexto(...)
```

Si el contexto detecta `MANO` y la plantilla cargada contiene terminos de `COLUMNA`, se omite la restauracion de lineas normales de esa plantilla.

Esto evita contaminacion como:

```text
Correcta alineacion en el plano sagital.
Cuerpos vertebrales y espacios discales de altura conservada.
```

en un informe de mano.

### Conclusion solo patologica

Funcion:

```text
_aplicar_guardrail_conclusion_patologica(...)
```

La conclusion no debe incluir estructuras normales si hay patologia.

Ejemplo antes:

```text
Desgarro del ligamento cruzado anterior en rodilla derecha con meniscos y resto de estructuras ligamentarias sin alteraciones.
```

Despues:

```text
Desgarro del ligamento cruzado anterior en rodilla derecha.
```

### No inventar salvo pedido explicito

El prompt ahora diferencia entre:

- dictado clinico habitual: no inventar hallazgos;
- pedido explicito de descripcion hipotetica: por ejemplo, "describi como seria un encondroma".

Solo en el segundo caso puede desarrollar una descripcion no literal.

## Aprendizaje del usuario

Modelo:

```text
CorreccionAprendizaje
```

El sistema ya guardaba diferencias entre:

- `texto_original`
- `texto_ia`
- `texto_final`

Se reforzo para aprender no solo palabras, sino tambien orden y ubicacion.

### Cambios aprendidos

El sistema detecta:

- reemplazos terminologicos;
- agregados;
- eliminaciones;
- conflictos plantilla-patologia;
- reordenamiento de lineas en `COMENTARIO` / `HALLAZGOS`.

Nuevo tipo:

```json
{
  "tipo": "reordenamiento_linea",
  "texto": "Desgarro del ligamento cruzado anterior.",
  "posicion_ia": 3,
  "posicion_final": 1,
  "categoria": "estructural_orden",
  "score": 88
}
```

### Memoria fuerte del usuario

Nuevo agregador:

```text
CorreccionAprendizaje.obtener_preferencias_aprendidas(...)
```

Genera una memoria compacta para prompt:

```text
ORDEN Y UBICACION APRENDIDOS:
- Ubicar "Desgarro del ligamento cruzado anterior." inmediatamente antes de "Ligamento cruzado posterior conservado."

TERMINOLOGIA APRENDIDA:
- Preferir "Meniscos de configuracion habitual" en lugar de "Meniscos normales".
```

En `AIService`, esa memoria se cachea con:

```text
_get_preferencias_aprendidas_cached(...)
```

y entra al prompt como `MEMORIA FUERTE DEL USUARIO`.

Regla de seguridad: aplicar preferencias solo si el dictado aporta el hallazgo correspondiente; no inventar hallazgos para satisfacer una preferencia.

## Feature flag del agente

Se agrego un kill switch para produccion:

```text
DICTADO_AGENTE_HABILITADO
```

Default:

```text
True
```

Para apagar modo agente sin rollback:

```env
DICTADO_AGENTE_HABILITADO=False
```

Efectos:

- oculta la opcion `Agente de informe` en UI;
- si alguien llama la API manualmente con `modo: AGENTE`, responde `403`;
- mantiene activos `FIEL` y `ESTRUCTURADO`.

## Frontend

Archivo principal:

```text
templates/dictado_informes/dictado_rapido_whisper.html
```

Cambios relevantes:

- modo `AGENTE` visible segun feature flag;
- muestra plantilla sugerida por el agente;
- muestra guardrails aplicados;
- guarda aprendizaje cuando el usuario corrige y confirma al copiar;
- mantiene flujo de copia con formato y texto plano.

Importacion:

```text
templates/dictado_informes/importar_plantilla_docx.html
```

Cambios relevantes:

- drag and drop de archivos;
- pegar desde portapapeles;
- checkbox `Estructurar con IA`;
- vista previa editable antes de guardar.

## Tests agregados/reforzados

Archivos principales:

```text
dictado_informes/tests/test_template_importer.py
dictado_informes/tests/test_plantilla_estructura_flexible.py
dictado_informes/tests/test_ai_guardrails.py
dictado_informes/tests/test_apis.py
dictado_informes/tests/test_aprendizaje.py
dictado_informes/tests/test_piloto_dictado.py
```

Casos cubiertos:

- importacion desde docx/txt/md/html/rtf/doc basado en RTF;
- texto pegado desde formulario;
- estructura flexible sin conclusion;
- modo agente con flag apagado;
- selector por rodilla/cadera/mano;
- no mezclar cadera con columna;
- no mezclar mano con columna;
- contexto de gonalgia derecha;
- contexto de ambas caderas;
- normalizacion de titulo `RM DE AMBAS CADERAS`;
- guardrails de conclusion patologica;
- limpieza de numeracion `[1]`;
- no duplicar lineas normales equivalentes;
- aprendizaje de reordenamiento de lineas;
- preferencias aprendidas por usuario.

Suites verificadas durante el desarrollo:

```bash
python manage.py test dictado_informes.tests.test_template_importer dictado_informes.tests.test_plantilla_estructura_flexible dictado_informes.tests.test_ai_guardrails dictado_informes.tests.test_apis dictado_informes.tests.test_piloto_dictado dictado_informes.tests.test_aprendizaje
```

Ultima verificacion reportada:

```text
94 tests OK
```

Migraciones:

```bash
python manage.py makemigrations --check --dry-run dictado_informes
```

Resultado:

```text
No changes detected in app 'dictado_informes'
```

## Commits relevantes

```text
65292d12 Mejora dictado inteligente y plantillas flexibles
6be1e56b Refuerza agente dictado y aprendizaje de estilo
1cdd6430 Evita mezclar regiones en agente dictado
```

## Riesgos conocidos

- El selector sigue siendo deterministico y basado en palabras clave; puede requerir agregar regiones/terminos nuevos segun uso real.
- Las plantillas con titulos muy genericos pueden competir peor que plantillas especificas.
- El aprendizaje de orden usa similitud textual; si el usuario reescribe completamente una linea movida, puede no detectarla como la misma linea.
- El modo `agente con confirmacion` esta modelado pero todavia no tiene una UI conversacional completa de aceptar/rechazar cambios por paso.
- La opcion `Estructurar con IA` depende de API LLM; si falla, usa fallback local.

## Pendientes recomendados

1. Crear UI para ver "memoria fuerte" activa por usuario.
2. Permitir desactivar una regla aprendida desde el admin o panel del usuario.
3. Registrar explicitamente `tipo_plantilla` y `modo_dictado` en `CorreccionAprendizaje`.
4. Agregar una tabla dedicada para reglas aprendidas versionadas si el aprendizaje crece.
5. Sumar regiones adicionales segun casuistica real: pelvis, abdomen, torax, cuello, pie.
6. Convertir `agente con confirmacion` en flujo real: propuesta, diferencias, aceptar/rechazar.

## Guia rapida de debug

### Ver plantilla sugerida por agente

La respuesta de `/dictado_informes/api/mejorar-texto/` incluye:

```json
{
  "plantilla_sugerida": {
    "codigo": "...",
    "nombre": "...",
    "score": 123
  },
  "tipo_plantilla_usada": "...",
  "contexto_clinico": {
    "region": "...",
    "lateralidad": "..."
  }
}
```

### Ver preferencias aprendidas

```python
from dictado_informes.models import CorreccionAprendizaje

print(CorreccionAprendizaje.obtener_preferencias_aprendidas(usuario=request.user))
```

### Ver ejemplos de aprendizaje

```python
print(CorreccionAprendizaje.obtener_ejemplos_aprendizaje(usuario=request.user))
```

### Apagar agente temporalmente

```env
DICTADO_AGENTE_HABILITADO=False
```

