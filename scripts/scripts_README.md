# Scripts de carga masiva de estudios médicos

Este directorio contiene scripts auxiliares para cargar registros médicos desde archivos Excel al sistema de gestión.

## 📁 Archivos

### `cargar_ecografias_denise.py`
Carga estudios de tipo **Ecografía** (mod. `US`) realizados por la médica **Denise Buteler** durante el mes de junio. Usa como estudio base: `ECO ABDOMINAL`.

- Ruta del Excel: `Ecografías_Denise_Junio.xlsx`
- Se validan duplicados por médico + DNI + fecha
- Se interpreta correctamente la fecha usando `dayfirst=True`

### `cargar_estudios_denise.py`
Carga estudios de tipo **Radiografía, Tomografía y Resonancia** para Denise Buteler.

- Ruta del Excel: `Estudios_Denise_Junio.xlsx`
- Mapeo usado:
  - `CR` → `RX DE TÓRAX`
  - `CT` → `TC DE CEREBRO`
  - `MR` → `RM CEREBRO C/ DIFUSIÓN`

## ▶️ Cómo ejecutarlos

Desde la raíz del proyecto (`gestion_servicio`), ejecutá:

```bash
python manage.py shell < scripts/cargar_ecografias_denise.py
python manage.py shell < scripts/cargar_estudios_denise.py
```

> Asegurate de que los archivos `.xlsx` estén en la ruta correcta especificada dentro del script.

## 🛡️ Notas
- Los scripts evitan registros duplicados.
- Las fechas se procesan con cuidado para evitar errores de formato (`dayfirst=True`).
- Adaptado para `RegistroEstudiosPorMedico` con estudios relacionados por `ManyToMany`.

