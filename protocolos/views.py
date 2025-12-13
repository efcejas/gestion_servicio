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
    Página de decisión clínica: muestra escenarios comunes y enlaces a protocolos recomendados.
    """
    
    # Definir escenarios clínicos con protocolos asociados
    escenarios = [
        {
            'titulo': 'Lesión focal hepática indeterminada',
            'descripcion': 'Lesión detectada incidentalmente en US/TC que requiere caracterización',
            'protocolos': ['TC Hígado trifásico (caracterización de lesión focal)']
        },
        {
            'titulo': 'Masa renal indeterminada',
            'descripcion': 'Masa renal detectada en US/TC que requiere caracterización (¿quiste vs tumor?)',
            'protocolos': ['TC Riñón multifásico (renal mass protocol)']
        },
        {
            'titulo': 'Sospecha de masa pancreática',
            'descripcion': 'Ictericia obstructiva, masa pancreática o estadificación de cáncer pancreático',
            'protocolos': ['TC Páncreas bifásico (fase pancreática + portal)']
        },
        {
            'titulo': 'Hematuria macroscópica',
            'descripcion': 'Hematuria sin causa clara, sospecha de tumor urotelial',
            'protocolos': ['Uro-TC hematuria (urograma CT)']
        },
        {
            'titulo': 'Sangrado activo abdominal',
            'descripcion': 'Sospecha de sangrado intraabdominal activo (trauma, post-quirúrgico, anticoagulado)',
            'protocolos': ['TC sangrado activo abdomen (arterial + portal)']
        },
        {
            'titulo': 'Dolor abdominal agudo',
            'descripcion': 'Sospecha de apendicitis, diverticulitis, perforación intestinal',
            'protocolos': ['TC abdomen-pelvis dolor agudo']
        },
        {
            'titulo': 'Sospecha de TEP',
            'descripcion': 'Tromboembolismo pulmonar (dolor torácico, disnea, taquicardia)',
            'protocolos': ['Angio-TC para TEP']
        },
        {
            'titulo': 'Stroke code (ACV agudo)',
            'descripcion': 'ACV isquémico agudo, evaluación de oclusión de grandes vasos',
            'protocolos': ['Angio-TC cerebral (stroke code)']
        },
        {
            'titulo': 'Síndrome aórtico agudo',
            'descripcion': 'Sospecha de disección aórtica, aneurisma roto, hematoma intramural',
            'protocolos': ['Angio-TC Aorta (síndrome aórtico agudo)']
        },
        {
            'titulo': 'Seguimiento oncológico',
            'descripcion': 'Control de enfermedad oncológica (metástasis, respuesta a tratamiento)',
            'protocolos': ['TC TAP oncológico']
        },
    ]
    
    # Recopilar todos los nombres de protocolos mencionados
    todos_nombres = []
    for escenario in escenarios:
        todos_nombres.extend(escenario['protocolos'])
    
    # Query única a la base de datos
    protocolos_dict = {
        p.nombre: p 
        for p in Protocolo.objects.filter(
            nombre__in=todos_nombres,
            es_activo=True
        ).select_related('modalidad', 'region')
    }
    
    # Enriquecer escenarios con objetos Protocolo
    for escenario in escenarios:
        escenario['protocolos_objetos'] = []
        for nombre in escenario['protocolos']:
            protocolo = protocolos_dict.get(nombre)
            if protocolo:
                escenario['protocolos_objetos'].append({
                    'nombre': nombre,
                    'protocolo': protocolo,
                    'url': reverse('protocolos:detalle', kwargs={'pk': protocolo.pk}),
                    'existe': True
                })
            else:
                escenario['protocolos_objetos'].append({
                    'nombre': nombre,
                    'protocolo': None,
                    'url': None,
                    'existe': False
                })
    
    context = {
        'escenarios': escenarios
    }
    
    return render(request, 'protocolos/elegir_protocolo.html', context)
