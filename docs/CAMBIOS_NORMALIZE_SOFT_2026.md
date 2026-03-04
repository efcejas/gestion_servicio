# 🔄 Cambios en Normalización de HTML - Marzo 2026

## 📋 Resumen Ejecutivo

Se ha implementado una nueva función `normalize_html_content_soft()` que **reemplaza** a `normalize_html_content()` en todos los flujos principales. El cambio resuelve el problema de destrucción de estructura intencional en plantillas de preinformes.

**Estado:** ✅ Implementado, testeado y validado  
**Fecha:** Marzo 2026  
**Impacto:** MEDIO - Cambio en flujo crítico de procesamiento de plantillas  
**Tests:** 10/10 pasados correctamente

---

## 🎯 Problema Resuelto

### ❌ Versión anterior: `normalize_html_content()`

**Comportamiento:** Agresivo - convierte **TODOS** los `<br>` a `</p><p>`

**Casos problemáticos:**

1. **Técnicas narrativas destruidas:**
   ```html
   <!-- INPUT (intencional del usuario) -->
   <p><strong>TÉCNICA:</strong></p>
   <p>Se realizó estudio<br>con contraste EV</p>
   
   <!-- OUTPUT (destruido) -->
   <p><strong>TÉCNICA:</strong></p>
   <p>Se realizó estudio</p>
   <p>con contraste EV</p>  <!-- ❌ Rompió la estructura -->
   ```

2. **Espaciado vertical perdido:**
   ```html
   <!-- INPUT (2 <br> intencionalmente) -->
   <p>Texto 1<br><br>Texto 2</p>
   
   <!-- OUTPUT (espaciado perdido) -->
   <p>Texto 1</p>
   <p>Texto 2</p>  <!-- ❌ Solo 1 espacio entre párrafos -->
   ```

3. **Tablas rotas:**
   ```html
   <!-- INPUT (tabla con <br> intencionales) -->
   <table>
     <tr><td>Línea 1<br>Línea 2</td></tr>
   </table>
   
   <!-- OUTPUT (tabla rota con <p> dentro de <td>) -->
   <table>
     <tr><td><p>Línea 1</p><p>Línea 2</p></td></tr>
   </table>  <!-- ❌ HTML inválido -->
   ```

---

## ✅ Nueva Solución: `normalize_html_content_soft()`

### Heurística de Decisión

La nueva función **analiza el contexto** antes de decidir si convierte o no:

```python
def normalize_html_content_soft(content, br_threshold=3):
    """
    1. HTML con 2+ <p>: NO reestructurar (ya está bien formado)
    2. HTML con 0 <p>: Convertir líneas por saltos \n
    3. HTML con 1 <p> y >= 3 <br>: Interpretar como "pegado sucio" → convertir
    4. HTML con 1 <p> y < 3 <br>: PRESERVAR (probablemente intencional)
    5. No tocar <br> dentro de <table>, <ul>, <ol>
    """
```

### Comparativa de Comportamiento

| Caso | Versión Agresiva | Versión Soft |
|------|-----------------|--------------|
| **2+ párrafos bien formados** | ❌ Intenta reestructurar | ✅ Preserva tal cual |
| **1 párrafo con 1-2 `<br>`** | ❌ Convierte (destruye técnica) | ✅ Preserva (técnica narrativa) |
| **1 párrafo con 5+ `<br>`** | ✅ Convierte ("pegado sucio") | ✅ Convierte ("pegado sucio") |
| **`<br>` en tablas/listas** | ❌ Convierte (rompe estructura) | ✅ NO convierte (preserva) |
| **Texto plano sin HTML** | ✅ Convierte líneas a `<p>` | ✅ Convierte líneas a `<p>` |
| **Párrafos vacíos `<p>&nbsp;</p>`** | ✅ Elimina | ✅ Elimina |

---

## 🔧 Cambios en el Código

### Archivos Modificados

1. **`preinformes/models.py`**
   - **Añadido:** `normalize_html_content_soft()` (líneas 127-270)
   - **Preservado:** `normalize_html_content()` (por compatibilidad, deprecado)
   - **Actualizado:** `RevisionPreinforme.inicializar_informe_final()` (línea 688)
     ```python
     # ANTES
     self.informe_final_html = normalize_html_content(plantilla.contenido_html)
     
     # DESPUÉS
     self.informe_final_html = normalize_html_content_soft(plantilla.contenido_html)
     ```

