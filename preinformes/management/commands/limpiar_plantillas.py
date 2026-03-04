"""
Comando para limpiar plantillas existentes en la BD.
Elimina backgrounds, centrado, normaliza HTML.

Uso:
    python manage.py limpiar_plantillas
    python manage.py limpiar_plantillas --dry-run  # Ver qué se modificaría sin guardar
    python manage.py limpiar_plantillas --id 5     # Limpiar solo una plantilla específica
"""

from django.core.management.base import BaseCommand
from preinformes.models import PlantillaPreinforme, sanitize_center_alignment, normalize_html_content
from bs4 import BeautifulSoup


class Command(BaseCommand):
    help = 'Limpia todas las plantillas: elimina backgrounds, centrado y normaliza HTML'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se modificaría sin guardar cambios',
        )
        parser.add_argument(
            '--id',
            type=int,
            help='Limpiar solo una plantilla específica por ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        plantilla_id = options.get('id')

        # Filtrar plantillas
        if plantilla_id:
            plantillas = PlantillaPreinforme.objects.filter(id=plantilla_id)
            if not plantillas.exists():
                self.stdout.write(self.style.ERROR(f'Plantilla con ID {plantilla_id} no encontrada'))
                return
        else:
            plantillas = PlantillaPreinforme.objects.all()

        total = plantillas.count()
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n🔍 MODO DRY-RUN: No se guardará nada\n'))
        
        self.stdout.write(f'Total de plantillas a procesar: {total}\n')

        modificadas = 0
        sin_cambios = 0

        for plantilla in plantillas:
            original_contenido = plantilla.contenido or ''
            
            if not original_contenido:
                self.stdout.write(f'  ⚪ ID {plantilla.id}: "{plantilla.nombre}" - Sin contenido')
                sin_cambios += 1
                continue

            # Guardar contenido original para comparar
            contenido_limpio = original_contenido

            # 1. Eliminar alineación centrada
            contenido_limpio = sanitize_center_alignment(contenido_limpio)

            # 2. Eliminar backgrounds
            soup = BeautifulSoup(contenido_limpio, 'html.parser')
            for tag in soup.find_all(True):
                if tag.has_attr('style'):
                    style_parts = [s.strip() for s in tag['style'].split(';') if s.strip()]
                    cleaned_parts = [p for p in style_parts if not p.lower().startswith('background')]
                    
                    if cleaned_parts:
                        tag['style'] = '; '.join(cleaned_parts)
                    else:
                        del tag['style']
            
            contenido_limpio = str(soup)

            # 3. Normalizar HTML
            contenido_limpio = normalize_html_content(contenido_limpio)

            # Verificar si hubo cambios
            if contenido_limpio != original_contenido:
                modificadas += 1
                
                # Mostrar preview de cambios
                self.stdout.write(f'\n  🔧 ID {plantilla.id}: "{plantilla.nombre}"')
                self.stdout.write(f'     Tipo: {plantilla.tipo_estudio.nombre} - {plantilla.region.nombre}')
                self.stdout.write(f'     Estado: {plantilla.estado} | Creada por: {plantilla.creada_por.username}')
                
                # Detectar qué se limpió
                cambios = []
                if 'text-align:center' in original_contenido or '<center' in original_contenido.lower():
                    cambios.append('centrado')
                if 'background' in original_contenido.lower():
                    cambios.append('backgrounds')
                if '<br' in original_contenido.lower() and '<br' not in contenido_limpio.lower():
                    cambios.append('<br>→<p>')
                if '&nbsp;' in original_contenido:
                    cambios.append('&nbsp;')
                
                if cambios:
                    self.stdout.write(f'     Limpieza: {", ".join(cambios)}')
                
                if not dry_run:
                    plantilla.contenido = contenido_limpio
                    plantilla.save(update_fields=['contenido', 'fecha_modificacion'])
                    self.stdout.write(self.style.SUCCESS('     ✅ Guardada'))
                else:
                    self.stdout.write(self.style.WARNING('     ⚠️  No guardada (dry-run)'))
            else:
                sin_cambios += 1
                self.stdout.write(f'  ✅ ID {plantilla.id}: "{plantilla.nombre}" - Sin cambios necesarios')

        # Resumen
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'\n📊 RESUMEN:')
        self.stdout.write(f'   Total procesadas: {total}')
        self.stdout.write(self.style.SUCCESS(f'   Modificadas: {modificadas}'))
        self.stdout.write(f'   Sin cambios: {sin_cambios}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Ejecuta sin --dry-run para guardar los cambios'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Cambios guardados en la base de datos'))
