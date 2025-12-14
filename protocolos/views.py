from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .models import Protocolo, Modalidad, RegionAnatomica, Tag


class ProtocoloListView(ListView):
    model = Protocolo
    template_name = 'protocolos/lista_protocolos.html'
    context_object_name = 'protocolos'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Protocolo.objects.filter(
            es_activo=True
        ).select_related(
            'modalidad', 
            'region'
        ).prefetch_related(
            'tags'
        ).order_by(
            'modalidad__codigo', 
            'region__nombre', 
            'nombre'
        )
        
        # Filtros
        modalidad_id = self.request.GET.get('modalidad')
        region_id = self.request.GET.get('region')
        tag_slug = self.request.GET.get('tag')
        search_query = self.request.GET.get('q')
        
        if modalidad_id:
            queryset = queryset.filter(modalidad_id=modalidad_id)
        
        if region_id:
            queryset = queryset.filter(region_id=region_id)
        
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)
        
        if search_query:
            queryset = queryset.filter(
                Q(nombre__icontains=search_query) |
                Q(descripcion__icontains=search_query)
            )
        
        return queryset.distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['modalidades'] = Modalidad.objects.all().order_by('codigo')
        context['regiones'] = RegionAnatomica.objects.all().order_by('nombre')
        context['tags'] = Tag.objects.all().order_by('nombre')
        context['filtros_activos'] = {
            'modalidad': self.request.GET.get('modalidad', ''),
            'region': self.request.GET.get('region', ''),
            'tag': self.request.GET.get('tag', ''),
            'q': self.request.GET.get('q', ''),
        }
        return context


class ProtocoloDetailView(DetailView):
    model = Protocolo
    template_name = 'protocolos/detalle_protocolo.html'
    context_object_name = 'protocolo'
    
    def get_queryset(self):
        return Protocolo.objects.filter(
            es_activo=True
        ).select_related(
            'modalidad',
            'region'
        ).prefetch_related(
            'tags',
            'fases__region'
        )


