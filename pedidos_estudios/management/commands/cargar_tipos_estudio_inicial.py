"""
Management command para cargar tipos de estudio iniciales de Ecodoppler y Ecocardiograma.

Uso:
    python manage.py cargar_tipos_estudio_inicial
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from pedidos_estudios.models import TipoEstudio

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga los tipos de estudio iniciales (Ecodoppler y Ecocardiograma)'
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Cargando tipos de estudio iniciales...')
        )
        
        # Datos de tipos de estudio
        tipos_estudio = [
            # Ecocardiogramas
            {
                'nombre': 'Ecocardiograma Transtorácico',
                'modalidad': 'US',
                'descripcion': 'Ecocardiograma transtorácico (ETT) con evaluación de función ventricular, válvulas y estructuras cardíacas',
                'codigo_interno': 'ECO-TT',
                'requiere_preparacion': False,
                'tiempo_estimado': 45,
            },
            {
                'nombre': 'Ecocardiograma Transesofágico',
                'modalidad': 'US',
                'descripcion': 'Ecocardiograma transesofágico (ETE/TEE) con sedación. Requiere ayuno de 6 horas',
                'codigo_interno': 'ECO-TE',
                'requiere_preparacion': True,
                'tiempo_estimado': 60,
            },
            {
                'nombre': 'Ecocardiograma Doppler Color',
                'modalidad': 'US',
                'descripcion': 'Ecocardiograma con Doppler color para evaluación de flujos intracardíacos',
                'codigo_interno': 'ECO-DOP',
                'requiere_preparacion': False,
                'tiempo_estimado': 45,
            },
            
            # Ecodoppler Vascular - Miembros
            {
                'nombre': 'Ecodoppler de Miembros Inferiores',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler arterial y venoso de miembros inferiores (MMII)',
                'codigo_interno': 'DOP-MMII',
                'requiere_preparacion': False,
                'tiempo_estimado': 40,
            },
            {
                'nombre': 'Ecodoppler de Miembros Superiores',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler arterial y venoso de miembros superiores (MMSS)',
                'codigo_interno': 'DOP-MMSS',
                'requiere_preparacion': False,
                'tiempo_estimado': 30,
            },
            
            # Ecodoppler Vascular - Específicos
            {
                'nombre': 'Ecodoppler Carotídeo y Vertebral',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler de arterias carótidas y vertebrales',
                'codigo_interno': 'DOP-CAR',
                'requiere_preparacion': False,
                'tiempo_estimado': 30,
            },
            {
                'nombre': 'Ecodoppler Arterial de MMII',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler arterial de miembros inferiores',
                'codigo_interno': 'DOP-ART-MMII',
                'requiere_preparacion': False,
                'tiempo_estimado': 35,
            },
            {
                'nombre': 'Ecodoppler Venoso de MMII',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler venoso de miembros inferiores para detección de TVP',
                'codigo_interno': 'DOP-VEN-MMII',
                'requiere_preparacion': False,
                'tiempo_estimado': 35,
            },
            {
                'nombre': 'Ecodoppler Renal',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler de arterias renales',
                'codigo_interno': 'DOP-REN',
                'requiere_preparacion': False,
                'tiempo_estimado': 30,
            },
            {
                'nombre': 'Ecodoppler de Aorta Abdominal',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler de aorta abdominal',
                'codigo_interno': 'DOP-AOR',
                'requiere_preparacion': False,
                'tiempo_estimado': 30,
            },
            
            # Otros estudios vasculares
            {
                'nombre': 'Ecodoppler Testicular',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler testicular',
                'codigo_interno': 'DOP-TEST',
                'requiere_preparacion': False,
                'tiempo_estimado': 20,
            },
            {
                'nombre': 'Ecodoppler Peneano',
                'modalidad': 'US',
                'descripcion': 'Ecodoppler de arterias peneanas',
                'codigo_interno': 'DOP-PEN',
                'requiere_preparacion': True,
                'tiempo_estimado': 30,
            },
        ]
        
        creados = 0
        actualizados = 0
        
        for tipo_data in tipos_estudio:
            tipo, created = TipoEstudio.objects.update_or_create(
                codigo_interno=tipo_data['codigo_interno'],
                defaults=tipo_data
            )
            
            if created:
                creados += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Creado: {tipo.nombre}')
                )
            else:
                actualizados += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Actualizado: {tipo.nombre}')
                )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nResumen:\n'
                f'  • Tipos de estudio creados: {creados}\n'
                f'  • Tipos de estudio actualizados: {actualizados}\n'
                f'  • Total: {creados + actualizados}'
            )
        )
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            '\n' + self.style.WARNING(
                '⚠ Recuerda asignar médicos responsables a cada tipo de estudio '
                'desde el admin: /admin/pedidos_estudios/tipoestudio/'
            )
        )
