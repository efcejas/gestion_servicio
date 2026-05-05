---
name: "Colegiales Review Critico"
description: "Prompt para pedir review tecnico con foco en bugs, regresiones y riesgos operativos."
argument-hint: "Describe modulo, alcance del review y riesgo principal"
agent: "agent"
---
Realiza un review tecnico con mentalidad de produccion clinica.

Orden obligatorio de salida:
1) Hallazgos por severidad (critico, alto, medio, bajo)
2) Evidencia concreta por archivo/linea
3) Riesgo operativo-clinico de cada hallazgo
4) Fix sugerido minimo viable
5) Gaps de testing

Criterios de control:
- Seguridad y permisos por rol
- Integridad de datos y transacciones
- Reglas de dominio medico
- Rendimiento (N+1, queries costosas)
- Timezone y fechas
- UX de flujo real (menos friccion, mas claridad)

Si no hay hallazgos:
- Decir explicitamente "sin hallazgos de bug o regresion"
- Indicar riesgos remanentes y pruebas faltantes