@login_required
def elegir_protocolo(request):
    """
    Página de decisión clínica mejorada: escenarios con metadata rica para soporte de decisiones.
    """
    
    # Definir escenarios clínicos con metadata completa
    escenarios = [
        {
            'key': 'lesion-hepatica',
            'titulo': 'Lesión focal hepática indeterminada',
            'pregunta': '¿Qué protocolo uso para caracterizar una lesión hepática?',
            'cuando': [
                'Lesión detectada en US/TC sin contraste',
                'Paciente cirrótico con nódulo sospechoso',
                'Metástasis hipervasculares a caracterizar',
            ],
            'phase_summary': 'Trifásico',
            'quick_tags': ['Caracterización', 'Oncológico'],
            'protocolos': ['TC Hígado trifásico (caracterización de lesión focal)'],
            'recommendation': {
                'level': 'TRIFASICO',
                'phase_template': 'Sin contraste + Arterial tardía (35-40s) + Portal (65-70s)',
                'rationale': [
                    'Arterial tardía: detecta hipervascularización (hemangioma, HCC, FNH)',
                    'Portal: caracteriza washout (típico de HCC y metástasis)',
                    'Sin contraste basal: diferencia calcio de contraste, evalúa densidad',
                ],
                'must_have': [
                    'Vía venosa calibre 20G o mayor',
                    'Contraste yodado 100-120 mL a 3-4 mL/s',
                    'Paciente en ayunas (4-6 horas)',
                ],
                'avoid': [
                    'NO usar trifásico para seguimiento oncológico de rutina (sobredosis)',
                    'NO solicitar si solo se busca metástasis conocidas (portal única)',
                    'NO indicado en cólico hepático o colecistitis aguda simple',
                ],
                'mnemonica': {
                    'titulo': 'Mnemotecnia: Metástasis hipervasculares',
                    'frase': 'MAMA CAFÉ PARA LA MESA TRES',
                    'items': [
                        ('MA', 'Melanoma'),
                        ('MA', 'Mama'),
                        ('CA', 'Carcinoide'),
                        ('FE', 'Feocromocitoma'),
                        ('PA', 'Páncreas (neuroendocrino)'),
                        ('RA', 'Renal (células claras)'),
                        ('LA', 'Leiomiosarcoma'),
                        ('ME', 'Médula ósea (mieloma)'),
                        ('SA', 'Sarcoma'),
                        ('TRES', 'Tiroideo, Renal endocrino, Estroma GI'),
                    ],
                    'nota': 'Estas metástasis muestran wash-in arterial y pueden simular HCC',
                },
            }
        },
        {
            'key': 'masa-renal',
            'titulo': 'Masa renal indeterminada',
            'pregunta': '¿Quiste o tumor renal?',
            'cuando': [
                'Masa renal en US sin caracterización',
                'Quiste complejo (Bosniak ≥3)',
                'Seguimiento de lesión renal sospechosa',
            ],
            'phase_summary': 'Multifásico (4 fases)',
            'quick_tags': ['Caracterización', 'Oncológico'],
            'protocolos': ['TC Riñón multifásico (renal mass protocol)'],
            'recommendation': {
                'level': 'MULTIFASICO',
                'phase_template': 'Sin contraste + Corticomedular (25-30s) + Nefrográfica (85-90s) + Excretora (5-10 min)',
                'rationale': [
                    'Corticomedular: detecta tumores papilares (hipovascular) vs células claras (hipervascular)',
                    'Nefrográfica: mide realce (>15 UH confirma tumor sólido)',
                    'Excretora tardía: evalúa sistema colector y estadifica',
                ],
                'must_have': [
                    'Vía venosa 20G mínimo',
                    'Contraste 100-120 mL a 3-4 mL/s',
                    'Hidratación oral previa (500 mL agua 1h antes)',
                ],
                'avoid': [
                    'NO usar multifásico para quiste simple típico de Bosniak I',
                    'NO indicado en cólico renal sin masa (sobredosis)',
                    'NO necesario en seguimiento de lesiones benignas confirmadas',
                ],
            }
        },
        {
            'key': 'masa-pancreatica',
            'titulo': 'Sospecha de masa pancreática',
            'pregunta': '¿Cómo estadifico un cáncer de páncreas?',
            'cuando': [
                'Ictericia obstructiva con masa pancreática',
                'CA 19-9 elevado con sospecha clínica',
                'Estadificación de adenocarcinoma pancreático',
            ],
            'phase_summary': 'Bifásico',
            'quick_tags': ['Caracterización', 'Oncológico'],
            'protocolos': ['TC Páncreas bifásico (fase pancreática + portal)'],
            'recommendation': {
                'level': 'BIFASICO',
                'phase_template': 'Arterial pancreática (40-45s) + Portal (65-70s)',
                'rationale': [
                    'Arterial pancreática: detecta adenocarcinoma (hipovascular) vs tumor neuroendocrino (hipervascular)',
                    'Portal: evalúa compromiso venoso mesentérico-portal (clave para resecabilidad)',
                    'Sin fase basal necesaria (el páncreas normal es hiperdenso)',
                ],
                'must_have': [
                    'Vía venosa 20G, contraste 100-120 mL a 4-5 mL/s (flujo rápido)',
                    'Agua oral 500-750 mL para distender duodeno',
                    'Paciente en decúbito supino con brazos arriba',
                ],
                'avoid': [
                    'NO solicitar para pancreatitis aguda simple (portal única es suficiente)',
                    'NO usar bifásico para seguimiento post-Whipple de rutina',
                    'NO indicado en pseudoquiste sin sospecha de neoplasia',
                ],
            }
        },
        {
            'key': 'hematuria',
            'titulo': 'Hematuria macroscópica',
            'pregunta': '¿Dónde está el tumor urotelial?',
            'cuando': [
                'Hematuria macroscópica sin causa clara',
                'Tabaquismo + edad >50 años',
                'Antecedente de tumor urotelial resecado',
            ],
            'phase_summary': 'Bifásico (nefrográfica + excretora)',
            'quick_tags': ['Caracterización', 'Oncológico'],
            'protocolos': ['Uro-TC hematuria (urograma CT)'],
            'recommendation': {
                'level': 'BIFASICO',
                'phase_template': 'Nefrográfica (85-100s) + Excretora (5-10 min)',
                'rationale': [
                    'Nefrográfica: detecta tumores renales parenquimatosos',
                    'Excretora: visualiza defectos de llenado en urotelio (pelvis, uréter, vejiga)',
                    'Combina evaluación de parénquima + vía excretora en un solo estudio',
                ],
                'must_have': [
                    'Vía venosa 20G, contraste 100-120 mL',
                    'Hidratación oral 500 mL agua 1h antes',
                    'Furosemida 10-20 mg IV opcional para opacificar uréteres',
                ],
                'avoid': [
                    'NO usar Uro-TC con contraste para cólico renal (preferir TC sin contraste)',
                    'NO indicado en ITU simple sin hematuria',
                    'NO solicitar en hematuria traumática obvia (evaluar con TC sin contraste primero)',
                ],
            }
        },
        {
            'key': 'sangrado-activo',
            'titulo': 'Sangrado activo abdominal',
            'pregunta': '¿Hay extravasación de contraste?',
            'cuando': [
                'Trauma abdominal con inestabilidad hemodinámica',
                'Post-quirúrgico con sospecha de sangrado',
                'Paciente anticoagulado con hematoma',
            ],
            'phase_summary': 'Bifásico (arterial + portal)',
            'quick_tags': ['Urgencia', 'Vascular'],
            'protocolos': ['TC sangrado activo abdomen (arterial + portal)'],
            'recommendation': {
                'level': 'BIFASICO',
                'phase_template': 'Arterial (25-30s) + Portal (65-70s)',
                'rationale': [
                    'Arterial: detecta extravasación activa de contraste (signo directo de sangrado)',
                    'Portal: confirma persistencia del sangrado y mapea anatomía venosa',
                    'Permite planificar embolización o cirugía urgente',
                ],
                'must_have': [
                    'Vía venosa 18G idealmente (flujo rápido 4-5 mL/s)',
                    'Contraste 100-120 mL',
                    'Avisar a radiólogo de guardia ANTES (evaluar intervención)',
                ],
                'avoid': [
                    'NO usar bifásico para anemia crónica sin signos de sangrado agudo',
                    'NO indicado si estabilidad hemodinámica permite endoscopía primero',
                    'NO solicitar en sangrado menor autolimitado',
                ],
                'red_flags': ['Shock hipovolémico', 'Hb <7 g/dL', 'Coagulopatía'],
            }
        },
        {
            'key': 'dolor-abdominal',
            'titulo': 'Dolor abdominal agudo',
            'pregunta': '¿Apendicitis, diverticulitis o perforación?',
            'cuando': [
                'Dolor abdominal agudo sin diagnóstico claro',
                'Sospecha de apendicitis o diverticulitis',
                'Abdomen agudo con sospecha de perforación',
            ],
            'phase_summary': 'Portal única',
            'quick_tags': ['Urgencia'],
            'protocolos': ['TC de abdomen y pelvis con contraste para dolor agudo'],
            'recommendation': {
                'level': 'MONOFASE',
                'phase_template': 'Portal única (65-70s)',
                'rationale': [
                    'Portal: suficiente para diagnosticar apendicitis, diverticulitis, obstrucción, perforación',
                    'Dosis mínima de radiación para patología urgente',
                    'NO se busca lesión focal que requiera caracterización',
                ],
                'must_have': [
                    'Vía venosa 20G, contraste 100 mL a 3 mL/s',
                    'Contraste oral opcional (500-1000 mL agua en 45-60 min)',
                    'Ayunas no mandatorias en urgencia',
                ],
                'avoid': [
                    'NO solicitar multifásico para dolor típico de apendicitis',
                    'NO usar protocolo bifásico/trifásico si no hay lesión focal conocida',
                    'NO indicar contraste oral en sospecha de perforación libre',
                ],
            }
        },
        {
            'key': 'tep',
            'titulo': 'Sospecha de TEP',
            'pregunta': '¿Hay trombo en las arterias pulmonares?',
            'cuando': [
                'Disnea + dolor torácico + taquicardia',
                'Score de Wells alto para TEP',
                'Dímero D elevado con alta sospecha clínica',
            ],
            'phase_summary': 'Angio arterial pulmonar',
            'quick_tags': ['Urgencia', 'Vascular'],
            'protocolos': ['Angio-TC para descarte de TEP'],
            'recommendation': {
                'level': 'MONOFASE',
                'phase_template': 'Angio arterial pulmonar (timing 100% arterial)',
                'rationale': [
                    'Timing arterial puro: opacifica arterias pulmonares hasta 5ta orden',
                    'Detecta trombos centrales y periféricos',
                    'Evalúa signos de sobrecarga derecha (dilatación VD, reflujo)',
                ],
                'must_have': [
                    'Vía venosa 18G en brazo DERECHO (flujo más directo)',
                    'Contraste 80-100 mL a 4-5 mL/s',
                    'Bolus tracking en tronco pulmonar (trigger 100 UH)',
                ],
                'avoid': [
                    'NO usar para evaluar parénquima pulmonar (pedir TC tórax simple o portal)',
                    'NO solicitar en paciente estable con Wells bajo y dímero D normal',
                    'NO indicado para control de rutina sin sospecha clínica',
                ],
                'red_flags': ['Hipotensión', 'Síncope', 'Signos de cor pulmonale'],
            }
        },
        {
            'key': 'stroke',
            'titulo': 'Stroke code (ACV agudo)',
            'pregunta': '¿Hay oclusión de gran vaso?',
            'cuando': [
                'Déficit neurológico focal de inicio súbito',
                'Candidato a trombectomía (ventana <6-24h)',
                'TC basal sin hemorragia',
            ],
            'phase_summary': 'Angio arterial cerebral',
            'quick_tags': ['Urgencia', 'Vascular'],
            'protocolos': ['Angio-TC cerebral (stroke code)'],
            'recommendation': {
                'level': 'MONOFASE',
                'phase_template': 'Angio arterial cerebral (de cayado a vertex)',
                'rationale': [
                    'Detecta oclusión de gran vaso (M1, M2, ACI, basilar)',
                    'Evalúa circulación colateral (score ASPECTS)',
                    'Determina candidatos a trombectomía mecánica',
                ],
                'must_have': [
                    'Vía venosa 18-20G, contraste 80-100 mL a 4-5 mL/s',
                    'Bolus tracking en cayado aórtico',
                    'TC simple previo para descartar hemorragia (MANDATORIO)',
                ],
                'avoid': [
                    'NO hacer angio sin TC simple previo (riesgo de hemorragia)',
                    'NO solicitar si >24h de evolución sin indicación de trombectomía',
                    'NO indicado para cefalea o mareo sin déficit focal',
                ],
                'red_flags': ['NIHSS ≥6', 'Wake-up stroke', 'Oclusión de basilar'],
            }
        },
        {
            'key': 'aorta',
            'titulo': 'Síndrome aórtico agudo',
            'pregunta': '¿Disección, aneurisma roto o hematoma intramural?',
            'cuando': [
                'Dolor torácico transfixiante de inicio súbito',
                'Asimetría de pulsos o PA entre brazos',
                'Ensanchamiento mediastinal en RX tórax',
            ],
            'phase_summary': 'Angio arterial aórtico',
            'quick_tags': ['Urgencia', 'Vascular'],
            'protocolos': ['Angio-TC Aorta (síndrome aórtico agudo)'],
            'recommendation': {
                'level': 'MONOFASE',
                'phase_template': 'Angio arterial (cayado a femorales + ECG-gating cardíaco opcional)',
                'rationale': [
                    'Detecta flap intimal (disección), hematoma intramural, ruptura',
                    'Clasifica disección (Stanford A vs B) para decidir cirugía vs manejo médico',
                    'Evalúa compromiso de ramas viscerales',
                ],
                'must_have': [
                    'Vía venosa 18G, contraste 100-120 mL a 4-5 mL/s',
                    'Bolus tracking en aorta ascendente',
                    'ECG-gating SI se sospecha disección Stanford A (evita artefactos cardíacos)',
                ],
                'avoid': [
                    'NO solicitar para dolor torácico atípico sin signos de alarma',
                    'NO usar protocolo TEP para evaluar aorta (timing incorrecto)',
                    'NO indicado en control de rutina de aneurisma estable',
                ],
                'red_flags': ['Hipotensión', 'Síncope', 'Déficit de pulso', 'Derrame pericárdico'],
            }
        },
        {
            'key': 'oncologico',
            'titulo': 'Seguimiento oncológico',
            'pregunta': '¿Cómo está la enfermedad oncológica?',
            'cuando': [
                'Control post-tratamiento de cáncer',
                'Evaluación de respuesta a quimioterapia',
                'Seguimiento de metástasis conocidas',
            ],
            'phase_summary': 'Portal única (TAP)',
            'quick_tags': ['Oncológico'],
            'protocolos': ['TC TAP con contraste EV para estadificación oncológica'],
            'recommendation': {
                'level': 'MONOFASE',
                'phase_template': 'Portal única (65-70s) de tórax-abdomen-pelvis',
                'rationale': [
                    'Portal: detecta metástasis en hígado, pulmón, ganglios, hueso',
                    'Criterios RECIST: mide respuesta objetiva al tratamiento',
                    'Dosis acumulativa mínima para controles frecuentes',
                ],
                'must_have': [
                    'Vía venosa 20G, contraste 100-120 mL',
                    'Contraste oral opcional según tumor primario',
                    'Estudios previos para comparación (traer CD/pendrive)',
                ],
                'avoid': [
                    'NO usar trifásico para seguimiento de metástasis conocidas',
                    'NO solicitar TAP para tumores localizados sin riesgo metastásico',
                    'NO indicar multifásico si no hay lesión nueva a caracterizar',
                ],
            }
        },
    ]
    
    # Recopilar todos los nombres de protocolos
    todos_nombres = []
    for escenario in escenarios:
        todos_nombres.extend(escenario['protocolos'])
    
    # Query única optimizada a la base de datos
    protocolos_dict = {
        p.nombre: p 
        for p in Protocolo.objects.filter(
            nombre__in=todos_nombres,
            es_activo=True
        ).select_related('modalidad', 'region').prefetch_related('tags', 'fases')
    }
    
    # Enriquecer escenarios con objetos Protocolo
    escenarios_vinculados = 0
    for escenario in escenarios:
        escenario['protocolos_objetos'] = []
        for nombre in escenario['protocolos']:
            protocolo = protocolos_dict.get(nombre)
            if protocolo:
                escenario['protocolos_objetos'].append({
                    'nombre': nombre,
                    'protocolo': protocolo,
                    'url': reverse('protocolos:detalle', kwargs={'pk': protocolo.pk}),
                    'existe': True,
                    'num_fases': protocolo.fases.count()
                })
                escenarios_vinculados += 1
            else:
                escenario['protocolos_objetos'].append({
                    'nombre': nombre,
                    'protocolo': None,
                    'url': None,
                    'existe': False,
                    'num_fases': 0
                })
    
    context = {
        'escenarios': escenarios,
        'total_escenarios': len(escenarios),
        'escenarios_vinculados': escenarios_vinculados,
    }
    
    return render(request, 'protocolos/elegir_protocolo.html', context)
