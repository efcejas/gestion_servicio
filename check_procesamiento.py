from pedidos_estudios.models import LogProcesamientoEmail
from django.utils import timezone
from datetime import timedelta

# Ver últimos 10 logs
logs = LogProcesamientoEmail.objects.order_by('-fecha_procesamiento')[:10]

print("=" * 80)
print("ÚLTIMOS 10 PROCESAMIENTOS DE EMAILS")
print("=" * 80)

if not logs.exists():
    print("No hay logs de procesamiento registrados.")
else:
    for log in logs:
        print(f"\n📧 Email ID: {log.email_message_id}")
        print(f"   Fecha: {timezone.localtime(log.fecha_procesamiento).strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"   Asunto: {log.email_asunto}")
        print(f"   Remitente: {log.email_remitente}")
        print(f"   Resultado: {log.get_resultado_display()}")
        
        if log.mensaje_error:
            print(f"   ❌ Error: {log.mensaje_error[:100]}")
        
        if log.pedido:
            print(f"   ✅ Pedido creado: #{log.pedido.id} - {log.pedido.paciente.nombre_completo}")

print("\n" + "=" * 80)
print("EMAILS NO LEÍDOS EN GMAIL")
print("=" * 80)

# Intentar obtener emails no leídos
try:
    from pedidos_estudios.services.gmail_service import obtener_servicio_gmail
    
    servicio = obtener_servicio_gmail()
    if servicio:
        resultados = servicio.users().messages().list(
            userId='me',
            q='is:unread',
            maxResults=10
        ).execute()
        
        mensajes = resultados.get('messages', [])
        print(f"\nTotal de emails no leídos: {len(mensajes)}")
        
        if mensajes:
            for msg in mensajes[:5]:
                msg_data = servicio.users().messages().get(
                    userId='me', 
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()
                
                headers = {h['name']: h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
                print(f"\n   📨 {headers.get('Subject', 'Sin asunto')}")
                print(f"      De: {headers.get('From', 'Desconocido')}")
                print(f"      Fecha: {headers.get('Date', 'Desconocida')}")
        else:
            print("✓ No hay emails sin leer.")
    else:
        print("⚠️ No se pudo conectar con Gmail.")
except Exception as e:
    print(f"❌ Error al consultar Gmail: {e}")
