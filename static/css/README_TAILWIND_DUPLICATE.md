Este archivo existía para explicar por qué se eliminó el tailwind.css duplicado.

Se eliminó `static/css/tailwind.css` porque el build oficial de Tailwind vive en `theme/static/css/tailwind.css` (app de django-tailwind). Tener ambos generaba el warning de collectstatic:
"Found another file with the destination path 'css/tailwind.css'".

Si necesitas sobreescribir Tailwind en el futuro, hazlo vía:
1. theme/static_src/css/input.css (fuente usada por django-tailwind) y correr el build.
2. O agrega un nuevo archivo con nombre distinto, por ejemplo `overrides.css`.

No volver a añadir un `tailwind.css` manual en `static/css/`.
