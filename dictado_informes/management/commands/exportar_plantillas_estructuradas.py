"""Exporta PlantillaEstructurada a una fixture JSON portable e idempotente."""
from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from dictado_informes.models import PlantillaEstructurada


class Command(BaseCommand):
    help = "Exporta plantillas estructuradas a dictado_informes/fixtures/plantillas_estructuradas_local.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="dictado_informes/fixtures/plantillas_estructuradas_local.json",
            help="Ruta de salida relativa al proyecto o absoluta.",
        )

    def handle(self, *args, **options):
        output = Path(options["output"])
        if not output.is_absolute():
            output = Path(settings.BASE_DIR) / output

        output.parent.mkdir(parents=True, exist_ok=True)

        data = []
        queryset = PlantillaEstructurada.objects.order_by("codigo")
        for plantilla in queryset:
            data.append(
                {
                    "codigo": plantilla.codigo,
                    "nombre": plantilla.nombre,
                    "titulo": plantilla.titulo,
                    "seccion_tecnica": plantilla.seccion_tecnica,
                    "comentarios_base": plantilla.comentarios_base,
                    "origen": plantilla.origen,
                    "activa": plantilla.activa,
                }
            )

        output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(f"✅ Exportadas {len(data)} plantillas a {output}")
        )
