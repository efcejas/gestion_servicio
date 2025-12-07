"""
Script para poblar el diccionario médico con términos comunes de ortopedia/traumatología
Ejecutar: python manage.py runscript poblar_diccionario_medico
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from dictado_informes.models import TerminoMedico, CategoriaTerminoMedico


def run():
    """Poblar diccionario con términos médicos comunes"""
    
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
            'incorrecto': 'menisco',
            'correcto': 'menisco',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Estructura fibrocartilaginosa de la rodilla'
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
            'incorrecto': 'femoral',
            'correcto': 'femoral',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Relativo al fémur'
        },
        {
            'incorrecto': 'tibial',
            'correcto': 'tibial',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Relativo a la tibia'
        },
        {
            'incorrecto': 'patelar',
            'correcto': 'patelar',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Relativo a la rótula'
        },
        {
            'incorrecto': 'rotuliano',
            'correcto': 'rotuliano',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Relativo a la rótula'
        },
        {
            'incorrecto': 'edema',
            'correcto': 'edema',
            'categoria': CategoriaTerminoMedico.RADIOLOGIA,
            'notas': 'Acumulación de líquido'
        },
        {
            'incorrecto': 'derrame',
            'correcto': 'derrame',
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
            'incorrecto': 'osteofitos',
            'correcto': 'osteofitos',
            'categoria': CategoriaTerminoMedico.RADIOLOGIA,
            'notas': 'Formaciones óseas anormales'
        },
        {
            'incorrecto': 'quiste',
            'correcto': 'quiste',
            'categoria': CategoriaTerminoMedico.RADIOLOGIA,
            'notas': 'Lesión quística'
        },
        {
            'incorrecto': 'baker',
            'correcto': 'Baker',
            'categoria': CategoriaTerminoMedico.ORTOPEDIA,
            'notas': 'Quiste de Baker en hueco poplíteo'
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
        {
            'incorrecto': 'isointenso',
            'correcto': 'isointenso',
            'categoria': CategoriaTerminoMedico.RADIOLOGIA,
            'notas': 'Intensidad de señal similar'
        },
        
        # LIGAMENTOS
        {
            'incorrecto': 'lca',
            'correcto': 'LCA',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Ligamento cruzado anterior'
        },
        {
            'incorrecto': 'lcp',
            'correcto': 'LCP',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Ligamento cruzado posterior'
        },
        {
            'incorrecto': 'lcm',
            'correcto': 'LCM',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Ligamento colateral medial'
        },
        {
            'incorrecto': 'lcl',
            'correcto': 'LCL',
            'categoria': CategoriaTerminoMedico.ANATOMIA,
            'notas': 'Ligamento colateral lateral'
        },
    ]
    
    creados = 0
    actualizados = 0
    
    print("\n🏥 Poblando diccionario médico...\n")
    
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
            print(f"✅ Creado: '{termino_data['incorrecto']}' → '{termino_data['correcto']}'")
        else:
            actualizados += 1
            print(f"🔄 Actualizado: '{termino_data['incorrecto']}' → '{termino_data['correcto']}'")
    
    print(f"\n📊 Resumen:")
    print(f"   • Términos creados: {creados}")
    print(f"   • Términos actualizados: {actualizados}")
    print(f"   • Total en diccionario: {TerminoMedico.objects.count()}")
    print("\n✅ Diccionario médico poblado exitosamente!")


if __name__ == '__main__':
    run()
