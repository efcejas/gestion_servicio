"""Sincroniza PlantillaEstructurada desde una fixture JSON hacia la BD actual."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dictado_informes.models import PlantillaEstructurada


class Command(BaseCommand):
    help = "Sincroniza plantillas estructuradas desde una fixture JSON usando update_or_create por código"

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            default="dictado_informes/fixtures/plantillas_estructuradas_local.json",
            help="Ruta de la fixture JSON relativa al proyecto o absoluta.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué haría sin escribir cambios en la base.",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        if not input_path.is_absolute():
            input_path = Path(settings.BASE_DIR) / input_path

        if not input_path.exists():
            raise CommandError(f"No existe la fixture: {input_path}")

        data = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise CommandError("La fixture debe ser una lista JSON de plantillas.")

        creadas = 0
        actualizadas = 0
        dry_run = options["dry_run"]

        for item in data:
            codigo = item.get("codigo")
            if not codigo:
                raise CommandError("Cada plantilla debe incluir 'codigo'.")

            defaults = {
                "nombre": item.get("nombre", ""),
                "titulo": item.get("titulo", ""),
                "seccion_tecnica": item.get("seccion_tecnica", ""),
                "comentarios_base": item.get("comentarios_base", []),
                "origen": item.get("origen", "legacy"),
                "activa": item.get("activa", True),
            }

            existe = PlantillaEstructurada.objects.filter(codigo=codigo).exists()
            accion = "actualizaría" if existe else "crearía"
            self.stdout.write(f"- {accion}: {codigo}")

            if dry_run:
                if existe:
                    actualizadas += 1
                else:
                    creadas += 1
                continue

            _, created = PlantillaEstructurada.objects.update_or_create(
                codigo=codigo,
                defaults=defaults,
            )
            if created:
                creadas += 1
            else:
                actualizadas += 1

        total = PlantillaEstructurada.objects.count() if not dry_run else "sin cambios"
        resumen = (
            f"✅ Sincronización completada. Creadas: {creadas} | Actualizadas: {actualizadas} | Total: {total}"
        )
        self.stdout.write(self.style.SUCCESS(resumen))
