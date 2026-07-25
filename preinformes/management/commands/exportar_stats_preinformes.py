"""
Management command: exportar_stats_preinformes

Genera estadísticas del sistema de preinformes para el abstract de CADI 2026.
Salida por terminal y CSV opcional.

Uso:
    python manage.py exportar_stats_preinformes
    python manage.py exportar_stats_preinformes --csv stats_preinformes.csv
    python manage.py exportar_stats_preinformes --desde 2024-01-01 --hasta 2025-12-31
"""

import csv
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone


class Command(BaseCommand):
    help = 'Exporta estadísticas de preinformes para CADI 2026'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, default=None, help='Ruta del archivo CSV de salida')
        parser.add_argument('--desde', type=str, default=None, help='Fecha inicio (YYYY-MM-DD)')
        parser.add_argument('--hasta', type=str, default=None, help='Fecha fin (YYYY-MM-DD)')

    def handle(self, *args, **options):
        from preinformes.models import EncuestaResidente, Preinforme

        # Filtro de fechas
        qs = Preinforme.objects.filter(es_registro_demo=False)
        if options['desde']:
            qs = qs.filter(fecha_creacion__date__gte=options['desde'])
        if options['hasta']:
            qs = qs.filter(fecha_creacion__date__lte=options['hasta'])

        total = qs.count()
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('   ESTADÍSTICAS SISTEMA DE PREINFORMES — CADI 2026'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))
        self.stdout.write(f'  Total de preinformes analizados: {total}\n')

        # 1. Volumen mensual
        self.stdout.write(self.style.HTTP_INFO('\n[1] Volumen mensual de preinformes\n'))
        vol_mensual = (
            qs.annotate(mes=TruncMonth('fecha_creacion'))
            .values('mes')
            .annotate(cantidad=Count('id'))
            .order_by('mes')
        )
        rows_vol = []
        for row in vol_mensual:
            mes_str = row['mes'].strftime('%Y-%m') if row['mes'] else 'N/A'
            self.stdout.write(f'    {mes_str}: {row["cantidad"]} preinformes')
            rows_vol.append({'mes': mes_str, 'cantidad': row['cantidad']})

        # 2. Tiempo promedio de revisión (en horas)
        finalizados = qs.filter(
            estado='finalizado',
            fecha_finalizacion__isnull=False,
            fecha_envio_revision__isnull=False,
        )
        self.stdout.write(self.style.HTTP_INFO('\n[2] Tiempo promedio de revisión\n'))
        if finalizados.exists():
            tiempos = [
                (p.fecha_finalizacion - p.fecha_envio_revision).total_seconds() / 3600
                for p in finalizados.only('fecha_finalizacion', 'fecha_envio_revision')
                if p.fecha_finalizacion and p.fecha_envio_revision
                   and p.fecha_finalizacion > p.fecha_envio_revision
            ]
            if tiempos:
                promedio_hs = sum(tiempos) / len(tiempos)
                self.stdout.write(f'    Promedio: {promedio_hs:.1f} h  (n={len(tiempos)})')
                self.stdout.write(f'    Mínimo: {min(tiempos):.1f} h   Máximo: {max(tiempos):.1f} h')
            else:
                self.stdout.write('    Sin datos de tiempo válidos.')
        else:
            self.stdout.write('    No hay preinformes finalizados con timestamps completos.')

        # 3. Puntuación promedio global y por año de residencia (via revisión)
        self.stdout.write(self.style.HTTP_INFO('\n[3] Puntuación promedio de revisiones (0-100)\n'))
        calificados = qs.filter(revision__puntuacion__isnull=False)
        global_avg = calificados.aggregate(avg=Avg('revision__puntuacion'))['avg']
        if global_avg:
            self.stdout.write(f'    Global: {global_avg:.1f}/100')
        else:
            self.stdout.write('    Sin puntuaciones registradas.')
        por_anio = (
            calificados
            .filter(residente__anio_residencia__isnull=False)
            .values('residente__anio_residencia')
            .annotate(avg=Avg('revision__puntuacion'), n=Count('id'))
            .order_by('residente__anio_residencia')
        )
        for row in por_anio:
            anio = row['residente__anio_residencia'] or '?'
            self.stdout.write(f'    R{anio}: {row["avg"]:.1f}/100  (n={row["n"]})')

        # 4. Distribución por TipoEstudio
        self.stdout.write(self.style.HTTP_INFO('\n[4] Distribución por tipo de estudio\n'))
        por_tipo = (
            qs.values('tipo_estudio__nombre')
            .annotate(n=Count('id'))
            .order_by('-n')[:15]
        )
        rows_tipo = []
        for row in por_tipo:
            nombre = row['tipo_estudio__nombre'] or 'Sin tipo'
            self.stdout.write(f'    {nombre}: {row["n"]}')
            rows_tipo.append({'tipo': nombre, 'n': row['n']})

        # 5. % con comentarios de revisión
        self.stdout.write(self.style.HTTP_INFO('\n[5] Uso del feedback (comentarios)\n'))
        con_comentario = qs.filter(
            revision__comentarios_generales__isnull=False
        ).exclude(revision__comentarios_generales='').count()
        pct = (con_comentario / total * 100) if total > 0 else 0
        self.stdout.write(f'    Con comentario de revisión: {con_comentario} ({pct:.1f}%)')

        # 6. Encuesta de satisfacción (si hay datos)
        self.stdout.write(self.style.HTTP_INFO('\n[6] Encuesta de satisfacción CADI 2026\n'))
        try:
            enc_qs = EncuestaResidente.objects.all()
            n_enc = enc_qs.count()
            if n_enc > 0:
                promedios = enc_qs.aggregate(
                    p1=Avg('p1'), p2=Avg('p2'), p3=Avg('p3'), p4=Avg('p4'), p5=Avg('p5'),
                    p6=Avg('p6'), p7=Avg('p7'), p8=Avg('p8'), p9=Avg('p9'), p10=Avg('p10'),
                )
                global_enc = sum(v for v in promedios.values() if v) / len([v for v in promedios.values() if v])
                self.stdout.write(f'    Respuestas recibidas: {n_enc}')
                self.stdout.write(f'    Promedio global (Likert 1-5): {global_enc:.2f}')
                for k, v in promedios.items():
                    if v:
                        self.stdout.write(f'    {k}: {v:.2f}')
            else:
                self.stdout.write('    Todavía no hay respuestas de la encuesta.')
        except Exception as e:
            self.stdout.write(f'    Error al leer encuesta: {e}')

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}\n'))

        # Exportar CSV si se pidió
        if options['csv']:
            self._exportar_csv(options['csv'], rows_vol, rows_tipo, total, global_avg, pct)

    def _exportar_csv(self, ruta, rows_vol, rows_tipo, total, global_avg, pct):
        with open(ruta, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ESTADÍSTICAS PREINFORMES — CADI 2026'])
            writer.writerow([])

            writer.writerow(['Volumen mensual'])
            writer.writerow(['Mes', 'Cantidad'])
            for r in rows_vol:
                writer.writerow([r['mes'], r['cantidad']])
            writer.writerow([])

            writer.writerow(['Distribución por tipo de estudio'])
            writer.writerow(['Tipo', 'N'])
            for r in rows_tipo:
                writer.writerow([r['tipo'], r['n']])
            writer.writerow([])

            writer.writerow(['Resumen'])
            writer.writerow(['Total preinformes', total])
            writer.writerow(['Calificación promedio', f'{global_avg:.1f}' if global_avg else 'N/A'])
            writer.writerow(['% con comentario', f'{pct:.1f}%'])

        self.stdout.write(self.style.SUCCESS(f'CSV exportado en: {ruta}'))
