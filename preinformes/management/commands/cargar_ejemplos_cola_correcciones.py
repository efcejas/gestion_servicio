from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from preinformes.models import Preinforme, Region, RevisionPreinforme, TipoEstudio


class Command(BaseCommand):
    help = 'Carga ejemplos locales para probar la cola de correcciones de un residente.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--limpiar', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            residente = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError('No existe el usuario indicado.') from exc

        prefijo = 'DEMO-COLA-'
        if options['limpiar']:
            borrados, _ = Preinforme.objects.filter(
                residente=residente, numero_estudio__startswith=prefijo
            ).delete()
            self.stdout.write(self.style.SUCCESS(f'Registros eliminados: {borrados}'))
            return

        staff = User.objects.filter(rol='medico_staff').order_by('pk').first()
        tipos = list(TipoEstudio.objects.order_by('pk'))
        regiones = list(Region.objects.order_by('pk'))
        if not staff or len(tipos) < 2 or len(regiones) < 2:
            raise CommandError('Faltan staff, tipos de estudio o regiones para crear ejemplos.')
        tc = TipoEstudio.objects.filter(pk=5).first() or tipos[-1]
        rm = TipoEstudio.objects.filter(pk=4).first() or tipos[0]
        torax = Region.objects.filter(pk=3).first() or regiones[-1]
        abdomen = Region.objects.filter(pk=1).first() or regiones[0]
        ahora = timezone.now()

        finales = [
            ('001', tc, torax, 7, None,
             '<p>TC DE TÓRAX</p><p>Opacidad redondeada basal derecha.</p>',
             '<p><strong>TC DE TÓRAX</strong></p><p>Consolidación pulmonar redondeada en el lóbulo inferior derecho, con broncograma aéreo.</p><p><strong>CONCLUSIÓN:</strong> Hallazgos compatibles con neumonía redonda.</p>',
             'Se agregó localización y broncograma aéreo.', 8),
            ('002', tc, abdomen, 5, None,
             '<p>Engrosamiento parietal del colon ascendente.</p>',
             '<p><strong>TC DE ABDOMEN</strong></p><p>Engrosamiento parietal irregular y estenosante del colon ascendente, asociado a adenopatías regionales.</p><p><strong>CONCLUSIÓN:</strong> Hallazgos sospechosos de neoplasia de colon.</p>',
             'Describir longitud, morfología y adenopatías asociadas.', 7),
            ('003', rm, abdomen, 3, None,
             '<p>Lesión hepática hiperintensa en T2.</p>',
             '<p><strong>RM DE ABDOMEN</strong></p><p>Lesión hepática de 18 mm, hiperintensa en T2, con realce periférico discontinuo y llenado centrípeto.</p><p><strong>CONCLUSIÓN:</strong> Hemangioma hepático.</p>',
             'El patrón dinámico permite sostener la conclusión.', 9),
            ('004', tc, torax, 10, ahora - timedelta(days=9),
             '<p>Sin consolidaciones.</p>',
             '<p><strong>TC DE TÓRAX</strong></p><p>Sin consolidaciones ni derrame pleural. Granuloma calcificado residual.</p>',
             'Caso ya marcado como revisado para comparar el estado visual.', 10),
        ]

        with transaction.atomic():
            Preinforme.objects.filter(
                residente=residente, numero_estudio__startswith=prefijo
            ).delete()
            for sufijo, tipo, region, dias, visto, original, final, comentario, puntaje in finales:
                pre = Preinforme.objects.create(
                    residente=residente, numero_estudio=prefijo + sufijo,
                    tipo_estudio=tipo, region=region, sistema_destino='eges',
                    apellido_paciente='PACIENTE', nombre_paciente='DEMOSTRACIÓN',
                    informe_html=original, estado='finalizado', revisor=staff,
                    fecha_envio_revision=ahora - timedelta(days=dias + 1),
                    fecha_inicio_revision=ahora - timedelta(days=dias, hours=2),
                    fecha_finalizacion=ahora - timedelta(days=dias),
                    fecha_correccion_vista=visto,
                )
                RevisionPreinforme.objects.create(
                    preinforme=pre, revisor=staff,
                    informe_residente_snapshot=original, informe_final_html=final,
                    comentarios_generales=comentario, puntuacion=puntaje,
                )

            extras = [
                ('005', 'en_revision', tc, torax, '<p>Nódulo pulmonar en evaluación.</p>'),
                ('006', 'pendiente_revision', tc, abdomen, '<p>Dolor abdominal. Sin hallazgos agudos.</p>'),
                ('007', 'borrador', rm, abdomen, '<p>Borrador de estudio hepático.</p>'),
            ]
            for sufijo, estado, tipo, region, original in extras:
                pre = Preinforme.objects.create(
                    residente=residente, numero_estudio=prefijo + sufijo,
                    tipo_estudio=tipo, region=region, sistema_destino='eges',
                    apellido_paciente='PACIENTE', nombre_paciente='DEMOSTRACIÓN',
                    informe_html=original, estado=estado,
                    revisor=staff if estado == 'en_revision' else None,
                    fecha_envio_revision=ahora - timedelta(days=1) if estado != 'borrador' else None,
                    fecha_inicio_revision=ahora - timedelta(hours=5) if estado == 'en_revision' else None,
                )
                if estado == 'en_revision':
                    RevisionPreinforme.objects.create(
                        preinforme=pre, revisor=staff,
                        informe_residente_snapshot=original, informe_final_html=original,
                    )

        self.stdout.write(self.style.SUCCESS(
            f'Creados 7 ejemplos para {residente.username}: 3 correcciones nuevas, '
            '1 revisada, 1 en revisión, 1 pendiente y 1 borrador.'
        ))
