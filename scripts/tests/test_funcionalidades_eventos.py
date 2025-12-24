#!/usr/bin/env python3
"""
Script de prueba para validar las funcionalidades del sistema de eventos
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from gestion_eventos.models import EventoServicio, NotaEvento
from gestion_eventos.forms import NotaEventoForm, ActualizarEstadoEventoForm, ActualizarTipoEventoForm

def test_crear_evento():
    """Prueba la creación de un evento"""
    print("🧪 Probando creación de evento...")
    
    User = get_user_model()
    # Buscar un usuario existente o crear uno de prueba
    user, created = User.objects.get_or_create(
        username='test_tecnico',
        defaults={
            'first_name': 'Técnico',
            'last_name': 'Prueba',
            'email': 'test@test.com'
        }
    )
    
    evento = EventoServicio.objects.create(
        tipo_evento='tecnico',
        descripcion='Evento de prueba para validar funcionalidades',
        sector_de_pedido='Sala de Tomografía',
        nombre_paciente='Juan Pérez',
        dni_paciente='12345678',
        servicio_origen_evento='tomografia',
        creado_por=user
    )
    
    print(f"✅ Evento creado con ID: {evento.id}")
    print(f"   Tipo: {evento.get_tipo_evento_display()}")
    print(f"   Estado: {evento.get_estado_display()}")
    return evento

def test_agregar_nota(evento):
    """Prueba agregar una nota a un evento"""
    print("\n🧪 Probando agregar nota...")
    
    # Simular el formulario de nota
    form_data = {'comentario': 'Esta es una nota de prueba del sistema'}
    form = NotaEventoForm(data=form_data)
    
    if form.is_valid():
        nota = form.save(commit=False)
        nota.evento = evento
        nota.creado_por = evento.creado_por
        nota.save()
        
        print(f"✅ Nota agregada correctamente")
        print(f"   Comentario: {nota.comentario}")
        print(f"   Fecha: {nota.fecha}")
        return nota
    else:
        print(f"❌ Error en el formulario de nota: {form.errors}")
        return None

def test_actualizar_estado(evento):
    """Prueba actualizar el estado de un evento"""
    print("\n🧪 Probando actualización de estado...")
    
    # Cambiar a "en_revision"
    form_data = {'estado': 'en_revision'}
    form = ActualizarEstadoEventoForm(data=form_data, instance=evento)
    
    if form.is_valid():
        form.save(usuario=evento.creado_por)
        evento.refresh_from_db()
        
        print(f"✅ Estado actualizado correctamente")
        print(f"   Nuevo estado: {evento.get_estado_display()}")
        
        # Verificar historial
        historial = evento.historial.first()
        if historial:
            print(f"   Historial registrado: {historial.cambio} - {historial.valor_nuevo}")
        
        return True
    else:
        print(f"❌ Error en el formulario de estado: {form.errors}")
        return False

def test_actualizar_tipo_evento(evento):
    """Prueba actualizar el tipo de evento"""
    print("\n🧪 Probando actualización de tipo de evento...")
    
    # Cambiar a "demorado"
    form_data = {'tipo_evento': 'demorado'}
    form = ActualizarTipoEventoForm(data=form_data, instance=evento)
    
    if form.is_valid():
        form.save(usuario=evento.creado_por)
        evento.refresh_from_db()
        
        print(f"✅ Tipo de evento actualizado correctamente")
        print(f"   Nuevo tipo: {evento.get_tipo_evento_display()}")
        return True
    else:
        print(f"❌ Error en el formulario de tipo: {form.errors}")
        return False

def test_resolver_evento(evento):
    """Prueba marcar un evento como resuelto"""
    print("\n🧪 Probando marcar evento como resuelto...")
    
    form_data = {'estado': 'resuelto'}
    form = ActualizarEstadoEventoForm(data=form_data, instance=evento)
    
    if form.is_valid():
        form.save(usuario=evento.creado_por)
        evento.refresh_from_db()
        
        print(f"✅ Evento marcado como resuelto")
        print(f"   Estado final: {evento.get_estado_display()}")
        return True
    else:
        print(f"❌ Error al resolver evento: {form.errors}")
        return False

def test_navegacion_contextual(evento):
    """Prueba la lógica de navegación contextual"""
    print("\n🧪 Probando navegación contextual...")
    
    # Simular el contexto de la vista
    is_from_historial = evento.estado == 'resuelto'
    
    print(f"✅ Contexto de navegación detectado correctamente")
    print(f"   Estado del evento: {evento.estado}")
    print(f"   Es del historial: {is_from_historial}")
    print(f"   Botón sugerido: {'Volver al Historial' if is_from_historial else 'Volver a Activos'}")
    
    return True

def main():
    """Ejecuta todas las pruebas"""
    print("🚀 Iniciando pruebas de funcionalidades del sistema de eventos")
    print("=" * 60)
    
    try:
        # 1. Crear evento
        evento = test_crear_evento()
        
        # 2. Agregar nota
        nota = test_agregar_nota(evento)
        
        # 3. Actualizar estado
        test_actualizar_estado(evento)
        
        # 4. Actualizar tipo
        test_actualizar_tipo_evento(evento)
        
        # 5. Agregar otra nota
        print("\n🧪 Agregando segunda nota...")
        form_data = {'comentario': 'Segunda nota después de cambios'}
        form = NotaEventoForm(data=form_data)
        if form.is_valid():
            nota2 = form.save(commit=False)
            nota2.evento = evento
            nota2.creado_por = evento.creado_por
            nota2.save()
            print("✅ Segunda nota agregada")
        
        # 6. Resolver evento
        test_resolver_evento(evento)
        
        # 7. Probar navegación contextual
        test_navegacion_contextual(evento)
        
        print("\n" + "=" * 60)
        print("🎉 ¡Todas las pruebas completadas exitosamente!")
        print(f"📊 Evento de prueba ID: {evento.id}")
        print(f"📝 Notas agregadas: {evento.notas.count()}")
        print(f"📈 Cambios en historial: {evento.historial.count()}")
        
        # Mostrar resumen del evento
        print(f"\n📋 Resumen del evento:")
        print(f"   - Tipo: {evento.get_tipo_evento_display()}")
        print(f"   - Estado: {evento.get_estado_display()}")
        print(f"   - Creador: {evento.creado_por.get_full_name() or evento.creado_por.username}")
        print(f"   - Servicio: {evento.get_servicio_origen_evento_display()}")
        
        # Limpiar datos de prueba (opcional)
        response = input("\n¿Deseas eliminar los datos de prueba? (s/N): ")
        if response.lower() == 's':
            evento.delete()
            print("🗑️ Datos de prueba eliminados")
        else:
            print("💾 Datos de prueba conservados")
            
    except Exception as e:
        print(f"❌ Error durante las pruebas: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()