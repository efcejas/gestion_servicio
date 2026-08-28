# Mejoras Dictado IA: plantillas flexibles, modo agente y aprendizaje

Fecha inicial: 2026-07-09

Ultima actualizacion: 2026-08-27

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

### Acentuacion obligatoria de encabezados

La salida final normaliza de forma deterministica los encabezados completos,
incluso cuando el modelo los devuelve en mayusculas sin tilde:

```text
INFORMACION CLINICA -> INFORMACIÓN CLÍNICA
DATOS CLINICOS      -> DATOS CLÍNICOS
TECNICA             -> TÉCNICA
CONCLUSION          -> CONCLUSIÓN
IMPRESION           -> IMPRESIÓN
DESCRIPCION         -> DESCRIPCIÓN
```

El guardrail solo modifica lineas que son encabezados completos; no reemplaza
palabras dentro del contenido clinico. Se aplica al proveedor principal y al
fallback. La clave de cache de mejora fue versionada para evitar reutilizar
resultados anteriores sin acentuacion.

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

## Motor de redaccion GPT-5.6 Terra

El motor OpenAI predeterminado para redactar informes es `gpt-5.6-terra`, con
esfuerzo de razonamiento `low` para equilibrar coherencia y latencia. La
transcripcion de audio continua separada y no cambia con esta configuracion.

Variables de entorno:

```env
OPENAI_LLM_MODEL=gpt-5.6-terra
OPENAI_LLM_FALLBACK_MODEL=gpt-4.1-mini
OPENAI_LLM_REASONING_EFFORT=low
```

Si Terra no esta habilitado para la cuenta o una llamada falla, el sistema
reintenta el mismo pedido con `gpt-4.1-mini`. Si tambien falla y Groq esta
configurado, utiliza `llama-3.3-70b-versatile` como tercer nivel.

Rollback inmediato sin codigo:

```env
OPENAI_LLM_MODEL=gpt-4.1-mini
```

La cache incluye modelo y esfuerzo de razonamiento en su clave. Cada
`TrazaAgenteDictado` registra `modelo_ia` para comparar calidad, latencia y
correcciones manuales por modelo.

## Trazabilidad de decisiones del agente

Se agrego `TrazaAgenteDictado` para poder auditar por que el agente eligio una
plantilla y que controles se aplicaron. La traza registra:

- usuario, fecha y duracion;
- region y lateralidad detectadas;
- cinco mejores plantillas candidatas y sus puntajes;
- puntaje ganador, margen y confianza del selector;
- guardrails aplicados, necesidad de confirmacion y posible invencion;
- resultado exitoso o error.

Por privacidad no almacena el dictado ni el informe completo. Conserva solamente
la longitud de entrada y una huella SHA-256 irreversible para correlacion tecnica.
Las trazas son de solo lectura en Django Admin y se generan exclusivamente en
modo `AGENTE`.

### Selector hibrido con activacion gradual

El selector `hibrido_v1` calcula una segunda recomendacion y puede tomar control
solo cuando alcanza confianza alta, supera el puntaje minimo y no detecta
contradicciones explicitas. Combina:

- filtro obligatorio de compatibilidad anatomica;
- similitud de tokens con nombre, titulo, tecnica, comentarios y guia de estilo;
- similitud textual con nombre y titulo;
- prioridad moderada para plantillas propias del usuario.

La extraccion de contexto separa:

- modalidad (`RES`, `TOM`, `RAD`, `ECO`);
- region anatomica explicita;
- region inferida desde el dato clinico;
- lateralidad del estudio y lateralidad de la indicacion clinica;
- conflictos entre regiones o modalidades explicitas.

Una region mencionada directamente tiene prioridad sobre la inferida. Por
ejemplo, en "gonalgia derecha, resonancia de ambas caderas", el estudio se
clasifica como caderas bilateral y conserva "Gonalgia derecha" como informacion
clinica.

Si el hibrido no cumple todas las condiciones, continua el selector legacy. La
traza conserva ambas recomendaciones, la plantilla realmente usada, el origen
de la seleccion y cualquier conflicto de contexto.

### Confirmacion humana para selecciones inciertas

El modo agente separa seleccion y generacion cuando la decision no es segura:

- confianza alta, puntaje suficiente y sin conflictos: genera automaticamente;
- confianza media o baja: propone hasta tres candidatas;
- desacuerdo relevante entre selector legacy e hibrido: propone candidatas;
- conflicto de region o modalidad: exige eleccion del usuario;
- sin coincidencia clara: permite elegir entre todas las plantillas visibles.

