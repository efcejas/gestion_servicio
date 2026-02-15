from pedidos_estudios.models import PedidoEstudio
from pedidos_estudios.services.notificador import notificar_pedido_nuevo
from django.utils import timezone

# Obtener el último pedido
p = PedidoEstudio.objects.last()

print(f"Pedido #{p.id}: {p.paciente.nombre_completo}")
print(f"Fecha solicitud (UTC): {p.fecha_solicitud}")
print(f"Fecha solicitud (Local): {timezone.localtime(p.fecha_solicitud)}")
print(f"Fecha local formateada: {timezone.localtime(p.fecha_solicitud).strftime('%d/%m/%Y %H:%M')}")
print("\nReenviando notificación...")

resultado = notificar_pedido_nuevo(p)

if resultado:
    print("✅ Notificación enviada correctamente")
    print(f"Revisa tu email para verificar que ahora muestra la hora local: {timezone.localtime(p.fecha_solicitud).strftime('%H:%M')}")
else:
    print("❌ Error al enviar notificación")
