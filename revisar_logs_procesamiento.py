from pedidos_estudios.models import LogProcesamientoEmail
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("LOGS DE PROCESAMIENTO DE EMAILS - ÚLTIMAS 24 HORAS")
print("=" * 80)

# Últimas 24 horas
hace_24h = timezone.now() - timedelta(hours=24)

logs_query = LogProcesamientoEmail.objects.filter(
    fecha_procesamiento__gte=hace_24h
).order_by('-fecha_procesamiento')

# Agrupar por resultado (antes de slice)
duplicados = logs_query.filter(resultado='DUPLICADO')
exitosos = logs_query.filter(resultado__in=['EXITO', 'MULTIPLES'])
errores = logs_query.filter(resultado='ERROR')

# Ahora sí, obtener los logs
logs = logs_query[:20]

if logs:
    print(f"\nEncontrados {len(logs)} logs recientes (últimos 20):\n")
    
    print(f"📊 RESUMEN:")
    print(f"   ✅ Exitosos: {exitosos.count()}")
    print(f"   🔁 Duplicados: {duplicados.count()}")
    print(f"   ❌ Errores: {errores.count()}")
    
    if duplicados.exists():
        print(f"\n{'='*80}")
        print(f"🔁 DUPLICADOS DETECTADOS ({duplicados.count()}):")
        print(f"{'='*80}")
        for log in duplicados:
            fecha_local = timezone.localtime(log.fecha_procesamiento)
            print(f"\n📧 {log.email_asunto}")
            print(f"   Fecha: {fecha_local.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"   Remitente: {log.email_remitente}")
            print(f"   Message ID: {log.email_message_id}")
            print(f"   Mensaje: {log.mensaje}")
    
    if exitosos.exists():
        print(f"\n{'='*80}")
        print(f"✅ ÚLTIMOS PROCESADOS EXITOSAMENTE (últimos 5):")
        print(f"{'='*80}")
        for log in exitosos[:5]:
            fecha_local = timezone.localtime(log.fecha_procesamiento)
            print(f"\n📧 {log.email_asunto}")
            print(f"   Fecha: {fecha_local.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"   Resultado: {log.resultado}")
            if log.pedido_creado:
                print(f"   Pedido creado: #{log.pedido_creado.id} - {log.pedido_creado.paciente.nombre_completo}")
    
    if errores.exists():
        print(f"\n{'='*80}")
        print(f"❌ ERRORES RECIENTES:")
        print(f"{'='*80}")
        for log in errores:
            fecha_local = timezone.localtime(log.fecha_procesamiento)
            print(f"\n📧 {log.email_asunto}")
            print(f"   Fecha: {fecha_local.strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"   Mensaje: {log.mensaje}")
            if log.errores:
                errores_str = str(log.errores)[:200]
                print(f"   Errores: {errores_str}")
else:
    print("\n⚠️  No se encontraron logs en las últimas 24 horas")

print("\n" + "=" * 80)