La primera llamada a `/api/mejorar-texto/` devuelve
`requiere_seleccion_plantilla=true` y no invoca el LLM de redaccion. La interfaz
muestra candidatos combinados por posicion y consenso, sin presentar sus scores
como porcentajes porque los dos selectores usan escalas diferentes.

Al elegir una opcion, el frontend repite la solicitud con:

```json
{
  "plantilla_confirmada_codigo": "CODIGO_VISIBLE"
}
```

El servidor vuelve a validar que la plantilla este activa y visible. La traza
final registra `origen_seleccion=usuario_confirmada`, la plantilla elegida y los
rankings legacy e hibrido. Esto permite calibrar posteriormente desacuerdos y
preferencias sin almacenar texto clinico.

Configuracion:

```env
DICTADO_SELECTOR_HIBRIDO_ACTIVO=True
DICTADO_SELECTOR_HIBRIDO_SCORE_MINIMO=45.0
DICTADO_SELECTOR_HIBRIDO_SOMBRA=True
DICTADO_SELECTOR_CONFIRMACION_ACTIVA=True
```

Rollback inmediato al selector anterior:

```env
DICTADO_SELECTOR_HIBRIDO_ACTIVO=False
DICTADO_SELECTOR_CONFIRMACION_ACTIVA=False
```

### Etapa de calibracion en produccion

Durante esta etapa el usuario puede utilizar el agente normalmente. Se recomienda
continuar reuniendo informes variados, especialmente de regiones con plantillas
similares. El selector hibrido solo modifica la plantilla utilizada cuando entra
en el carril de alta confianza; los demas casos conservan el flujo anterior.

Para el analisis posterior se necesitan solamente datos agregados de
`TrazaAgenteDictado`:

- porcentaje de coincidencia entre selector activo y selector en sombra;
- desacuerdos por region;
- distribucion de margenes y niveles de confianza;
- pares de plantillas que compiten con frecuencia;
- casos marcados con error, posible invencion o confirmacion requerida.

El asistente de desarrollo no tiene acceso automatico a produccion. Estos datos
deben compartirse mediante una exportacion anonimizada, una consulta de resumen
o un panel administrativo. La traza no almacena el dictado ni el informe.

## Evaluacion y memoria versionada

Se agrego una capa de aprendizaje observable que convive con
`CorreccionAprendizaje`, `FeedbackCalidadDictado` y `TrazaAgenteDictado`.

Modelos nuevos:

- `EventoAprendizajeDictado`: registra decisiones no clinicas como plantilla
  confirmada, correccion por voz aplicada o deshecha, feedback y correccion manual;
- `PreferenciaAprendidaDictado`: consolida patrones por usuario, categoria y
  contexto, conservando version, evidencia, confianza y estado.

La bitacora nueva no copia dictados, instrucciones ni informes. Solo guarda
codigos de plantilla, contexto anatomico normalizado, tipos de operacion y
metricas agregadas.

Politica inicial para seleccion de plantilla:

1. Una eleccion confirmada crea evidencia para la combinacion exacta de region,
   modalidad y lateralidad.
2. La memoria nace como `candidata`.
3. Se activa con al menos tres confirmaciones y 75% de consistencia.
4. Una preferencia activa prioriza esa plantilla cuando el selector vuelve a
   pedir confirmacion humana; no reemplaza una seleccion automatica de alta
   confianza ni elimina el modal de confirmacion.
5. Si el patron ganador cambia, la preferencia anterior queda como
   `reemplazada` y se crea una version nueva.

Las correcciones de terminologia, orden, estructura y conclusion quedan por ahora
como evidencia categorizada. No se convierten automaticamente en reglas de texto
hasta contar con volumen suficiente y validacion contra falsos aprendizajes.

El dashboard `/dictado_informes/metricas/` muestra:

- selecciones de plantilla confirmadas y coincidencia con la sugerencia;
- correcciones por voz y porcentaje deshecho;
- memoria activa y candidata;
- selecciones corregidas por el usuario;
- historial reciente de preferencias con version y evidencia.

Desde el admin se pueden auditar los eventos y desactivar una preferencia sin
borrar su historial.

### Panel personal y aislamiento por plantilla

Se agrego `/dictado_informes/mi-memoria/` para usuarios habilitados del modulo.
El panel permite:

- ver preferencias activas, candidatas y pausadas;
- revisar evidencia agregada de terminologia, orden y otras categorias;
- consultar versiones reemplazadas;
- pausar o reactivar una preferencia fuerte propia.

