# Ejemplos de Emails de Pedidos de Estudios

Este archivo contiene ejemplos de formatos de email que podrías recibir para pedidos de ecodoppler y ecocardiogramas. Úsalos para ajustar el parser en `services/email_parser.py`.

## Ejemplo 1: Ecocardiograma simple

```
Asunto: Pedido de estudio - Habitación 302A

Paciente: María González López
DNI: 35.123.456
Historia Clínica: HC-2024-001234
Habitación: 302A
Cama: 1
Piso: 3

Estudio solicitado: Ecocardiograma transtorácico

Indicación clínica: Control post IAM

Médico solicitante: Dr. Roberto Fernández
Servicio: Cardiología

Fecha de solicitud: 13/02/2026
```

## Ejemplo 2: Ecodoppler URGENTE

```
Asunto: URGENTE - Ecodoppler MMII

PACIENTE: Juan Carlos Pérez
DNI: 28456789
HC: HC-2026-005678
HABITACION: 405B - CAMA 2

ESTUDIO: Ecodoppler venoso de miembros inferiores bilateral

INDICACION: Sospecha de TVP. Edema de MII izquierdo.

PRIORIDAD: URGENTE

Dr. Ana Martínez
Clínica Médica
Int: 4501
```

## Ejemplo 3: Ecodoppler carotídeo con formato estructurado

```
--------------------------------------------
SOLICITUD DE ESTUDIO
--------------------------------------------

DATOS DEL PACIENTE:
Apellido y Nombre: RODRIGUEZ, Alberto José
Documento: 42.987.654
Nro. H.C.: 2026-HC-009876
Ubicación: Piso 2 - Habitación 215 - Cama A
Obra Social: OSDE 210
Nro. Afiliado: 2-1234567-8

ESTUDIO REQUERIDO:
Tipo: Ecodoppler carotídeo y vertebral bilateral

DATOS CLINICOS:
Indicación: ACV isquémico hace 72hs. Evaluación de estenosis carotídea.
Prioridad: ALTA

MEDICO SOLICITANTE:
Dr. Carlos Gutiérrez
Servicio: Neurología
Interno: 3210

Fecha: 13/02/2026 10:30hs
--------------------------------------------
```

## Ejemplo 4: Email HTML (simplificado)

```html
<html>
<body>
<h3>Pedido de Estudio</h3>
<table>
  <tr><td>Paciente:</td><td>Silva, Rosa María</td></tr>
  <tr><td>DNI:</td><td>31234567</td></tr>
  <tr><td>HC:</td><td>HC-2026-011223</td></tr>
  <tr><td>Habitación:</td><td>108C</td></tr>
  <tr><td>Estudio:</td><td>Ecocardiograma doppler color</td></tr>
  <tr><td>Indicación:</td><td>Soplo sistólico. Descartar valvulopatía</td></tr>
  <tr><td>Médico:</td><td>Dra. Patricia López</td></tr>
</table>
</body>
</html>
```

## Ejemplo 5: Formato muy simple (WhatsApp/SMS style)

```
Pac: Lopez Juan
DNI 25123456
Hab 310-2
Ecodoppler MMSS derecho
Indicación: fístula para HD
Dr Martinez
```

## Ejemplo 6: Múltiples estudios en un email

```
Buenos días,

Solicito los siguientes estudios:

1) Paciente: González, María Teresa
   DNI: 33456789
   Habitación: 205A
   Estudio: Ecocardiograma TT
   Indicación: Disnea de esfuerzo
   
2) Paciente: Fernández, Pedro Luis  
   DNI: 29876543
   Habitación: 205B
   Estudio: Ecodoppler venoso MMII bilateral
   Indicación: Edema en miembro inferior izquierdo
   
Gracias,
Dr. Roberto Sánchez
Clínica Médica
```

## Ejemplo 7: Ecocardiograma transesofágico (con preparación)

```
Asunto: Pedido TEE - HAB 501

Paciente: Morales, Alberto Ramón
DNI: 27.654.321
HC: 2026-008765
Habitación: 501 - Cama única
Piso: 5to

ESTUDIO SOLICITADO:
Ecocardiograma transesofágico (TEE)

INDICACIÓN CLÍNICA:
FA de reciente comienzo. Descartar trombos intracavitarios previo a cardioversión.

PREPARACIÓN:
Paciente en ayunas desde las 6am
Consentimiento informado firmado

PRIORIDAD: NORMAL

Dra. Claudia Vega
Servicio de Cardiología
Interno: 5502

Fecha: 13/02/2026
```

## Ejemplo 8: Formato con siglas médicas

```
Pcte: Ramirez L.
HC: 2026/1234
Hab: 312-B

Solicito:
- ECD carotídeo bilat.
- Indicación: AIT hace 1 semana

Dr. M. Torres
Neuro
```

---

## Cómo usar estos ejemplos

1. **Copia** uno de estos ejemplos
2. **Pega** en el shell de Django:

```python
from pedidos_estudios.services.email_parser import extraer_informacion_basica

texto = """
# Pega aquí el ejemplo
"""

datos = extraer_informacion_basica(texto)
print(datos)
```

3. **Verifica** qué datos extrae correctamente
4. **Ajusta** los patrones regex en `email_parser.py` según sea necesario
5. **Repite** con los diferentes formatos hasta que funcione bien

---

## Patrones comunes detectados

### Para el nombre del paciente:
- `Paciente: María González`
- `PACIENTE: Juan Pérez`
- `Apellido y Nombre: RODRIGUEZ, Alberto`
- `Pac: Lopez Juan`
- `Pcte: Ramirez L.`

### Para DNI:
- `DNI: 35.123.456`
- `DNI 25123456`
- `Documento: 42.987.654`

### Para Habitación:
- `Habitación: 302A`
- `HAB 310-2`
- `Hab: 312-B`
- `Ubicación: Piso 2 - Habitación 215`

### Para el estudio:
- `Estudio solicitado: Ecocardiograma`
- `ESTUDIO: Ecodoppler venoso`
- `Tipo: Ecodoppler carotídeo`
- `Solicito: ECD carotídeo`

### Para prioridad:
- Palabras clave: `URGENTE`, `ALTA`, `STAT`, `EMERGENCIA`
