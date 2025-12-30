"""
Script para generar un archivo Excel de prueba para EGES Import.
Genera datos de ejemplo con diferentes modalidades y estados.
"""
import openpyxl
from datetime import datetime, time, timedelta
import random

def generar_excel_prueba():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "EGES"
    
    # Encabezados
    encabezados = [
        'Nro. Turno',
        'Fecha Turno',
        'Hora Turno',
        'Centro de Atención',
        'Historia Clínica',
        'Apellido y Nombre',
        'Servicio',
        'Equipo',
        'Estado Turno'
    ]
    ws.append(encabezados)
    
    # Datos de ejemplo
    pacientes = [
        ('HC001', 'PEREZ, JUAN'),
        ('HC002', 'GOMEZ, MARIA'),
        ('HC003', 'RODRIGUEZ, CARLOS'),
        ('HC004', 'MARTINEZ, ANA'),
        ('HC005', 'LOPEZ, PEDRO'),
        ('HC006', 'GARCIA, LAURA'),
        ('HC007', 'FERNANDEZ, JOSE'),
        ('HC008', 'SANCHEZ, SOFIA'),
    ]
    
    centros = ['Sede Central', 'Sede Norte', 'Sede Sur']
    estados = ['Informado', 'Pendiente', 'En Proceso']
    
    # Estudios por modalidad
    estudios = {
        'TC': [
            ('TOMOGRAFIA DE TORAX', 'TC SIEMENS 64'),
            ('TOMOGRAFIA DE CEREBRO', 'TC PHILIPS'),
            ('SCANNER DE ABDOMEN', 'TC GE'),
            ('TAC COLUMNA LUMBAR', 'TC SIEMENS 64'),
        ],
        'RM': [
            ('RESONANCIA MAGNETICA CEREBRAL', 'RM PHILIPS 1.5T'),
            ('RESONANCIA DE RODILLA', 'RM SIEMENS 3T'),
            ('RMN COLUMNA DORSAL', 'RM GE 1.5T'),
        ],
        'RX': [
            ('RADIOGRAFIA DE TORAX', 'RAYOS X DIGITAL'),
            ('RX COLUMNA LUMBAR', 'RAYOS X CONVENCIONAL'),
            ('RADIOGRAFIA DE MANO', 'RAYOS X DIGITAL'),
        ],
        'ECO': [
            ('ECOGRAFIA ABDOMINAL', 'ECOGRAFO PHILIPS'),
            ('ECO DOPPLER CAROTIDEO', 'ECOGRAFO GE'),
            ('ULTRASONIDO TIROIDEO', 'ECOGRAFO SAMSUNG'),
        ],
    }
    
    # Insumos
    insumos = [
        ('CONTRASTE INTRAVENOSO IODADO', 'BOMBA INYECTORA'),
        ('MEDICACION PREANESTESICA', 'FARMACIA'),
        ('SEDACION CONSCIENTE', 'ANESTESIA'),
        ('GADOLINIO 15ML', 'CONTRASTE'),
    ]
    
    turno_num = 10000
    fecha_base = datetime(2024, 1, 1)
    
    # Generar 100 filas de ejemplo
    for i in range(100):
        # Fecha aleatoria en enero-marzo 2024
        dias_offset = random.randint(0, 89)  # 3 meses
        fecha = fecha_base + timedelta(days=dias_offset)
        
        # Hora aleatoria entre 8:00 y 18:00
        hora_int = random.randint(8, 18)
        minuto_int = random.choice([0, 15, 30, 45])
        hora = time(hora_int, minuto_int)
        
        # Paciente aleatorio
        hc, nombre = random.choice(pacientes)
        
        # Centro aleatorio
        centro = random.choice(centros)
        
        # Estado (80% Informado, 20% otros)
        estado = random.choices(estados, weights=[80, 10, 10])[0]
        
        # Elegir modalidad (70% estudios, 30% insumos)
        if random.random() < 0.7:
            # Estudio real
            modalidad = random.choice(list(estudios.keys()))
            servicio, equipo = random.choice(estudios[modalidad])
        else:
            # Insumo
            servicio, equipo = random.choice(insumos)
        
        # Agregar fila
        ws.append([
            str(turno_num),
            fecha.strftime('%d/%m/%Y'),
            hora.strftime('%H:%M'),
            centro,
            hc,
            nombre,
            servicio,
            equipo,
            estado
        ])
        
        turno_num += 1
    
    # Guardar archivo
    filename = 'eges_prueba_100filas.xlsx'
    wb.save(filename)
    print(f"✅ Archivo generado: {filename}")
    print(f"   - Total filas: 100")
    print(f"   - Rango de fechas: Enero-Marzo 2024")
    print(f"   - ~70 estudios + ~30 insumos")
    print(f"   - ~80% Estado=Informado")
    
    # Generar archivo pequeño (20 filas) para pruebas rápidas
    wb_small = openpyxl.Workbook()
    ws_small = wb_small.active
    ws_small.title = "EGES"
    ws_small.append(encabezados)
    
    turno_num_small = 20000
    fecha_prueba = datetime(2024, 2, 15)
    
    ejemplos = [
        # TC
        (fecha_prueba, time(9, 0), 'HC001', 'PEREZ, JUAN', 'TOMOGRAFIA DE TORAX', 'TC SIEMENS', 'Informado'),
        (fecha_prueba, time(9, 30), 'HC001', 'PEREZ, JUAN', 'CONTRASTE INTRAVENOSO', 'BOMBA', 'Informado'),
        # RM
        (fecha_prueba, time(10, 0), 'HC002', 'GOMEZ, MARIA', 'RESONANCIA CEREBRAL', 'RM PHILIPS', 'Informado'),
        (fecha_prueba, time(10, 45), 'HC002', 'GOMEZ, MARIA', 'GADOLINIO 15ML', 'CONTRASTE', 'Informado'),
        # RX
        (fecha_prueba, time(11, 0), 'HC003', 'RODRIGUEZ, CARLOS', 'RADIOGRAFIA TORAX FRENTE Y PERFIL', 'RAYOS X', 'Informado'),
        # ECO
        (fecha_prueba, time(14, 0), 'HC004', 'MARTINEZ, ANA', 'ECOGRAFIA ABDOMINAL COMPLETA', 'ECOGRAFO GE', 'Informado'),
        # Pendientes
        (fecha_prueba, time(15, 0), 'HC005', 'LOPEZ, PEDRO', 'SCANNER DE ABDOMEN', 'TC GE', 'Pendiente'),
        (fecha_prueba, time(16, 0), 'HC006', 'GARCIA, LAURA', 'RMN COLUMNA LUMBAR', 'RM SIEMENS', 'En Proceso'),
    ]
    
    for idx, ejemplo in enumerate(ejemplos):
        fecha, hora, hc, nombre, servicio, equipo, estado = ejemplo
        ws_small.append([
            str(20000 + idx),
            fecha.strftime('%d/%m/%Y'),
            hora.strftime('%H:%M'),
            'Sede Central',
            hc,
            nombre,
            servicio,
            equipo,
            estado
        ])
    
    filename_small = 'eges_prueba_8filas.xlsx'
    wb_small.save(filename_small)
    print(f"\n✅ Archivo pequeño generado: {filename_small}")
    print(f"   - Total filas: 8")
    print(f"   - 4 ingresos diferentes")
    print(f"   - 6 estudios finalizados + 2 pendientes")
    print(f"   - 2 insumos (contraste)")


if __name__ == '__main__':
    generar_excel_prueba()
