// Ejecuta el controlador real sin navegador ni datos de pacientes.
// node --test eges_import/tests_ui_consolidacion.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Elemento {
    constructor(texto = '') {
        this.dataset = {}; this.children = []; this.listeners = {}; this.attrs = {};
        this.hidden = false; this.disabled = false; this.value = ''; this.texto = texto;
        this.selectores = {}; this.clases = new Set();
        this.classList = {
            add: nombre => this.clases.add(nombre),
            contains: nombre => this.clases.has(nombre),
            toggle: (nombre, activo) => activo ? this.clases.add(nombre) : this.clases.delete(nombre),
        };
    }
    appendChild(hijo) { hijo.parent = this; this.children.push(hijo); return hijo; }
    get textContent() { return this.texto + this.children.map(hijo => hijo.textContent).join(' '); }
    set textContent(valor) { this.texto = String(valor); this.children = []; }
    querySelector(selector) { return this.selectores[selector] || null; }
    querySelectorAll(selector) { return this.selectores[selector] || []; }
    setAttribute(clave, valor) { this.attrs[clave] = valor; }
    addEventListener(tipo, callback) { (this.listeners[tipo] ||= []).push(callback); }
    closest(selector) {
        return this.dataset.pasoRevision ? this : this.parent?.closest(selector);
    }
    matches() { return !!this.esDecision; }
    focus() { this.enfocado = true; }
    scrollIntoView() {}
    async emitir(tipo, evento) {
        evento ||= {target: this, preventDefault() { this.prevenido = true; }};
        for (const callback of this.listeners[tipo] || []) await callback.call(this, evento);
        if (this.parent) await this.parent.emitir(tipo, evento);
        return evento;
    }
}

