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

Presentación interactiva de 9 secciones navegables por sidebar lateral y teclado (← →).

### Secciones actuales (18/04/2026)
| id | Nombre | Estado |
|----|--------|--------|
| portada | Título general | ✅ |
| contexto-clinico | Problema + motivación | ✅ |
| dictado-rapido | Demo dictado IA | ✅ |
| estructuracion-informes | Antes/Después estructurado | ✅ |
| aprendizaje-sistema | Adaptación al estilo del servicio | ✅ |
| asistente-residentes | Video YouTube + IFrame API | ✅ |
| evaluacion-docente | Métricas Antes/Después Q1 2026 | ✅ |
| carrusel-evidencia | Galería de evidencia clínica | ✅ |
| cierre | Roadmap 3 fases + frase de impacto | ✅ |

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

---

## Narrativa clínica (tono)

- Audiencia: profesionales médicos, no técnicos.
- Evitar jerga de software; hablar de "el sistema", "el asistente", "el flujo de trabajo".
- Métricas reales preferidas (ej: "~18 min/preinforme → ~6 min").
- Comparativas Antes/Después siempre con datos concretos.
- Roadmap: 3 fases con estado visual claro (✓/→/◈) y colores semánticos (emerald/sky/violet).
