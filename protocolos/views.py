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
            'protocolos': ['TC Hígado trifásico (caracterización de lesión focal)']
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
            'protocolos': ['TC Riñón multifásico (renal mass protocol)']
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
            'protocolos': ['TC Páncreas bifásico (fase pancreática + portal)']
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
            'protocolos': ['Uro-TC hematuria (urograma CT)']
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
            'protocolos': ['TC sangrado activo abdomen (arterial + portal)']
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
            'protocolos': ['TC de abdomen y pelvis con contraste para dolor agudo']
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
            'protocolos': ['Angio-TC para descarte de TEP']
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
            'protocolos': ['Angio-TC cerebral (stroke code)']
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
            'protocolos': ['Angio-TC Aorta (síndrome aórtico agudo)']
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
            'protocolos': ['TC TAP con contraste EV para estadificación oncológica']
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
