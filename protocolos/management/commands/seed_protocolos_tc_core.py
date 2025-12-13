from django.core.management.base import BaseCommand
from protocolos.models import Modalidad, RegionAnatomica, Tag, Protocolo, FaseAdquisicion


class Command(BaseCommand):
    help = 'Carga 5 protocolos críticos de TC faltantes para un servicio general de radiología'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Cargando protocolos críticos de TC...'))
        
        protocolos_creados = 0
        protocolos_actualizados = 0
        fases_creadas = 0
        fases_actualizadas = 0
        fases_eliminadas = 0

        # Asegurar que existe modalidad TC
        tc, _ = Modalidad.objects.get_or_create(
            codigo='TC',
            defaults={'nombre': 'Tomografía Computada'}
        )

        # Asegurar que existen las regiones necesarias
        tap, _ = RegionAnatomica.objects.get_or_create(
            codigo='TAP',
            defaults={'nombre': 'Tórax-Abdomen-Pelvis'}
        )
        abdomen, _ = RegionAnatomica.objects.get_or_create(
            codigo='ABD',
            defaults={'nombre': 'Abdomen'}
        )
        craneo, _ = RegionAnatomica.objects.get_or_create(
            codigo='CRANEO',
            defaults={'nombre': 'Cráneo'}
        )
        columna, _ = RegionAnatomica.objects.get_or_create(
            codigo='COLUMNA',
            defaults={'nombre': 'Columna'}
        )
        torax, _ = RegionAnatomica.objects.get_or_create(
            codigo='TORAX',
            defaults={'nombre': 'Tórax'}
        )

        # Asegurar que existen los tags necesarios
        tag_urgencia, _ = Tag.objects.get_or_create(nombre='Urgencia')
        tag_aorta, _ = Tag.objects.get_or_create(nombre='Aorta')
        tag_litiasis, _ = Tag.objects.get_or_create(nombre='Litiasis')
        tag_acv, _ = Tag.objects.get_or_create(nombre='ACV')
        tag_trauma, _ = Tag.objects.get_or_create(nombre='Trauma')
        tag_oncologico, _ = Tag.objects.get_or_create(nombre='Oncológico')
        tag_infeccion, _ = Tag.objects.get_or_create(nombre='Infección')
        tag_mediastino, _ = Tag.objects.get_or_create(nombre='Mediastino')

        # ===== PROTOCOLO 1: ANGIO-TC AORTA =====
        protocolo_aorta, created = Protocolo.objects.update_or_create(
            nombre='Angio-TC Aorta (síndrome aórtico agudo)',
            modalidad=tc,
            region=tap,
            defaults={
                'descripcion': 'Protocolo de urgencia para evaluación de síndrome aórtico agudo: disección, aneurisma roto, hematoma intramural, úlcera penetrante.',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': True,
                'calibre_via_minimo': '18G',
                'sitio_via_preferido': 'Fosa antecubital (preferible derecha)',
                'preparacion_paciente': '''Vía periférica calibre 18G o 20G obligatorio
Flujo de inyección alto: 4-5 ml/seg
Verificar función renal (urgencia relativa)
NO retrasar el estudio por ayuno en emergencia vital
Paciente en decúbito supino con brazos elevados''',
                'cobertura_global': 'Desde entrada torácica (cayado aórtico completo) hasta bifurcación ilíaca',
                'notas_docentes': '''URGENCIA VITAL - Evaluación sistemática:

1. AORTA TORÁCICA:
   - Cayado: origen de troncos supraaórticos
   - Descendente: buscar doble lumen, flap intimal
   - Diámetro: >4cm en ascendente es aneurisma
   
2. AORTA ABDOMINAL:
   - Emergencia de troncos viscerales (tronco celíaco, AMS, renales)
   - Flap de disección: diferenciar luz verdadera (más pequeña) de falsa
   - Trombosis de ramas: buscar hipoperfusión visceral
   
3. SIGNOS CRÍTICOS:
   - Hemopericardio (disección tipo A)
   - Hemomediastino, hemotórax
   - Contraste extravasado = ruptura activa
   
4. VARIANTES: Distinguir disección de úlcera penetrante y hematoma intramural''',
                'es_activo': True,
            }
        )
        protocolo_aorta.tags.set([tag_urgencia, tag_aorta])
        
        if created:
            protocolos_creados += 1
        else:
            protocolos_actualizados += 1

        # Fase para angio-TC aorta
        fase_aorta, fase_created = FaseAdquisicion.objects.update_or_create(
            protocolo=protocolo_aorta,
            orden=1,
            defaults={
                'nombre': 'Fase arterial aórtica',
                'tipo_fase': 'ART',
                'region': tap,
                'delay_segundos': None,
                'cobertura_desde': 'Entrada torácica',
                'cobertura_hasta': 'Bifurcación ilíaca',
                'ventanas_recomendadas': 'Mediastino (W350/L50), Vascular (W600/L200)',
                'detalles_tecnicos': '100-120 kVp, cortes 1-2mm, MPR y MIP en múltiples planos',
                'notas_para_residente': '''Usar BOLUS TRACKING con ROI en aorta descendente, umbral 150 UH.
Flujo: 4-5 ml/seg, volumen 80-100ml.
Evaluar inmediatamente: flap intimal, doble luz, calibre aórtico.
Reconstruir en planos coronal y sagital oblicuo siguiendo el eje aórtico.
MIP de 10-15mm útiles para visión panorámica de la aorta.'''
            }
        )
        if fase_created:
            fases_creadas += 1
        else:
            fases_actualizadas += 1
        
        # Eliminar fases obsoletas (solo debe tener orden 1)
        expected_orders = [1]
        deleted_count = FaseAdquisicion.objects.filter(protocolo=protocolo_aorta).exclude(orden__in=expected_orders).delete()[0]
        fases_eliminadas += deleted_count

        # ===== PROTOCOLO 2: URO-TC LITIASIS =====
        protocolo_urotc, created = Protocolo.objects.update_or_create(
            nombre='Uro-TC litiasis (KUB sin contraste)',
            modalidad=tc,
            region=abdomen,
            defaults={
                'descripcion': 'Protocolo de urgencia para evaluación de cólico renal, litiasis urinaria y obstrucción del tracto urinario. Sin contraste para máxima sensibilidad a cálculos.',
                'requiere_contraste_ev': False,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'preparacion_paciente': '''NO requiere contraste, NO requiere ayuno
NO requiere vía periférica
Vejiga llena es ideal pero no obligatorio
Protocolo de BAJA DOSIS (low dose)
Paciente en decúbito supino''',
                'cobertura_global': 'Desde polos renales superiores hasta vejiga completa (incluir uretra proximal)',
                'notas_docentes': '''URGENCIA - Cólico renal:

1. DETECTAR LITIASIS:
   - Buscar imágenes hiperdensas en trayecto urinario
   - Medir tamaño en mm (>5mm difícil pasaje espontáneo)
   - Localización: cálices, pelvis, UPU, uréter, UVU, vejiga
   
2. SIGNOS DE OBSTRUCCIÓN:
   - Hidronefrosis (dilatación calicopiélica)
   - Hidrouréter proximal al cálculo
   - Edema perirrenal (grasa aumentada de densidad)
   - Nefrograma estriado (si hay contraste previo)
   
3. DIAGNÓSTICOS DIFERENCIALES:
   - Flebolito (redondo, liso, en trayecto venoso)
   - Apendicitis retrocecal (en cólico derecho)
   - Quiste ovárico complicado
   
4. COMPLICACIONES:
   - Pionefrosis (nivel hidroaéreo en sistema colector)
   - Absceso perinéfrico''',
                'es_activo': True,
            }
        )
        protocolo_urotc.tags.set([tag_urgencia, tag_litiasis])
        
        if created:
            protocolos_creados += 1
        else:
            protocolos_actualizados += 1

        # Fase para uro-TC
        fase_urotc, fase_created = FaseAdquisicion.objects.update_or_create(
            protocolo=protocolo_urotc,
            orden=1,
            defaults={
                'nombre': 'Adquisición sin contraste KUB',
                'tipo_fase': 'SIN',
                'region': abdomen,
                'cobertura_desde': 'Polos renales superiores',
                'cobertura_hasta': 'Vejiga (incluir completa)',
                'ventanas_recomendadas': 'Parénquima (W400/L40), Ósea (W2000/L400)',
                'detalles_tecnicos': 'BAJA DOSIS: 100-120 kVp, mAs reducidos (50-100), cortes 3mm',
                'notas_para_residente': '''Protocolo LOW DOSE para reducir radiación (pacientes jóvenes, múltiples estudios).
Sin contraste: todos los cálculos son hiperdensos, no necesitamos contraste.
Evaluar SISTEMÁTICAMENTE:
- Riñones: tamaño, hidronefrosis, edema perirrenal
- Uréteres: seguir TODO el trayecto buscando cálculos (UPU, iliaco, pelviano, UVU)
- Vejiga: cálculos vesicales, engrosamiento parietal
Usar ventana ÓSEA para detectar cálculos pequeños.
Reconstrucciones coronales muy útiles para seguir uréter.'''
            }
        )
        if fase_created:
            fases_creadas += 1

        # ===== PROTOCOLO 3: ANGIO-TC CEREBRAL =====
        protocolo_angiotc_cerebral, created = Protocolo.objects.update_or_create(
            nombre='Angio-TC cerebral (stroke code)',
            modalidad=tc,
            region=craneo,
            defaults={
                'descripcion': 'Protocolo de urgencia para evaluación de ACV isquémico agudo en contexto de stroke code. Detecta oclusión de grandes vasos (LVO) para candidatos a trombectomía mecánica.',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'calibre_via_minimo': '18G',
                'sitio_via_preferido': 'Fosa antecubital',
                'preparacion_paciente': '''Vía periférica calibre 18G o 20G
Flujo: 4-5 ml/seg para opacificación arterial óptima
NO RETRASAR por ayuno (urgencia tiempo-dependiente)
Inmovilización de cabeza con cinta/almohada
Ventana terapéutica: primeras 6-24 horas del ictus''',
                'cobertura_global': 'Desde cayado aórtico/origen de carótidas comunes hasta vertex craneal',
                'notas_docentes': '''STROKE CODE - URGENCIA TIEMPO-DEPENDIENTE:

1. PROTOCOLO COMPLETO:
   - TC sin contraste (descartar hemorragia)
   - Angio-TC (este protocolo: detectar LVO)
   - Perfusión cerebral (opcional según centro)
   
2. BUSCAR OCLUSIÓN DE GRANDES VASOS (LVO):
   - ACI intracraneal
   - M1 de ACM (segmento horizontal)
   - M2 de ACM (ramas insulares)
   - Basilar
   - ACP, ACA (menos frecuente)
   
3. HALLAZGOS CLAVE:
   - Stop abrupto de contraste = oclusión
   - Circulación colateral: leptomeníngea (buen pronóstico)
   - Placas de ateroma en carótidas
   - Disección arterial (flap, doble luz)
   
4. CANDIDATOS A TROMBECTOMÍA:
   - Oclusión de gran vaso (ACI, M1, basilar)
   - Dentro de ventana terapéutica
   - Sin hemorragia en TC basal
   - Penumbra salvable (perfusión)''',
                'es_activo': True,
            }
        )
        protocolo_angiotc_cerebral.tags.set([tag_urgencia, tag_acv])
        
        if created:
            protocolos_creados += 1
        else:
            protocolos_actualizados += 1

        # Fase para angio-TC cerebral
        fase_cerebral, fase_created = FaseAdquisicion.objects.update_or_create(
            protocolo=protocolo_angiotc_cerebral,
            orden=1,
            defaults={
                'nombre': 'Fase arterial intracraneal',
                'tipo_fase': 'ART',
                'region': craneo,
                'delay_segundos': None,
                'cobertura_desde': 'Cayado aórtico / Origen de carótidas comunes',
                'cobertura_hasta': 'Vertex craneal',
                'ventanas_recomendadas': 'Cerebro (W80/L40), Vascular (W600/L200)',
                'detalles_tecnicos': '100-120 kVp, cortes 0.625-1mm, MPR y MIP',
                'notas_para_residente': '''Usar BOLUS TRACKING con ROI en carótida común o cayado aórtico, umbral 100-150 UH.
Flujo alto: 4-5 ml/seg, volumen 60-80ml.
Adquisición cráneo-caudal para captar pico arterial cerebral.

EVALUACIÓN SISTEMÁTICA:
1. Polígono de Willis: simetría, variantes anatómicas
2. ACM: seguir M1 (horizontal) y M2 (insular) bilateralmente
3. ACA: A1, A2 (interhemisférica)
4. Circulación posterior: basilar, ACPs
5. Circulación extracraneal: carótidas, vertebrales

Reconstrucciones MIP 5-10mm en plano axial y coronal.
Comparar ambos hemisferios siempre (asimetría = oclusión).'''
            }
        )
        if fase_created:
            fases_creadas += 1
        else:
            fases_actualizadas += 1
        
        # Eliminar fases obsoletas (solo debe tener orden 1)
        expected_orders = [1]
        deleted_count = FaseAdquisicion.objects.filter(protocolo=protocolo_angiotc_cerebral).exclude(orden__in=expected_orders).delete()[0]
        fases_eliminadas += deleted_count

        # ===== PROTOCOLO 4: TC COLUMNA CERVICAL TRAUMA =====
        protocolo_columna_cervical, created = Protocolo.objects.update_or_create(
            nombre='TC columna cervical trauma (sin contraste)',
            modalidad=tc,
            region=columna,
            defaults={
                'descripcion': 'Protocolo de urgencia para evaluación de trauma cervical, descarte de fracturas vertebrales y lesión raquimedular. Sin contraste para máxima resolución ósea.',
                'requiere_contraste_ev': False,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'preparacion_paciente': '''NO requiere contraste ni vía periférica
NO requiere ayuno
Paciente con collar cervical hasta descartar fractura
Inmovilización estricta durante el estudio
Brazos a los lados para no interferir con T1
Coordinación con equipo de trauma/emergencias''',
                'cobertura_global': 'Desde base de cráneo (clivus/occipital) hasta cuerpo vertebral T1 completo',
                'notas_docentes': '''TRAUMA - Politraumatizado:

1. EVALUACIÓN SISTEMÁTICA (de C1 a T1):
   - Alineación: líneas anterior, posterior, espinolaminar
   - Espacios: interdiscales, prevertebral, interespinoso
   - Fracturas: cuerpos, pedículos, láminas, apófisis
   - Luxaciones/subluxaciones facetarias
   
2. FRACTURAS INESTABLES (requieren fijación):
   - Fractura de Jefferson (C1, estallido del atlas)
   - Fractura del ahorcado (C2, espondilolistesis traumática)
   - Fractura-luxación (cualquier nivel)
   - Estallido con compromiso del canal
   
3. TEJIDOS BLANDOS:
   - Hematoma prevertebral (engrosamiento >7mm en C2)
   - Ligamento longitudinal posterior (interrupción)
   - Canal raquídeo: medir diámetro, buscar estenosis
   - Médula: hipodensidad = contusión/edema
   
4. SIGNOS DE LESIÓN MEDULAR:
   - Canal raquídeo <13mm en cualquier nivel
   - Fracturas con desplazamiento hacia canal
   - Listesis >3.5mm
   
VENTANAS: Ósea (W2000/L400) y tejidos blandos (W350/L40).
Reconstrucciones sagitales OBLIGATORIAS.''',
                'es_activo': True,
            }
        )
        protocolo_columna_cervical.tags.set([tag_trauma, tag_urgencia])
        
        if created:
            protocolos_creados += 1
        else:
            protocolos_actualizados += 1

        # Fase para TC columna cervical
        fase_columna, fase_created = FaseAdquisicion.objects.update_or_create(
            protocolo=protocolo_columna_cervical,
            orden=1,
            defaults={
                'nombre': 'Adquisición sin contraste cervical',
                'tipo_fase': 'SIN',
                'region': columna,
                'cobertura_desde': 'Base de cráneo (clivus)',
                'cobertura_hasta': 'T1 completo',
                'ventanas_recomendadas': 'Ósea (W2000/L400), Tejidos blandos (W350/L40)',
                'detalles_tecnicos': '120 kVp, cortes submilimétricos 0.625-1mm, MPR sagital y coronal',
                'notas_para_residente': '''Sin contraste: optimiza visualización ósea y reduce tiempo.
Cortes FINOS (submilimétricos) para no perder fracturas pequeñas.

REVISIÓN SISTEMÁTICA:
1. Contar vértebras: C1 a T1 (7 cervicales)
2. Evaluar CADA vértebra: cuerpo, pedículos, láminas, apófisis espinosa
3. Líneas de alineación en sagital: anterior, posterior, espinolaminar (deben ser rectas)
4. Espacios intervertebrales: deben ser simétricos
5. Tejidos blandos prevertebrales: <7mm en C2, <20mm en C6

Reconstrucciones sagitales son MÁS IMPORTANTES que los axiales para alineación.
Usar ventana ÓSEA para fracturas, tejidos blandos para hematomas/médula.
Ante duda de fractura: buscar líneas corticales interrumpidas.'''
            }
        )
        if fase_created:
            fases_creadas += 1
        else:
            fases_actualizadas += 1
        
        # Eliminar fases obsoletas (solo debe tener orden 1)
        expected_orders = [1]
        deleted_count = FaseAdquisicion.objects.filter(protocolo=protocolo_columna_cervical).exclude(orden__in=expected_orders).delete()[0]
        fases_eliminadas += deleted_count

        # ===== PROTOCOLO 5: TC TÓRAX CON CONTRASTE (NO TEP) =====
        protocolo_torax_contraste, created = Protocolo.objects.update_or_create(
            nombre='TC tórax con contraste EV (no TEP)',
            modalidad=tc,
            region=torax,
            defaults={
                'descripcion': 'Protocolo para evaluación de mediastino, masas torácicas, adenopatías, derrame pleural, lesiones pulmonares. Diferente del angio-TC de TEP por timing más tardío (fase venosa).',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': True,
                'calibre_via_minimo': '20G',
                'sitio_via_preferido': 'Fosa antecubital',
                'preparacion_paciente': '''Vía periférica calibre 20G o mayor
Ayuno de 6 horas (electivo)
Flujo de inyección: 2-3 ml/seg (NO necesita flujo alto como TEP)
Fase venosa/portal permite mejor opacificación de estructuras mediastinales
Apnea en inspiración durante adquisición''',
                'cobertura_global': 'Desde entrada torácica (incluir tiroides) hasta bases pulmonares completas (incluir suprarrenales)',
                'notas_docentes': '''Indicaciones principales:

1. ONCOLOGÍA:
   - Estadificación de cáncer pulmonar (T, N, M)
   - Adenopatías mediastinales (>1cm anormal)
   - Metástasis pulmonares
   - Invasión mediastinal o parietal
   
2. INFECCIONES:
   - Neumonía complicada (abscesos, empiema)
   - Tuberculosis (adenopatías necróticas)
   - Mediastinitis
   
3. MASAS MEDIASTINALES:
   - Timoma, linfoma, teratoma
   - Bocio intratorácico
   - Quistes (pericárdico, broncogénico)
   
4. DERRAME PLEURAL:
   - Caracterización (trasudado vs exudado)
   - Empiema (realce pleural)
   - Derrame tabicado
   
DIFERENCIA CON ANGIO-TC DE TEP:
- TEP: fase arterial precoz (bolus tracking, árbol vascular pulmonar)
- Este protocolo: fase portal/venosa (70s), evalúa mediastino y parénquima

VENTANAS: Mediastino (W350/L50) y Parénquima (W1500/L-600).''',
                'es_activo': True,
            }
        )
        protocolo_torax_contraste.tags.set([tag_oncologico, tag_infeccion, tag_mediastino])
        
        if created:
            protocolos_creados += 1
        else:
            protocolos_actualizados += 1

        # Fase para TC tórax con contraste
        fase_torax, fase_created = FaseAdquisicion.objects.update_or_create(
            protocolo=protocolo_torax_contraste,
            orden=1,
            defaults={
                'nombre': 'Fase portal/venosa tórax',
                'tipo_fase': 'PORT',
                'region': torax,
                'delay_segundos': 70,
                'cobertura_desde': 'Entrada torácica (incluir tiroides)',
                'cobertura_hasta': 'Bases pulmonares (incluir suprarrenales)',
                'ventanas_recomendadas': 'Mediastino (W350/L50), Parénquima (W1500/L-600)',
                'detalles_tecnicos': '120 kVp, 200 mAs, cortes 3mm con reconstrucciones 1mm',
                'notas_para_residente': '''Delay de 70 segundos: fase PORTAL/VENOSA (NO arterial como TEP).
Permite mejor opacificación de estructuras mediastinales y adenopatías.
Flujo moderado: 2-3 ml/seg suficiente, volumen 80-100ml.

EVALUACIÓN SISTEMÁTICA:
1. VÍA AÉREA: tráquea, carina, bronquios principales
2. MEDIASTINO: 
   - Vascular: aorta, pulmonar, VCS, VCI
   - Ganglios: paratraqueales, subcarinales, hiliares (>1cm = patológico)
   - Esófago, timo
3. PARÉNQUIMA PULMONAR:
   - Nódulos: <3cm, solitarios o múltiples
   - Masas: >3cm, caracterizar bordes
   - Consolidaciones, atelectasias
4. PLEURA: derrames, engrosamientos, masas
5. PARED: costillas, partes blandas, invasión tumoral

Revisar SIEMPRE ventana parénquima para no perder lesiones pulmonares.
Reconstrucciones coronales útiles para relaciones anatómicas.'''
            }
        )
        if fase_created:
            fases_creadas += 1
        else:
            fases_actualizadas += 1
        
        # Eliminar fases obsoletas (solo debe tener orden 1)
        expected_orders = [1]
        deleted_count = FaseAdquisicion.objects.filter(protocolo=protocolo_torax_contraste).exclude(orden__in=expected_orders).delete()[0]
        fases_eliminadas += deleted_count

        # Resumen final
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('✅ CARGA DE PROTOCOLOS CRÍTICOS COMPLETADA'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS(f'\n📊 RESUMEN:'))
        self.stdout.write(self.style.SUCCESS(f'  • Protocolos NUEVOS creados: {protocolos_creados}'))
        self.stdout.write(self.style.SUCCESS(f'  • Protocolos actualizados: {protocolos_actualizados}'))
        self.stdout.write(self.style.SUCCESS(f'  • Fases NUEVAS creadas: {fases_creadas}'))
        self.stdout.write(self.style.SUCCESS(f'  • Fases actualizadas: {fases_actualizadas}'))
        if fases_eliminadas > 0:
            self.stdout.write(self.style.WARNING(f'  • Fases obsoletas eliminadas: {fases_eliminadas}'))
        self.stdout.write(self.style.SUCCESS(f'\n✅ Total de protocolos en sistema: {Protocolo.objects.count()}'))
        self.stdout.write(self.style.SUCCESS('='*80))
        
        self.stdout.write(self.style.WARNING('\n📋 PROTOCOLOS AGREGADOS:'))
        self.stdout.write('  1. Angio-TC Aorta (síndrome aórtico agudo)')
        self.stdout.write('  2. Uro-TC litiasis (KUB sin contraste)')
        self.stdout.write('  3. Angio-TC cerebral (stroke code)')
        self.stdout.write('  4. TC columna cervical trauma (sin contraste)')
        self.stdout.write('  5. TC tórax con contraste EV (no TEP)')
        
        self.stdout.write(self.style.WARNING('\n🎯 Próximos pasos sugeridos:'))
        self.stdout.write('  • Acceder a http://localhost:8000/protocolos/')
        self.stdout.write('  • Revisar y ajustar protocolos en admin si es necesario')
        self.stdout.write('  • Considerar agregar protocolos de RM (columna, abdomen)')
        self.stdout.write('')