2. **`preinformes/views.py`**
   - **Actualizado:** `crear_plantilla_residente()` (línea 750)
     ```python
     # ANTES
     from .models import normalize_html_content
     plantilla.contenido_html = normalize_html_content(html_contenido)
     
     # DESPUÉS
     from .models import normalize_html_content_soft
     plantilla.contenido_html = normalize_html_content_soft(html_contenido)
     ```

3. **`preinformes/admin.py`**
   - **Actualizado:** `PlantillaPreinformeAdmin.save_model()` (línea 85)
     ```python
     # ANTES
     from .models import normalize_html_content
     obj.contenido_html = normalize_html_content(obj.contenido_html)
     
     # DESPUÉS
     from .models import normalize_html_content_soft
     obj.contenido_html = normalize_html_content_soft(obj.contenido_html)
     ```

4. **`preinformes/management/commands/limpiar_plantillas.py`**
   - **Actualizado:** Comando batch (líneas 12 y 83)
     ```python
     # ANTES
     from preinformes.models import normalize_html_content
     plantilla.contenido_html = normalize_html_content(plantilla.contenido_html)
     
     # DESPUÉS
     from preinformes.models import normalize_html_content_soft
     plantilla.contenido_html = normalize_html_content_soft(plantilla.contenido_html)
     ```

5. **`preinformes/tests.py`**
   - **Añadido:** Clase `NormalizeHTMLContentSoftTest` con 10 tests unitarios

6. **`docs/ANALISIS_PROCESAMIENTO_HTML.md`**
   - **Actualizado:** Documentación marcando `normalize_html_content()` como deprecada
   - **Añadido:** Sección completa de `normalize_html_content_soft()`

---

## ✅ Testing y Validación

### Tests Unitarios (10/10 ✓)

```
test_caso1_preservar_tecnica_narrativa ............................. ok
test_caso2_convertir_pegado_sucio ................................... ok
test_caso3_multiples_parrafos_bien_estructurados ..................... ok
test_caso4_eliminar_parrafos_vacios ................................. ok
test_caso5_texto_plano_con_saltos ................................... ok
test_caso6_br_threshold_custom ...................................... ok
test_caso7_contenido_vacio_o_none ................................... ok
test_caso8_html_con_atributos ....................................... ok
test_caso9_br_en_tabla_no_convierte ................................. ok
test_caso10_comparacion_con_normalize_original ....................... ok

----------------------------------------------------------------------
Ran 10 tests in 0.015s

OK
```

### Test de Integración

```python
# INPUT
<p><strong>TÉCNICA:</strong></p><p>Se realizó estudio<br>con contraste EV</p>

# OUTPUT
<p><strong>TÉCNICA:</strong></p><p>Se realizó estudio<br>con contraste EV</p>

✓ Preservó estructura (2+ <p>)
```

---

## 📊 Cobertura de Casos de Prueba

| Test | Descripción | Resultado |
|------|-------------|-----------|
| **Caso 1** | Técnica narrativa con 1-2 `<br>` | ✅ Preservó |
| **Caso 2** | "Pegado sucio" con 5+ `<br>` | ✅ Convirtió |
| **Caso 3** | Múltiples párrafos bien formados | ✅ No reestructuró |
| **Caso 4** | Párrafos vacíos (`<p>&nbsp;</p>`) | ✅ Eliminó |
| **Caso 5** | Texto plano sin HTML | ✅ Convirtió líneas a `<p>` |
| **Caso 6** | Threshold customizado (`br_threshold=2`) | ✅ Funcionó |
| **Caso 7** | Edge cases (`None`, `''`, espacios) | ✅ Manejó correctamente |
| **Caso 8** | HTML con atributos (`class`, `style`) | ✅ Preservó atributos |
| **Caso 9** | `<br>` dentro de tablas/listas | ✅ NO convirtió |
| **Caso 10** | Comparación soft vs agresiva | ✅ Comportamientos diferenciados |

---

## 🚀 Despliegue y Rollout

### Estado Actual

