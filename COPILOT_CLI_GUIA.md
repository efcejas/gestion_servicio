# Guía de GitHub Copilot CLI para el Proyecto

## 📦 Instalación
✅ Ya instalado: `@github/copilot@0.0.421`

## � Idioma
⚠️ **IMPORTANTE**: La CLI de Copilot solo está disponible en inglés actualmente. No hay opción para cambiar el idioma, pero esta guía traduce todos los comandos y mensajes importantes.

## 🔐 Autenticación (Primer Uso)

**1. Iniciar sesión:**
```bash
copilot
# Luego escribe: /login
```

**Qué hacer:**
1. Se abrirá tu navegador en GitHub
2. Copia el código que aparece en el terminal (ejemplo: `A1B2-C3D4`)
3. Pégalo en la página de GitHub que se abrió
4. Haz clic en "Authorize" (Autorizar)
5. ✅ Vuelve al terminal, verás: `✓ You are now logged in`

**Mensaje de éxito:**
```
✓ You are now logged in
```
Traducción: "Ya has iniciado sesión"

**Si aparece un error:**
```
✗ Not authenticated. Please login first.
```
Traducción: "No autenticado. Por favor inicia sesión primero."
→ Solución: Ejecuta `/login` nuevamente

## 🚀 Primeros Pasos Después del Login

**Paso 1: Verificar que detectó el archivo de instrucciones**
```bash
# La CLI debería mostrar:
● Found copilot-instructions.md in project root
  → "Encontrado copilot-instructions.md en la raíz del proyecto"
```

Si dice `No copilot instructions found`, escribe `/init` para crearlo.

**Paso 2: Probar tu primer comando**
```bash
# Escribe en el terminal de copilot:
/plan "agregar un campo de teléfono al modelo de paciente"
```

Verás algo como:
```
📋 Generating plan... (wait a few seconds)
  → "Generando plan... (espera unos segundos)"

Plan to add phone field to patient model:

1. Edit: preinformes/models.py
   - Add phone field to Preinforme model
   
2. Create: preinformes/migrations/0017_add_phone_field.py
   - Generate migration

3. Edit: preinformes/forms.py
   - Add phone field to form

Do you want to proceed with this plan? (Y/n)
  → "¿Quieres proceder con este plan? (S/n)"
```

**Paso 3: Revisar y aprobar (o rechazar)**
- Escribe `Y` (o `S`) para aplicar los cambios
- Escribe `n` para cancelar
- Presiona `Ctrl+C` para abortar completamente

## 🎯 Comandos Principales (Traducidos)

### 1. `/plan` - Planificar Cambios Grandes
Genera un esquema revisable antes de modificar múltiples archivos.

**Ejemplo aplicado a tu proyecto:**
```bash
copilot /plan "refactorizar el módulo de liquidación para separar la lógica de cálculo en servicios independientes"
```

**Ventajas:**
- Ve un resumen de todos los archivos que se modificarán
- Revisa la estrategia antes de ejecutar
- Previene errores en cambios complejos

### 2. `/model` - Comparar Modelos
Compara diferentes estrategias entre modelos de IA.

**Ejemplo:**
```bash
copilot /model "optimizar la consulta de pedidos pendientes en pedidos_estudios"
```

**Ventajas:**
- Obtén diferentes perspectivas sobre el mismo problema
- Compara Claude vs GPT-4 vs otros modelos
- Elige la mejor solución

### 3. `/delegate` - Delegar Tareas
Asigna trabajo específico manteniendo el contexto.

**Ejemplo aplicado a tu proyecto:**
```bash
copilot /delegate "crear tests unitarios para el módulo de liquidacion/models.py"
```

**Ventajas:**
- El agente trabaja de forma autónoma
- Puedes revisar el resultado en la pestaña Agentes
- Mantiene el historial visible

### 4. `/fleet` - Subagentes Paralelos
Ejecuta múltiples tareas en paralelo.

**Ejemplo:**
```bash
copilot /fleet "agregar validaciones a formularios de pedidos" "optimizar queries en consultorios" "actualizar tests de agenda"
```

**Ventajas:**
- Múltiples tareas simultáneas
- Más rápido para cambios independientes
- Cada subagente puede usar un modelo diferente

### 5. `/init` - Crear AGENTS.md
Genera un archivo de configuración para estandarizar el comportamiento.

**Ejemplo:**
```bash
copilot /init
```

**Crea un archivo con reglas como:**
```markdown
# Agent Instructions

## Django Best Practices
- Siempre usar timezone-aware datetimes (django.utils.timezone.now())
- Seguir estructura de apps Django estándar
- Validaciones en modelos Y formularios
- Tests con pytest-django

## Proyecto Específico
- El sistema gestiona servicios médicos
- Apps principales: liquidacion, pedidos_estudios, consultorios, agenda
- Base de datos: SQLite local, PostgreSQL en producción
- Usar decoradores personalizados en accounts/decorators.py
```

## 🚀 Casos de Uso para Tu Proyecto

