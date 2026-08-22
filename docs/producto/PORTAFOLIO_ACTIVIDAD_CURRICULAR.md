# Actividad curricular del Portafolio

Fecha de implementación: 22/08/2026

Estado: etapa 1 implementada

## Alcance

El residente puede registrar cursos, congresos o jornadas, ateneos,
presentaciones, trabajos científicos, actividad docente, rotaciones externas y
otras actividades curriculares. El registro admite múltiples evidencias y un
enlace externo opcional.

Las rotaciones externas quedan en esta etapa como antecedente curricular. No
modifican todavía la distribución ni las ausencias de Guardias.

## Flujo

1. El residente activo crea y edita un borrador.
2. Puede adjuntar uno o más documentos y enviarlo para revisión.
3. Un jefe de residentes, instructor o superusuario valida la actividad o la
   devuelve con una observación obligatoria.
4. Una actividad observada vuelve a ser editable y puede reenviarse.
5. Solo las actividades validadas integran los indicadores, la evolución y la
   trayectoria del Portafolio.

Los egresados conservan su historial en modo de solo lectura.

## Evidencias

Los archivos se almacenan con ACL privada en S3/MinIO y con un nombre interno
aleatorio. La base conserva el nombre original, tipo MIME, tamaño, usuario,
fecha de carga y hash SHA-256. La descarga exige autorización del propietario o
de un perfil docente y utiliza una URL firmada de corta duración.

Se admiten imágenes, PDF, documentos de texto, presentaciones y planillas. En
esta etapa la carga pasa por Django. Una carga directa navegador a S3 puede
incorporarse después si el uso real con archivos grandes justifica configurar
CORS y un flujo de confirmación específico.

## Permisos

| Perfil | Registrar | Ver propias | Revisar todas |
|---|---:|---:|---:|
| Residente activo | Sí | Sí | No |
| Egresado | No | Sí | No |
| Jefe de residentes | No | No | Sí |
| Instructor | No | No | Sí |
| Superusuario | No | No | Sí |
| Otros perfiles | No | No | No |

## Próxima integración

La etapa siguiente especializará las rotaciones externas y separará dos
decisiones: su validación curricular y su impacto operativo sobre Guardias. No
se crearán ausencias ni restricciones automáticamente a partir de una actividad
curricular sin una aprobación explícita.
