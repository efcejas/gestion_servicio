import pandas as pd
from django.contrib.auth import get_user_model
from liquidacion.models import RegistroEstudiosPorMedico, Estudios
from datetime import datetime

User = get_user_model()
medico = User.objects.get(username='DenButeler')

mapeo_estudios = {
    'CR': 'RX DE TÓRAX',
    'CT': 'TC DE CEREBRO',
    'MR': 'RM CEREBRO C/ DIFUSIÓN'
}

ruta_excel = r'C:\Users\efcce\OneDrive\Documentos\GitHub\gestion_servicio\Estudios_Denise_Junio.xlsx'
df = pd.read_excel(ruta_excel)
df = df[df['Mod.'].isin(mapeo_estudios.keys())]
df['fecha_parseada'] = pd.to_datetime(df['Fecha de firma final'], dayfirst=True)

cargados = 0
saltados = 0
errores = 0

for _, fila in df.iterrows():
    try:
        mod = fila['Mod.'].strip()
        nombre_estudio = mapeo_estudios.get(mod)
        estudio_base = Estudios.objects.get(nombre__iexact=nombre_estudio)

        dni = str(fila['Id. paciente'])[:8]
        partes = fila['Nombre del paciente'].strip().split(',')
        apellido = partes[0].strip()
        nombre = partes[1].strip() if len(partes) > 1 else ''

        fecha = pd.to_datetime(fila['Fecha de firma final'], dayfirst=True).date()

        existe = RegistroEstudiosPorMedico.objects.filter(
            medico=medico,
            dni_paciente=dni,
            fecha_del_informe=fecha
        ).exists()

        if existe:
            saltados += 1
            continue

        registro = RegistroEstudiosPorMedico.objects.create(
            medico=medico,
            nombre_paciente=nombre,
            apellido_paciente=apellido,
            dni_paciente=dni,
            fecha_del_informe=fecha,
            cantidad_estudio=1
        )
        registro.estudio.add(estudio_base)
        cargados += 1

    except Exception as e:
        errores += 1
        print(f"⚠️ Error con fila: {fila['Nombre del paciente']} ({mod}) → {e}")
        continue

print(f"\n✅ Registros cargados: {cargados}")
print(f"⏭️ Saltados por duplicado: {saltados}")
print(f"❌ Errores: {errores}")
