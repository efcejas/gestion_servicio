"""
Comando de gestión para poblar el diccionario médico
Ejecutar: python manage.py poblar_diccionario
"""
from django.core.management.base import BaseCommand
from dictado_informes.models import TerminoMedico, CategoriaTerminoMedico


class Command(BaseCommand):
    help = 'Pobla el diccionario médico con términos comunes de ortopedia/traumatología'

    def handle(self, *args, **options):
        terminos_iniciales = [
            # ORTOPEDIA - Términos mal transcritos comunes
            {
                'incorrecto': 'con artrosis trick compartimental',
                'correcto': 'gonartrosis tricompartimental',
                'categoria': CategoriaTerminoMedico.ORTOPEDIA,
                'notas': 'Artrosis de rodilla en los tres compartimentos'
            },
            {
                'incorrecto': 'con artrosis',
                'correcto': 'gonartrosis',
                'categoria': CategoriaTerminoMedico.ORTOPEDIA,
                'notas': 'Artrosis de rodilla'
            },
            {
                'incorrecto': 'meniscos de configuración y señal normal',
                'correcto': 'meniscos de configuración y señal normales',
                'categoria': CategoriaTerminoMedico.ANATOMIA,
                'notas': 'Descripción de meniscos sin alteraciones'
            },
            {
                'incorrecto': 'ligamentos cruzados de trayecto y señal normal',
                'correcto': 'ligamentos cruzados de trayecto y señal normales',
                'categoria': CategoriaTerminoMedico.ANATOMIA,
                'notas': 'LCA y LCP sin lesiones'
            },
            {
                'incorrecto': 'meniscopatía',
                'correcto': 'meniscopatía',
                'categoria': CategoriaTerminoMedico.ORTOPEDIA,
                'notas': 'Lesión del menisco'
            },
            {
                'incorrecto': 'condropatía',
                'correcto': 'condropatía',
                'categoria': CategoriaTerminoMedico.ORTOPEDIA,
                'notas': 'Lesión del cartílago articular'
            },
            {
                'incorrecto': 'edema óseo',
                'correcto': 'edema óseo',
                'categoria': CategoriaTerminoMedico.RADIOLOGIA,
                'notas': 'Acumulación de líquido en hueso'
            },
            {
                'incorrecto': 'derrame articular',
                'correcto': 'derrame articular',
                'categoria': CategoriaTerminoMedico.RADIOLOGIA,
                'notas': 'Acumulación de líquido en articulación'
            },
            {
                'incorrecto': 'sinovitis',
                'correcto': 'sinovitis',
                'categoria': CategoriaTerminoMedico.ORTOPEDIA,
                'notas': 'Inflamación de la membrana sinovial'
            },
            {
                'incorrecto': 'osteofitos marginales',
                'correcto': 'osteofitos marginales',
                'categoria': CategoriaTerminoMedico.RADIOLOGIA,
                'notas': 'Formaciones óseas anormales en márgenes articulares'
            },
            {
                'incorrecto': 'quiste de baker',
                'correcto': 'quiste de Baker',
                'categoria': CategoriaTerminoMedico.ORTOPEDIA,
                'notas': 'Quiste en hueco poplíteo'
            },
            
            # TÉRMINOS DE DESCRIPCIÓN RADIOLÓGICA
            {
                'incorrecto': 'hipotenso',
                'correcto': 'hipointenso',
                'categoria': CategoriaTerminoMedico.RADIOLOGIA,
                'notas': 'Baja intensidad de señal en RM'
            },
            {
                'incorrecto': 'hiperintenso',
                'correcto': 'hiperintenso',
                'categoria': CategoriaTerminoMedico.RADIOLOGIA,
                'notas': 'Alta intensidad de señal en RM'
            },
            
            # LIGAMENTOS
            {
                'incorrecto': 'ligamento cruzado anterior',
                'correcto': 'ligamento cruzado anterior',
                'categoria': CategoriaTerminoMedico.ANATOMIA,
                'notas': 'LCA'
            },
            {
                'incorrecto': 'ligamento cruzado posterior',
                'correcto': 'ligamento cruzado posterior',
                'categoria': CategoriaTerminoMedico.ANATOMIA,
                'notas': 'LCP'
            },
        ]
        
        creados = 0
        actualizados = 0
        
        self.stdout.write("\n🏥 Poblando diccionario médico...\n")
        
        for termino_data in terminos_iniciales:
            obj, created = TerminoMedico.objects.update_or_create(
                termino_incorrecto=termino_data['incorrecto'].lower(),
                defaults={
                    'termino_correcto': termino_data['correcto'],
                    'categoria': termino_data['categoria'],
                    'notas': termino_data.get('notas', ''),
                    'activo': True
                }
            )
            
            if created:
                creados += 1
                self.stdout.write(self.style.SUCCESS(
                    f"✅ Creado: '{termino_data['incorrecto']}' → '{termino_data['correcto']}'"
                ))
            else:
                actualizados += 1
                self.stdout.write(self.style.WARNING(
                    f"🔄 Actualizado: '{termino_data['incorrecto']}' → '{termino_data['correcto']}'"
                ))
        
        total = TerminoMedico.objects.count()
        
        self.stdout.write("\n📊 Resumen:")
        self.stdout.write(f"   • Términos creados: {creados}")
        self.stdout.write(f"   • Términos actualizados: {actualizados}")
        self.stdout.write(f"   • Total en diccionario: {total}")
        self.stdout.write(self.style.SUCCESS("\n✅ Diccionario médico poblado exitosamente!"))
