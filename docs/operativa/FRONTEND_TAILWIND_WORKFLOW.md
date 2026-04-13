# Frontend Tailwind Workflow

Guia operativa para desarrollo frontend con Tailwind CSS en este proyecto Django.

## Requisitos

- Node.js 18 o superior.
- Dependencias instaladas en la raiz y en theme/static_src.

## Instalacion inicial

```bash
# Raiz del proyecto
npm install

# Dependencias del compilador Tailwind
cd theme/static_src
npm install
cd ../..
```

## Flujo diario de desarrollo

Abrir 2 terminales.

```bash
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Tailwind watch desde raiz
npm run tailwind:dev
```

Si el watch esta activo, al guardar templates o CSS se recompila automaticamente.

## Comandos utiles

```bash
# Watch de Tailwind
npm run tailwind:dev

# Build minificado
npm run tailwind:build

# Solo watch directo (sin orquestacion)
npm run tailwind:watch
```

## VS Code IntelliSense

Recomendado tener estas extensiones:

- Tailwind CSS IntelliSense
- Django
- Python
- Pylance

El proyecto ya incluye:

- .vscode/extensions.json con recomendaciones
- .vscode/settings.json con mapeo para templates Django y regex de clases en strings

Si no aparecen sugerencias:

1. Ejecutar `Developer: Reload Window`.
2. Verificar que el archivo este en modo de lenguaje HTML o Django HTML.
3. Confirmar que `npm run tailwind:dev` este corriendo.

## Solucion de problemas

### No se aplican clases nuevas

1. Confirmar que el watch esta corriendo.
2. Guardar el archivo y recargar navegador.
3. Revisar que la ruta del archivo este incluida en `theme/static_src/tailwind.config.js` en `content`.
4. Evitar depender de clases arbitrarias complejas cuando no haga falta.

### Mensaje "caniuse-lite is outdated"

No rompe la compilacion. Si molesta, ejecutar:

```bash
cd theme/static_src
npx update-browserslist-db@latest --yes
```

### npm audit con "Invalid package tree" o "400 Bad Request"

En Windows puede aparecer despues de `npm audit fix`.

```bash
cd theme/static_src
npm install
npm audit
```

## Convenciones de CSS en el proyecto

- Usar primero clases Tailwind en templates.
- Usar `tailwind-medical.css` solo para variables CSS y clases muy puntuales.
- No agregar estilos nuevos en `static/styles/styles.css` (archivo legado).
- Usar `extra_css` en templates solo para overrides puntuales de librerias de terceros.
