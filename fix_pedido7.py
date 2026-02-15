from pedidos_estudios.models import PedidoEstudio, TipoEstudio

# Ver pedido 7
try:
    p7 = PedidoEstudio.objects.get(id=7)
    print(f"Pedido #7: {p7.paciente.nombre_completo}")
    print(f"Tipo: {p7.tipo_estudio.nombre if p7.tipo_estudio else 'Sin tipo'}")
    print(f"Desc: {p7.descripcion_estudio}")
    
    # Corregir si es necesario
    if 'venoso' in p7.descripcion_estudio.lower() and 'arterial' in (p7.tipo_estudio.nombre.lower() if p7.tipo_estudio else ''):
        tipo_correcto = TipoEstudio.objects.get(nombre='Ecodoppler Venoso de MMII')
        p7.tipo_estudio = tipo_correcto
        p7.save()
        print(f"✅ CORREGIDO a: {tipo_correcto.nombre}")
    else:
        print("✓ No requiere corrección")
except PedidoEstudio.DoesNotExist:
    print("Pedido #7 no encontrado")