### Caso 1: Refactorización Segura de Liquidación
```bash
# 1. Planificar primero
copilot /plan "mover lógica de cálculo de liquidacion/views.py a liquidacion/services.py"

# 2. Revisar el plan
# 3. Ejecutar si se ve bien
```

### Caso 2: Agregar Feature Nueva
```bash
# Delegar la creación de una nueva funcionalidad
copilot /delegate "crear módulo de notificaciones push para avisos de pedidos urgentes"
```

### Caso 3: Debugging Complejo
```bash
# Comparar soluciones entre modelos
copilot /model "resolver el problema de race condition en procesamiento automático de pedidos"
```

### Caso 4: Trabajo en Equipo
```bash
# 1. Crear AGENTS.md con reglas del proyecto
copilot /init

# 2. Commitearlo al repo
# 3. Todo el equipo tendrá el mismo comportamiento de Copilot
```

## 🎯 Ventajas Principales

### Para Ti Solo
- **Planificación**: Ve todo el cambio antes de ejecutarlo
- **Seguridad**: Menos riesgo de romper código
- **Velocidad**: Delega tareas repetitivas

### Para Trabajo en Equipo
- **Estandarización**: Todos los devs usan las mismas reglas
- **Documentación**: AGENTS.md documenta las prácticas del proyecto
- **Consistencia**: Copilot se comporta igual para todos

## 📝 Próximos Pasos

1. **Crear AGENTS.md para este proyecto**
   ```bash
   copilot
   /init
   ```

2. **Probar `/plan` en una refactorización pequeña**
   ```bash
   copilot
   /plan "agregar índice a campo fecha_estudio en pedidos"
   ```

3. **Usar `/delegate` para tareas específicas**
   ```bash
   copilot
   /delegate "documentar la API de liquidacion en docstrings"
   ```

## 📖 Diccionario de Mensajes Comunes (Inglés → Español)

### Mensajes de Estado
| Inglés | Español |
|--------|---------|
| `You must be logged in` | Debes iniciar sesión |
| `Please run /login` | Por favor ejecuta /login |
| `You are now logged in` | Ya has iniciado sesión |
| `Not authenticated` | No autenticado |
| `Environment loaded: Visual Studio Code connected` | Entorno cargado: VS Code conectado |
| `No copilot instructions found` | No se encontraron instrucciones de copilot |
| `Run /init to generate a copilot-instructions.md file` | Ejecuta /init para generar el archivo |

### Comandos del Terminal
| Comando | Traducción | Descripción |
|---------|------------|-------------|
| `/login` | Iniciar sesión | Autenticarte con GitHub |
| `/logout` | Cerrar sesión | Salir de tu cuenta |
| `/init` | Inicializar | Crear archivo de instrucciones |
| `/plan <prompt>` | Planificar | Ver esquema de cambios |
| `/delegate <prompt>` | Delegar | Asignar tarea a Copilot |
| `/model` | Modelo | Comparar modelos de IA |
| `/fleet` | Flota | Tareas paralelas |
| `/help` | Ayuda | Ver todos los comandos |
| `/clear` o `/new` | Limpiar | Nueva conversación |
| `/exit` | Salir | Cerrar la CLI |
| `/context` | Contexto | Ver uso de tokens |
| `/diff` | Diferencias | Ver cambios realizados |
| `/cwd` o `/cd` | Cambiar directorio | Ver o cambiar carpeta actual |

### Prompts de Confirmación
| Inglés | Español |
|--------|---------|
| `Are you sure?` | ¿Estás seguro? |
| `Do you want to continue?` | ¿Quieres continuar? |
| `Yes` | Sí |
| `No` | No |
| `Cancel` | Cancelar |
| `Please select an option` | Por favor selecciona una opción |
| `Enter to select` | Enter para seleccionar |
| `Esc to cancel` | Esc para cancelar |

### Mensajes de Progreso
| Inglés | Español |
|--------|---------|
| `Processing...` | Procesando... |
| `Generating plan...` | Generando plan... |
| `Analyzing code...` | Analizando código... |
| `Creating files...` | Creando archivos... |
| `Writing changes...` | Escribiendo cambios... |
| `Done!` | ¡Listo! |
| `Error:` | Error: |
| `Warning:` | Advertencia: |

## 🗣️ Ejemplo de Conversación (con Traducción)

```bash
❯ copilot
╭────────────────────────────────────────────╮
│          GitHub Copilot v0.0.421           │
│     Copilot uses AI. Check for mistakes    │
╰────────────────────────────────────────────╯

● Environment loaded: Visual Studio Code connected
  → "Entorno cargado: VS Code conectado"

● 💡 No copilot instructions found. Run /init
  → "No se encontraron instrucciones. Ejecuta /init"

❯ /init
  → "Inicializar instrucciones del proyecto"

✓ Created copilot-instructions.md
  → "✓ Creado copilot-instructions.md"

❯ /plan "agregar validación a formulario de pedidos"
  → "Planificar: agregar validación a formulario de pedidos"

📋 Plan:
  1. Edit: pedidos_estudios/forms.py
  2. Edit: pedidos_estudios/tests.py
  3. Add validation logic
  
Do you want to proceed? (Y/n)
  → "¿Quieres proceder? (S/n)"

❯ Y

✓ Changes applied successfully
  → "✓ Cambios aplicados exitosamente"
```