function escenario() {
    const ids = new Map();
    function id(nombre, elemento = new Elemento()) { ids.set(nombre, elemento); return elemento; }
    const form = id('confirmar-produccion');
    const campos = ['estado-revision','ir-primera-pendiente','etapa-anterior','etapa-siguiente',
        'herramientas-revision','recalcular-resumen','buscar-revision','filtro-revision',
        'coincidencias-revision','revision-sin-coincidencias','tarjetas-resumen','contador-pendientes',
        'contador-sin-guardar','contador-guardadas','texto-progreso','progreso-revision',
        'guardar-revision','estado-guardado','motivo-revision','decisiones-produccion',
        'total-excepciones-visibles','resueltas-por-grupo','resumen-produccion',
        'resumen-total','resumen-eges','resumen-netterm','resumen-pacientes'];
    campos.forEach(nombre => id(nombre));
    ids.get('filtro-revision').value = 'pendientes';
    const confirmacion = new Elemento();
    form.selectores['button[type="submit"]'] = confirmacion;
    const secciones = ['repeticiones','excepciones','resumen'].map(nombre => {
        const s = form.appendChild(new Elemento()); s.dataset.pasoRevision = nombre; return s;
    });
    const botones = secciones.map(s => {
        const boton = new Elemento(s.dataset.pasoRevision); boton.dataset.irEtapa = s.dataset.pasoRevision; return boton;
    });
    function grupo(clave, texto, miembros, accion = '') {
        const g = secciones[0].appendChild(new Elemento(texto));
        g.dataset.grupoRepeticion = clave; g.dataset.miembros = miembros;
        const select = g.appendChild(new Elemento()); select.value = accion; select.esDecision = true;
        g.selectores['[data-decision-bilateral]'] = select;
        g.selectores['[data-estado-guardado]'] = g.appendChild(new Elemento());
        g.selectores['[data-resultado-grupo]'] = g.appendChild(new Elemento());
        return g;
    }
    const guardado = grupo('eco:guardado','Álvarez Demo · Netterm Pedido 80012','', 'UNICO');
    const pendiente = grupo('eco:pendiente','Paciente Demo B · Netterm Pedido 80013','1');
    function fila(clave, texto) {
        const f = secciones[1].appendChild(new Elemento(texto)); f.dataset.excepcion = clave;
        for (const selector of ['[data-accion]','[data-modalidad]','[data-seleccionar]','[data-estado-guardado]']) {
            const elemento = f.appendChild(new Elemento()); f.selectores[selector] = elemento;
            elemento.esDecision = selector === '[data-accion]' || selector === '[data-modalidad]';
        }
        f.selectores['[data-modalidad]'].value = 'ECO';
        f.selectores['[data-accion]'].options = [{value:''},{value:'VINCULAR:10'},{value:'ADICIONAL'},{value:'EXCLUIR'}];
        return f;
    }
    const f1 = fila('1','Paciente Demo B · Pedido 80013');
    const f2 = fila('2','Paciente Demo C · Pedido 80020');
    const grupos = [guardado, pendiente], filas = [f1,f2];
    form.selectores['[data-excepcion]'] = filas;
    form.selectores['[data-grupo-bilateral], [data-grupo-procedimiento], [data-grupo-repeticion]'] = grupos;
    form.selectores['[data-paso-revision]'] = secciones;
    form.selectores['[data-ir-etapa]'] = botones;
    id('sugerencias-repeticiones', new Elemento(JSON.stringify({
        'eco:pendiente': {UNICO:{'1':{accion:'VINCULAR:10',modalidad:'ECO'}}, INDEPENDIENTES:{}},
    })));
    id('revisiones-guardadas',new Elemento(JSON.stringify({'eco:guardado':{accion:'UNICO'}})));
    const peticiones = [];
    const contexto = {
        document: {getElementById: nombre => ids.get(nombre) || null, createElement: () => new Elemento()},
        window: Object.assign(new Elemento(), {location:{href:'http://prueba.invalid/'}}),
        FormData: class {
            constructor() { this.valores = new Map([
                ['decisiones_json',ids.get('decisiones-produccion').value],
                ['motivo_revision',ids.get('motivo-revision').value],
            ]); }
            set(clave, valor) { this.valores.set(clave, valor); }
            get(clave) { return this.valores.get(clave); }
        },
        AbortController,
        fetch: async (url, opciones) => {
            const datos = opciones.body; peticiones.push(datos.get('accion'));
            return {ok:true, json:async()=>({
                decisiones_guardadas:Object.fromEntries(Object.entries(JSON.parse(datos.get('decisiones_json'))).filter(([,v])=>v.accion)),
                mensaje:'Revisión guardada.', total_produccion:3,base_eges:2,aporte_netterm:1,pacientes_unicos_identificables:2,
            })};
        },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../static/js/eges_consolidacion.js'),'utf8'), contexto);
    return {ids,form,grupos,filas,botones,secciones,peticiones,contexto,confirmacion};
}

test('puede cambiar de etapa con pendientes, pero no confirmar ni calcular totales', async () => {
    const s = escenario();
    assert.equal(s.ids.get('etapa-siguiente').disabled,false);
    assert.equal(s.botones[1].disabled,false);
    await s.botones[2].emitir('click');
    assert.equal(s.secciones[2].hidden,false);
    assert.equal(s.confirmacion.disabled,true);
    assert.match(s.ids.get('resumen-produccion').textContent,/decisiones pendientes/);
    assert.deepEqual(s.peticiones,[]);
    assert.equal((await s.form.emitir('submit')).prevenido,true);
});

test('buscar y ocultar guardadas no cambia los datos ni resuelve casos pendientes', async () => {
    const s = escenario();
    assert.equal(s.grupos[0].classList.contains('revision-filtrada'),true);
    s.ids.get('filtro-revision').value='todas'; await s.ids.get('filtro-revision').emitir('change');
    s.ids.get('buscar-revision').value='alvarez'; await s.ids.get('buscar-revision').emitir('input');
    assert.equal(s.grupos[0].classList.contains('revision-filtrada'),false);
    assert.equal(s.grupos[1].classList.contains('revision-filtrada'),true);
    assert.equal(s.grupos[1].hidden,false);
    assert.equal(s.ids.get('contador-pendientes').textContent,'3');
    await s.botones[2].emitir('click');
    assert.equal(s.confirmacion.disabled,true);
    assert.deepEqual(s.peticiones,[]);
});

test('una decisión cambia a sin guardar y sólo queda guardada tras respuesta del servidor', async () => {
    const s = escenario();
    const select = s.grupos[1].querySelector('[data-decision-bilateral]');
    select.value='UNICO'; await select.emitir('change');
    assert.equal(s.grupos[1].querySelector('[data-estado-guardado]').textContent,'Cambios sin guardar');
    assert.match(s.grupos[1].querySelector('[data-resultado-grupo]').textContent,/no se suma una práctica por cada fuente/);
    assert.equal(s.filas[0].hidden,true);
    await s.ids.get('guardar-revision').emitir('click');
    assert.deepEqual(s.peticiones,[]); // Falta motivo: ni siquiera envía el formulario.
    s.ids.get('motivo-revision').value='Comprobación sintética';
    await s.ids.get('guardar-revision').emitir('click');
    assert.deepEqual(s.peticiones,['guardar_revision']);
    assert.equal(s.grupos[1].querySelector('[data-estado-guardado]').textContent,'Guardada · sin confirmar producción');
    assert.equal(s.ids.get('contador-pendientes').textContent,'1');
    assert.equal(s.ids.get('contador-sin-guardar').textContent,'0');
    assert.equal(s.confirmacion.disabled,true);
});

test('un fallo al guardar conserva los cambios y no muestra una confirmación falsa', async () => {
    const s = escenario();
    const select = s.grupos[1].querySelector('[data-decision-bilateral]');
    select.value='UNICO'; await select.emitir('change');
    s.ids.get('motivo-revision').value='Comprobación sintética';
    s.contexto.fetch=async()=>({ok:false,json:async()=>({error:'Las fuentes cambiaron.'})});
    await s.ids.get('guardar-revision').emitir('click');
    assert.match(s.ids.get('estado-guardado').textContent,/fuentes cambiaron/);
    assert.equal(s.grupos[1].querySelector('[data-estado-guardado]').textContent,'Cambios sin guardar');
    assert.equal(s.ids.get('guardar-revision').disabled,false);
});

test('resumen listo sólo tras completar todas las decisiones, incluso las ocultadas por filtros', async () => {
    const s = escenario();
    const select=s.grupos[1].querySelector('[data-decision-bilateral]');
    select.value='UNICO'; await select.emitir('change');
    const accion=s.filas[1].querySelector('[data-accion]');
    accion.value='EXCLUIR'; await accion.emitir('change');
    await s.botones[2].emitir('click');
    assert.deepEqual(s.peticiones,['resumen']);
    assert.equal(s.confirmacion.disabled,false);
    assert.equal(s.ids.get('tarjetas-resumen').hidden,false);
    accion.value=''; await accion.emitir('change');
    assert.equal(s.confirmacion.disabled,true);
    assert.equal(s.ids.get('tarjetas-resumen').hidden,true);
});
