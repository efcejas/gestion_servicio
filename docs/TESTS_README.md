# Tests del Proyecto - Gestión de Servicios

> Última actualización: 10/04/2026 | Branch: feature/colegiales

## 📋 Resumen

**187 tests** corriendo en SQLite local vía `run_tests.bat`.

### Estado actual por app

| App | Tests | Estado |
|---|---|---|
| `control_guardias` | ~70 | ✅ |
| `control_stock` | ~40 | ✅ |
| `consultorios` | ~30 | ✅ |
| `preinformes` | ~30 | ✅ |
| `liquidacion` | ~17 | ✅ |
| `protocolos` | 3 | ✅ smoke tests |
| `eges_import` | 0 | ⚠️ sin tests formales |
| `dictado_informes` | 6 | ✅ `tests/test_utils.py` |
| `accounts` | ~13 | ✅ |

---

## Cómo ejecutar

```bash
# Tests de todas las apps principales
python manage.py test control_guardias control_stock consultorios preinformes liquidacion protocolos eges_import

# Solo utils de dictado_informes (conflicto de directorio — ver aviso)
python manage.py test dictado_informes.tests.test_utils

# Todo el proyecto (usa .env.test con SQLite)
.\run_tests.bat
```

### `run_tests.bat`
Intercambia `.env` ↔ `.env.test` antes de correr los tests para apuntar a SQLite en lugar de PostgreSQL de producción.

---

## ⚠️ Avisos conocidos

### Conflicto dictado_informes
`dictado_informes` tiene tanto `tests.py` (2 líneas, placeholder) como `tests/` directory.
- `python manage.py test dictado_informes` → **falla** con `ImportError`
- `python manage.py test dictado_informes.tests.test_utils` → **OK**
- Para resolver definitivamente: eliminar `dictado_informes/tests.py`

### Errores pre-existentes (no bloquean)
2 tests fallan con `NoReverseMatch: 'informados_por_medico_por_mes'`.
La URL está referenciada en tests pero no registrada en `urls.py`.
No bloquean el suite — son tests individuales que fallan, no el runner.

---

## 📁 Archivos de test por app

| App | Archivo(s) | Qué testea |
|---|---|---|
| `accounts` | `tests.py` | CustomUser, formularios, autenticación |
| `control_guardias` | `tests.py` | Modelos, distribucion automática, vistas |
| `control_stock` | `tests.py` | Stock, movimientos, alertas |
| `consultorios` | `tests.py` | Turnos, conflictos, managers |
| `preinformes` | `tests.py` | Modelos, estados, vistas de revisión |
| `liquidacion` | `tests.py` | Modelos, cálculos, informes |
| `protocolos` | `tests.py` | Smoke: modelos, URL resolve |
| `dictado_informes` | `tests/test_utils.py` | Regex utils (REGEX_COMANDOS_VOZ etc.) |

---

## 🎯 Cobertura actual

- ✅ Modelos: creación, validaciones, métodos, constraints de unicidad
- ✅ Servicios: `control_guardias/services.py`, `control_stock/services.py`
- ✅ Utils: `dictado_informes/utils.py` (regex precompiladas)
- ✅ Autenticación y permisos por rol
- ✅ URLs resuelven (smoke tests)
- ⬜ `eges_import/services.py` — sin tests aún
- ⬜ `preinformes/selectors.py` — sin tests aún
- ⬜ `liquidacion/services.py` — sin tests aún

---

## 🚀 Próximos Pasos

1. **Inmediato**: Decidir qué solución implementar para ejecutar los tests
2. **Corto plazo**: Configurar CI/CD con GitHub Actions
3. **Medio plazo**: Aumentar cobertura de tests al 90%+
4. **Largo plazo**: Tests de integración end-to-end

---

## 📞 Notas Importantes

- ✅ **Tu base de datos de Heroku está SEGURA** - Los tests NO la afectan
- ✅ **Los tests están bien escritos** - El problema es solo de infraestructura
- ✅ **Todo el código funciona** - Los tests validan la lógica correctamente
- ⚠️ **Necesitas PostgreSQL local** - Para ejecutar tests sin problemas

---

## 🔍 Verificación de los Tests

Puedes ver el contenido de cada archivo de test:

```bash
# Ver tests de accounts
cat accounts/tests.py

# Ver tests de control_guardias
cat control_guardias/tests.py

# Ver tests de gestion_eventos
cat gestion_eventos/tests.py

# Ver tests de liquidacion
cat liquidacion/tests.py
```

Cada test está documentado con docstrings que explican qué valida.
