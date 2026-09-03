from django.test import SimpleTestCase

from dictado_informes.anatomy_ontology import (
    ONTOLOGIA_ANATOMICA,
    componentes_afectados,
    construir_linea_residual,
    grupo_para_linea,
    obtener_grupo,
    puntuar_linea_relacionada,
    resumen_ontologia_relevante,
)


class TestOntologiaAnatomica(SimpleTestCase):
    def test_define_los_cuatro_conjuntos_iniciales(self):
        codigos = {grupo.codigo for grupo in ONTOLOGIA_ANATOMICA}

        self.assertEqual(codigos, {
            'meniscos',
            'ligamentos_cruzados',
            'manguito_rotador',
            'parenquima_cerebral',
        })

    def test_resuelve_sinonimos_de_menisco_y_cruzado(self):
        meniscos = obtener_grupo('meniscos')
        cruzados = obtener_grupo('ligamentos_cruzados')

        afectados_menisco = componentes_afectados(
            meniscos,
            'Desgarro complejo del menisco medial.',
        )
        afectados_cruzado = componentes_afectados(
            cruzados,
            'Rotura completa del LCA.',
        )

        self.assertEqual(afectados_menisco[0].codigo, 'menisco_interno')
        self.assertEqual(afectados_cruzado[0].codigo, 'ligamento_cruzado_anterior')

    def test_reemplaza_normalidad_de_conjunto_por_componente_restante(self):
        residual = construir_linea_residual(
            'Meniscos de altura y señal normales.',
            'Desgarro del menisco interno.',
        )

        self.assertEqual(residual, 'Menisco externo de altura y señal conservadas.')

    def test_patologia_meniscal_en_plural_no_infiere_componente_normal(self):
        residual = construir_linea_residual(
            'Meniscos de altura y señal normales.',
            (
                'Meniscos con cambios degenerativos hialinos difusos, de predominio '
                'en el cuerno posterior del menisco interno.'
            ),
        )

        self.assertIsNone(residual)

    def test_manguito_usa_frase_residual_para_varios_componentes_restantes(self):
        residual = construir_linea_residual(
            'Tendones del manguito rotador sin alteraciones.',
            'Tendinopatía del supraespinoso.',
        )

        self.assertEqual(residual, 'Resto de tendones del manguito rotador sin alteraciones.')

    def test_parenquima_reconoce_lesion_lobar_aunque_no_nombre_componente(self):
        residual = construir_linea_residual(
            'No se observan alteraciones en la sustancia gris ni blanca encefálicas.',
            'Lesión nodular focal frontal izquierda.',
        )

        self.assertEqual(
            residual,
            'No se observan otras alteraciones en el resto del parénquima cerebral.',
        )

    def test_no_infiere_patologia_por_una_mencion_normal(self):
        residual = construir_linea_residual(
            'Meniscos de altura y señal normales.',
            'Menisco interno y externo conservados.',
        )

        self.assertIsNone(residual)

    def test_una_linea_de_componente_no_se_interpreta_como_conjunto(self):
        grupo = grupo_para_linea(
            'Tendón supraespinoso de señal conservada.',
            exigir_conjunto=True,
        )

        self.assertIsNone(grupo)

    def test_puntaje_prioriza_hallazgo_del_mismo_componente(self):
        grupo = obtener_grupo('ligamentos_cruzados')

        relacionado = puntuar_linea_relacionada(
            'Desgarro del ligamento cruzado anterior.',
            grupo,
        )
        no_relacionado = puntuar_linea_relacionada('Derrame articular.', grupo)

        self.assertGreater(relacionado, no_relacionado)

    def test_resumen_para_prompt_expone_solo_relaciones_relevantes(self):
        resumen = resumen_ontologia_relevante(
            'Desgarro del menisco interno.',
            'Meniscos de altura y señal normales.',
        )

        self.assertIn('Meniscos incluye: Menisco interno, Menisco externo.', resumen)
        self.assertNotIn('Manguito rotador incluye', resumen)
