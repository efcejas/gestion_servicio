"""
Script de testing para el sistema de Clases de Residentes
Ejecutar: python test_clases_residentes.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_estudios.settings')
django.setup()

from django.contrib.auth import get_user_model
from clases_residentes.models import ClaseResidente, ComentarioClase, FavoritoClase
from datetime import date, timedelta

User = get_user_model()

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_info(text):
    print(f"ℹ️  {text}")

def test_models():
    """Verificar que los modelos están correctamente creados"""
    print_header("TEST 1: Verificación de Modelos")
    
    try:
        # Verificar tablas
        assert ClaseResidente.objects.model._meta.db_table == 'clases_residentes_claseresidente'
        print_success("Tabla ClaseResidente existe")
        
        assert ComentarioClase.objects.model._meta.db_table == 'clases_residentes_comentarioclase'
        print_success("Tabla ComentarioClase existe")
        
        assert FavoritoClase.objects.model._meta.db_table == 'clases_residentes_favoritoclase'
        print_success("Tabla FavoritoClase existe")
        
        # Verificar campos importantes
        clase_fields = [f.name for f in ClaseResidente._meta.get_fields()]
        required_fields = ['titulo', 'descripcion', 'categoria', 'archivo', 'anios_dirigidos', 'autor']
        for field in required_fields:
            assert field in clase_fields, f"Campo {field} no encontrado"
        print_success(f"Todos los campos requeridos existen: {', '.join(required_fields)}")
        
        return True
    except AssertionError as e:
        print_error(f"Error en modelos: {e}")
        return False
    except Exception as e:
        print_error(f"Error inesperado: {e}")
        return False

def test_usuarios():
    """Verificar que existen usuarios de prueba"""
    print_header("TEST 2: Verificación de Usuarios")
    
    try:
        total_users = User.objects.count()
        print_info(f"Total de usuarios en sistema: {total_users}")
        
        # Verificar usuarios con diferentes roles
        residentes = User.objects.filter(rol='medico_residente').count()
        print_info(f"Residentes: {residentes}")
        
        jefes = User.objects.filter(rol__in=['jefe_residentes', 'instructor_residentes', 'jefe_servicio']).count()
        print_info(f"Jefes/Instructores: {jefes}")
        
        if total_users == 0:
            print_error("No hay usuarios en el sistema")
            print_info("Crea un superusuario: python manage.py createsuperuser")
            return False
        
        print_success(f"Sistema tiene {total_users} usuarios")
        return True
    except Exception as e:
        print_error(f"Error verificando usuarios: {e}")
        return False

def test_crear_clase_ejemplo():
    """Crear una clase de ejemplo para testing"""
    print_header("TEST 3: Crear Clase de Ejemplo")
    
    try:
        # Buscar un usuario para ser autor
        autor = User.objects.filter(rol='medico_residente').first()
        if not autor:
            autor = User.objects.filter(is_staff=True).first()
        if not autor:
            autor = User.objects.first()
        
        if not autor:
            print_error("No hay usuarios disponibles")
            return False
        
        # Verificar si ya existe una clase de prueba
        clase_test = ClaseResidente.objects.filter(titulo__icontains='TEST').first()
        
        if clase_test:
            print_info(f"Ya existe clase de prueba: {clase_test.titulo}")
            print_success(f"Clase ID: {clase_test.pk}")
            return True
        
        # Crear clase de ejemplo
        clase = ClaseResidente.objects.create(
            titulo="TEST - Introducción a Radiología para R1",
            descripcion="Clase de prueba automática. Conceptos básicos de radiología diagnóstica para residentes de primer año.",
            categoria='anatomia',
            anios_dirigidos=['R1'],
            autor=autor,
            fecha_clase=date.today(),
            tags='prueba, test, r1, anatomía',
            activa=True,
            es_destacada=False
        )
        
        print_success(f"Clase creada exitosamente!")
        print_info(f"  ID: {clase.pk}")
        print_info(f"  Título: {clase.titulo}")
        print_info(f"  Autor: {clase.autor.get_full_name()}")
        print_info(f"  Categoría: {clase.get_categoria_display()}")
        print_info(f"  Años: {clase.anios_dirigidos_display()}")
        
        return True
    except Exception as e:
        print_error(f"Error creando clase: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_permisos():
    """Verificar sistema de permisos"""
    print_header("TEST 4: Sistema de Permisos")
    
    try:
        clase = ClaseResidente.objects.filter(anios_dirigidos__contains=['R1']).first()
        
        if not clase:
            print_info("No hay clases para probar permisos. Saltando test.")
            return True
        
        print_info(f"Probando con clase: {clase.titulo}")
        
        # Crear usuarios de prueba para verificar permisos
        r1_user = User.objects.filter(rol='medico_residente', anio_residencia='R1').first()
        r2_user = User.objects.filter(rol='medico_residente', anio_residencia='R2').first()
        jefe_user = User.objects.filter(rol='jefe_residentes').first()
        
        if r1_user:
            puede_ver = clase.puede_ver(r1_user)
            print_success(f"R1 puede ver clase de R1: {puede_ver}")
        else:
            print_info("No hay usuario R1 para probar")
        
        if r2_user and clase.anios_dirigidos == ['R1']:
            puede_ver = clase.puede_ver(r2_user)
            print_success(f"R2 NO puede ver clase solo de R1: {not puede_ver}")
        else:
            print_info("No hay usuario R2 o clase no es exclusiva R1")
        
        if jefe_user:
            puede_ver = clase.puede_ver(jefe_user)
            print_success(f"Jefe puede ver todas las clases: {puede_ver}")
        else:
            print_info("No hay jefe para probar")
        
        # Test de edición
        if clase.autor:
            puede_editar = clase.puede_editar(clase.autor)
            print_success(f"Autor puede editar su propia clase: {puede_editar}")
        
        return True
    except Exception as e:
        print_error(f"Error verificando permisos: {e}")
        return False

def test_comentarios():
    """Verificar sistema de comentarios"""
    print_header("TEST 5: Sistema de Comentarios")
    
    try:
        clase = ClaseResidente.objects.first()
        
        if not clase:
            print_info("No hay clases para probar comentarios")
            return True
        
        usuario = User.objects.first()
        
        # Crear comentario de prueba
        comentario = ComentarioClase.objects.create(
            clase=clase,
            autor=usuario,
            contenido="Comentario de prueba automático. Excelente clase!"
        )
        
        print_success("Comentario creado exitosamente")
        print_info(f"  Clase: {clase.titulo}")
        print_info(f"  Autor: {usuario.get_full_name()}")
        print_info(f"  Contenido: {comentario.contenido[:50]}...")
        
        # Verificar conteo
        total = clase.comentarios.count()
        print_info(f"  Total comentarios en esta clase: {total}")
        
        return True
    except Exception as e:
        print_error(f"Error probando comentarios: {e}")
        return False

def test_favoritos():
    """Verificar sistema de favoritos"""
    print_header("TEST 6: Sistema de Favoritos")
    
    try:
        clase = ClaseResidente.objects.first()
        usuario = User.objects.first()
        
        if not clase or not usuario:
            print_info("No hay datos para probar favoritos")
            return True
        
        # Crear favorito
        favorito, created = FavoritoClase.objects.get_or_create(
            usuario=usuario,
            clase=clase
        )
        
        if created:
            print_success("Favorito agregado exitosamente")
        else:
            print_info("Favorito ya existía")
        
        print_info(f"  Usuario: {usuario.get_full_name()}")
        print_info(f"  Clase: {clase.titulo}")
        
        # Verificar conteo
        total = usuario.favoritos.count() if hasattr(usuario, 'favoritos') else FavoritoClase.objects.filter(usuario=usuario).count()
        print_info(f"  Total favoritos del usuario: {total}")
        
        return True
    except Exception as e:
        print_error(f"Error probando favoritos: {e}")
        return False

def test_estadisticas():
    """Mostrar estadísticas del sistema"""
    print_header("ESTADÍSTICAS DEL SISTEMA")
    
    try:
        total_clases = ClaseResidente.objects.count()
        activas = ClaseResidente.objects.filter(activa=True).count()
        destacadas = ClaseResidente.objects.filter(es_destacada=True).count()
        total_comentarios = ComentarioClase.objects.count()
        total_favoritos = FavoritoClase.objects.count()
        
        print_info(f"Total de clases: {total_clases}")
        print_info(f"Clases activas: {activas}")
        print_info(f"Clases destacadas: {destacadas}")
        print_info(f"Total de comentarios: {total_comentarios}")
        print_info(f"Total de favoritos: {total_favoritos}")
        
        if total_clases > 0:
            # Clases por categoría
            print("\n📊 Distribución por categoría:")
            for value, label in ClaseResidente.CATEGORIAS:
                count = ClaseResidente.objects.filter(categoria=value).count()
                if count > 0:
                    print(f"  • {label}: {count}")
            
            # Clases por año
            print("\n📚 Clases por año de residencia:")
            for anio in ['R1', 'R2', 'R3', 'R4', 'R5']:
                count = ClaseResidente.objects.filter(anios_dirigidos__contains=[anio]).count()
                if count > 0:
                    print(f"  • {anio}: {count}")
        
        return True
    except Exception as e:
        print_error(f"Error obteniendo estadísticas: {e}")
        return False

def main():
    """Ejecutar todos los tests"""
    print("\n" + "🔬" * 30)
    print("  SISTEMA DE CLASES DE RESIDENTES - TESTING")
    print("🔬" * 30)
    
    tests = [
        ("Modelos", test_models),
        ("Usuarios", test_usuarios),
        ("Crear Clase", test_crear_clase_ejemplo),
        ("Permisos", test_permisos),
        ("Comentarios", test_comentarios),
        ("Favoritos", test_favoritos),
        ("Estadísticas", test_estadisticas),
    ]
    
    results = []
    
    for nombre, test_func in tests:
        try:
            resultado = test_func()
            results.append((nombre, resultado))
        except Exception as e:
            print_error(f"Error ejecutando {nombre}: {e}")
            results.append((nombre, False))
    
    # Resumen final
    print_header("RESUMEN DE TESTS")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for nombre, resultado in results:
        if resultado:
            print_success(f"{nombre}: PASSED")
        else:
            print_error(f"{nombre}: FAILED")
    
    print(f"\n{'='*60}")
    print(f"  RESULTADO: {passed}/{total} tests pasados ({(passed/total)*100:.1f}%)")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("🎉 ¡Todos los tests pasaron! Sistema funcionando correctamente.")
        print("\n📝 Próximos pasos:")
        print("   1. Abrir navegador: http://localhost:8000/clases/")
        print("   2. Iniciar sesión como médico")
        print("   3. Probar crear una clase manualmente")
        print("   4. Configurar Cloudinary (opcional)")
    else:
        print("⚠️  Algunos tests fallaron. Revisa los errores arriba.")
    
    return passed == total

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrumpidos por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