- ✅ Código implementado
- ✅ Tests unitarios aprobados (10/10)
- ✅ Test de integración validado
- ✅ Documentación actualizada
- ⏳ **Pendiente:** Deploy a producción en Heroku
- ⏳ **Pendiente:** Monitoreo post-deploy (1 semana)

### Checklist de Deploy

- [ ] `git add` archivos modificados
- [ ] `git commit -m "feat: Implement normalize_html_content_soft() to respect user structure"`
- [ ] `git push heroku feature/colegiales:main`
- [ ] Validar deploy exitoso (logs en Heroku)
- [ ] User acceptance testing con residentes (crear 2-3 plantillas nuevas)
- [ ] Monitorear logs de errores (primeras 48h)
- [ ] Ejecutar `python manage.py limpiar_plantillas --dry-run` en producción

### Rollback Plan

Si surgen problemas, revertir a versión anterior:

```bash
# En models.py, views.py, admin.py, limpiar_plantillas.py
# Cambiar de nuevo a:
from .models import normalize_html_content
plantilla.contenido_html = normalize_html_content(...)
```

**Nota:** `normalize_html_content()` NO ha sido eliminada, solo marcada como deprecada.

---

## 📈 Métricas de Éxito

Después del deploy, validar:

1. **Calidad de plantillas:**
   - ✅ Técnicas narrativas preservadas (revisar 5 plantillas aleatorias)
   - ✅ Espaciado vertical correcto en CKEditor
   - ✅ Tablas/listas sin `<p>` internos

2. **Detección de "pegado sucio":**
   - ✅ HTML copiado de Word se normaliza correctamente
   - ✅ No más bloques de texto sin párrafos

3. **Usabilidad:**
   - ✅ Residentes reportan mejor experiencia (menos "el sistema rompió mi plantilla")
   - ✅ Staff no reporta regresiones en revisiones

---

## 🔍 Parámetro Configurable

### `br_threshold` (default=3)

```python
# Uso básico (threshold por defecto = 3)
normalize_html_content_soft(html)

# Uso customizado (más estricto, threshold = 2)
normalize_html_content_soft(html, br_threshold=2)
```

**Recomendaciones:**

- **br_threshold=3** (default): Balance entre preservar técnicas narrativas y detectar "pegado sucio"
- **br_threshold=2**: Más agresivo, convierte antes. Usar si se detectan muchos "pegados sucios" en producción
- **br_threshold=4**: Más conservador, preserva más. Usar si usuarios reportan conversiones no deseadas

---

## 📚 Documentación Relacionada

1. [ANALISIS_PROCESAMIENTO_HTML.md](./ANALISIS_PROCESAMIENTO_HTML.md) - Análisis completo de funciones HTML
2. [FLUJO_HTML_VISUAL.md](./FLUJO_HTML_VISUAL.md) - Diagramas de flujo ASCII
3. [REFERENCIA_RAPIDA_HTML.md](./REFERENCIA_RAPIDA_HTML.md) - Cheat sheet para desarrolladores

---

## 👥 Autores y Contacto

- **Implementación:** Sistema de Gestión de Preinformes
- **Testing:** 10 tests unitarios automatizados
- **Deploy:** Pendiente a Heroku (entorno `feature/colegiales`)
- **Revisión de código:** Pendiente

---

## 📅 Timeline

| Fecha | Evento |
|-------|--------|
| **Marzo 2026** | Implementación y testing |
| **Marzo 2026** | Documentación completa |
| **Pendiente** | Deploy a producción |
| **Pendiente + 1 semana** | Monitoreo post-deploy |
| **Pendiente + 1 mes** | Evaluación de métricas de éxito |

---

## 🎓 Lecciones Aprendidas

1. **Heurística > Reglas universales:** No todos los `<br>` son iguales. El contexto importa.
2. **Preserve primero, normaliza después:** En caso de duda, es mejor NO tocar la estructura del usuario.
3. **Testing exhaustivo:** Los 10 tests cubrieron edge cases que no habíamos considerado inicialmente.
4. **Backward compatibility:** Preservar `normalize_html_content()` permitirá rollback sin problemas.

---

**🔖 Versión:** 1.0  
**📅 Última actualización:** Marzo 2026  
**📌 Estado:** ✅ Implementado, ⏳ Deploy pendiente
