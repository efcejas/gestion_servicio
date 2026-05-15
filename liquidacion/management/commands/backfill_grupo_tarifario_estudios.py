"""
Comando: backfill_grupo_tarifario_estudios

Asigna grupo_tarifario a estudios existentes basándose en tipo + patrones del nombre.

REGLAS DE MAPEO:
  TOM + ANGIO en nombre  → TOM_ANGIO
  TOM + CON CONTRASTE    → TOM_CONTRASTE
  TOM + SIN CONTRASTE    → TOM_SIN_CONTRASTE
  TOM (resto)            → TOM_SIMPLE

  RES + ANGIO en nombre  → RES_ANGIO
  RES (resto)            → RES_SIMPLE

  ECO + DOPPLER          → ECO_DOPPLER
  ECO (resto)            → ECO_ECOGRAFIA

  DOP                    → ECO_DOPPLER
  RAD                    → RAD_RADIOGRAFIA
  MAM                    → MAM_MAMOGRAFIA
  ECOCAR                 → sin mapeo automático (requiere revisión manual)

Uso:
  python manage.py backfill_grupo_tarifario_estudios --dry-run
  python manage.py backfill_grupo_tarifario_estudios
  python manage.py backfill_grupo_tarifario_estudios --solo-sin-grupo
"""
import re
import unicodedata

from django.core.management.base import BaseCommand

from liquidacion.models import Estudios, GrupoTarifario


def strip_accents(text):
    normalized = unicodedata.normalize("NFD", str(text))
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalizado(text):
    return re.sub(r"\s+", " ", strip_accents(text).upper()).strip()


PATRONES_ANGIO = [r"\bANGIO"]
PATRONES_CON_CONTRASTE = [
    r"\bCON\s+CONTRASTE\b",
    r"\bCON\s*/\s*CTE\b",
    r"\bC/CONTRASTE\b",
    r"\bC/CONTR\b",
]
PATRONES_SIN_CONTRASTE = [
    r"\bSIN\s+CONTRASTE\b",
    r"\bSIN\s*/\s*CTE\b",
    r"\bS/CONTRASTE\b",
    r"\bS/CONTR\b",
]
PATRONES_DOPPLER = [r"\bDOPPLER\b", r"\bECODOPPLER\b"]


def detecta(nombre, patrones):
    texto = normalizado(nombre)
    return any(re.search(p, texto) for p in patrones)


def inferir_codigo_grupo(tipo, nombre):
    """
    Retorna el código de GrupoTarifario que corresponde al estudio,
    o None si no se puede asignar automáticamente.
    """
    if tipo == "TOM":
        if detecta(nombre, PATRONES_ANGIO):
            return "TOM_ANGIO"
        if detecta(nombre, PATRONES_CON_CONTRASTE):
            return "TOM_CONTRASTE"
        if detecta(nombre, PATRONES_SIN_CONTRASTE):
            return "TOM_SIN_CONTRASTE"
        return "TOM_SIMPLE"

    if tipo == "RES":
        if detecta(nombre, PATRONES_ANGIO):
            return "RES_ANGIO"
        return "RES_SIMPLE"

    if tipo == "ECO":
        if detecta(nombre, PATRONES_DOPPLER):
            return "ECO_DOPPLER"
        return "ECO_ECOGRAFIA"

    if tipo == "DOP":
        return "ECO_DOPPLER"

    if tipo == "RAD":
        return "RAD_RADIOGRAFIA"

    if tipo == "MAM":
        return "MAM_MAMOGRAFIA"

    # ECOCAR y otros sin mapeo automático
    return None


class Command(BaseCommand):
    help = "Asigna grupo_tarifario a estudios existentes por tipo y nombre (backfill)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué se asignaría sin escribir en la base de datos",
        )
        parser.add_argument(
            "--solo-sin-grupo",
            action="store_true",
            help="Solo procesa estudios que aún no tienen grupo_tarifario asignado",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        solo_sin_grupo = options["solo_sin_grupo"]

        grupos = {g.codigo: g for g in GrupoTarifario.objects.all()}
        if not grupos:
            self.stdout.write(self.style.ERROR(
                "No hay grupos tarifarios cargados. Ejecutá primero: "
                "python manage.py cargar_grupos_tarifarios_eges"
            ))
            return

        qs = Estudios.objects.all().order_by("tipo", "nombre")
        if solo_sin_grupo:
            qs = qs.filter(grupo_tarifario__isnull=True)

        asignados = 0
        sin_cambio = 0
        sin_mapeo = 0
        sin_mapeo_tipos = []

        self.stdout.write(self.style.WARNING(
            f"{'[DRY-RUN] ' if dry_run else ''}Procesando {qs.count()} estudios..."
        ))

        for estudio in qs.select_related("grupo_tarifario"):
            codigo_grupo = inferir_codigo_grupo(estudio.tipo, estudio.nombre)

            if codigo_grupo is None:
                sin_mapeo += 1
                sin_mapeo_tipos.append(f"{estudio.tipo} | {estudio.nombre}")
                continue

            grupo = grupos.get(codigo_grupo)
            if grupo is None:
                sin_mapeo += 1
                sin_mapeo_tipos.append(
                    f"{estudio.tipo} | {estudio.nombre} → grupo {codigo_grupo} no encontrado en DB"
                )
                continue

            ya_asignado = estudio.grupo_tarifario_id == grupo.pk
            if ya_asignado and not dry_run:
                sin_cambio += 1
                continue

            if dry_run:
                actual = estudio.grupo_tarifario.codigo if estudio.grupo_tarifario else "—"
                flecha = f"{actual} → {codigo_grupo}" if actual != codigo_grupo else f"{codigo_grupo} (sin cambio)"
                self.stdout.write(f"  {estudio.tipo} | {estudio.nombre[:60]:<60} {flecha}")
            else:
                estudio.grupo_tarifario = grupo
                estudio.save(update_fields=["grupo_tarifario"])
                asignados += 1

        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"Dry-run: ningún cambio aplicado. "
                f"Sin mapeo automático: {sin_mapeo}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Asignados: {asignados}  |  Sin cambio: {sin_cambio}  |  Sin mapeo: {sin_mapeo}"
            ))

        if sin_mapeo_tipos:
            self.stdout.write(
                self.style.WARNING(f"\nEstudios sin mapeo automático ({sin_mapeo}):")
            )
            for item in sin_mapeo_tipos:
                self.stdout.write(f"  ⚠  {item}")
