from django.core.management.base import BaseCommand
from protocolos.models import Modalidad, RegionAnatomica, Tag, Protocolo, FaseAdquisicion


class Command(BaseCommand):
    help = 'Carga datos iniciales básicos para protocolos radiológicos'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Cargando datos iniciales...'))

        # 1. Modalidades
        modalidades_data = [
            ('TC', 'Tomografía Computada'),
            ('RM', 'Resonancia Magnética'),
            ('RX', 'Radiografía'),
            ('US', 'Ecografía'),
        ]
        
        for codigo, nombre in modalidades_data:
            Modalidad.objects.get_or_create(
                codigo=codigo,
                defaults={'nombre': nombre}
            )
        self.stdout.write(self.style.SUCCESS(f'✓ {len(modalidades_data)} modalidades creadas'))

        # 2. Regiones anatómicas
        regiones_data = [
            ('TORAX', 'Tórax'),
            ('ABD', 'Abdomen'),
            ('PELVIS', 'Pelvis'),
            ('TAP', 'Tórax-Abdomen-Pelvis'),
            ('CRANEO', 'Cráneo'),
            ('CUELLO', 'Cuello'),
            ('COLUMNA', 'Columna'),
            ('MMSS', 'Miembros superiores'),
            ('MMII', 'Miembros inferiores'),
        ]
        
        for codigo, nombre in regiones_data:
            RegionAnatomica.objects.get_or_create(
                codigo=codigo,
                defaults={'nombre': nombre}
            )
        self.stdout.write(self.style.SUCCESS(f'✓ {len(regiones_data)} regiones creadas'))

        # 3. Tags comunes
        tags_data = [
            'TEP',
            'Dolor abdominal',
            'Trauma',
            'Politraumatismo',
            'Oncológico',
            'ACV',
            'Hematuria',
            'Hemorragia digestiva',
            'Dolor torácico',
            'Disnea',
            'Cefalea',
            'Urgencia',
        ]
        
        for tag_nombre in tags_data:
            Tag.objects.get_or_create(nombre=tag_nombre)
        self.stdout.write(self.style.SUCCESS(f'✓ {len(tags_data)} tags creados'))

        # 4. Obtener objetos para usar en protocolos
        tc = Modalidad.objects.get(codigo='TC')
        rm = Modalidad.objects.get(codigo='RM')
        rx = Modalidad.objects.get(codigo='RX')
        us = Modalidad.objects.get(codigo='US')
        
        tap = RegionAnatomica.objects.get(codigo='TAP')
        torax = RegionAnatomica.objects.get(codigo='TORAX')
        craneo = RegionAnatomica.objects.get(codigo='CRANEO')
        abdomen = RegionAnatomica.objects.get(codigo='ABD')
        columna = RegionAnatomica.objects.get(codigo='COLUMNA')
        
        onco_tag = Tag.objects.get(nombre='Oncológico')
        tep_tag = Tag.objects.get(nombre='TEP')
        trauma_tag = Tag.objects.get(nombre='Trauma')
        acv_tag = Tag.objects.get(nombre='ACV')
        dolor_abd_tag = Tag.objects.get(nombre='Dolor abdominal')
        urgencia_tag = Tag.objects.get(nombre='Urgencia')

        protocolos_creados = 0

        # ===== PROTOCOLO 1: TC TAP ONCOLÓGICO =====
        protocolo_tap, created = Protocolo.objects.get_or_create(
            modalidad=tc,
            region=tap,
            nombre='TC TAP con contraste EV para estadificación oncológica',
            defaults={
                'descripcion': 'Protocolo estándar para estadificación y seguimiento de pacientes oncológicos. Incluye tórax, abdomen y pelvis en una sola adquisición.',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': True,
                'calibre_via_minimo': '20G',
                'sitio_via_preferido': 'Fosa antecubital',
                'preparacion_paciente': '''Ayuno de sólidos: 6 horas
Líquidos claros: hasta 2 horas antes
Vía periférica calibre 20G o 18G
Verificar función renal (creatinina <1.5)
Hidratación previa de 500ml SF si función renal limítrofe''',
                'cobertura_global': 'Desde apex pulmonar hasta sínfisis púbica',
                'notas_docentes': '''Evaluar:
- Tumor primario (localización, tamaño, invasión)
- Adenopatías (mediastino, retroperitoneo, pelvis)
- Metástasis hepáticas, pulmonares y óseas
- Ascitis y derrame pleural
- Comparar con estudios previos si disponibles''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolo_tap.tags.add(onco_tag)
            protocolos_creados += 1

            FaseAdquisicion.objects.create(
                protocolo=protocolo_tap,
                orden=1,
                nombre='Fase portal TAP',
                tipo_fase='PORT',
                region=tap,
                delay_segundos=70,
                cobertura_desde='Apex pulmonar',
                cobertura_hasta='Sínfisis púbica',
                ventanas_recomendadas='Parénquima (W400/L40), Mediastino (W350/L50)',
                detalles_tecnicos='120 kVp, 200 mAs, cortes 3mm',
                notas_para_residente='Fase estándar para evaluación oncológica. Permite buena visualización de lesiones hepáticas y adenopatías.'
            )

        # ===== PROTOCOLO 2: TC TÓRAX TEP =====
        protocolo_tep, created = Protocolo.objects.get_or_create(
            modalidad=tc,
            region=torax,
            nombre='Angio-TC para descarte de TEP',
            defaults={
                'descripcion': 'Protocolo específico para descarte de tromboembolismo pulmonar. Fase arterial con sincronización óptima.',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'calibre_via_minimo': '18G',
                'sitio_via_preferido': 'Fosa antecubital derecha',
                'preparacion_paciente': '''Vía periférica calibre 18G (obligatorio para flujo alto)
Preferible en brazo derecho
Test de extravasación previo
Verificar función renal''',
                'cobertura_global': 'Desde apex pulmonar hasta diafragma (incluir bases pulmonares completas)',
                'notas_docentes': '''Puntos clave:
- Sincronización crítica: usar bolus tracking en arteria pulmonar
- Flujo alto (4-5 ml/seg) para máxima opacificación
- Evaluar ramas subsegmentarias
- Buscar signos indirectos: dilatación VD, cor pulmonale
- Evaluar TVP en MMII si se sospecha''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolo_tep.tags.add(tep_tag, urgencia_tag)
            protocolos_creados += 1

            FaseAdquisicion.objects.create(
                protocolo=protocolo_tep,
                orden=1,
                nombre='Fase arterial pulmonar',
                tipo_fase='ART',
                region=torax,
                delay_segundos=None,  # Se usa bolus tracking
                cobertura_desde='Apex pulmonar',
                cobertura_hasta='Bases pulmonares',
                ventanas_recomendadas='Mediastino (W350/L50), Parénquima (W1500/L-600)',
                detalles_tecnicos='100-120 kVp, cortes 1mm con reconstrucciones MIP',
                notas_para_residente='Usar bolus tracking con ROI en tronco de arteria pulmonar. Umbral de 100 UH. Flujo 4-5 ml/seg, volumen 80-100ml.'
            )

        # ===== PROTOCOLO 3: TC CRÁNEO SIN CONTRASTE =====
        protocolo_craneo, created = Protocolo.objects.get_or_create(
            modalidad=tc,
            region=craneo,
            nombre='TC de cráneo sin contraste para trauma/ACV',
            defaults={
                'descripcion': 'Protocolo de urgencia para evaluación de trauma craneoencefálico o ACV agudo. Sin contraste para detectar sangrado.',
                'requiere_contraste_ev': False,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'preparacion_paciente': '''No requiere preparación especial
No necesita ayuno
No necesita vía periférica
Retirar objetos metálicos de la cabeza''',
                'cobertura_global': 'Desde base de cráneo hasta vertex',
                'notas_docentes': '''Evaluar sistemáticamente:
- Sangre: epidural, subdural, subaracnoideo, intraparenquimatoso
- Fracturas de calota y base de cráneo
- Línea media y ventrículos (desplazamiento, hidrocefalia)
- Cisuras y surcos (borramiento por edema)
- Ventana ósea obligatoria''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolo_craneo.tags.add(trauma_tag, acv_tag, urgencia_tag)
            protocolos_creados += 1

            FaseAdquisicion.objects.create(
                protocolo=protocolo_craneo,
                orden=1,
                nombre='Adquisición sin contraste',
                tipo_fase='SIN',
                region=craneo,
                cobertura_desde='Base de cráneo',
                cobertura_hasta='Vertex',
                ventanas_recomendadas='Cerebro (W80/L40), Ósea (W2000/L400)',
                detalles_tecnicos='120 kVp, cortes 5mm con MPR',
                notas_para_residente='Sangre aguda es hiperdensa (blanca). Evaluar en ventana cerebro primero, luego ventana ósea para fracturas.'
            )

        # ===== PROTOCOLO 4: RM CEREBRO CON CONTRASTE =====
        protocolo_rm_cerebro, created = Protocolo.objects.get_or_create(
            modalidad=rm,
            region=craneo,
            nombre='RM de cerebro con contraste para estudio oncológico',
            defaults={
                'descripcion': 'Protocolo completo de RM cerebral con contraste para evaluación de lesiones tumorales primarias o metástasis.',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'calibre_via_minimo': '22G',
                'sitio_via_preferido': 'Cualquier vena periférica',
                'preparacion_paciente': '''Vía periférica calibre 22G o mayor
Verificar función renal (para gadolinio)
Retirar todos los objetos metálicos
Cuestionario de seguridad de RM completo
Informar claustrofobia si existe''',
                'cobertura_global': 'Cerebro completo en planos axial, coronal y sagital',
                'notas_docentes': '''Secuencias estándar:
- T1 sin contraste (anatomía)
- T2 FLAIR (edema, desmielinización)
- Difusión (isquemia aguda, abscesos)
- T1 con contraste en 3 planos (tumores, metástasis)
- Buscar refuerzo patológico y edema perilesional''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolo_rm_cerebro.tags.add(onco_tag)
            protocolos_creados += 1

            FaseAdquisicion.objects.create(
                protocolo=protocolo_rm_cerebro,
                orden=1,
                nombre='Secuencias sin contraste',
                tipo_fase='SIN',
                region=craneo,
                ventanas_recomendadas='T1, T2, FLAIR, Difusión',
                detalles_tecnicos='3T preferible, FOV 220mm, matriz 256x256',
                notas_para_residente='Completar todas las secuencias sin contraste antes de inyectar. Revisar calidad antes de contraste.'
            )

            FaseAdquisicion.objects.create(
                protocolo=protocolo_rm_cerebro,
                orden=2,
                nombre='T1 con contraste',
                tipo_fase='OTRA',
                region=craneo,
                ventanas_recomendadas='T1 post-contraste en 3 planos',
                detalles_tecnicos='Gadolinio 0.1 mmol/kg, adquisición 3D',
                notas_para_residente='Inyección rápida de gadolinio. Iniciar adquisición inmediatamente. Comparar con T1 sin contraste para identificar refuerzo.'
            )

        # ===== PROTOCOLO 5: TC ABDOMEN DOLOR AGUDO =====
        protocolo_abd_agudo, created = Protocolo.objects.get_or_create(
            modalidad=tc,
            region=abdomen,
            nombre='TC de abdomen y pelvis con contraste para dolor agudo',
            defaults={
                'descripcion': 'Protocolo de urgencia para evaluación de dolor abdominal agudo. Incluye fase portal para diagnóstico general.',
                'requiere_contraste_ev': True,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'calibre_via_minimo': '20G',
                'sitio_via_preferido': 'Fosa antecubital',
                'preparacion_paciente': '''Vía periférica 20G
En urgencias no se requiere ayuno estricto
Verificar función renal si es posible
Contraste oral solo si se sospecha perforación (gastrografín)''',
                'cobertura_global': 'Desde diafragma hasta sínfisis púbica',
                'notas_docentes': '''Diagnósticos frecuentes:
- Apendicitis aguda
- Diverticulitis
- Pancreatitis
- Obstrucción intestinal
- Isquemia mesentérica
- Perforación visceral
- Colecciones/abscesos''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolo_abd_agudo.tags.add(dolor_abd_tag, urgencia_tag)
            protocolos_creados += 1

            FaseAdquisicion.objects.create(
                protocolo=protocolo_abd_agudo,
                orden=1,
                nombre='Fase portal abdomen-pelvis',
                tipo_fase='PORT',
                region=abdomen,
                delay_segundos=70,
                cobertura_desde='Diafragma',
                cobertura_hasta='Sínfisis púbica',
                ventanas_recomendadas='Parénquima (W400/L40), Intestinal (W350/L50)',
                detalles_tecnicos='120 kVp, cortes 3mm',
                notas_para_residente='Evaluar sistemáticamente: intestino, apéndice, páncreas, vía biliar, riñones y pelvis. Buscar líquido libre y neumoperitoneo.'
            )

        # ===== PROTOCOLO 6: ECOGRAFÍA ABDOMINAL =====
        protocolo_eco_abd, created = Protocolo.objects.get_or_create(
            modalidad=us,
            region=abdomen,
            nombre='Ecografía abdominal completa',
            defaults={
                'descripcion': 'Ecografía transabdominal para evaluación de órganos sólidos y vía biliar. Primera línea en patología hepatobiliar.',
                'requiere_contraste_ev': False,
                'requiere_contraste_oral': False,
                'requiere_ayuno': True,
                'preparacion_paciente': '''Ayuno de 6-8 horas (obligatorio)
Evitar goma de mascar y caramelos
Suspender medicación que produzca gas intestinal
Vejiga llena si se va a evaluar pelvis''',
                'cobertura_global': 'Hígado, vesícula, vía biliar, páncreas, bazo, riñones',
                'notas_docentes': '''Técnica sistemática:
1. Hígado en múltiples cortes (buscar lesiones focales)
2. Vesícula y vía biliar (colelitiasis, dilatación)
3. Páncreas (difícil por gas, usar compresión)
4. Bazo (tamaño, lesiones)
5. Riñones en longitudinal y transversal
6. Evaluar líquido libre en espacios de Morrison y Douglas''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolo_eco_abd.tags.add(dolor_abd_tag)
            protocolos_creados += 1

        # ===== PROTOCOLO 7: RX COLUMNA LUMBAR =====
        protocolo_rx_columna, created = Protocolo.objects.get_or_create(
            modalidad=rx,
            region=columna,
            nombre='Radiografía de columna lumbosacra',
            defaults={
                'descripcion': 'Estudio radiográfico simple de columna lumbar en dos proyecciones. Primera línea para dolor lumbar y evaluación de alineación.',
                'requiere_contraste_ev': False,
                'requiere_contraste_oral': False,
                'requiere_ayuno': False,
                'preparacion_paciente': '''No requiere preparación especial
Retirar objetos metálicos de la zona
Idealmente evacuación intestinal previa''',
                'cobertura_global': 'Desde T12 hasta sacro',
                'notas_docentes': '''Evaluar sistemáticamente:
- Alineación vertebral (lordosis, escoliosis)
- Altura de discos intervertebrales
- Fracturas vertebrales
- Osteofitos y cambios degenerativos
- Espacios articulares posteriores
- Tejidos blandos paravertebrales
Proyecciones: AP y lateral''',
                'es_activo': True,
            }
        )
        
        if created:
            protocolos_creados += 1

        self.stdout.write(self.style.SUCCESS(f'\n✓ {protocolos_creados} protocolos creados'))
        self.stdout.write(self.style.SUCCESS('\n✅ Datos iniciales cargados correctamente'))
        self.stdout.write(self.style.WARNING('\nPróximos pasos:'))
        self.stdout.write('1. Acceder al admin: http://localhost:8000/admin/')
        self.stdout.write('2. Ver protocolos: http://localhost:8000/protocolos/')
        self.stdout.write('3. Crear más protocolos según necesidad')
