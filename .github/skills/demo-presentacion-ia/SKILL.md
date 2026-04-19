# Skill: demo-presentacion-ia

## Cuándo usar este skill
Cuando se trabaje en `templates/dictado_informes/demo_presentacion_ia.html`:
- Agregar o reestructurar secciones de la presentación
- Añadir nuevas demos interactivas (Aplicar/Reiniciar)
- Integrar videos o medios externos
- Ajustar layout, centrado vertical o responsividad
- Actualizar el roadmap o la narrativa clínica

---

## Contexto del archivo

**Ruta**: `templates/dictado_informes/demo_presentacion_ia.html`
**URL**: `/dictado_informes/demo-presentacion-ia/`
**Stack**: Tailwind CSS via CDN (solo este template) · Alpine.js · Vanilla JS · YouTube IFrame API

Presentación interactiva de 11 secciones navegables por sidebar lateral y teclado (← →).

### Secciones actuales (19/04/2026)
| # | id | Nombre | Stage chip |
|---|-----|--------|------------|
| 1 | `portada` | Título + logos institucional y profesional | Inicio |
| 2 | `recorrido-personal` | Del problema al primer sistema en producción | Contexto |
| 3 | `introduccion` | Problemas clave | Problema |
| 4 | `dictado-ia` | Hito 1 · Dictado con IA + video YouTube | Demo |
| 5 | `estructuracion-informes` | Capa 2 · Estructuración de informes | Demo |
| 6 | `aprendizaje-sistema` | Capa 3 · Aprendizaje del sistema | Demo |
| 7 | `asistente-residentes` | Hito 2 · Preinformes + Mentor IA + video YouTube | Docencia |
| 8 | `evaluacion-docente` | Evaluación docente · métricas Q1 2026 | Impacto |
| 9 | `guardias-asistidas` | Hito 3 · Guardias (demo en vivo) | Gestión |
| 10 | `cierre` | Roadmap 3 fases + frase de impacto | Visión |
| 11 | `agradecimiento` | Muchas gracias + tres logos | Final |

---

## Reglas de diseño

### CSS centrado vertical (CRÍTICO)
```css
.section-panel {
    position: absolute; inset: 0;
    display: none; flex-direction: column;
    justify-content: safe center;  /* NO usar "center" puro */
    padding: 2.2rem 3rem;
    overflow-y: auto;
}
```
- **`safe center` es obligatorio**: con `center` puro el contenido que desborda se clipea por arriba y no es scrolleable.

### Activar sección visible
```js
// El panel activo recibe display:flex via JS — no usar flex directamente en CSS por conflicto con display:none
panelActivo.style.display = 'flex';
```

---

## Patrón de demos interactivas

Toda demo que muestre un resultado tras acción del usuario debe seguir este patrón:

```html
<!-- Estado inicial (placeholder) -->
<div id="placeholderX" class="...">Texto o instrucción inicial</div>

<!-- Resultado (oculto al inicio) -->
<div id="textoResultadoX" class="hidden ...">Texto resultante</div>

<!-- Controles -->
<button id="btnAplicarX">Aplicar X</button>
<span id="chipX" class="hidden ...">✓ X aplicado</span>
<button id="btnResetX">Reiniciar demo</button>
```

```js
document.getElementById('btnAplicarX').addEventListener('click', function () {
    document.getElementById('textoResultadoX').classList.remove('hidden');
    document.getElementById('placeholderX').classList.add('hidden');
    document.getElementById('chipX').classList.remove('hidden');
});
document.getElementById('btnResetX').addEventListener('click', function () {
    document.getElementById('textoResultadoX').classList.add('hidden');
    document.getElementById('placeholderX').classList.remove('hidden');
    document.getElementById('chipX').classList.add('hidden');
});
```

---

## YouTube IFrame API — reglas

```html
<!-- Contenedor para fullscreen (no el iframe directamente) -->
<div id="videoHost" class="flex-1 bg-slate-950 p-3">
    <iframe id="ytPlayer"
        src="https://www.youtube.com/embed/VIDEO_ID?si=TOKEN&enablejsapi=1&modestbranding=1&rel=0&iv_load_policy=3"
        class="h-full min-h-[320px] w-full rounded-lg"
        frameborder="0" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
</div>
```

```js
// ✅ Usar playerVars.origin en el constructor, NO mutar iframe.src
ytPlayerInstance = new YT.Player('ytPlayer', {
    playerVars: { origin: window.location.origin },
    events: {
        onStateChange: function (event) {
            if (event.data !== YT.PlayerState.PLAYING) return;
            requestFullscreenSafe(document.getElementById('videoHost'));
        }
    }
});

// Función de fullscreen cross-browser
function requestFullscreenSafe(element) {
    if (!element || document.fullscreenElement) return;
    var req = element.requestFullscreen
        || element.webkitRequestFullscreen
        || element.mozRequestFullScreen
        || element.msRequestFullscreen;
    if (!req) return;
    try {
        var result = req.call(element);
        if (result && typeof result.catch === 'function') result.catch(function () {});
    } catch (e) {}
}
```

- **NO** hacer fullscreen sobre el iframe directamente (origen cruzado → bloqueado).
- Siempre incluir botón fallback "Play + pantalla completa" para que el usuario active fullscreen desde el contexto de la página.
- El `onStateChange` automático puede ser bloqueado por el browser; el botón es el camino seguro.

---

## Bugs conocidos y resueltos

| Bug | Causa | Fix |
|-----|-------|-----|
| Sección invisible (`opacity:0`, `offsetHeight:0`) | `</div>` faltante en sección anterior, causando anidamiento | Verificar divs de cierre de cada sección con inspector |
| `postMessage origin mismatch` en consola | Iframe enviaba mensajes a `youtube.com` pero origen era `localhost` | Agregar `playerVars: { origin: window.location.origin }` |
| Fullscreen bloqueado automáticamente | Browser bloquea fullscreen desde eventos de iframes cross-origin | Botón fallback en contexto de la página principal |
| Scroll inaccesible en sección larga | `justify-content: center` clipea contenido que desborda | Cambiar a `justify-content: safe center` |
| `btnSkipToClose` saltaba a `agradecimiento` (último slide) | Usaba `sectionIds.length - 1` → cambia si se agregan slides después de `cierre` | Usar `sectionIds.indexOf('cierre')` — robusto frente a reordenamientos |
| Fullscreen area negra en video dictado | Host sin `flex-1`, iframe sin `h-full` | Host como `flex-1`, iframe con `h-full min-h-[320px]` |

---

## Narrativa clínica (tono)

- Audiencia: profesionales médicos, no técnicos.
- Evitar jerga de software; hablar de "el sistema", "el asistente", "el flujo de trabajo".
- Métricas reales preferidas (ej: "~18 min/preinforme → ~6 min").
- Comparativas Antes/Después siempre con datos concretos.
- Roadmap: 3 fases con estado visual claro (✓/→/◈) y colores semánticos (emerald/sky/violet).
