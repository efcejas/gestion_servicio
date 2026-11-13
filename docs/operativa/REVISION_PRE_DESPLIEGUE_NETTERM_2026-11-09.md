# Revision de publicacion EGES / Netterm

Fecha: 09/11/2026 (America/Buenos_Aires). Revision realizada por Codex a pedido del
usuario. Esta revision no autoriza ni ejecuta un despliegue.

**Hallazgo final:** las funciones Netterm ya estan presentes en el codigo publicado
de gestion-colegiales y sus migraciones estan aplicadas. Los 25 archivos revisados
coinciden byte por byte con los blobs Git de 5c83248e. La etiqueta de release dice
818a324f y no describe fielmente ese contenido. No se hizo un nuevo deploy aqui.

## Version revisada

- Rama: `feature/liquidacion-copilot-specialization`.
- HEAD: `5c83248e56b6bca43aa608585298c520291a3b44`.
- Arbol limpio al iniciar la revision.
- GitHub, consultado con `git ls-remote`: la rama sigue en
  `818a324f113ca8b2a311eb53537fd1b9a0e0f416`. Los dos commits siguientes no estan
  enviados a esa rama remota:
  - `2c31703b`: lector, preview y archivo separado de Netterm, migracion 0010.
  - `5c83248e`: conciliacion, auditoria 0011/0012, produccion, respaldo y ajustes UI.

Se encuentran en esos commits los servicios, pantallas, enlaces, pruebas y
documentacion de la entrega. El segundo incluye las correcciones de UI posteriores:
enlace visible en estadisticas, aviso RX y guardas de controles JavaScript opcionales.

No cambia `liquidacion/models.py` ni migraciones de Liquidacion. El respaldo de origen
no ejecuta calculo de montos ni escrituras de registros o revisiones economicas.
EGES tiene una correccion de clasificacion de practicas con/sin contraste para futuras
lecturas; no se encontro reclasificacion historica automatica en estos commits.

## Heroku consultado despues del login autorizado

- Aplicaciones visibles: `gestion-colegiales` y `gestion-servicio-alj`.
- `heroku pipelines --json` devuelve `[]`.
- No se identifico un staging configurado para este proyecto. La otra aplicacion
  no se considera un ambiente de pruebas ni se reutilizo; no se verifico su finalidad
  ni aislamiento de datos.
- Los remotes locales **heroku y colegiales apuntan ambos a gestion-colegiales**.
  No representan dos ambientes distintos.
- Produccion identificada: `gestion-colegiales`, consistente con la documentacion
  operativa del proyecto y con el destino de ambos remotes.
- Release activo reportado: **v511, Deploy 818a324f**, 09/11/2026 21:37:55 -0300.
  El release v510 tambien reportaba 818a324f. Esa etiqueta no permite concluir
  ausencia de Netterm: la comprobacion de archivos siguiente encontro su codigo.
  La publicacion reciente no fue realizada por esta revision.

Comprobacion directa del contenido del paquete publicado mediante `sha256sum`,
ejecutado en un dyno puntual de solo lectura: los **25 archivos** de eges_import,
liquidacion y templates cambiados entre 818a324f y HEAD coinciden exactamente con
los blobs de **5c83248e**. Incluye servicios, modelos, migraciones, URLs, vistas,
pruebas y plantillas de estas funciones. No solo se verifico que las rutas existan.

Manifiesto completo con hashes esperados/observados:
[NETTERM_MANIFIESTO_HEROKU_2026-11-09.json](NETTERM_MANIFIESTO_HEROKU_2026-11-09.json).
Se comparo contra bytes Git, evitando confundir diferencias CRLF/LF del checkout
Windows. Esto no certifica todos los otros archivos de la aplicacion, ni explica
que mecanismo de publicacion produjo la discrepancia de etiqueta; no se especula
sobre su causa o autor.

La guia historica `README_colegiales_deploy.md` menciona otra disposicion de remotes
y otra rama. No seguir sus ejemplos de checkout/push sin comprobar los destinos
actuales: podria publicarse una rama distinta de la version revisada.

## Respaldo y migraciones

