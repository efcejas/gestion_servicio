# MVP: crear plantilla inexistente en AGENTE

En el modal de selección (sin coincidencia o cuando ninguna candidata sirve), abrir
**Crear plantilla inexistente**, elegir región/modalidad, generar, revisar/editar
y confirmar explícitamente. Se crea una plantilla nueva activa, privada por defecto;
compartir es optativo con la misma política de la biblioteca. Se usa inmediatamente
por su código confirmado y queda disponible para futuros informes. Nunca se modifican
las referencias. No requiere migración.

## Estilo y edición personal

Antes de generar, **Preferencias de esta plantilla** permite elegir redacción breve
o descriptiva, frases separadas o párrafos por región anatómica, e indicaciones libres
de estilo (hasta 1000 caracteres). Se envían al generador: no pegar informes ni datos
de pacientes. Las líneas base siempre se presentan por separado para revisarlas.
La vista previa incluye una guía de estilo editable (hasta 2000 caracteres), que se
guarda en `guia_estilo` y se usa en futuros informes ESTRUCTURADOS/AGENTE con esa plantilla.
El estilo no modifica las restricciones clínicas ni las secciones. No se crean
preferencias globales; compartir la plantilla también comparte su guía.

En **Plantillas Estructuradas → Mis plantillas → Editar** se pueden adaptar nombre,
título, líneas normales y guía después de guardarla. No se exige inventar una técnica.
Al editar, los campos visibles y su sección JSON se sincronizan en ambos sentidos.
Si se cambian ambos con contenidos distintos, se muestra un error. Las estructuras
con varias secciones de hallazgos conservan su organización: su contenido se edita
en el JSON avanzado, no se aplana desde el campo de líneas normales.
Los cambios afectan futuros informes, no reescriben informes anteriores.

## Cambiar plantilla después de generar

Después de cada generación exitosa en AGENTE aparece **Cambiar plantilla** junto a
las opciones de copiado, incluso con selección automática de confianza alta.
Reutiliza el selector y permite elegir otra plantilla o crear una inexistente.
Antes de regenerar pide confirmación: usa el texto fuente de la generación original,
no el informe editado, y las ediciones manuales no se trasladan al nuevo resultado.
**Restaurar informe anterior** recupera el borrador con su formato, plantilla,
advertencias de confianza y estado de feedback. Se conserva una versión anterior.
Cancelar o fallar no reemplaza el borrador; si cambia durante la solicitud, la respuesta
no se aplica. Un nuevo dictado limpia este estado. El reintento exitoso en AGENTE también
habilita el botón. No hay copiado automático al cambiar de plantilla.

Los permisos y visibilidad se verifican en el mismo endpoint de mejora. La confirmación
previa por incertidumbre sigue siendo `usuario_confirmada`; el cambio posterior
explícito se audita como `usuario_cambio_post`. No requiere migración.

## Referencias y privacidad

- Sólo plantillas activas visibles al usuario; modalidad identificada en nombre/título
  primero y coincidencia anatómica después. Modalidades explícitamente distintas se excluyen.
- `Informe.plantilla_usada` apunta a `PlantillaInforme`, no a `PlantillaEstructurada`.
  `TrazaAgenteDictado.plantilla_seleccionada` audita decisiones/llamadas, no aceptación
  clínica final ni uso en informes firmados. **No se usa como frecuencia fiable**.
  Popularidad queda pendiente para una fase futura con una señal validada.
- El generador recibe catálogo cerrado de región/modalidad y nombres, títulos, líneas
  normales y encabezados de referencias; no recibe dictado, audio, aprendizaje ni pacientes.
  Las plantillas de biblioteca deben ser genéricas, sin datos de pacientes.
  También recibe las preferencias de redacción ingresadas explícitamente por el usuario.
- El catálogo anatómico del MVP incluye brazo y dedo además de las regiones ya listadas;
  la modalidad y región detectadas en el dictado se preseleccionan y el médico puede corregirlas.
  Sin referencias compatibles, no se genera: se pide crear manualmente desde la biblioteca.
- Usa el LLM configurado; fallback OpenAI configurado y luego Groq si está disponible.
  Los tests simulan proveedores, sin llamadas externas.

## Seguridad clínica y persistencia

El contrato permite únicamente nombre, título, líneas normales, técnica y conclusión
vacías. La estructura persistida es estricta: TITULO, COMENTARIO, CONCLUSION vacía,
sin secciones nuevas. Se valida nuevamente lo editado al confirmar. El título debe
conservar región/modalidad; se rechazan técnica, datos clínicos evidentes, duplicados,
afirmaciones patológicas y líneas sin expresión explícita de normalidad. Se aceptan
descripciones negativas claras, por ejemplo “sin lesiones” o “ausencia de lesiones”.
También se reconocen negaciones como “No se identifican adenopatías” y
“No se observa líquido libre”. Si el filtro no reconoce una expresión de normalidad,
la generación muestra el borrador con advertencias numeradas, en vez de descartarlo.
El médico puede reformular o eliminar esas líneas; el guardado conserva la validación
estricta. Técnica, datos clínicos evidentes y posibles afirmaciones patológicas siguen
bloqueando la generación y el guardado. Los filtros no certifican normalidad clínica.

No es una validación semántica médica exhaustiva: la IA puede proponer anatomía
inadecuada o normalidades no evaluables. El médico debe revisar **cada línea**.
Las líneas aprobadas pueden preservarse si no se mencionan en dictados posteriores,
igual que en las plantillas existentes: nunca interpretar silencio como constatación
clínica sin revisión del informe. No se agrega una técnica genérica.

Ambas acciones son POST con CSRF, login, permiso del módulo y flag AGENTE en backend.
La confirmación exige booleano explícito y token firmado del usuario (30 minutos).
Reintentar con el mismo token devuelve la plantilla ya creada, sin duplicarla ni editarla.
Si falla la mejora del informe tras guardar, la plantilla sigue disponible y el flujo
existente conserva el borrador/reintento. No se registra contenido del proveedor.

Pruebas:
`python manage.py test dictado_informes.tests.test_template_drafts dictado_informes.tests.test_plantilla_estructura_flexible dictado_informes.tests.test_apis dictado_informes.tests.test_piloto_dictado`
