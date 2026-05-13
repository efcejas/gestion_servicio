# Generated migration on 2026-05-11
# Updated 2026-05-12: PostgreSQL no soporta subqueries en CHECK constraints.
# La protección equivalente se realiza a nivel Python en:
#   - SesionContable.puede_registrar_practicas() en models.py
#   - dispatch() en RegistroEstudiosPorMedicoCreateView y UpdateView en views.py
#   - Tests en tests_auditoria_2026_05_11.py (SesionContableConstraintTest)

from django.db import migrations


def add_constraint_trigger_postgresql(apps, schema_editor):
    """
    Agrega un TRIGGER en PostgreSQL para prevenir prácticas en sesiones cerradas.
    Los triggers SÍ pueden usar subqueries, a diferencia de CHECK constraints.
    SQLite no soporta triggers con la misma sintaxis — se omite allí.
    """
    db_type = schema_editor.connection.settings_dict['ENGINE'].split('.')[-1]

    if db_type == 'postgresql':
        # Crear función trigger
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION fn_check_sesion_abierta_para_practicas()
            RETURNS TRIGGER AS $$
            DECLARE
                estado_sesion VARCHAR(10);
            BEGIN
                IF NEW.sesion_contable_id IS NOT NULL THEN
                    SELECT estado INTO estado_sesion
                    FROM liquidacion_sesioncontable
                    WHERE id = NEW.sesion_contable_id;

                    IF estado_sesion IN ('CERRADA', 'FACTURADA', 'PAGADA') THEN
                        RAISE EXCEPTION 'No se pueden registrar prácticas en una sesión contable con estado %', estado_sesion;
                    END IF;
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """)
        # Crear trigger que dispara antes de INSERT o UPDATE
        schema_editor.execute("""
            CREATE TRIGGER tg_check_sesion_abierta_para_practicas
            BEFORE INSERT OR UPDATE ON liquidacion_registroestudiospormedico
            FOR EACH ROW EXECUTE FUNCTION fn_check_sesion_abierta_para_practicas();
        """)
    # SQLite y otros: protección solo a nivel Python (views + models)


def remove_constraint_trigger_postgresql(apps, schema_editor):
    db_type = schema_editor.connection.settings_dict['ENGINE'].split('.')[-1]

    if db_type == 'postgresql':
        schema_editor.execute("""
            DROP TRIGGER IF EXISTS tg_check_sesion_abierta_para_practicas
            ON liquidacion_registroestudiospormedico;
        """)
        schema_editor.execute("""
            DROP FUNCTION IF EXISTS fn_check_sesion_abierta_para_practicas();
        """)


class Migration(migrations.Migration):

    dependencies = [
        ('liquidacion', '0028_registroestudio_and_more'),
    ]

    operations = [
        migrations.RunPython(
            add_constraint_trigger_postgresql,
            remove_constraint_trigger_postgresql,
        ),
    ]
