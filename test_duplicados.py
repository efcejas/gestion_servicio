from pedidos_estudios.models import PedidoEstudio
from pedidos_estudios.services.procesador import ProcesadorPedidos

# Crear instancia del procesador
procesador = ProcesadorPedidos()

print("=" * 80)
print("TEST: Verificación de detección de duplicados")
print("=" * 80)

# Test 1: Email simple con message_id directo
test_message_id_1 = "test-simple-12345"
print(f"\n1. Verificando message_id simple: {test_message_id_1}")
print(f"   ¿Ya procesado?: {procesador._email_ya_procesado(test_message_id_1)}")

# Crear un pedido de prueba con este message_id
if not PedidoEstudio.objects.filter(email_message_id=test_message_id_1).exists():
    print(f"   Creando pedido de prueba...")
    # (En un test real crearías el pedido completo, aquí solo simulamos)
    print(f"   (Simulando creación)")

# Test 2: Email con múltiples estudios base
test_message_id_2 = "test-multiple-67890"
print(f"\n2. Verificando message_id con múltiples estudios: {test_message_id_2}")

# Buscar si existen pedidos con este message_id base
pedidos_con_base = PedidoEstudio.objects.filter(
    email_message_id__startswith=test_message_id_2
)
print(f"   Pedidos encontrados con este base: {pedidos_con_base.count()}")
for p in pedidos_con_base:
    print(f"   - Pedido #{p.id}: {p.email_message_id}")

print(f"   ¿Ya procesado? (con lógica nueva): {procesador._email_ya_procesado(test_message_id_2)}")

# Test 3: Verificar con emails reales de la BD
print(f"\n3. Verificando con emails reales de la BD:")
print("-" * 80)

# Buscar pedidos recientes con sufijos (múltiples estudios)
pedidos_con_sufijos = PedidoEstudio.objects.filter(
    email_message_id__contains="-estudio"
).order_by('-id')[:5]

if pedidos_con_sufijos.exists():
    print(f"   Encontrados {pedidos_con_sufijos.count()} pedidos con sufijos:")
    for p in pedidos_con_sufijos:
        # Extraer el message_id base (sin sufijo)
        message_id_base = p.email_message_id.split('-estudio')[0]
        esta_duplicado = procesador._email_ya_procesado(message_id_base)
        print(f"\n   Pedido #{p.id}:")
        print(f"     email_message_id completo: {p.email_message_id}")
        print(f"     message_id base: {message_id_base}")
        print(f"     ¿Se detectaría como duplicado?: {esta_duplicado}")
        print(f"     Paciente: {p.paciente.nombre_completo}")
else:
    print("   No se encontraron pedidos con sufijos -estudio")

# Test 4: Verificar pedidos sin sufijos
print(f"\n4. Verificando pedidos sin sufijos (emails simples):")
print("-" * 80)

pedidos_sin_sufijos = PedidoEstudio.objects.exclude(
    email_message_id__contains="-estudio"
).exclude(
    email_message_id__isnull=True
).exclude(
    email_message_id=""
).order_by('-id')[:3]

if pedidos_sin_sufijos.exists():
    print(f"   Encontrados {pedidos_sin_sufijos.count()} pedidos sin sufijos:")
    for p in pedidos_sin_sufijos:
        esta_duplicado = procesador._email_ya_procesado(p.email_message_id)
        print(f"\n   Pedido #{p.id}:")
        print(f"     email_message_id: {p.email_message_id}")
        print(f"     ¿Se detectaría como duplicado?: {esta_duplicado}")
        print(f"     Paciente: {p.paciente.nombre_completo}")
else:
    print("   No se encontraron pedidos sin sufijos")

print("\n" + "=" * 80)
print("✅ Test de detección de duplicados completado")
print("=" * 80)
