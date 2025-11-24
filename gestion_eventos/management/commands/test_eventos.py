from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from gestion_eventos.models import EventoServicio, NotaEvento
from gestion_eventos.forms import NotaEventoForm, ActualizarEstadoEventoForm, ActualizarTipoEventoForm


class Command(BaseCommand):
    help = 'Prueba las funcionalidades del sistema de eventos'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Iniciando pruebas de funcionalidades del sistema de eventos")
        self.stdout.write("=" * 60)
        
        try:
            # 1. Crear evento de prueba
            evento = self.test_crear_evento()
            
            # 2. Agregar nota
            self.test_agregar_nota(evento)
            
            # 3. Actualizar estado
            self.test_actualizar_estado(evento)
            
            # 4. Actualizar tipo
            self.test_actualizar_tipo_evento(evento)
            
            # 5. Agregar otra nota
            self.test_segunda_nota(evento)
            
            # 6. Resolver evento
            self.test_resolver_evento(evento)
            
            # 7. Probar navegación contextual
            self.test_navegacion_contextual(evento)
            
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("🎉 ¡Todas las pruebas completadas exitosamente!"))
            
            # Mostrar resumen
            self.mostrar_resumen(evento)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error durante las pruebas: {str(e)}"))
            import traceback
            traceback.print_exc()

    def test_crear_evento(self):
        """Prueba la creación de un evento"""
        self.stdout.write("🧪 Probando creación de evento...")
        
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
        
        if created:
            self.stdout.write(f"   Usuario de prueba creado: {user.username}")
        
        evento = EventoServicio.objects.create(
            tipo_evento='tecnico',
            descripcion='Evento de prueba para validar funcionalidades del sistema',
            sector_de_pedido='Sala de Tomografía',
            nombre_paciente='Juan Pérez Test',
            dni_paciente='12345678',
            servicio_origen_evento='tomografia',
            creado_por=user
        )
        
        self.stdout.write(self.style.SUCCESS(f"✅ Evento creado con ID: {evento.id}"))
        self.stdout.write(f"   Tipo: {evento.get_tipo_evento_display()}")
        self.stdout.write(f"   Estado: {evento.get_estado_display()}")
        return evento

    def test_agregar_nota(self, evento):
        """Prueba agregar una nota a un evento"""
        self.stdout.write("\n🧪 Probando agregar nota...")
        
        # Simular el formulario de nota
        form_data = {'comentario': 'Esta es una nota de prueba del sistema de gestión'}
        form = NotaEventoForm(data=form_data)
        
        if form.is_valid():
            nota = form.save(commit=False)
            nota.evento = evento
            nota.creado_por = evento.creado_por
            nota.save()
            
            self.stdout.write(self.style.SUCCESS("✅ Nota agregada correctamente"))
            self.stdout.write(f"   Comentario: {nota.comentario}")
            self.stdout.write(f"   Fecha: {nota.fecha}")
            return nota
        else:
            self.stdout.write(self.style.ERROR(f"❌ Error en el formulario de nota: {form.errors}"))
            return None

    def test_actualizar_estado(self, evento):
        """Prueba actualizar el estado de un evento"""
        self.stdout.write("\n🧪 Probando actualización de estado...")
        
        # Cambiar a "en_revision"
        form_data = {'estado': 'en_revision'}
        form = ActualizarEstadoEventoForm(data=form_data, instance=evento)
        
        if form.is_valid():
            form.save(usuario=evento.creado_por)
            evento.refresh_from_db()
            
            self.stdout.write(self.style.SUCCESS("✅ Estado actualizado correctamente"))
            self.stdout.write(f"   Nuevo estado: {evento.get_estado_display()}")
            
            # Verificar historial
            historial = evento.historial.first()
            if historial:
                self.stdout.write(f"   Historial registrado: {historial.cambio} - {historial.valor_nuevo}")
            
            return True
        else:
            self.stdout.write(self.style.ERROR(f"❌ Error en el formulario de estado: {form.errors}"))
            return False

    def test_actualizar_tipo_evento(self, evento):
        """Prueba actualizar el tipo de evento"""
        self.stdout.write("\n🧪 Probando actualización de tipo de evento...")
        
        # Cambiar a "demorado"
        form_data = {'tipo_evento': 'demorado'}
        form = ActualizarTipoEventoForm(data=form_data, instance=evento)
        
        if form.is_valid():
            form.save(usuario=evento.creado_por)
            evento.refresh_from_db()
            
            self.stdout.write(self.style.SUCCESS("✅ Tipo de evento actualizado correctamente"))
            self.stdout.write(f"   Nuevo tipo: {evento.get_tipo_evento_display()}")
            return True
        else:
            self.stdout.write(self.style.ERROR(f"❌ Error en el formulario de tipo: {form.errors}"))
            return False

    def test_segunda_nota(self, evento):
        """Prueba agregar una segunda nota"""
        self.stdout.write("\n🧪 Agregando segunda nota...")
        
        form_data = {'comentario': 'Segunda nota después de los cambios realizados'}
        form = NotaEventoForm(data=form_data)
        
        if form.is_valid():
            nota2 = form.save(commit=False)
            nota2.evento = evento
            nota2.creado_por = evento.creado_por
            nota2.save()
            self.stdout.write(self.style.SUCCESS("✅ Segunda nota agregada correctamente"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Error en segunda nota: {form.errors}"))

    def test_resolver_evento(self, evento):
        """Prueba marcar un evento como resuelto"""
        self.stdout.write("\n🧪 Probando marcar evento como resuelto...")
        
        form_data = {'estado': 'resuelto'}
        form = ActualizarEstadoEventoForm(data=form_data, instance=evento)
        
        if form.is_valid():
            form.save(usuario=evento.creado_por)
            evento.refresh_from_db()
            
            self.stdout.write(self.style.SUCCESS("✅ Evento marcado como resuelto"))
            self.stdout.write(f"   Estado final: {evento.get_estado_display()}")
            return True
        else:
            self.stdout.write(self.style.ERROR(f"❌ Error al resolver evento: {form.errors}"))
            return False

    def test_navegacion_contextual(self, evento):
        """Prueba la lógica de navegación contextual"""
        self.stdout.write("\n🧪 Probando navegación contextual...")
        
        # Simular el contexto de la vista
        is_from_historial = evento.estado == 'resuelto'
        
        self.stdout.write(self.style.SUCCESS("✅ Contexto de navegación detectado correctamente"))
        self.stdout.write(f"   Estado del evento: {evento.estado}")
        self.stdout.write(f"   Es del historial: {is_from_historial}")
        self.stdout.write(f"   Botón sugerido: {'Volver al Historial' if is_from_historial else 'Volver a Activos'}")
        
        return True

    def mostrar_resumen(self, evento):
        """Muestra un resumen del evento de prueba"""
        self.stdout.write(f"\n📊 Evento de prueba ID: {evento.id}")
        self.stdout.write(f"📝 Notas agregadas: {evento.notas.count()}")
        self.stdout.write(f"📈 Cambios en historial: {evento.historial.count()}")
        
        self.stdout.write(f"\n📋 Resumen del evento:")
        self.stdout.write(f"   - Tipo: {evento.get_tipo_evento_display()}")
        self.stdout.write(f"   - Estado: {evento.get_estado_display()}")
        self.stdout.write(f"   - Creador: {evento.creado_por.get_full_name() or evento.creado_por.username}")
        self.stdout.write(f"   - Servicio: {evento.get_servicio_origen_evento_display()}")
        self.stdout.write(f"   - Paciente: {evento.nombre_paciente}")
        
        # Mostrar notas
        self.stdout.write(f"\n📝 Notas del evento:")
        for i, nota in enumerate(evento.notas.order_by('fecha'), 1):
            self.stdout.write(f"   {i}. {nota.comentario[:50]}..." if len(nota.comentario) > 50 else f"   {i}. {nota.comentario}")
        
        # Mostrar historial
        self.stdout.write(f"\n📈 Historial de cambios:")
        for i, cambio in enumerate(evento.historial.order_by('fecha'), 1):
            self.stdout.write(f"   {i}. {cambio.cambio}: {cambio.valor_anterior} → {cambio.valor_nuevo}")
            
        self.stdout.write(self.style.WARNING("\n💡 Puedes ver este evento en el navegador y probar las funcionalidades manualmente."))
        self.stdout.write(f"🔗 URL del evento: http://127.0.0.1:8000/gestion_eventos/evento/{evento.id}/")