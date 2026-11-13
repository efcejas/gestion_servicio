# MVP: crear plantilla inexistente en AGENTE

En el modal de selección (sin coincidencia o cuando ninguna candidata sirve), abrir
**Crear plantilla inexistente**, elegir región/modalidad, generar, revisar/editar
y confirmar explícitamente. Se crea una plantilla nueva activa, privada por defecto;
compartir es optativo con la misma política de la biblioteca. Se usa inmediatamente
por su código confirmado y queda disponible para futuros informes. Nunca se modifican
las referencias. No requiere migración.

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
`python manage.py test dictado_informes.tests.test_template_drafts`
