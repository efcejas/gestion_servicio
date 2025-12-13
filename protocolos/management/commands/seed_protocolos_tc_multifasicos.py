from django.core.management.base import BaseCommand
from protocolos.models import Modalidad, RegionAnatomica, Tag, Protocolo, FaseAdquisicion


class Command(BaseCommand):
    help = 'Carga protocolos multifásicos de TC para caracterización y estudios vasculares'

    def __init__(self):
        super().__init__()
        self.protocolos_creados = 0
        self.protocolos_actualizados = 0
        self.fases_creadas = 0
        self.fases_actualizadas = 0
        self.fases_eliminadas = 0

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Cargando protocolos multifásicos de TC...'))
        
        # Asegurar modalidad TC
        tc, _ = Modalidad.objects.get_or_create(
            codigo='TC',
            defaults={'nombre': 'Tomografía Computada'}
        )

        # Asegurar regiones
        abd = self.ensure_region('ABD', 'Abdomen')
        tap = self.ensure_region('TAP', 'Tórax-Abdomen-Pelvis')
        higado = self.ensure_region('HIGADO', 'Hígado')
        pancreas = self.ensure_region('PANCREAS', 'Páncreas')
        rinon = self.ensure_region('RINON', 'Riñón')
        uro = self.ensure_region('URO', 'Sistema urinario')

        # Asegurar tags
        tag_onco = self.ensure_tag('Oncológico')
        tag_caract = self.ensure_tag('Caracterización')
        tag_higado = self.ensure_tag('Hígado')
        tag_lesion = self.ensure_tag('Lesión focal')
        tag_pancreas = self.ensure_tag('Páncreas')
        tag_rinon = self.ensure_tag('Riñón')
        tag_hematuria = self.ensure_tag('Hematuria')
        tag_sangrado = self.ensure_tag('Sangrado')
        tag_urgencia = self.ensure_tag('Urgencia')
        tag_vascular = self.ensure_tag('Vascular')

        # ===== PROTOCOLO A: TC HÍGADO TRIFÁSICO =====
        protocolo_higado = self.upsert_protocolo(
            tc=tc,
            nombre='TC Hígado trifásico (caracterización de lesión focal)',
            region=higado,
            descripcion='Protocolo multifásico para caracterización de lesiones hepáticas focales. Permite evaluar patrón de captación y washout para diagnóstico diferencial (HCC, metástasis, hemangioma, FNH, adenoma).',
            tags=[tag_onco, tag_caract, tag_higado, tag_lesion],
            requiere_contraste_ev=True,
            requiere_contraste_oral=False,
            requiere_ayuno=True,
            calibre_via='20G',
            sitio_via='Fosa antecubital',
            preparacion='''Ayuno de 6 horas
Vía periférica calibre 20G o mayor
Flujo de inyección: 3-4 ml/seg
Volumen de contraste: 1.5 ml/kg (100-150ml)
Apnea en inspiración para cada fase''',
            cobertura='Desde diafragma hasta crestas ilíacas (incluir hígado completo)',
            notas_docentes='''CUÁNDO ELEGIR ESTE PROTOCOLO:
- Lesión focal hepática detectada en US/TC previo que requiere caracterización
- Paciente cirrótico con sospecha de hepatocarcinoma (HCC)
- Lesión hepática indeterminada (diferenciar hemangioma, FNH, adenoma, metástasis)
- Metástasis hipervasculares o lesión a caracterizar en paciente oncológico

CUÁNDO NO ELEGIR ESTE PROTOCOLO:
- TC de seguimiento oncológico rutinario → protocolo portal simple (menos radiación)
- Sospecha de colangiocarcinoma → usar colangioRM o TC con fase tardía de equilibrio

QUÉ EVALUAR:
1. FASE SIN CONTRASTE:
   - Densidad basal de la lesión (grasa, calcio, hemorragia)
   - Tamaño y localización (segmento hepático según Couinaud)
   
2. FASE ARTERIAL TARDÍA (25-35s):
   - Hipervascularización: HCC, FNH, adenoma, hemangioma periférico
   - Realce arterial precoz sugiere malignidad o lesión hipervascular
   
3. FASE PORTAL (65-75s):
   - Mayoría de lesiones se visualizan mejor aquí
   - Washout rápido sugiere HCC
   - Iso/hiperrealce sostenido: FNH, hemangioma
   - Hipodenso: metástasis, absceso

PATRONES CLÁSICOS:
- HCC: realce arterial + washout portal/tardío
- Hemangioma: realce periférico nodular progresivo
- FNH: realce homogéneo arterial + cicatriz central
- Metástasis: hipodensas en portal, realce en anillo''',
            es_activo=True
        )

        self.upsert_fase(protocolo_higado, orden=1, nombre='Sin contraste',
                        tipo='SIN', region=higado, delay=None,
                        cobertura_desde='Diafragma', cobertura_hasta='Crestas ilíacas',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 3-5mm',
                        notas_residente='Medir densidad basal de la lesión en UH. Buscar grasa (-20 a -80 UH) o calcio (>100 UH). Sirve para calcular el realce real en fases contrastadas.')

        self.upsert_fase(protocolo_higado, orden=2, nombre='Arterial tardía hepática',
                        tipo='ART', region=higado, delay=None,
                        cobertura_desde='Diafragma', cobertura_hasta='Crestas ilíacas',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 2-3mm. Usar bolus tracking: ROI en aorta abdominal supracelíaca, umbral 100 UH, delay 15-20s post-umbral',
                        notas_residente='Fase crítica para detectar lesiones hipervasculares. El HCC, FNH y adenoma muestran realce arterial intenso. Hemangiomas tienen realce periférico en "charco" (discontinuo).')

        self.upsert_fase(protocolo_higado, orden=3, nombre='Portal venosa hepática',
                        tipo='PORT', region=higado, delay=70,
                        cobertura_desde='Diafragma', cobertura_hasta='Crestas ilíacas',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 2-3mm',
                        notas_residente='Fase más sensible para detectar la mayoría de lesiones. Comparar con fase arterial: si hay WASHOUT (menos denso que fase arterial) → HCC probable. Si sigue isointenso → benigno más probable.')

        expected = [1, 2, 3]
        deleted = FaseAdquisicion.objects.filter(protocolo=protocolo_higado).exclude(orden__in=expected).delete()[0]
        self.fases_eliminadas += deleted

        # ===== PROTOCOLO B: TC PÁNCREAS BIFÁSICO =====
        protocolo_pancreas = self.upsert_protocolo(
            tc=tc,
            nombre='TC Páncreas bifásico (fase pancreática + portal)',
            region=pancreas,
            descripcion='Protocolo optimizado para evaluación del parénquima pancreático y lesiones focales. Fase pancreática (arterial tardía) maximiza contraste entre tumor y parénquima normal.',
            tags=[tag_pancreas, tag_onco, tag_caract],
            requiere_contraste_ev=True,
            requiere_contraste_oral=False,
            requiere_ayuno=True,
            calibre_via='20G',
            sitio_via='Fosa antecubital',
            preparacion='''Ayuno de 6 horas
Vía periférica calibre 20G o mayor
Flujo: 3-4 ml/seg, volumen 100-150ml
Hidratación oral previa con 500ml de agua (distender estómago y duodeno)
Apnea en inspiración''',
            cobertura='Desde diafragma hasta crestas ilíacas (incluir hígado para evaluar metástasis)',
            notas_docentes='''CUÁNDO ELEGIR ESTE PROTOCOLO:
- Sospecha de adenocarcinoma de páncreas (masa, ictericia obstructiva, CA 19-9 elevado)
- Pancreatitis aguda complicada (necrosis, colecciones)
- Tumor neuroendocrino pancreático
- Estadificación de cáncer pancreático (resecabilidad)

CUÁNDO NO ELEGIR ESTE PROTOCOLO:
- Pancreatitis aguda leve no complicada → TC simple sin contraste suficiente
- Tumor quístico pancreático (IPMN, cistoadenoma) → considerar RM pancreática

QUÉ EVALUAR:
1. FASE PANCREÁTICA (35-45s):
   - Adenocarcinoma: hipodenso respecto al parénquima normal (40-60 UH menos)
   - Parénquima normal realza intensamente (130-150 UH)
   - Tumor neuroendocrino: hiperrealce (lesión hipervascular)
   - Evaluar contacto con vasos: AMS, tronco celíaco, porta, VMS
   
2. FASE PORTAL (65-75s):
   - Metástasis hepáticas (hipodensas)
   - Vena porta: trombosis tumoral
   - Adenopatías peripancreáticas
   - Ascitis

CRITERIOS DE RESECABILIDAD:
- Sin contacto con AMS ni tronco celíaco (lesión resecable)
- Contacto <180° con arteria hepática común (borderline)
- Contacto >180° con AMS o tronco celíaco (irresecable)
- Oclusión de vena porta (irresecable)''',
            es_activo=True
        )

        self.upsert_fase(protocolo_pancreas, orden=1, nombre='Fase pancreática (arterial tardía)',
                        tipo='ART', region=pancreas, delay=40,
                        cobertura_desde='Diafragma', cobertura_hasta='Crestas ilíacas',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 2-3mm con MPR coronal y sagital',
                        notas_residente='Máximo contraste entre tumor (hipodenso) y parénquima normal (hiperdenso). Delay fijo 40s suele ser adecuado. Evaluar contacto vascular con AMS, tronco celíaco, arteria hepática. MPR coronales son clave para estadificación.')

        self.upsert_fase(protocolo_pancreas, orden=2, nombre='Fase portal venosa',
                        tipo='PORT', region=pancreas, delay=70,
                        cobertura_desde='Diafragma', cobertura_hasta='Crestas ilíacas',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 3mm',
                        notas_residente='Evaluar hígado completo para metástasis. Vena porta y VMS para trombosis. Adenopatías en ligamento hepatoduodenal, tronco celíaco, retroperitoneo. Ascitis peritoneal.')

        expected = [1, 2]
        deleted = FaseAdquisicion.objects.filter(protocolo=protocolo_pancreas).exclude(orden__in=expected).delete()[0]
        self.fases_eliminadas += deleted

        # ===== PROTOCOLO C: TC RIÑÓN MULTIFÁSICO =====
        protocolo_rinon = self.upsert_protocolo(
            tc=tc,
            nombre='TC Riñón multifásico (renal mass protocol)',
            region=rinon,
            descripcion='Protocolo de 4 fases para caracterización de masas renales indeterminadas. Evalúa realce, vascularización y sistema colector.',
            tags=[tag_rinon, tag_caract, tag_onco],
            requiere_contraste_ev=True,
            requiere_contraste_oral=False,
            requiere_ayuno=True,
            calibre_via='20G',
            sitio_via='Fosa antecubital',
            preparacion='''Ayuno de 6 horas
Vía periférica calibre 20G o mayor
Flujo: 3-4 ml/seg, volumen 100-150ml
Hidratación oral: 500ml de agua 30min antes (distender sistema colector)
Paciente en decúbito supino''',
            cobertura='Desde diafragma hasta sínfisis púbica (incluir riñones completos y vejiga)',
            notas_docentes='''CUÁNDO ELEGIR ESTE PROTOCOLO:
- Masa renal indeterminada en US o TC simple
- Diferenciación entre quiste complicado y tumor sólido
- Caracterización de masa renal <4cm (¿quiste Bosniak III-IV vs carcinoma?)
- Estadificación de carcinoma de células renales (CCR)

CUÁNDO NO ELEGIR ESTE PROTOCOLO:
- Quiste simple clásico en US (Bosniak I) → no requiere TC
- Cólico renal típico → usar Uro-TC sin contraste (litiasis)

QUÉ EVALUAR:
1. FASE SIN CONTRASTE:
   - Densidad basal: grasa (-20 a -80 UH) = angiomiolipoma
   - Calcificación (>100 UH)
   - Hemorragia aguda (50-70 UH)
   - Quiste simple: <20 UH, sin realce
   
2. FASE CORTICOMEDULAR (25-40s):
   - Lesiones hipervasculares: CCR células claras, oncocitoma
   - Anatomía vascular: arterias renales, variantes
   - Útil para planning quirúrgico
   
3. FASE NEFROGRÁFICA (80-120s):
   - FASE CLAVE: mejor realce de la mayoría de tumores renales
   - Medir realce: >15-20 UH respecto a fase sin contraste = sólido
   - Realce <15 UH = quiste complicado (Bosniak II-IIF)
   - Evaluar extensión: grasa perirrenal, fascia de Gerota, vena renal/cava
   
4. FASE EXCRETORA (5-10 min):
   - Opacificación de cálices, pelvis, uréter, vejiga
   - Defectos de llenado: tumor urotelial (carcinoma transicional)
   - Invasión del sistema colector por tumor renal

CLASIFICACIÓN BOSNIAK (quistes complejos):
- I: quiste simple, benigno (sin seguimiento)
- II: septaciones finas, calcificación, benigno (sin seguimiento)
- IIF: múltiples septaciones, follow-up (10% maligno)
- III: septaciones gruesas, realce parietal, cirugía (50% maligno)
- IV: componente sólido con realce, cirugía (>90% maligno)''',
            es_activo=True
        )

        self.upsert_fase(protocolo_rinon, orden=1, nombre='Sin contraste',
                        tipo='SIN', region=rinon, delay=None,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40), Ósea (W2000/L400) si sospecha litiasis',
                        tecnicos='120 kVp, cortes 3mm',
                        notas_residente='Medir densidad de la lesión en UH (colocar ROI grande evitando bordes). Si <20 UH → quiste simple. Si -20 a -80 UH → grasa (angiomiolipoma). Si >20 UH → necesita contraste para caracterizar.')

        self.upsert_fase(protocolo_rinon, orden=2, nombre='Fase corticomedular',
                        tipo='ART', region=rinon, delay=30,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='100-120 kVp, cortes 2-3mm',
                        notas_residente='Fase temprana: corteza renal hiperdensa, médula hipodensa (diferenciación corticomedular). Lesiones hipervasculares se ven aquí (CCR células claras). Evaluar arterias renales principales y accesorias.')

        self.upsert_fase(protocolo_rinon, orden=3, nombre='Fase nefrográfica',
                        tipo='PORT', region=rinon, delay=100,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 2-3mm',
                        notas_residente='FASE MÁS IMPORTANTE. Realce homogéneo de todo el parénquima renal. Medir realce de la lesión: restar UH de fase sin contraste. Si realce >15-20 UH → componente sólido vascularizado (tumor). Evaluar extensión: grasa perirrenal, vena renal, adenopatías.')

        self.upsert_fase(protocolo_rinon, orden=4, nombre='Fase excretora',
                        tipo='TARD', region=rinon, delay=600,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 3-5mm. Delay: 5-10 minutos post-inyección (típicamente 10 min)',
                        notas_residente='Sistema colector opacificado con contraste. Buscar defectos de llenado en cálices/pelvis/uréter (tumor urotelial). Evaluar si tumor renal invade pelvis. Útil para planning quirúrgico (anatomía colectora).')

        expected = [1, 2, 3, 4]
        deleted = FaseAdquisicion.objects.filter(protocolo=protocolo_rinon).exclude(orden__in=expected).delete()[0]
        self.fases_eliminadas += deleted

        # ===== PROTOCOLO D: URO-TC HEMATURIA =====
        protocolo_urotc_hematuria = self.upsert_protocolo(
            tc=tc,
            nombre='Uro-TC hematuria (urograma CT)',
            region=uro,
            descripcion='Protocolo para evaluación de hematuria macroscópica. Combina fase nefrográfica (parénquima renal) + excretora (sistema colector, uréter, vejiga) para detectar tumores uroteliales.',
            tags=[tag_hematuria, tag_rinon, tag_onco],
            requiere_contraste_ev=True,
            requiere_contraste_oral=False,
            requiere_ayuno=True,
            calibre_via='20G',
            sitio_via='Fosa antecubital',
            preparacion='''Ayuno de 6 horas
Vía periférica calibre 20G o mayor
Flujo: 3-4 ml/seg, volumen 100-150ml
Hidratación oral: 500-1000ml de agua 1 hora antes
Furosemida 10-20mg IV 5 minutos antes de fase excretora (opcional, aumenta opacificación ureteral)
Vejiga llena al inicio del estudio''',
            cobertura='Desde diafragma hasta sínfisis púbica (incluir sistema urinario completo)',
            notas_docentes='''CUÁNDO ELEGIR ESTE PROTOCOLO:
- Hematuria macroscópica sin causa clara (>50 años, tabaquismo)
- Sospecha de tumor urotelial (carcinoma de células transicionales)
- Seguimiento de paciente con antecedente de tumor urotelial resecado
- Hidronefrosis unilateral sin litiasis identificable

CUÁNDO NO ELEGIR ESTE PROTOCOLO:
- Cólico renal típico → usar Uro-TC litiasis sin contraste (más rápido, menos radiación)
- Trauma renal agudo → usar protocolo multifásico renal con fase arterial

QUÉ EVALUAR:
1. FASE NEFROGRÁFICA (90-120s):
   - Parénquima renal: masas renales (CCR, metástasis)
   - Realce del urotelio normal (homogéneo, fino)
   - Adenopatías retroperitoneales (>1cm patológicas)
   - Infartos renales (áreas cuneiformes sin realce)
   
2. FASE EXCRETORA (10 min):
   - FASE CRÍTICA para detectar tumor urotelial
   - Defectos de llenado en cálices, pelvis, uréter, vejiga
   - Engrosamiento parietal vesical (>5mm = anormal)
   - Estenosis ureterales (tumor vs TBC vs iatrogenia)

DIFERENCIACIÓN CLAVE:
- Tumor urotelial: defecto de llenado hipodenso CON REALCE, irregular, no obstructivo
- Cálculo: hiperdenso (>100 UH), SIN realce, obstructivo, redondo
- Coágulo: densidad intermedia (40-70 UH), NO realza, móvil en decúbito

FACTORES DE RIESGO TUMOR UROTELIAL:
- Tabaquismo (factor más importante: 50% de casos)
- Exposición ocupacional: anilinas, hidrocarburos aromáticos (industria textil, goma)
- Ciclofosfamida crónica (quimioterapia)
- Litiasis urinaria crónica, infecciones recurrentes (carcinoma escamoso)

ESTADIFICACIÓN (si se detecta tumor):
- Ta/T1: superficial (mucosa/submucosa) → RTU
- T2: invade muscular → cistectomía
- T3: invade grasa perivesical → quimio + cirugía
- T4: invade órganos adyacentes → paliativo''',
            es_activo=True
        )

        self.upsert_fase(protocolo_urotc_hematuria, orden=1, nombre='Fase nefrográfica',
                        tipo='PORT', region=uro, delay=100,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 2-3mm',
                        notas_residente='Fase nefrográfica (90-120s): realce homogéneo del parénquima renal. Evaluar RIÑONES: masas, infartos, nefropatía obstructiva. Urotelio normal realza de forma fina y homogénea. Buscar adenopatías retroperitoneales (>1cm). Fase similar a protocolo de masa renal pero sin fase arterial.')

        self.upsert_fase(protocolo_urotc_hematuria, orden=2, nombre='Fase excretora',
                        tipo='TARD', region=uro, delay=600,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 3-5mm, MPR coronal siguiendo uréter. Delay: 8-15 min post-inyección (típicamente 10 min)',
                        notas_residente='''FASE CRÍTICA para detectar tumor urotelial. Sistema colector opacificado con contraste excretado.

EVALUACIÓN SISTEMÁTICA:
1. CÁLICES y PELVIS RENAL: buscar defectos de llenado, tumores papilares
2. URÉTERES: seguir TODO el trayecto (UPU → iliaco → pelviano → UVU). Buscar:
   - Defectos de llenado (tumor, coágulo, cálculo)
   - Estenosis (tumor infiltrante, TBC, radiación previa)
3. VEJIGA: evaluar pared completa, buscar:
   - Masas intraluminales (tumor vesical)
   - Engrosamiento focal (>5mm) o difuso (cistitis, hipertrofia)
   
DIFERENCIACIÓN:
- Tumor urotelial: irregular, hipodenso pero CON REALCE en fase nefrográfica previa
- Cálculo: redondeado, hiperdenso (>100 UH), SIN realce
- Coágulo: densidad intermedia (40-70 UH), NO realza

Reconstrucciones coronales ESENCIALES para seguir uréteres. Comparar con fase nefrográfica para confirmar realce de lesiones sospechosas.''')

        expected = [1, 2]
        deleted = FaseAdquisicion.objects.filter(protocolo=protocolo_urotc_hematuria).exclude(orden__in=expected).delete()[0]
        self.fases_eliminadas += deleted

        # ===== PROTOCOLO E: TC SANGRADO ACTIVO ABDOMEN =====
        protocolo_sangrado = self.upsert_protocolo(
            tc=tc,
            nombre='TC sangrado activo abdomen (arterial + portal)',
            region=abd,
            descripcion='Protocolo de urgencia bifásico para detectar sangrado activo intraabdominal. Fase arterial detecta extravasación, fase portal confirma y localiza.',
            tags=[tag_sangrado, tag_urgencia, tag_vascular],
            requiere_contraste_ev=True,
            requiere_contraste_oral=False,
            requiere_ayuno=False,
            calibre_via='20G',
            sitio_via='Fosa antecubital',
            preparacion='''NO requiere ayuno (urgencia)
Vía periférica calibre 20G o 18G
Flujo: 3-4 ml/seg, volumen 100-150ml
Reposición de volemia simultánea con cristaloides
Paciente estable hemodinámicamente para realizar el estudio''',
            cobertura='Desde diafragma hasta sínfisis púbica (evaluar hemoperitoneo completo)',
            notas_docentes='''CUÁNDO ELEGIR ESTE PROTOCOLO:
- Sangrado digestivo bajo severo (rectorragia masiva)
- Sospecha de sangrado intraabdominal post-trauma cerrado
- Sangrado post-quirúrgico (post-operatorio inmediato)
- Paciente con hemoperitoneo y causa no clara
- Anticoagulado con caída de hematocrito

CUÁNDO NO ELEGIR ESTE PROTOCOLO:
- Paciente hemodinámicamente inestable → cirugía directa sin TC
- Sangrado digestivo alto → endoscopia primero

QUÉ EVALUAR:
1. FASE ARTERIAL (25-35s):
   - EXTRAVASACIÓN ACTIVA: foco de contraste hiperdenso (jet, pooling)
   - Localización del vaso sangrante
   - Pseudoaneurisma (colección encapsulada con realce)
   - Hemoperitoneo (sangre en espacios peritoneales)
   
2. FASE PORTAL (65-75s):
   - Confirmar sangrado: el foco de extravasación CRECE (se hace más grande)
   - Pooling de contraste en pelvis, espacios parietocólicos
   - Origen del sangrado: intestinal, vascular, esplénico, hepático
   - Cuantificar hemoperitoneo (espacios de Morrison, Douglas, parietocólicos)

SIGNOS DE SANGRADO ACTIVO:
- "Jet sign": extravasación activa en spray (arterial)
- "Pooling": acumulación de contraste que crece en fase tardía
- "Sentinel clot": coágulo centinela que marca sitio de sangrado
- Hematoma en expansión (crece entre fases)

CAUSAS FRECUENTES:
- Trauma esplénico/hepático (órgano sólido)
- Sangrado de mesos intestinales (vasos mesentéricos)
- Aneurisma roto (aorta, esplénico, renal)
- Sangrado tumoral (tumor hipervascular)

INDICACIÓN DE ANGIOEMBOLIZACIÓN:
- Extravasación activa confirmada
- Pseudoaneurisma
- Sangrado persistente a pesar de reanimación
- Paciente no candidato a cirugía''',
            es_activo=True
        )

        self.upsert_fase(protocolo_sangrado, orden=1, nombre='Fase arterial',
                        tipo='ART', region=abd, delay=30,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40), Vascular (W600/L200)',
                        tecnicos='120 kVp, cortes 2-3mm',
                        notas_residente='BUSCAR EXTRAVASACIÓN: foco hiperdenso de contraste fuera del lumen vascular. Puede ser puntiforme (jet) o en colección (pooling). Ventana vascular útil para identificar focos pequeños. Evaluar órganos sólidos: laceración esplénica/hepática.')

        self.upsert_fase(protocolo_sangrado, orden=2, nombre='Fase portal venosa',
                        tipo='PORT', region=abd, delay=70,
                        cobertura_desde='Diafragma', cobertura_hasta='Sínfisis púbica',
                        ventanas='Parénquima (W400/L40)',
                        tecnicos='120 kVp, cortes 3mm',
                        notas_residente='Comparar con fase arterial: si el foco de contraste CRECIÓ → sangrado activo confirmado. Evaluar extensión del hemoperitoneo (cuantificar en pelvis, parietocólicos). Identificar origen anatómico del sangrado. Informar URGENTE al equipo tratante si hay extravasación.')

        expected = [1, 2]
        deleted = FaseAdquisicion.objects.filter(protocolo=protocolo_sangrado).exclude(orden__in=expected).delete()[0]
        self.fases_eliminadas += deleted

        # Resumen final
        self.print_summary()

    def ensure_region(self, codigo, nombre):
        """Helper para asegurar que existe una región."""
        region, _ = RegionAnatomica.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre}
        )
        return region

    def ensure_tag(self, nombre):
        """Helper para asegurar que existe un tag."""
        tag, _ = Tag.objects.get_or_create(nombre=nombre)
        return tag

    def upsert_protocolo(self, tc, nombre, region, descripcion, tags, requiere_contraste_ev,
                        requiere_contraste_oral, requiere_ayuno, calibre_via, sitio_via,
                        preparacion, cobertura, notas_docentes, es_activo):
        """Helper para crear/actualizar protocolo."""
        protocolo, created = Protocolo.objects.update_or_create(
            nombre=nombre,
            modalidad=tc,
            region=region,
            defaults={
                'descripcion': descripcion,
                'requiere_contraste_ev': requiere_contraste_ev,
                'requiere_contraste_oral': requiere_contraste_oral,
                'requiere_ayuno': requiere_ayuno,
                'calibre_via_minimo': calibre_via,
                'sitio_via_preferido': sitio_via,
                'preparacion_paciente': preparacion,
                'cobertura_global': cobertura,
                'notas_docentes': notas_docentes,
                'es_activo': es_activo,
            }
        )
        protocolo.tags.set(tags)
        
        if created:
            self.protocolos_creados += 1
        else:
            self.protocolos_actualizados += 1
        
        return protocolo

    def upsert_fase(self, protocolo, orden, nombre, tipo, region, cobertura_desde=None,
                   cobertura_hasta=None, delay=None, ventanas=None, tecnicos=None,
                   notas_residente=None):
        """Helper para crear/actualizar fase."""
        fase, created = FaseAdquisicion.objects.update_or_create(
            protocolo=protocolo,
            orden=orden,
            defaults={
                'nombre': nombre,
                'tipo_fase': tipo,
                'region': region,
                'delay_segundos': delay,
                'cobertura_desde': cobertura_desde,
                'cobertura_hasta': cobertura_hasta,
                'ventanas_recomendadas': ventanas,
                'detalles_tecnicos': tecnicos,
                'notas_para_residente': notas_residente,
            }
        )
        
        if created:
            self.fases_creadas += 1
        else:
            self.fases_actualizadas += 1

    def print_summary(self):
        """Imprime resumen final."""
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('✅ CARGA DE PROTOCOLOS MULTIFÁSICOS COMPLETADA'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS(f'\n📊 RESUMEN:'))
        self.stdout.write(self.style.SUCCESS(f'  • Protocolos NUEVOS creados: {self.protocolos_creados}'))
        self.stdout.write(self.style.SUCCESS(f'  • Protocolos actualizados: {self.protocolos_actualizados}'))
        self.stdout.write(self.style.SUCCESS(f'  • Fases NUEVAS creadas: {self.fases_creadas}'))
        self.stdout.write(self.style.SUCCESS(f'  • Fases actualizadas: {self.fases_actualizadas}'))
        if self.fases_eliminadas > 0:
            self.stdout.write(self.style.WARNING(f'  • Fases obsoletas eliminadas: {self.fases_eliminadas}'))
        self.stdout.write(self.style.SUCCESS(f'\n✅ Total de protocolos en sistema: {Protocolo.objects.count()}'))
        self.stdout.write(self.style.SUCCESS('='*80))
        
        self.stdout.write(self.style.WARNING('\n📋 PROTOCOLOS MULTIFÁSICOS ASEGURADOS:'))
        self.stdout.write('  A) TC Hígado trifásico (3 fases) - caracterización lesión focal')
        self.stdout.write('  B) TC Páncreas bifásico (2 fases) - fase pancreática + portal')
        self.stdout.write('  C) TC Riñón multifásico (4 fases) - renal mass protocol')
        self.stdout.write('  D) Uro-TC hematuria (3 fases) - urograma por TC')
        self.stdout.write('  E) TC sangrado activo abdomen (2 fases) - urgencia')
        
        self.stdout.write(self.style.WARNING('\n🎯 Próximos pasos:'))
        self.stdout.write('  • Acceder a http://localhost:8000/protocolos/')
        self.stdout.write('  • Filtrar por tags: Caracterización, Hematuria, Sangrado, etc.')
        self.stdout.write('  • Revisar fases de adquisición de cada protocolo')
        self.stdout.write('  • Comando es idempotente: puedes ejecutarlo múltiples veces')
        self.stdout.write('')
