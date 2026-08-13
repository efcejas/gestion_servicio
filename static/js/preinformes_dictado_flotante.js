(function () {
    'use strict';

    window.inicializarDictadoFlotante = function (opciones) {
        const configuracion = opciones || {};
        const boton = document.getElementById(configuracion.botonId || 'dictado-toggle');
        const ancla = document.getElementById(configuracion.anclaId || 'dictado-anchor');
        const editor = document.getElementById(configuracion.editorId || 'editor-container');

        if (!boton || !ancla || !editor || boton.dataset.flotanteInicializado === 'true') {
            return;
        }
        boton.dataset.flotanteInicializado = 'true';

        let framePendiente = null;

        const actualizar = function () {
            framePendiente = null;
            const anclaRect = ancla.getBoundingClientRect();
            const editorRect = editor.getBoundingClientRect();
            const margenInferior = window.innerWidth <= 640 ? 12 : 24;
            const margenSuperior = window.innerWidth <= 640 ? 8 : 16;
            const altoBoton = boton.offsetHeight || 44;
            const debeFlotar = (
                anclaRect.bottom <= margenSuperior
                && editorRect.top < window.innerHeight
                && editorRect.bottom > altoBoton + margenInferior
            );

            boton.classList.toggle('dictado-floating', debeFlotar);
            if (!debeFlotar) {
                boton.style.removeProperty('left');
                boton.style.removeProperty('bottom');
                return;
            }

            const limiteEditor = window.innerHeight - editorRect.bottom + 12;
            const margenHorizontal = 12;
            const posicionIzquierda = Math.max(
                editorRect.left + margenHorizontal,
                editorRect.right - boton.offsetWidth - margenHorizontal
            );
            boton.style.left = `${posicionIzquierda}px`;
            boton.style.bottom = `${Math.max(margenInferior, limiteEditor)}px`;
        };

        const solicitarActualizacion = function () {
            if (framePendiente !== null) return;
            framePendiente = window.requestAnimationFrame(actualizar);
        };

        window.addEventListener('scroll', solicitarActualizacion, { passive: true });
        window.addEventListener('resize', solicitarActualizacion);
        window.addEventListener('pageshow', solicitarActualizacion);
        boton.addEventListener('dictado:estado', solicitarActualizacion);
        if ('ResizeObserver' in window) {
            const observador = new ResizeObserver(solicitarActualizacion);
            observador.observe(editor);
        }
        actualizar();
    };
})();
