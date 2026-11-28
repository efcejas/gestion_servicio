const confirmacion = document.getElementById('confirmar-produccion');
if (confirmacion) {
    const filas = Array.from(confirmacion.querySelectorAll('[data-excepcion]'));
    const grupos = Array.from(confirmacion.querySelectorAll('[data-grupo-bilateral], [data-grupo-procedimiento], [data-grupo-repeticion]'));
    const sugerenciasRepeticiones = JSON.parse(document.getElementById('sugerencias-repeticiones')?.textContent || '{}');
    let revisionesGuardadas = JSON.parse(document.getElementById('revisiones-guardadas')?.textContent || '{}');
    let guardando = false;
    let cambiosSinGuardar = 0;
    const buscar = document.getElementById('buscar-revision');
    const filtro = document.getElementById('filtro-revision');
    const claveRevision = elemento => elemento.dataset.excepcion || elemento.dataset.grupoBilateral || elemento.dataset.grupoProcedimiento || elemento.dataset.grupoRepeticion;
    const decisionActual = elemento => elemento.dataset.excepcion ? {
        accion: elemento.querySelector('[data-accion]').value,
        modalidad: elemento.querySelector('[data-modalidad]').value,
    } : {accion: elemento.querySelector('[data-decision-bilateral]').value};
    function estadoDecision(clave, actual) {
        const anterior = revisionesGuardadas[clave] || {};
        const coincide = (actual.accion || '') === (anterior.accion || '') &&
            (!actual.accion || actual.accion === 'EXCLUIR' || !('modalidad' in actual) || actual.modalidad === anterior.modalidad);
        const lista = !!actual.accion && (actual.accion === 'EXCLUIR' || !('modalidad' in actual) || !!actual.modalidad);
        return {guardada: coincide && lista, pendiente: !lista, sinGuardar: !coincide};
    }
    function mostrarEstadoGuardado(elemento, clave, actual) {
        const etiqueta = elemento.querySelector('[data-estado-guardado]');
        if (!etiqueta) return;
        const {guardada, sinGuardar} = estadoDecision(clave, actual);
        etiqueta.textContent = guardada ? 'Guardada · sin confirmar producción' :
            !sinGuardar ? 'Pendiente de revisión' : 'Cambios sin guardar';
        etiqueta.dataset.estadoRevision = guardada ? 'guardada' : sinGuardar ? 'sin_guardar' : 'pendiente';
        etiqueta.classList.toggle('text-teal-300', guardada);
        etiqueta.classList.toggle('border-teal-700', guardada);
        etiqueta.classList.toggle('text-amber-300', !guardada);
        etiqueta.classList.toggle('border-amber-700', !guardada);
    }
    const estado = document.getElementById('estado-revision');
    const irPendiente = document.getElementById('ir-primera-pendiente');
    const decisionesAntesDelGrupo = new Map();
    const secciones = Array.from(confirmacion.querySelectorAll('[data-paso-revision]'));
    grupos.forEach(grupo => grupo.classList.add('consol-case'));
    const ordenEtapas = ['doppler', 'procedimientos', 'repeticiones', 'excepciones', 'resumen'];
    const botonesEtapa = Array.from(confirmacion.querySelectorAll('[data-ir-etapa]'));
    botonesEtapa.forEach(boton => { boton.dataset.titulo = boton.textContent.trim(); });
    let etapaActual = ordenEtapas.find(etapa => secciones.some(seccion => seccion.dataset.pasoRevision === etapa));
    let versionRevision = 0;
    let resumenListo = false;
    let peticionResumen = null;
    let primerPendiente = null;
    function etapaResuelta(etapa) {
        if (etapa === 'excepciones') return filas.filter(fila => !fila.hidden).every(fila => {
            const accion = fila.querySelector('[data-accion]').value;
            return accion && (accion === 'EXCLUIR' || fila.querySelector('[data-modalidad]').value);
        });
        if (etapa === 'doppler' || etapa === 'procedimientos' || etapa === 'repeticiones') return grupos.filter(grupo =>
            etapa === 'doppler' ? grupo.dataset.grupoBilateral : etapa === 'procedimientos' ? grupo.dataset.grupoProcedimiento : grupo.dataset.grupoRepeticion
        ).every(grupo => grupo.querySelector('[data-decision-bilateral]').value);
        return true;
    }
    function etapasDisponibles() {
        return ordenEtapas.filter(etapa => secciones.some(seccion => seccion.dataset.pasoRevision === etapa) &&
            (etapa !== 'excepciones' || filas.some(fila => !fila.hidden)));
    }
    function actualizarNavegacion() {
        const etapas = etapasDisponibles();
        botonesEtapa.forEach(boton => {
            const etapa = boton.dataset.irEtapa;
            const posicion = etapas.indexOf(etapa);
            boton.hidden = posicion < 0;
            boton.disabled = false;
            boton.setAttribute('aria-current', etapa === etapaActual ? 'step' : 'false');
            const elementos = elementosEtapa(etapa);
            const listas = elementos.filter(elemento => !estadoDecision(claveRevision(elemento), decisionActual(elemento)).pendiente).length;
            boton.textContent = boton.dataset.titulo;
            const detalle = document.createElement('small');
            detalle.textContent = etapa === 'resumen' ? 'Revisar totales y publicar' : `${listas} de ${elementos.length} listas`;
            boton.appendChild(detalle);
        });
        document.getElementById('etapa-anterior').hidden = etapas.indexOf(etapaActual) <= 0;
        const siguiente = document.getElementById('etapa-siguiente');
        siguiente.hidden = etapaActual === 'resumen';
        siguiente.disabled = false;
        const confirmar = confirmacion.querySelector('button[type="submit"]');
        confirmar.hidden = etapaActual !== 'resumen';
        confirmar.disabled = !resumenListo || !etapas.every(etapaResuelta);
        document.getElementById('herramientas-revision').hidden = etapaActual === 'resumen';
        document.getElementById('recalcular-resumen').disabled = !etapas.every(etapaResuelta);
    }
    function elementosEtapa(etapa) {
        if (etapa === 'excepciones') return filas.filter(fila => !fila.hidden);
        return grupos.filter(grupo => grupo.closest('[data-paso-revision]').dataset.pasoRevision === etapa);
    }
    function aplicarFiltros() {
        const normalizar = texto => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
        const termino = normalizar(buscar.value.trim());
        const elementos = elementosEtapa(etapaActual);
        let visibles = 0;
        elementos.forEach(elemento => {
            const actual = estadoDecision(claveRevision(elemento), decisionActual(elemento));
            const coincideEstado = filtro.value === 'todas' ||
                (filtro.value === 'pendientes' && !actual.guardada) ||
                (filtro.value === 'guardadas' && actual.guardada) ||
                (filtro.value === 'sin_guardar' && actual.sinGuardar);
            const visible = coincideEstado && normalizar(elemento.textContent).includes(termino);
            elemento.classList.toggle('revision-filtrada', !visible);
            if (visible) visibles += 1;
        });
        document.getElementById('coincidencias-revision').textContent = `${visibles} de ${elementos.length} revisiones visibles`;
        document.getElementById('revision-sin-coincidencias').hidden = etapaActual === 'resumen' || visibles > 0;
    }
    function mostrarEtapa(etapa) {
        if (!etapasDisponibles().includes(etapa)) return;
        if (etapa !== etapaActual) buscar.value = '';
        etapaActual = etapa;
        secciones.forEach(seccion => seccion.hidden = seccion.dataset.pasoRevision !== etapa);
        actualizarNavegacion();
        aplicarFiltros();
        if (etapa === 'resumen') return calcularResumen();
    }
    function actualizarRevision(conservarResumen = false) {
        filas.forEach(fila => mostrarEstadoGuardado(fila, fila.dataset.excepcion, {
            accion: fila.querySelector('[data-accion]').value,
            modalidad: fila.querySelector('[data-modalidad]').value,
        }));
        grupos.forEach(grupo => {
            const accion = grupo.querySelector('[data-decision-bilateral]').value;
            mostrarEstadoGuardado(grupo,
                grupo.dataset.grupoBilateral || grupo.dataset.grupoProcedimiento || grupo.dataset.grupoRepeticion,
                {accion});
            const explicacion = grupo.querySelector('[data-resultado-grupo]');
            if (explicacion) explicacion.textContent = accion === 'UNICO'
                ? 'Las copias se agrupan: no se suma una práctica por cada fuente.'
                : accion === 'INDEPENDIENTES'
                ? 'Se conservan las realizaciones separadas. Vincular fuentes no agrega otra práctica.'
                : 'Elegí cómo contabilizar este grupo. Se conservan todos los registros originales.';
        });
        if (!conservarResumen) { versionRevision += 1; resumenListo = false; document.getElementById('tarjetas-resumen').hidden = true; }
        let acciones = 0;
        let modalidades = 0;
        let bilaterales = 0;
        primerPendiente = null;
        filas.forEach(fila => {
            if (fila.hidden) return;
            const accion = fila.querySelector('[data-accion]');
            const modalidad = fila.querySelector('[data-modalidad]');
            const faltaAccion = !accion.value;
            const faltaModalidad = !!accion.value && accion.value !== 'EXCLUIR' && !modalidad.value;
            accion.setAttribute('aria-invalid', String(faltaAccion));
            modalidad.setAttribute('aria-invalid', String(faltaModalidad));
            if (faltaAccion) { acciones += 1; primerPendiente = primerPendiente || accion; }
            if (faltaModalidad) { modalidades += 1; primerPendiente = primerPendiente || modalidad; }
        });
        let primerGrupoPendiente = null;
        grupos.forEach(grupo => {
            const decision = grupo.querySelector('[data-decision-bilateral]');
            decision.setAttribute('aria-invalid', String(!decision.value));
            if (!decision.value) { bilaterales += 1; primerGrupoPendiente = primerGrupoPendiente || decision; }
        });
        primerPendiente = primerGrupoPendiente || primerPendiente;
        const faltantes = [];
        if (acciones) faltantes.push(`${acciones} decisiones de excepción`);
        if (modalidades) faltantes.push(`${modalidades} modalidades de práctica`);
        if (bilaterales) faltantes.push(`${bilaterales} decisiones de grupos clínicos`);
        estado.textContent = faltantes.length ? `Para confirmar faltan ${faltantes.join(', ')}.` : 'Todas las excepciones están resueltas. Podés confirmar la producción.';
        irPendiente.hidden = faltantes.length === 0;
        const totalVisibles = document.getElementById('total-excepciones-visibles');
        const resueltasPorGrupo = document.getElementById('resueltas-por-grupo');
        if (totalVisibles) totalVisibles.textContent = filas.filter(fila => !fila.hidden).length;
        if (resueltasPorGrupo) {
            const resueltas = filas.filter(fila => fila.hidden).length;
            resueltasPorGrupo.hidden = resueltas === 0;
            resueltasPorGrupo.textContent = `${resueltas} filas resueltas dentro de sus grupos.`;
        }
        const elementos = grupos.concat(filas.filter(fila => !fila.hidden));
        const estados = elementos.map(elemento => estadoDecision(claveRevision(elemento), decisionActual(elemento)));
        const pendientes = estados.filter(item => item.pendiente).length;
        cambiosSinGuardar = estados.filter(item => item.sinGuardar).length;
        // Las filas resueltas dentro de grupos también pueden contener cambios
        // pendientes de guardar, aunque no sean otra tarea de revisión visible.
        const cambiosDerivados = filas.filter(fila => fila.hidden && estadoDecision(claveRevision(fila), decisionActual(fila)).sinGuardar).length;
        const totalCambios = cambiosSinGuardar + cambiosDerivados;
        document.getElementById('contador-pendientes').textContent = pendientes;
        document.getElementById('contador-sin-guardar').textContent = totalCambios;
        document.getElementById('contador-guardadas').textContent = estados.filter(item => item.guardada).length;
        document.getElementById('texto-progreso').textContent = `${elementos.length - pendientes} de ${elementos.length} revisiones listas. Podés cambiar de etapa aunque queden pendientes.`;
        const progreso = document.getElementById('progreso-revision');
        progreso.max = Math.max(1, elementos.length);
        progreso.value = elementos.length ? elementos.length - pendientes : 1;
        document.getElementById('guardar-revision').disabled = guardando || !totalCambios;
        cambiosSinGuardar = totalCambios;
        actualizarNavegacion();
        aplicarFiltros();
    }
    irPendiente.addEventListener('click', () => {
        if (primerPendiente) {
            filtro.value = 'pendientes'; buscar.value = '';
            const seccion = primerPendiente.closest('[data-paso-revision]');
            if (seccion) mostrarEtapa(seccion.dataset.pasoRevision);
            primerPendiente.scrollIntoView({ behavior: 'smooth', block: 'center' });
            primerPendiente.focus({ preventScroll: true });
        }
    });
    confirmacion.addEventListener('change', evento => {
        if (evento.target.matches('[data-accion], [data-modalidad], [data-decision-bilateral]')) actualizarRevision();
    });
    buscar.addEventListener('input', aplicarFiltros);
    filtro.addEventListener('change', aplicarFiltros);
    function resolverGrupo(grupo) {
        const accionGrupo = grupo.querySelector('[data-decision-bilateral]').value;
        const claveGrupo = grupo.dataset.grupoRepeticion || grupo.dataset.grupoBilateral;
        if (sugerenciasRepeticiones[claveGrupo]) {
            const sugerencias = sugerenciasRepeticiones[claveGrupo]?.[accionGrupo] || {};
            grupo.dataset.miembros.split(',').forEach(id => {
                const fila = filas.find(item => item.dataset.excepcion === id);
                if (!fila) return;
                const select = fila.querySelector('[data-accion]');
                const modalidad = fila.querySelector('[data-modalidad]');
                const clave = `${claveGrupo}:${id}`;
                if (!decisionesAntesDelGrupo.has(clave)) decisionesAntesDelGrupo.set(clave, {accion: select.value, modalidad: modalidad.value});
                const sugerencia = sugerencias[id];
                const anterior = decisionesAntesDelGrupo.get(clave);
                select.value = sugerencia ? sugerencia.accion : anterior.accion;
                modalidad.value = sugerencia ? (sugerencia.modalidad || 'ECO') : anterior.modalidad;
                fila.hidden = !!sugerencia && !!select.value;
            });
            actualizarRevision();
            return;
        }
        grupo.dataset.miembros.split(',').forEach(id => {
            const fila = filas.find(item => item.dataset.excepcion === id);
            if (!fila) return;
            const select = fila.querySelector('[data-accion]');
            const candidatas = Array.from(select.options).filter(opcion => opcion.value.startsWith('VINCULAR:'));
            const esComponente = (grupo.dataset.componentes || '').split(',').includes(id);
            if (esComponente && accionGrupo === 'UNICO' && candidatas.length <= 1) {
                if (!decisionesAntesDelGrupo.has(id)) decisionesAntesDelGrupo.set(id, {
                    accion: select.value, modalidad: fila.querySelector('[data-modalidad]').value,
                });
                select.value = 'EXCLUIR';
                fila.hidden = true;
                fila.querySelector('[data-seleccionar]').checked = false;
            } else {
                if (esComponente && decisionesAntesDelGrupo.has(id)) {
                    const anterior = decisionesAntesDelGrupo.get(id);
                    select.value = anterior.accion;
                    fila.querySelector('[data-modalidad]').value = anterior.modalidad;
                    decisionesAntesDelGrupo.delete(id);
                    fila.hidden = false;
                }
                if (accionGrupo && !esComponente && !select.value && !candidatas.length && fila.querySelector('[data-modalidad]').value) select.value = 'ADICIONAL';
            }
        });
        actualizarRevision();
    }
    grupos.forEach(grupo => grupo.querySelector('[data-decision-bilateral]').addEventListener('change', () => resolverGrupo(grupo)));
    const aplicarGrupos = document.getElementById('aplicar-bilateral-conjunto');
    if (aplicarGrupos) aplicarGrupos.addEventListener('click', () => {
        const accion = document.getElementById('accion-bilateral-conjunto').value;
        if (accion) grupos.filter(grupo => grupo.dataset.grupoBilateral).forEach(grupo => {
            grupo.querySelector('[data-decision-bilateral]').value = accion;
            resolverGrupo(grupo);
        });
    });
    const aplicarProcedimientos = document.getElementById('aplicar-procedimiento-conjunto');
    if (aplicarProcedimientos) aplicarProcedimientos.addEventListener('click', () => {
        const accion = document.getElementById('accion-procedimiento-conjunto').value;
        if (accion) grupos.filter(grupo => grupo.dataset.grupoProcedimiento).forEach(grupo => {
            grupo.querySelector('[data-decision-bilateral]').value = accion;
            resolverGrupo(grupo);
        });
    });
    const todas = document.getElementById('seleccionar-excepciones');
    if (todas) {
        todas.addEventListener('change', () => filas.forEach(fila => fila.querySelector('[data-seleccionar]').checked = !fila.hidden && todas.checked));
        document.getElementById('aplicar-conjunto').addEventListener('click', () => {
            const accion = document.getElementById('accion-conjunto').value;
            filas.filter(fila => !fila.hidden && fila.querySelector('[data-seleccionar]').checked).forEach(fila => {
                const select = fila.querySelector('[data-accion]');
                if (accion === 'VINCULAR_UNICA') {
                    const candidatas = Array.from(select.options).filter(opcion => opcion.value.startsWith('VINCULAR:'));
                    if (candidatas.length === 1) select.value = candidatas[0].value;
                } else if (accion) select.value = accion;
            });
            actualizarRevision();
        });
    }
    function serializarDecisiones() {
        const decisiones = {};
        filas.forEach(fila => decisiones[fila.dataset.excepcion] = {
            accion: fila.querySelector('[data-accion]').value,
            modalidad: fila.querySelector('[data-modalidad]').value,
        });
        grupos.forEach(grupo => decisiones[grupo.dataset.grupoBilateral || grupo.dataset.grupoProcedimiento || grupo.dataset.grupoRepeticion] = {
            accion: grupo.querySelector('[data-decision-bilateral]').value,
        });
        document.getElementById('decisiones-produccion').value = JSON.stringify(decisiones);
    }
    document.getElementById('guardar-revision').addEventListener('click', async function () {
        const motivo = document.getElementById('motivo-revision');
        if (!motivo.value.trim()) {
            document.getElementById('estado-guardado').textContent = 'Escribí qué comprobaste antes de guardar estas decisiones.';
            motivo.focus();
            return;
        }
        serializarDecisiones();
        const datos = new FormData(confirmacion);
        datos.set('accion', 'guardar_revision');
        const estado = document.getElementById('estado-guardado');
        guardando = true;
        this.disabled = true;
        estado.textContent = 'Guardando revisión…';
        try {
            const respuesta = await fetch(window.location.href, {method: 'POST', body: datos});
            const resultado = await respuesta.json();
            if (!respuesta.ok) throw new Error(resultado.error || 'No se pudo guardar la revisión.');
            revisionesGuardadas = resultado.decisiones_guardadas;
            actualizarRevision(true);
            estado.textContent = resultado.mensaje;
        } catch (error) {
            estado.textContent = error.message || 'No se pudo guardar la revisión. Volvé a intentarlo.';
        } finally {
            guardando = false;
            actualizarRevision(true);
        }
    });
    async function calcularResumen() {
        if (!etapasDisponibles().every(etapaResuelta)) {
            document.getElementById('resumen-produccion').textContent = 'Todavía hay decisiones pendientes. Podés guardar el avance y volver a cualquier etapa para terminarlas. La producción aún no se puede confirmar.';
            document.getElementById('tarjetas-resumen').hidden = true;
            return;
        }
        if (peticionResumen) peticionResumen.abort();
        peticionResumen = new AbortController();
        const versionSolicitada = versionRevision;
        const texto = document.getElementById('resumen-produccion');
        texto.textContent = 'Calculando la producción con tus decisiones…';
        resumenListo = false;
        actualizarNavegacion();
        serializarDecisiones();
        const datos = new FormData(confirmacion);
        datos.set('accion', 'resumen');
        try {
            const respuesta = await fetch(window.location.href, {
                method: 'POST', body: datos, signal: peticionResumen.signal,
            });
            const resultado = await respuesta.json();
            if (versionSolicitada !== versionRevision) return;
            if (!respuesta.ok) throw new Error(resultado.error || 'Revisá las decisiones para calcular el resumen.');
            const numero = valor => Number(valor).toLocaleString('es-AR');
            texto.textContent = `${numero(resultado.total_produccion)} prácticas únicas. EGES ${numero(resultado.base_eges)} + aporte Netterm ${numero(resultado.aporte_netterm)}. Pacientes identificables ${numero(resultado.pacientes_unicos_identificables)}.`;
            [['resumen-total', 'total_produccion'], ['resumen-eges', 'base_eges'],
             ['resumen-netterm', 'aporte_netterm'], ['resumen-pacientes', 'pacientes_unicos_identificables']]
                .forEach(([id, clave]) => { document.getElementById(id).textContent = numero(resultado[clave]); });
            document.getElementById('tarjetas-resumen').hidden = false;
            resumenListo = true;
            actualizarRevision(true);
        } catch (error) {
            if (error.name !== 'AbortError' && versionSolicitada === versionRevision) {
                texto.textContent = error.message || 'No se pudo calcular el resumen. Volvé a intentarlo.';
                resumenListo = false;
                actualizarNavegacion();
            }
        }
    }
    botonesEtapa.forEach(boton => boton.addEventListener('click', () => mostrarEtapa(boton.dataset.irEtapa)));
    document.getElementById('etapa-anterior').addEventListener('click', () => {
        const etapas = etapasDisponibles();
        mostrarEtapa(etapas[etapas.indexOf(etapaActual) - 1]);
    });
    document.getElementById('etapa-siguiente').addEventListener('click', () => {
        const etapas = etapasDisponibles();
        mostrarEtapa(etapas[etapas.indexOf(etapaActual) + 1]);
    });
    document.getElementById('recalcular-resumen').addEventListener('click', calcularResumen);
    confirmacion.addEventListener('submit', evento => {
        if (!resumenListo || !etapasDisponibles().every(etapaResuelta)) {
            evento.preventDefault();
            mostrarEtapa('resumen');
            return;
        }
        serializarDecisiones();
        cambiosSinGuardar = 0;
    });
    window.addEventListener('beforeunload', evento => {
        if (cambiosSinGuardar) { evento.preventDefault(); evento.returnValue = ''; }
    });
    grupos.forEach(grupo => {
        if (grupo.querySelector('[data-decision-bilateral]').value) resolverGrupo(grupo);
    });
    actualizarRevision();
    const pendiente = etapasDisponibles().find(etapa => etapa !== 'resumen' && !etapaResuelta(etapa));
    mostrarEtapa(pendiente || 'resumen');
}
