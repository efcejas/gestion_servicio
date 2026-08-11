# Preinformes - Banco de Informes y búsqueda inteligente

Documento vigente del buscador de casos sobre informes definitivos aprobados.

Última actualización: 2026-08-11.

## Objetivo

Permitir que residentes, jefes de residentes e instructores encuentren casos docentes y ejemplos de redacción dentro de los preinformes finalizados del equipo.

- URL: `/preinformes/banco/`
- Vista: `preinformes.views.lista_banco_informes`
- Template: `templates/preinformes/lista_banco_informes.html`

## Alcance y permisos

El Banco incluye únicamente registros finalizados, reales —no demo—, pertenecientes a usuarios con rol `medico_residente` y con informe definitivo aprobado. Pueden ingresar `medico_residente`, `jefe_residentes` e `instructor_residentes`.

La IA no modifica estas reglas ni accede directamente a la base de datos.

## Búsqueda tradicional

Los filtros disponibles son contenido del informe definitivo, número de estudio, paciente —salvo usuarios demo—, tipo de estudio y región.

La búsqueda de contenido utiliza `RevisionPreinforme.informe_final_busqueda`, una representación normalizada sin diferencias de mayúsculas o tildes. `informe_final_texto` conserva la versión legible para mostrar el fragmento coincidente. Ambos campos se actualizan al guardar `informe_final_html`.

La migración `0030_revisionpreinforme_busqueda_contenido` completa estos campos para revisiones existentes. El texto completo no lleva índice B-tree: PostgreSQL no admite valores de índice tan largos y ese índice tampoco acelera `icontains`. `0031_eliminar_indice_btree_busqueda_contenido` conserva compatibilidad con instalaciones previas.

## Buscador inteligente de casos

El residente puede escribir, por ejemplo:

> Necesito casos de tumro de colon con compromiso hepático.

`preinformes.buscador_casos_service.BuscadorCasosIA`:

1. limita la consulta a 500 caracteres;
2. elimina documentos numéricos y correos detectables;
3. solicita una interpretación JSON estructurada;
4. corrige errores ortográficos;
5. propone entre 3 y 8 términos o sinónimos clínicos específicos;
6. extrae modalidad y región cuando son inequívocas;
7. devuelve la interpretación a Django;
8. Django aplica permisos, construye el ORM y ordena por relevancia.

El modelo solo recibe la consulta sanitizada. No recibe cuerpos de informes, nombres de pacientes ni acceso SQL.

## Resultados

Los resultados pueden mostrar metadatos del estudio, fragmento definitivo, coincidencia resaltada, interpretación de la IA, términos utilizados y filtros inferidos. Son resultados orientativos de recuperación de casos; no confirman diagnósticos.

## Degradación y caché

- Las interpretaciones exitosas se almacenan 24 horas.
- Sin `OPENAI_API_KEY`, o ante un error del proveedor, se busca literalmente el texto escrito.
- Una falla de IA no amplía permisos ni interrumpe la búsqueda tradicional.

## Configuración

```env
OPENAI_API_KEY=<clave>
PREINFORMES_BUSCADOR_IA_HABILITADO=True
```

`PREINFORMES_BUSCADOR_IA_HABILITADO` es opcional y vale `True` por defecto. En `False`, oculta y desactiva el buscador inteligente.

## Privacidad

- La interfaz pide no ingresar nombres, DNI ni otros identificadores.
- El backend reemplaza documentos y correos detectables antes de llamar al proveedor.
- No se envían cuerpos de informes al modelo.
- Los permisos se verifican antes de presentar resultados.
- Los registros demo no ingresan al Banco compartido.

## Pruebas

```bash
python manage.py test \
  preinformes.test_busqueda_contenido_banco \
  preinformes.test_buscador_casos_service
```