Una pausa manual prevalece sobre la consolidacion automatica: nueva evidencia
actualiza los contadores, pero no reactiva la regla sin intervencion del usuario.
El usuario no puede modificar memoria ajena ni borrar el historial.

`CorreccionAprendizaje` ahora registra tambien:

- `modo_dictado`;
- `tipo_plantilla`;
- `region`;
- `modalidad`;
- `lateralidad`.

Los ejemplos, preferencias de terminologia y ejemplos de estilo usados por el
LLM se filtran por `tipo_plantilla`. Las correcciones historicas sin contexto no
se inyectan en una plantilla especifica, evitando mezclar estilos entre regiones.
La clave de cache de generacion incluye tambien la plantilla y se invalida al
guardar una correccion contextualizada.

Los umbrales se pueden calibrar sin desplegar codigo:

```env
DICTADO_MEMORIA_CONFIRMACIONES_MINIMAS=3
DICTADO_MEMORIA_CONFIANZA_MINIMA=0.75
```

## Ontologia anatomica explicita

La relacion entre conjuntos y subestructuras dejo de depender de listas
repetidas dentro de los guardrails. La fuente unica inicial vive en:

```text
dictado_informes/anatomy_ontology.py
```

Conjuntos incluidos en la primera version:

- meniscos: interno/medial y externo/lateral;
- ligamentos cruzados: anterior/LCA y posterior/LCP;
- manguito rotador: supraespinoso, infraespinoso, subescapular y redondo menor;
- parenquima cerebral: sustancia gris y sustancia blanca, con disparadores
  lobares para lesiones focales.

Cada grupo define region, sinonimos, componentes, orden y frase residual. La
ontologia se usa para:

- reemplazar una normalidad del conjunto cuando un componente esta patologico;
- describir el componente restante o generar una frase `Resto de...`;
- insertar esa normalidad residual inmediatamente debajo del hallazgo relacionado;
- aportar al LLM solo las relaciones anatomicas relevantes para el dictado y la plantilla;
- dar el mismo contexto anatomico a la correccion por voz;
- reutilizar sinonimos estructurales en el detector de posibles invenciones.

La deteccion exige patologia y anatomia dentro del mismo segmento. Una mencion
normal de una estructura no se interpreta como afectacion. Las lineas que hablan
de un unico componente tampoco se confunden con una normalidad de todo el grupo.

Tests especificos:

```text
dictado_informes/tests/test_anatomy_ontology.py
```

Migracion:

```text
dictado_informes/migrations/0022_correccionaprendizaje_lateralidad_and_more.py
```

## Frontend

Archivo principal:

```text
templates/dictado_informes/dictado_rapido_whisper.html
```

Cambios relevantes:

- modo `AGENTE` visible segun feature flag;
- muestra plantilla sugerida por el agente;
- solicita eleccion entre candidatas cuando la seleccion es incierta;
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
dictado_informes/tests/test_aprendizaje_estructurado.py
dictado_informes/tests/test_anatomy_ontology.py
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
- activacion conservadora y versionado de memoria de seleccion;
- registro no clinico de correcciones por voz, deshacer y feedback;
- panel de metricas y priorizacion de memoria dentro de la confirmacion humana.

Suites verificadas durante el desarrollo:

```bash
python manage.py test dictado_informes.tests.test_template_importer dictado_informes.tests.test_plantilla_estructura_flexible dictado_informes.tests.test_ai_guardrails dictado_informes.tests.test_apis dictado_informes.tests.test_piloto_dictado dictado_informes.tests.test_aprendizaje
```

Ultima verificacion reportada:

```text
119 tests focalizados OK (ontologia, aprendizaje, APIs, guardrails y piloto de dictado).
```

Migraciones:

```bash
python manage.py makemigrations --check --dry-run dictado_informes
```

Resultado:

```text
No changes detected in app 'dictado_informes'
```

## Correccion conversacional del borrador

El dictado rapido permite corregir el informe generado sin volver a ejecutar el selector de plantillas.

Flujo de usuario:

1. Seleccionar opcionalmente un fragmento en el editor.
2. Presionar `Corregir por voz` y dictar una instruccion puntual.
3. Revisar o editar la transcripcion de la instruccion.
4. Presionar `Aplicar correccion`.
5. Usar `Deshacer correccion` si el resultado no es el esperado.

La voz se transcribe con el endpoint Whisper existente. La edicion usa:

```text
POST /dictado_informes/api/corregir-borrador/
```

Payload:

```json
{
  "texto_actual": "informe visible en el editor",
  "instruccion": "cambia derrame leve por moderado",
  "fragmento_objetivo": "Derrame articular leve."
}
```

