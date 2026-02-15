# -*- coding: utf-8 -*-
"""
Script para probar el sistema de notificaciones con tokens.
"""
from pedidos_estudios.models import PedidoEstudio, MedicoGuardia
from pedidos_estudios.services.notificador import NotificadorPedidos

print("\n=== TEST DE NOTIFICACIONES CON TOKENS ===\n")

# Obtener un pedido pendiente
pedido = PedidoEstudio.objects.filter(estado='PENDIENTE').first()

if not pedido:
    print("❌ No hay pedidos pendientes para probar")
else:
    print(f"📋 Pedido de prueba: #{pedido.id}")
    print(f"   Paciente: {pedido.paciente.nombre_completo}")
    print(f"   Estudio: {pedido.tipo_estudio.nombre if pedido.tipo_estudio else 'N/A'}")
    print(f"   Prioridad: {pedido.get_prioridad_display()}")
    print()
    
    # Obtener médicos que recibirán la notificación
    notificador = NotificadorPedidos()
    destinatarios = notificador._obtener_destinatarios(pedido)
    
    print(f"📧 Destinatarios ({len(destinatarios)}):")
    for email in destinatarios:
        medico = MedicoGuardia.objects.filter(email=email).first()
        if not medico:
            medico = MedicoGuardia.objects.filter(usuario__email=email).first()
        
        if medico:
            print(f"   ✓ {email} - {medico.nombre_completo} ({medico.get_especialidad_display()})")
            print(f"     URL: {medico.get_url_acceso()[:60]}...")
        else:
            print(f"   • {email} (sin perfil de guardia)")
    
    print("\n" + "="*70)
    print("⚠️  NOTA: Para enviar realmente el email, descomenta la línea:")
    print("   # notificador.notificar_pedido(pedido)")
    print("="*70)
    
    # Descomentar para enviar realmente
    # resultado = notificador.notificar_pedido(pedido)
    # print(f"\n{'✓' if resultado else '✗'} Resultado: {'Enviado' if resultado else 'Error'}")
    
    # Mostrar HTML de ejemplo (para el primer médico)
    medico_ejemplo = MedicoGuardia.objects.first()
    if medico_ejemplo:
        print("\n=== PREVIEW DEL EMAIL (primer médico) ===\n")
        html = notificador._generar_contenido_html(pedido, medico_ejemplo)
        print(html[:500] + "...")

print("\n✓ Test completado\n")
