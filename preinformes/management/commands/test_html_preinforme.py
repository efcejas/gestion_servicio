from django.core.management.base import BaseCommand
from preinformes.models import Preinforme, RevisionPreinforme
import logging


class Command(BaseCommand):
    help = 'Muestra el HTML generado para un preinforme específico (test/debug)'

    def add_arguments(self, parser):
        parser.add_argument(
            'numero_estudio',
            type=str,
            help='Número de estudio del preinforme a testear',
        )

    def handle(self, *args, **options):
        numero_estudio = options['numero_estudio']
        
        # Configurar logging para ver los mensajes
        logging.basicConfig(level=logging.DEBUG)
        
        try:
            preinforme = Preinforme.objects.get(numero_estudio=numero_estudio)
        except Preinforme.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ No existe preinforme con número: {numero_estudio}\n'))
            return
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'\n📋 PREINFORME: {preinforme.numero_estudio}'))
        self.stdout.write(f'   Paciente: {preinforme.apellido_paciente}, {preinforme.nombre_paciente}')
        self.stdout.write(f'   Estado: {preinforme.get_estado_display()}')
        self.stdout.write(f'   Residente: {preinforme.residente.get_full_name()}')
        
        if preinforme.plantilla_utilizada:
            self.stdout.write(f'   Plantilla: {preinforme.plantilla_utilizada.nombre}')
        else:
            self.stdout.write(f'   Tipo: {preinforme.tipo_estudio.nombre} (sin plantilla)')
        
        # Obtener o crear revisión
        revision, created = RevisionPreinforme.objects.get_or_create(
            preinforme=preinforme,
            defaults={'revisor': preinforme.residente}  # temporal para test
        )
        
        self.stdout.write('\n' + '-'*80)
        self.stdout.write(self.style.WARNING('\n🔧 GENERANDO HTML...\n'))
        
        # Generar HTML (esto imprimirá logs de debug)
        html_generado = revision.generar_informe_original_residente()
        
        self.stdout.write('\n' + '-'*80)
        self.stdout.write(self.style.SUCCESS('\n📄 HTML GENERADO COMPLETO:\n'))
        self.stdout.write('='*80 + '\n')
        self.stdout.write(html_generado)
        self.stdout.write('\n' + '='*80)
        
        # Análisis del HTML
        self.stdout.write('\n' + '-'*80)
        self.stdout.write(self.style.WARNING('\n🔍 ANÁLISIS DEL HTML:\n'))
        
        # Verificar problemas comunes
        checks = []
        
        if 'text-align:center' in html_generado or 'text-align: center' in html_generado:
            checks.append(('❌ FALLO', 'Contiene text-align:center'))
        else:
            checks.append(('✅ OK', 'NO contiene text-align:center'))
        
        if '<center' in html_generado.lower():
            checks.append(('❌ FALLO', 'Contiene tags <center>'))
        else:
            checks.append(('✅ OK', 'NO contiene tags <center>'))
        
        if 'text-center' in html_generado:
            checks.append(('❌ FALLO', 'Contiene class text-center'))
        else:
            checks.append(('✅ OK', 'NO contiene class text-center'))
        
        p_count = html_generado.count('<p>')
        checks.append((f'📊 INFO', f'Contiene {p_count} tags <p>'))
        
        if 'CONCLUSIÓN' in html_generado:
            checks.append(('📊 INFO', 'Contiene encabezado CONCLUSIÓN'))
        else:
            checks.append(('📊 INFO', 'NO contiene encabezado CONCLUSIÓN'))
        
        for status, msg in checks:
            if status.startswith('❌'):
                self.stdout.write(self.style.ERROR(f'   {status}: {msg}'))
            elif status.startswith('✅'):
                self.stdout.write(self.style.SUCCESS(f'   {status}: {msg}'))
            else:
                self.stdout.write(f'   {status}: {msg}')
        
        # Mostrar longitudes
        self.stdout.write('\n' + '-'*80)
        self.stdout.write('\n📏 ESTADÍSTICAS:\n')
        self.stdout.write(f'   Total caracteres: {len(html_generado)}')
        self.stdout.write(f'   Total palabras (aprox): {len(html_generado.split())}')
        self.stdout.write(f'   Total párrafos <p>: {p_count}')
        
        self.stdout.write('\n' + '='*80 + '\n')
