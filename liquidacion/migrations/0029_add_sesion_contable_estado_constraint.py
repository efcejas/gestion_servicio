# Generated migration on 2026-05-11

from django.db import migrations, models


def add_constraint_with_db_awareness(apps, schema_editor):
    """
    Agregar constraint verificador a nivel BD de forma multiplataforma.
    SQLite y PostgreSQL tienen sintaxis diferente.
    """
    db_type = schema_editor.connection.settings_dict['ENGINE'].split('.')[-1]
    
    if db_type == 'sqlite3':
        # SQLite no soporta CHECK constraints en ALTER TABLE en versiones antiguas
        # Por ahora, enforzamos en Python + signals + tests
        # En una migración futura, podríamos recrear tabla con CHECK
        pass
    else:
        # PostgreSQL y otros motores
        schema_editor.execute("""
            ALTER TABLE liquidacion_registroestudiospormedico
            ADD CONSTRAINT ck_sesion_abierta_para_practicas CHECK (
                sesion_contable_id IS NULL OR sesion_contable_id NOT IN (
                    SELECT id FROM liquidacion_sesioncontable 
                    WHERE estado IN ('CERRADA', 'FACTURADA', 'PAGADA')
                )
            );
        """)


def remove_constraint_with_db_awareness(apps, schema_editor):
    """
    Remover constraint de forma multiplataforma.
    """
    db_type = schema_editor.connection.settings_dict['ENGINE'].split('.')[-1]
    
    if db_type == 'sqlite3':
        pass  # SQLite: no hay nada que remover
    else:
        schema_editor.execute("""
            ALTER TABLE liquidacion_registroestudiospormedico
            DROP CONSTRAINT ck_sesion_abierta_para_practicas;
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('liquidacion', '0028_registroestudio_and_more'),
    ]

    operations = [
        # CONSTRAINT multiplataforma: Prevenir insertar prácticas en sesiones cerradas
        migrations.RunPython(add_constraint_with_db_awareness, remove_constraint_with_db_awareness),
        
        # NOTA: En SQLite, esta protección es principalmente en Python + signals + tests
        # En PostgreSQL/Heroku, se enforcement a nivel BD.
        # Ver: models.py SesionContable.puede_registrar_practicas()
        #      signals.py para protecciones adicionales
        #      tests.py para validación de restricciones
    ]
