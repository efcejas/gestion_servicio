# Guia de estilo UX

Estado: borrador vivo
Alcance: sistema web de gestion de diagnostico por imagenes

## Proposito

Esta guia define los patrones visuales y de interaccion que deben compartir los modulos. No reemplaza las reglas funcionales o de permisos de cada modulo.

## Principios

- La interfaz debe priorizar lectura rapida, claridad operativa y baja carga cognitiva.
- Las acciones principales deben ser visibles y consistentes; las acciones destructivas deben exigir confirmacion clara.
- La informacion clinica, administrativa y economica debe tener jerarquia visual distinta.
- La validacion debe ocurrir en backend y los errores deben aparecer junto al campo o accion que los provoca.
- Cada pantalla debe funcionar en desktop y mobile sin depender de hover.
- Preferir componentes reutilizables en `templates/components/` antes que repetir markup.

## Identidad visual actual

- Color primario: `#164569` (`medical-primary`).
- Color secundario: `#4b49c0` (`medical-secondary`).
- Exito: `#10b981`.
- Advertencia: `#f59e0b`.
- Error: `#ef4444`.
- Informacion: `#3b82f6`.
- Fondo claro: `#f8fafc`.
- Texto oscuro: `#0f172a`.
- Tipografia principal: `proxima-nova`, con fallback sans-serif.

Los colores deben consumirse mediante tokens `medical-*` o variables de tema. Evitar introducir colores hexadecimales nuevos directamente en templates.

## Layout

- Base operativa: `max-w-full px-4 sm:px-6 lg:px-10 py-4`.
- En portales centrados, usar `max-w-7xl mx-auto`.
- Separacion vertical habitual entre bloques: `gap-4`, `gap-6` o `space-y-6`.
- Las tablas y listados extensos deben permitir desplazamiento horizontal en mobile.
- No usar contenedores con altura fija cuando el contenido pueda crecer.

## Tipografia

- Titulos de pagina: una sola jerarquia principal, breve y orientada a la tarea.
- Subtitulos: describen el bloque, no repiten el titulo.
- Texto auxiliar: `text-sm` o `text-xs`, siempre con contraste suficiente.
- No usar mayusculas sostenidas para textos largos.
- Los mensajes de estado deben usar lenguaje directo: que ocurrio y que puede hacer el usuario.

## Botones y acciones

- Accion principal: fondo `medical-primary`, texto blanco, estado hover visible.
- Accion secundaria: fondo blanco, borde gris, texto `medical-primary`.
- Accion de exito: usar verde solo cuando confirme una operacion exitosa.
- Accion destructiva: usar rojo y confirmar antes de eliminar o cerrar datos sensibles.
- Incluir icono Font Awesome cuando ya exista el patron en el modulo; mantener texto visible en acciones importantes.
- Estados `disabled`, `focus` y carga deben ser perceptibles.

## Formularios

- Cada campo debe tener label visible y ayuda contextual solo cuando sea necesaria.
- Mantener una columna en mobile y agrupar campos relacionados en desktop.
- Mostrar errores server-side junto al campo y conservar los valores enviados.
- Para archivos, usar `request.FILES` y `multipart/form-data`; no confiar solo en `accept`.
- No usar placeholders como reemplazo del label.

### Filtros compactos para bandejas operativas

En listados con muchas opciones de filtrado, separar la búsqueda frecuente de
los filtros secundarios para reducir la carga visual.

Patrón recomendado:

1. Encabezado breve orientado a la tarea, por ejemplo `Buscar estudios`.
2. Bloque principal siempre visible con:
   - un único campo de búsqueda rápida;
   - rango de fechas próximo al campo principal;
   - texto auxiliar que explique el alcance de la búsqueda;
   - acciones alineadas a la derecha o al final del bloque.
3. Bloque `Filtros adicionales` plegable mediante `<details>` y `<summary>`
   para estado, tipo, región, sistema, profesional u otros criterios menos
   frecuentes.
4. Acciones finales consistentes:
   - `Aplicar filtros` como acción secundaria destacada;
   - `Limpiar todo` como acción neutral.

La búsqueda rápida debe evitar campos superpuestos. Por ejemplo, preferir
`Paciente o N.º de estudio` antes que mostrar por separado nombre, apellido,
DNI y número de estudio. Debe aceptar las formas habituales de escritura del
usuario, como `Juan Pérez`, `Pérez Juan`, `Pérez, Juan`, espacios repetidos y
DNI con o sin puntos o guiones.

Cuando el alcance dependa de una pestaña, explicarlo debajo del campo. Ejemplos:

- `Mis asignados`: puede incluir coincidencias asignadas a otros profesionales.
- `Sin asignar`: busca solamente dentro de los estudios sin asignar.
- `Asignados a otros`: busca solamente dentro de esa bandeja.

Usar una superficie suave con borde semántico para agrupar ambos bloques, sin
convertir cada filtro en una tarjeta independiente. En mobile, apilar los
campos en una columna; desde tablet, distribuir la búsqueda y las fechas en una
grilla compacta.

## Tablas y listados

- Encabezados con jerarquia clara y sin exceso de decoracion.
- Alinear numeros y montos para facilitar comparacion.
- Mostrar estados con badges semanticos, no solo con color.
- Acciones por fila agrupadas y con orden consistente.
- Incluir estado vacio, carga y error cuando corresponda.

## Estados y feedback

Toda pantalla interactiva debe contemplar, cuando aplique:

- carga o procesamiento;
- resultado exitoso;
- error recuperable;
- estado vacio;
- permiso insuficiente;
- confirmacion antes de acciones irreversibles.

Los toast globales deben complementar, no reemplazar, los mensajes persistentes de formularios o procesos criticos.

## Navegacion

- Mantener el navbar dinamico y sus permisos en `accounts/context_processors.py`.
- No modificar `templates/includes/_nav.html` para resolver reglas de visibilidad; la autorizacion vive en backend.
- El item activo debe ser evidente en desktop y mobile.
- Los menus desplegables deben ser accesibles por teclado y no depender solo de hover.

## Componentes compartidos

Antes de crear markup repetido, revisar:

- `templates/components/` para avatar, botones, badges y estados.
- `templates/layouts/base_tailwind.html` para la estructura global.
- `static/styles/styles.css` y `static/styles/tailwind-medical.css` para tokens y utilidades existentes.

## Proceso de evolucion

1. Relevar el patron existente y su problema de UX.
2. Proponer una regla o componente reusable.
3. Aplicarlo en una pantalla representativa.
4. Validar desktop, mobile, permisos y estados.
5. Documentar la decision y extenderla al resto del modulo.

## Deuda visual conocida

- Hay estilos Tailwind compilados y CSS legado en paralelo.
- Existen gradientes y radios de borde variados entre pantallas.
- `tailwind.config.js` mantiene una safelist muy amplia y clases de prueba historicas.
- La guia debe consolidar tokens antes de una limpieza global para evitar regresiones.