El LLM no devuelve un informe nuevo. Devuelve operaciones JSON de tipo:

- `reemplazar`;
- `eliminar`;
- `insertar_antes` / `insertar_despues`;
- `mover_antes` / `mover_despues`.
- `agregar_al_final` para una seccion nueva solicitada explicitamente.

Guardrails del servidor:

- aplica operaciones solo sobre fragmentos exactos y unicos del borrador;
- rechaza objetivos inexistentes o ambiguos;
- limita la cantidad de operaciones por solicitud;
- solo permite crear segmentos cuando la instruccion pide agregar, incluir, crear o generar una seccion;
- al crear una conclusion, el prompt exige usar solo patologias ya presentes y omitir normalidades;
- evita duplicar una seccion que ya existe;
- rechaza reemplazos amplios y resultados que reescriben demasiado contenido;
- no ejecuta seleccion de plantilla ni el flujo completo del agente;
- ante cualquier error devuelve el borrador sin modificar;
- la conversion para NetTerm no participa de este flujo ni del aprendizaje.

El aprendizaje conserva el comportamiento previo: si la correccion por voz cambia el informe, al copiar se puede confirmar el guardado usando el texto clinico normal del editor.

### Sesion clinica continua

La correccion del borrador ahora mantiene una sesion temporal en el navegador:

- conserva las acciones aplicadas y deshechas mientras se trabaja sobre el informe;
- permite multiples niveles de deshacer y rehacer;
- reconoce por voz `deshace lo ultimo` y `rehace` como comandos de sesion;
- envia al editor IA las ultimas cinco acciones para resolver referencias como
  `eso`, `esa linea` o `el hallazgo anterior`;
- reinicia la sesion cuando se genera o recupera otro informe.

Cada accion conserva en memoria del navegador el texto anterior y posterior. El
contenido clinico de esas versiones no se persiste en la base de datos. La
bitacora del servidor mantiene solo metadatos no clinicos y registra por separado
aplicar, deshacer y rehacer.

Cuando la IA no puede localizar un objetivo unico, devuelve una pregunta de
aclaracion y no modifica el editor. La respuesta del usuario puede aprovechar la
pregunta y las acciones recientes como contexto de la siguiente orden.

Cuando una propuesta contiene cuatro o mas operaciones, modifica una proporcion
relevante del informe o el modelo la clasifica como amplia, se muestra una vista
de confirmacion. La propuesta:

- se aplica primero contra los guardrails exactos del servidor;
- no modifica el editor ni genera aprendizaje hasta ser confirmada;
- al confirmarse vuelve a validarse sin una segunda llamada al LLM;
- se descarta si el borrador cambio mientras estaba pendiente.

La confirmacion no habilita reescrituras completas: cada operacion debe seguir
apuntando a fragmentos exactos y unicos del borrador.

Migracion asociada:

```text
dictado_informes/migrations/0023_alter_eventoaprendizajedictado_tipo_evento.py
```

Agrega el evento no clinico `correccion_voz_rehecha`.

## Commits relevantes

```text
65292d12 Mejora dictado inteligente y plantillas flexibles
6be1e56b Refuerza agente dictado y aprendizaje de estilo
1cdd6430 Evita mezclar regiones en agente dictado
```

## Riesgos conocidos

- La cobertura explicita de regiones aun debe ampliarse segun la casuistica real.
- Las plantillas con titulos muy genericos pueden competir peor que plantillas especificas.
- El aprendizaje de orden usa similitud textual; si el usuario reescribe completamente una linea movida, puede no detectarla como la misma linea.
- La sesion conversacional vive en memoria del navegador; al recargar la pagina se reinicia de forma intencional para no persistir contenido clinico.
- La opcion `Estructurar con IA` depende de API LLM; si falla, usa fallback local.

## Pendientes recomendados

1. Calibrar el puntaje minimo del selector hibrido con trazas de produccion.
2. Calibrar el umbral de activacion de memoria con decisiones reales.
3. Promover terminologia y orden a reglas estructuradas solo despues de evaluarlas offline.
4. Sumar regiones adicionales segun casuistica real: pelvis, abdomen, torax, cuello, pie.
5. Evaluar una vista de diferencias linea por linea si la casuistica muestra que el resumen de propuestas amplias no alcanza.

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
  "selector_origen": "legacy|hibrido_alta|fallback",
  "contexto_clinico": {
    "region": "...",
    "region_fuente": "explicita|inferida",
    "modalidad": "RES|TOM|RAD|ECO",
    "lateralidad": "...",
    "conflicto_region": false
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
