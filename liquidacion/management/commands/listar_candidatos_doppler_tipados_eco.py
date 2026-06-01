from django.core.management.base import BaseCommand

from liquidacion.grupo_tarifario_mapping import detecta, normalizado, PATRONES_DOPPLER
from liquidacion.models import Estudios


class Command(BaseCommand):
    help = (
        "Lista estudios candidatos a saneamiento: tipo ECO con nombre/codigo "
        "que sugieren Doppler. Solo lectura."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita la cantidad de filas impresas (0 = sin limite)",
        )

    def handle(self, *args, **options):
        limit = int(options.get("limit") or 0)

        candidatos = []
        qs = Estudios.objects.filter(tipo="ECO").select_related("grupo_tarifario").order_by("id")

        for estudio in qs:
            nombre_norm = normalizado(estudio.nombre)
            codigo_norm = normalizado(estudio.codigo or "")
            es_doppler_por_nombre = detecta(nombre_norm, PATRONES_DOPPLER)
            es_doppler_por_codigo = detecta(
                codigo_norm,
                [r"\bDOP\b", r"\bDOPPLER\b", r"\bECODOPPLER\b"],
            )
            if not (es_doppler_por_nombre or es_doppler_por_codigo):
                continue

            grupo = estudio.grupo_tarifario
            candidatos.append(
                {
                    "id": estudio.id,
                    "codigo": estudio.codigo or "",
                    "nombre": estudio.nombre,
                    "tipo": estudio.tipo,
                    "grupo_codigo": grupo.codigo if grupo else "",
                    "grupo_modalidad": grupo.modalidad if grupo else "",
                }
            )

        self.stdout.write("\n=== CANDIDATOS DOPPLER MAL TIPADOS COMO ECO (solo lectura) ===")
        self.stdout.write(f"Total candidatos: {len(candidatos)}")

        if not candidatos:
            self.stdout.write(self.style.SUCCESS("No se detectaron candidatos."))
            return

        filas = candidatos if limit <= 0 else candidatos[:limit]
        for c in filas:
            self.stdout.write(
                f"- id={c['id']} | tipo={c['tipo']} | codigo={c['codigo']} | "
                f"grupo={c['grupo_codigo']} ({c['grupo_modalidad']}) | {c['nombre']}"
            )

        if limit > 0 and len(candidatos) > limit:
            self.stdout.write(f"... {len(candidatos) - limit} filas adicionales omitidas por --limit")

        self.stdout.write("\nNo se realizaron cambios en la base de datos.")
