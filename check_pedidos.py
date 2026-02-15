from pedidos_estudios.models import PedidoEstudio, TipoEstudio

# Listar últimos pedidos
print("Últimos pedidos:")
print("-" * 80)
pedidos = PedidoEstudio.objects.all().order_by('-id')[:10]

for p in pedidos:
    tipo = p.tipo_estudio.nombre if p.tipo_estudio else "Sin tipo"
    print(f"#{p.id}: {p.paciente.nombre_completo}")
    print(f"   Tipo: {tipo}")
    print(f"   Desc: {p.descripcion_estudio[:60]}")
    print()

# Buscar pedidos con "venoso" en descripción pero tipo "Arterial"
print("\n" + "=" * 80)
print("Buscando inconsistencias...")
print("=" * 80 + "\n")

pedidos_problema = PedidoEstudio.objects.filter(
    descripcion_estudio__icontains='venoso',
    tipo_estudio__nombre__icontains='Arterial'
)

if pedidos_problema.exists():
    print(f"Encontrados {pedidos_problema.count()} pedidos con inconsistencia:")
    tipo_correcto = TipoEstudio.objects.filter(nombre__icontains='Venoso de MMII').first()
    
    for p in pedidos_problema:
        print(f"\n#{p.id}: {p.paciente.nombre_completo}")
        print(f"   Tipo actual: {p.tipo_estudio.nombre}")
        print(f"   Descripción: {p.descripcion_estudio}")
        
        if tipo_correcto:
            p.tipo_estudio = tipo_correcto
            p.save()
            print(f"   ✅ CORREGIDO a: {tipo_correcto.nombre}")
else:
    print("No se encontraron inconsistencias de venoso/arterial")

# Buscar otros problemas
pedidos_problema2 = PedidoEstudio.objects.filter(
    descripcion_estudio__icontains='arterial',
    tipo_estudio__nombre__icontains='Venoso'
)

if pedidos_problema2.exists():
    print(f"\n\nEncontrados {pedidos_problema2.count()} pedidos con inconsistencia inversa:")
    tipo_correcto = TipoEstudio.objects.filter(nombre__icontains='Arterial de MMII').first()
    
    for p in pedidos_problema2:
        print(f"\n#{p.id}: {p.paciente.nombre_completo}")
        print(f"   Tipo actual: {p.tipo_estudio.nombre}")
        print(f"   Descripción: {p.descripcion_estudio}")
        
        if tipo_correcto:
            p.tipo_estudio = tipo_correcto
            p.save()
            print(f"   ✅ CORREGIDO a: {tipo_correcto.nombre}")
