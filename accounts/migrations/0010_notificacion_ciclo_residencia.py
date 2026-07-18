from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_estado_academico_residencia'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotificacionCicloResidencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cierre_anio', models.PositiveSmallIntegerField()),
                ('tipo', models.CharField(choices=[('PROMOCION', 'Promoción'), ('EGRESO', 'Egreso')], max_length=12)),
                ('anio_anterior', models.CharField(max_length=2)),
                ('anio_nuevo', models.CharField(blank=True, max_length=2, null=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('vista_en', models.DateTimeField(blank=True, null=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notificaciones_ciclo_residencia', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notificación de ciclo de residencia',
                'verbose_name_plural': 'Notificaciones de ciclo de residencia',
                'ordering': ['creada_en'],
            },
        ),
        migrations.AddConstraint(
            model_name='notificacioncicloresidencia',
            constraint=models.UniqueConstraint(fields=('usuario', 'cierre_anio'), name='unique_notificacion_ciclo_usuario_cierre'),
        ),
    ]
