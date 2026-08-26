from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from preinformes.models import Preinforme, Region, RevisionPreinforme, TipoEstudio


User = get_user_model()


class Command(BaseCommand):
    help = 'Carga casos locales identificables para probar el copiado NetTerm.'

    def add_arguments(self, parser):
        parser.add_argument('--residente', default='ecejas')
        parser.add_argument('--revisor', default='superadmin')
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Elimina primero los casos NETTERM-FMT del residente indicado.',
        )

    def handle(self, *args, **options):
        try:
            residente = User.objects.get(username=options['residente'])
        except User.DoesNotExist as exc:
            raise CommandError('No existe el residente indicado.') from exc

        try:
            revisor = User.objects.get(username=options['revisor'])
        except User.DoesNotExist as exc:
            raise CommandError('No existe el revisor indicado.') from exc

        prefijo = 'NETTERM-FMT-'
        if options['limpiar']:
            eliminados, _ = Preinforme.objects.filter(
                residente=residente,
                numero_estudio__startswith=prefijo,
            ).delete()
            self.stdout.write(f'Eliminados: {eliminados}')

        tipo, _ = TipoEstudio.objects.get_or_create(nombre='TC prueba formato NetTerm')
        region, _ = Region.objects.get_or_create(nombre='Región prueba formato NetTerm')
        ahora = timezone.now()

        casos = [
            {
                'sufijo': '001-GUIONES',
                'estado': 'finalizado',
                'html': (
                    '<p><strong>TITULO CON ESPACIO</strong></p>'
                    '<p>&nbsp;</p><p>------</p>'
                    '<p>Primer parrafo del cuerpo con acentos: lesión y corazón.</p>'
                    '<p>------</p><p><strong>CONCLUSION</strong></p>'
                    '<p>Hallazgos sin alteraciones.</p>'
                ),
            },
            {
                'sufijo': '002-HR',
                'estado': 'finalizado',
                'html': (
                    '<p><strong>SEPARADOR HORIZONTAL</strong></p><hr>'
                    '<p>Este caso usa una etiqueta HR que debe copiarse como guiones.</p>'
                ),
            },
            {
                'sufijo': '003-DOBLE-SALTO',
                'estado': 'finalizado',
                'html': (
                    '<p><strong>ENCABEZADO</strong><br><br>'
                    'El cuerpo debe comenzar luego de una linea vacia.</p>'
                ),
            },
            {
                'sufijo': '004-EN-REVISION',
                'estado': 'en_revision',
                'html': (
                    '<p><strong>CASO EDITABLE NETTERM</strong></p>'
                    '<p>&nbsp;</p><p>------</p>'
                    '<p>Modifique este texto y pruebe copiar antes de finalizar.</p>'
                ),
            },
        ]

        for caso in casos:
            numero = prefijo + caso['sufijo']
            estado = caso['estado']
            preinforme, _ = Preinforme.objects.update_or_create(
                numero_estudio=numero,
                defaults={
                    'residente': residente,
                    'tipo_estudio': tipo,
                    'region': region,
                    'sistema_destino': 'netterm',
                    'apellido_paciente': 'Prueba',
                    'nombre_paciente': caso['sufijo'],
                    'dni_paciente': '',
                    'informe_html': caso['html'],
                    'estado': estado,
                    'revisor': revisor,
                    'fecha_envio_revision': ahora,
                    'fecha_inicio_revision': ahora,
                    'fecha_finalizacion': ahora if estado == 'finalizado' else None,
                },
            )
            RevisionPreinforme.objects.update_or_create(
                preinforme=preinforme,
                defaults={
                    'revisor': revisor,
                    'informe_residente_snapshot': caso['html'],
                    'informe_final_html': caso['html'],
                    'comentarios_generales': 'Caso local para validar formato NetTerm.',
                },
            )
            self.stdout.write(self.style.SUCCESS(f'{numero} · {estado}'))

        self.stdout.write(self.style.SUCCESS(
            f'Cargados {len(casos)} casos para {residente.username}; '
            f'revisor: {revisor.username}.'
        ))