`heroku pg:backups` lista un unico backup, **b001**, completado el **31/12/2025**.
No se consultaron respaldos externos a Heroku ni se creo/descargo un backup en esta
revision. Hace falta un respaldo actual y confirmado antes de una futura publicacion
que aplique migraciones.

Los dos commits incorporan **0010, 0011 y 0012** de `eges_import`, no solamente
0011/0012. Son creacion de tablas de origen/auditoria y una relacion de reemplazo;
no contienen una migracion de importes o cantidades de Liquidacion.

El Procfile de la version activa y de la candidata contiene:

```text
release: python manage.py collectstatic --noinput && python manage.py migrate
```

No correr `migrate` manualmente en produccion como parte de esta revision. En una
publicacion autorizada debe verificarse el resultado de la fase release y la version
activa posterior. Una vuelta al codigo previo no revierte los cambios de esquema;
su compatibilidad debe evaluarse antes de usarla como recuperacion.

Consulta remota `python manage.py showmigrations eges_import`: todas las migraciones
mostradas hasta **0012**, incluidas **0010, 0011 y 0012**, tienen `[X]`.
Se consulto el estado; no se aplicaron migraciones en esta revision.
Una primera consulta mediante `shell -c` fallo por las comillas de Windows y no
llego a ejecutarse; fue reemplazada por el comando estandar anterior.

## Verificacion local repetida sobre el HEAD exacto

- **211 pruebas OK**: `eges_import`, `liquidacion.tests_cruce_eges` y
  `liquidacion.tests_respaldo_fuentes`.
- SQLite temporal aislada, tests en memoria, con ruta efectiva comprobada antes de
  ejecutar. MD5PasswordHasher solo en el proceso de tests para agilizar fixtures.
- Carpeta temporal eliminada; no se uso la base habitual para los tests.
- `makemigrations --check --dry-run`: no se requieren archivos de migracion nuevos.
  Esto no demuestra que los existentes esten aplicados en la base productiva.
- `git diff --check 818a324f..HEAD`: sin errores de whitespace.
- Dependencias del lector ya declaradas: openpyxl 3.1.5 y xlrd 2.0.2; el proyecto
  declara Django 5.2.12 y psycopg2 2.9.10.
- No se ejecutaron las pruebas de esta revision en PostgreSQL ni en un staging.

## Alcance funcional encontrado en el codigo publicado

Produccion combinada y tasa de informes en una consulta separada; dashboards EGES
previos conservados. Respaldo automatico de origen por linea profesional con prioridad
EGES, complemento Netterm y autoria inequivoca; sin recalcular cantidades u horarios.

El OK de respaldo **no es OK economico**, no elimina pendientes del control de cierre
ni reemplaza validaciones persistidas. Produccion RX sigue provisional respecto a
unidad de conteo. Equivalencias no comprobadas y nombres truncados siguen pendientes
de calibracion. Detalle funcional:
[produccion y respaldo](../arquitectura/PRODUCCION_Y_RESPALDO_FUENTES_2026-11-09.md).

## Pendientes operativos y para futuras publicaciones

1. Sincronizar los commits con GitHub cuando se autorice el push y aclarar el
   mecanismo/etiquetado del deploy para que una version publicada sea trazable.
   No republicar ni revertir solo por ver 818a324f: las funciones ya estan presentes.
2. Definir si se habilitara un staging separado; no asumir que ya existe ni usar
   otra aplicacion como sustituto sin verificar su finalidad y aislamiento.
3. Confirmar un backup actual de la base destino antes de aplicar nuevos cambios.
4. Completar pruebas de humo/permisos autenticadas en el entorno publicado sin
   cargar fixtures clinicos ni recalcular registros. La revision actual certifica
   hashes, estado de migraciones y pruebas locales; no recorrio pacientes reales.
5. Para futuras versiones, verificar migraciones y pruebas con la candidata,
   preferentemente en PostgreSQL fuera de produccion.
6. Publicar solo la version exacta verificada cuando el usuario lo autorice, y
   comprobar release, login, carga, produccion, respaldo y pantallas anteriores.

No se hizo push, deploy, cambio de configuracion, creacion de app/pipeline/base,
importacion clinica ni modificacion de datos economicos durante esta revision.
Se inicio el login Heroku solicitado por el usuario y comandos puntuales de lectura.
