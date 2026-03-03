"""
Comando Django para cargar datos de ejemplo en la base de datos local
para probar el sistema de preinformes con plantillas NetTerm y EGES
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from preinformes.models import TipoEstudio, Region, PlantillaPreinforme, Preinforme, RevisionPreinforme

User = get_user_model()

class Command(BaseCommand):
    help = 'Carga datos de ejemplo para probar preinformes NetTerm y EGES'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('CARGANDO DATOS DE EJEMPLO'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        self.crear_tipos_estudios()
        self.crear_regiones()
        self.crear_plantillas()
        self.crear_preinformes()
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('✓ DATOS DE EJEMPLO CARGADOS EXITOSAMENTE'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'\nResumen:')
        self.stdout.write(f'- {TipoEstudio.objects.count()} tipos de estudio')
        self.stdout.write(f'- {Region.objects.count()} regiones')
        self.stdout.write(f'- {PlantillaPreinforme.objects.count()} plantillas')
        self.stdout.write(f'- {Preinforme.objects.count()} preinformes')
        self.stdout.write(self.style.WARNING('\nPuedes probar copiando los informes finalizados (2026-0001 a 2026-0004)'))
        self.stdout.write(self.style.WARNING('Verás la diferencia entre NetTerm (texto plano) y EGES (con formato)'))

    def crear_tipos_estudios(self):
        """Crear tipos de estudios comunes"""
        tipos = [
            'Ecocardiograma Transtorácico',
            'Ecocardiograma Transesofágico',
            'Ecodoppler Carotídeo',
            'Ecodoppler de Miembros Inferiores',
            'Ecodoppler de Miembros Superiores',
            'Ecodoppler Arterial de MMII',
            'Ecodoppler Venoso de MMII',
        ]
        
        self.stdout.write('\n=== CREANDO TIPOS DE ESTUDIO ===')
        for nombre in tipos:
            tipo, created = TipoEstudio.objects.get_or_create(
                nombre=nombre,
                defaults={'activo': True}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Creado: {nombre}'))
            else:
                self.stdout.write(f'- Ya existía: {nombre}')

    def crear_regiones(self):
        """Crear regiones anatómicas"""
        regiones = [
            'Cardíaco',
            'Vascular Periférico',
            'Cuello',
            'Miembros Superiores',
            'Miembros Inferiores',
            'Abdomen',
        ]
        
        self.stdout.write('\n=== CREANDO REGIONES ===')
        for nombre in regiones:
            region, created = Region.objects.get_or_create(
                nombre=nombre,
                defaults={'activo': True}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✓ Creada: {nombre}'))
            else:
                self.stdout.write(f'- Ya existía: {nombre}')

    def crear_plantillas(self):
        """Crear plantillas de ejemplo para NetTerm y EGES"""
        self.stdout.write('\n=== CREANDO PLANTILLAS ===')
        
        # Obtener datos necesarios
        try:
            jefe = User.objects.get(username='efccejas')
            eco_tt = TipoEstudio.objects.get(nombre='Ecocardiograma Transtorácico')
            region_cardiaco = Region.objects.get(nombre='Cardíaco')
            eco_carotideo = TipoEstudio.objects.get(nombre='Ecodoppler Carotídeo')
            region_cuello = Region.objects.get(nombre='Cuello')
            eco_mmii = TipoEstudio.objects.get(nombre='Ecodoppler Venoso de MMII')
            region_mmii = Region.objects.get(nombre='Miembros Inferiores')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {e}'))
            return
        
        plantillas = [
            {
                'nombre': 'Ecocardiograma Normal - NetTerm',
                'tipo_estudio': eco_tt,
                'region': region_cardiaco,
                'sistema_destino': 'netterm',
                'estado': 'publica',
                'contenido': '''<p><strong>TECNICA:</strong></p>
<p>Estudio ecocardiografico bidimensional con Doppler color, pulsado y continuo.</p>

<p><strong>HALLAZGOS:</strong></p>
<p>Cavidades cardiacas de tamano normal.</p>
<p>Funcion sistolica del ventriculo izquierdo conservada (FEVI: 60%).</p>
<p>Motilidad parietal normal.</p>
<p>Espesor parietal normal.</p>
<p>Valvulas cardiacas de aspecto anatomico normal.</p>
<p>No se observan alteraciones del flujo valvular.</p>
<p>Auricula izquierda de tamano normal.</p>
<p>Aorta ascendente de calibre normal.</p>
<p>No se observa derrame pericardico.</p>

<p><strong>CONCLUSION:</strong></p>
<p>Ecocardiograma dentro de limites normales.</p>'''
            },
            {
                'nombre': 'Ecocardiograma Normal - EGES',
                'tipo_estudio': eco_tt,
                'region': region_cardiaco,
                'sistema_destino': 'eges',
                'estado': 'publica',
                'contenido': '''<p><strong>TÉCNICA:</strong></p>
<p>Estudio ecocardiográfico bidimensional con Doppler color, pulsado y continuo.</p>

<p><strong>HALLAZGOS:</strong></p>
<p>Cavidades cardíacas de tamaño normal.</p>
<p>Función sistólica del ventrículo izquierdo conservada (FEVI: 60%).</p>
<p>Motilidad parietal normal.</p>
<p>Espesor parietal normal.</p>
<p>Válvulas cardíacas de aspecto anatómico normal.</p>
<p>No se observan alteraciones del flujo valvular.</p>
<p>Aurícula izquierda de tamaño normal.</p>
<p>Aorta ascendente de calibre normal.</p>
<p>No se observa derrame pericárdico.</p>

<p><strong>CONCLUSIÓN:</strong></p>
<p>Ecocardiograma dentro de límites normales.</p>'''
            },
            {
                'nombre': 'Ecodoppler Carotídeo Normal - NetTerm',
                'tipo_estudio': eco_carotideo,
                'region': region_cuello,
                'sistema_destino': 'netterm',
                'estado': 'publica',
                'contenido': '''<p><strong>TECNICA:</strong></p>
<p>Estudio ecografico con Doppler color y espectral de arterias carotidas y vertebrales.</p>

<p><strong>HALLAZGOS:</strong></p>
<p><strong>DERECHA:</strong></p>
<p>Arteria carotida comun: permeable, de calibre y morfologia normal.</p>
<p>Arteria carotida interna: permeable, sin evidencia de placas ateromatosas.</p>
<p>Arteria carotida externa: permeable.</p>
<p>Arteria vertebral: permeable, flujo anterogrado normal.</p>

<p><strong>IZQUIERDA:</strong></p>
<p>Arteria carotida comun: permeable, de calibre y morfologia normal.</p>
<p>Arteria carotida interna: permeable, sin evidencia de placas ateromatosas.</p>
<p>Arteria carotida externa: permeable.</p>
<p>Arteria vertebral: permeable, flujo anterogrado normal.</p>

<p><strong>CONCLUSION:</strong></p>
<p>Ecodoppler carotideo bilateral sin evidencia de lesiones significativas.</p>'''
            },
            {
                'nombre': 'Ecodoppler Carotídeo Normal - EGES',
                'tipo_estudio': eco_carotideo,
                'region': region_cuello,
                'sistema_destino': 'eges',
                'estado': 'publica',
                'contenido': '''<p><strong>TÉCNICA:</strong></p>
<p>Estudio ecográfico con Doppler color y espectral de arterias carótidas y vertebrales.</p>

<p><strong>HALLAZGOS:</strong></p>
<p><strong>DERECHA:</strong></p>
<p>Arteria carótida común: permeable, de calibre y morfología normal.</p>
<p>Arteria carótida interna: permeable, sin evidencia de placas ateromatosas.</p>
<p>Arteria carótida externa: permeable.</p>
<p>Arteria vertebral: permeable, flujo anterógrado normal.</p>

<p><strong>IZQUIERDA:</strong></p>
<p>Arteria carótida común: permeable, de calibre y morfología normal.</p>
<p>Arteria carótida interna: permeable, sin evidencia de placas ateromatosas.</p>
<p>Arteria carótida externa: permeable.</p>
<p>Arteria vertebral: permeable, flujo anterógrado normal.</p>

<p><strong>CONCLUSIÓN:</strong></p>
<p>Ecodoppler carotídeo bilateral sin evidencia de lesiones significativas.</p>'''
            },
            {
                'nombre': 'Ecodoppler Venoso MMII Normal - NetTerm',
                'tipo_estudio': eco_mmii,
                'region': region_mmii,
                'sistema_destino': 'netterm',
                'estado': 'publica',
                'contenido': '''<p><strong>TECNICA:</strong></p>
<p>Estudio ecografico con Doppler color del sistema venoso profundo y superficial de miembros inferiores.</p>

<p><strong>HALLAZGOS:</strong></p>
<p><strong>MIEMBRO INFERIOR DERECHO:</strong></p>
<p>Vena femoral comun, femoral superficial y profunda: permeables, compresibles, sin evidencia de trombosis.</p>
<p>Vena poplitea: permeable y compresible.</p>
<p>Venas tibiales: permeables.</p>

<p><strong>MIEMBRO INFERIOR IZQUIERDO:</strong></p>
<p>Vena femoral comun, femoral superficial y profunda: permeables, compresibles, sin evidencia de trombosis.</p>
<p>Vena poplitea: permeable y compresible.</p>
<p>Venas tibiales: permeables.</p>

<p><strong>CONCLUSION:</strong></p>
<p>Sistema venoso profundo de ambos miembros inferiores permeable.</p>
<p>No se evidencia trombosis venosa profunda.</p>'''
            },
            {
                'nombre': 'Ecodoppler Venoso MMII Normal - EGES',
                'tipo_estudio': eco_mmii,
                'region': region_mmii,
                'sistema_destino': 'eges',
                'estado': 'publica',
                'contenido': '''<p><strong>TÉCNICA:</strong></p>
<p>Estudio ecográfico con Doppler color del sistema venoso profundo y superficial de miembros inferiores.</p>

<p><strong>HALLAZGOS:</strong></p>
<p><strong>MIEMBRO INFERIOR DERECHO:</strong></p>
<p>Vena femoral común, femoral superficial y profunda: permeables, compresibles, sin evidencia de trombosis.</p>
<p>Vena poplítea: permeable y compresible.</p>
<p>Venas tibiales: permeables.</p>

<p><strong>MIEMBRO INFERIOR IZQUIERDO:</strong></p>
<p>Vena femoral común, femoral superficial y profunda: permeables, compresibles, sin evidencia de trombosis.</p>
<p>Vena poplítea: permeable y compresible.</p>
<p>Venas tibiales: permeables.</p>

<p><strong>CONCLUSIÓN:</strong></p>
<p>Sistema venoso profundo de ambos miembros inferiores permeable.</p>
<p>No se evidencia trombosis venosa profunda.</p>'''
            },
        ]
        
        for data in plantillas:
            plantilla, created = PlantillaPreinforme.objects.get_or_create(
                nombre=data['nombre'],
                tipo_estudio=data['tipo_estudio'],
                region=data['region'],
                defaults={
                    'sistema_destino': data['sistema_destino'],
                    'estado': data['estado'],
                    'contenido': data['contenido'],
                    'creada_por': jefe,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✓ Creada: {data['nombre']}"))
            else:
                self.stdout.write(f"- Ya existía: {data['nombre']}")

    def crear_preinformes(self):
        """Crear preinformes de ejemplo"""
        self.stdout.write('\n=== CREANDO PREINFORMES DE EJEMPLO ===')
        
        try:
            residente = User.objects.get(username='ResidentePrueba')
            revisor = User.objects.get(username='efccejas')
            
            eco_tt = TipoEstudio.objects.get(nombre='Ecocardiograma Transtorácico')
            region_cardiaco = Region.objects.get(nombre='Cardíaco')
            plantilla_netterm = PlantillaPreinforme.objects.get(nombre='Ecocardiograma Normal - NetTerm')
            plantilla_eges = PlantillaPreinforme.objects.get(nombre='Ecocardiograma Normal - EGES')
            
            eco_carotideo = TipoEstudio.objects.get(nombre='Ecodoppler Carotídeo')
            region_cuello = Region.objects.get(nombre='Cuello')
            plantilla_carotideo_netterm = PlantillaPreinforme.objects.get(nombre='Ecodoppler Carotídeo Normal - NetTerm')
            
            eco_mmii = TipoEstudio.objects.get(nombre='Ecodoppler Venoso de MMII')
            region_mmii = Region.objects.get(nombre='Miembros Inferiores')
            plantilla_mmii_eges = PlantillaPreinforme.objects.get(nombre='Ecodoppler Venoso MMII Normal - EGES')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error obteniendo datos: {e}'))
            return
        
        preinformes = [
            {
                'numero_estudio': '2026-0001',
                'tipo_estudio': eco_tt,
                'region': region_cardiaco,
                'sistema_destino': 'netterm',
                'plantilla': plantilla_netterm,
                'apellido': 'González',
                'nombre': 'María',
                'dni': '35123456',
                'edad': 45,
                'sexo': 'F',
                'estado': 'finalizado',
            },
            {
                'numero_estudio': '2026-0002',
                'tipo_estudio': eco_tt,
                'region': region_cardiaco,
                'sistema_destino': 'eges',
                'plantilla': plantilla_eges,
                'apellido': 'Pérez',
                'nombre': 'Juan',
                'dni': '28456789',
                'edad': 58,
                'sexo': 'M',
                'estado': 'finalizado',
            },
            {
                'numero_estudio': '2026-0003',
                'tipo_estudio': eco_carotideo,
                'region': region_cuello,
                'sistema_destino': 'netterm',
                'plantilla': plantilla_carotideo_netterm,
                'apellido': 'Rodríguez',
                'nombre': 'Alberto',
                'dni': '42987654',
                'edad': 62,
                'sexo': 'M',
                'estado': 'finalizado',
            },
            {
                'numero_estudio': '2026-0004',
                'tipo_estudio': eco_mmii,
                'region': region_mmii,
                'sistema_destino': 'eges',
                'plantilla': plantilla_mmii_eges,
                'apellido': 'Silva',
                'nombre': 'Rosa',
                'dni': '31234567',
                'edad': 52,
                'sexo': 'F',
                'estado': 'finalizado',
            },
            {
                'numero_estudio': '2026-0005',
                'tipo_estudio': eco_tt,
                'region': region_cardiaco,
                'sistema_destino': 'netterm',
                'plantilla': plantilla_netterm,
                'apellido': 'López',
                'nombre': 'Carlos',
                'dni': '25123456',
                'edad': 70,
                'sexo': 'M',
                'estado': 'pendiente_revision',
            },
        ]
        
        for data in preinformes:
            # Verificar si ya existe
            if Preinforme.objects.filter(numero_estudio=data['numero_estudio']).exists():
                self.stdout.write(f"- Ya existe preinforme {data['numero_estudio']}")
                continue
            
            preinforme = Preinforme.objects.create(
                residente=residente,
                numero_estudio=data['numero_estudio'],
                tipo_estudio=data['tipo_estudio'],
                region=data['region'],
                sistema_destino=data['sistema_destino'],
                plantilla_utilizada=data['plantilla'],
                apellido_paciente=data['apellido'],
                nombre_paciente=data['nombre'],
                dni_paciente=data['dni'],
                edad_paciente=data['edad'],
                sexo_paciente=data['sexo'],
                estado=data['estado'],
                informe_html=data['plantilla'].contenido,
            )
            
            # Si está finalizado, crear revisión
            if data['estado'] == 'finalizado':
                revision = RevisionPreinforme.objects.create(
                    preinforme=preinforme,
                    revisor=revisor,
                    informe_final_html=data['plantilla'].contenido,
                    puntuacion=8,
                    comentarios_generales='Informe correcto, bien estructurado.',
                )
                preinforme.revisor = revisor
                preinforme.save()
                self.stdout.write(self.style.SUCCESS(f"✓ Creado preinforme {data['numero_estudio']} ({data['sistema_destino']}) - FINALIZADO"))
            else:
                self.stdout.write(self.style.SUCCESS(f"✓ Creado preinforme {data['numero_estudio']} ({data['sistema_destino']}) - {data['estado']}"))