## 💡 Tips para Usar la CLI en Inglés

1. **Los prompts pueden ser en español:**
   ```bash
   /plan "agregar campo email al modelo Paciente"
   ```
   Copilot entiende español perfectamente en tus instrucciones.

2. **Usa Ctrl+C para cancelar en cualquier momento**

3. **Usa Tab para autocompletar comandos**

4. **Usa ↑↓ para navegar por el historial de comandos**

5. **Lee los mensajes clave:**
   - `✓` = Éxito
   - `✗` = Error
   - `●` = Información
   - `⚠` = Advertencia

## 🔧 Comandos de Terminal

**Iniciar CLI interactiva:**
```bash
copilot
```

**Ejecutar comando directo:**
```bash
copilot /plan "descripción del cambio"
```

**Ver ayuda:**
```bash
copilot --help
```

## 📊 Comparación: Antes vs Después

### Antes (solo VS Code Copilot)
- ✅ Chat con Copilot en VS Code
- ✅ Modificar archivos uno por uno
- ❌ Sin planificación previa visible
- ❌ Sin delegar tareas complejas
- ❌ Sin estandarización de equipo

### Después (con CLI)
- ✅ Chat con Copilot en VS Code
- ✅ Modificar archivos uno por uno
- ✅ **Planificar cambios grandes con `/plan`**
- ✅ **Delegar tareas con `/delegate`**
- ✅ **Estandarizar con AGENTS.md**
- ✅ **Comparar modelos con `/model`**
- ✅ **Paralelizar con `/fleet`**

## 🎓 Recursos
- [Documentación CLI](https://docs.github.com/copilot/using-github-copilot/copilot-cli)
- [Agent Skills](https://docs.github.com/copilot/customizing-copilot/agent-skills)
- [SDK Copilot](https://docs.github.com/copilot/building-copilot-extensions)

## 🆘 Solución de Problemas Comunes

### Problema 1: "You must be logged in"
```
✗ You must be logged in to send messages. Please run /login
```
**Solución:**
1. Escribe `/login` en el terminal de copilot
2. Copia el código que aparece
3. Pégalo en la página de GitHub que se abrió automáticamente
4. Autoriza y vuelve al terminal

### Problema 2: "No copilot instructions found"
```
● 💡 No copilot instructions found. Run /init
```
**Solución:**
Ya tienes el archivo `copilot-instructions.md` creado, pero la CLI no lo detecta. Esto puede pasar si:
1. No estás en el directorio correcto
2. El archivo no está en la raíz del proyecto

**Verifica:**
```bash
/cwd
# Debería mostrar: C:\Dev\GitHub\gestion_servicio

# Si no estás ahí:
/cd C:\Dev\GitHub\gestion_servicio
```

### Problema 3: La CLI se cierra sola
**Causa:** Probablemente presionaste `Ctrl+C` dos veces

**Solución:** Vuelve a abrir:
```bash
copilot
```

### Problema 4: Los comandos no funcionan
**Verifica que estás escribiendo el `/` antes del comando:**
```bash
# ✗ Incorrecto:
plan "mi tarea"

# ✓ Correcto:
/plan "mi tarea"
```

### Problema 5: "Error: Not found"
```
✗ Error: Not found
```
**Causa:** Comando mal escrito o no existe

**Solución:** Ver lista de comandos:
```bash
/help
```

### Problema 6: Quiero empezar de nuevo
**Solución:** Limpiar la conversación:
```bash
/clear
# o
/new
```

### Problema 7: No entiendo el inglés
**Solución:** 
1. Esta guía traduce todo lo importante
2. Tus prompts pueden ser en español:
   ```bash
   /plan "mi tarea en español"
   ```
3. Siempre puedes preguntarme aquí en VS Code Chat

## 🔑 Atajos de Teclado en la CLI

| Atajo | Acción |
|-------|--------|
| `Tab` | Autocompletar comando |
| `↑` `↓` | Navegar historial de comandos |
| `Ctrl + C` | Cancelar operación actual |
| `Ctrl + C` (x2) | Salir de la CLI |
| `Esc` | Cancelar selección |
| `Enter` | Confirmar/Seleccionar |
| `Shift + Enter` | Nueva línea en prompt multilínea |

## 📌 Resumen Rápido

**Para empezar HOY:**
```bash
# 1. Abrir la CLI
copilot

# 2. Hacer login (solo la primera vez)
/login

# 3. Tu primer comando
/plan "agregar campo al modelo"

# 4. Salir cuando termines
/exit
```

**Recuerda:**
- ✅ La interfaz está en inglés pero entiendes español
- ✅ Tus instrucciones pueden ser en español
- ✅ Ya tienes `copilot-instructions.md` configurado
- ✅ Siempre puedes volver a VS Code Chat (yo) si tienes dudas

¡Ahora sí, a probar la CLI! 🚀
