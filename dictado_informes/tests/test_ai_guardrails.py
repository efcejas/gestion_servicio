"""
Tests para guardrails de modo estructurado en AIService.
"""
from django.test import TestCase
from unittest.mock import MagicMock

from dictado_informes.ai_services import AIService


class AIGuardrailsTests(TestCase):
    def setUp(self):
        self.ai = AIService()

    def test_terra_usa_parametros_de_modelo_de_razonamiento(self):
        respuesta = MagicMock()
        self.ai.llm_client = MagicMock()
        self.ai.llm_client.chat.completions.create.return_value = respuesta
        self.ai.llm_model = 'gpt-5.6-terra'
        self.ai.llm_fallback_model = 'gpt-4.1-mini'
        self.ai.llm_reasoning_effort = 'low'

        resultado, modelo = self.ai._crear_chat_completion_openai(
            messages=[{'role': 'user', 'content': 'Informe'}],
            temperature=0.3,
            max_tokens=1500,
        )

        self.assertIs(resultado, respuesta)
        self.assertEqual(modelo, 'gpt-5.6-terra')
        kwargs = self.ai.llm_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs['max_completion_tokens'], 1500)
        self.assertEqual(kwargs['extra_body'], {'reasoning_effort': 'low'})
        self.assertNotIn('temperature', kwargs)
        self.assertNotIn('max_tokens', kwargs)

    def test_terra_reintenta_con_gpt_4_1_mini(self):
        respuesta = MagicMock()
        self.ai.llm_client = MagicMock()
        self.ai.llm_client.chat.completions.create.side_effect = [
            RuntimeError('modelo no habilitado'),
            respuesta,
        ]
        self.ai.llm_model = 'gpt-5.6-terra'
        self.ai.llm_fallback_model = 'gpt-4.1-mini'
        self.ai.llm_reasoning_effort = 'low'

        resultado, modelo = self.ai._crear_chat_completion_openai(
            messages=[{'role': 'user', 'content': 'Informe'}],
            temperature=0.2,
            max_tokens=1200,
        )

        self.assertIs(resultado, respuesta)
        self.assertEqual(modelo, 'gpt-4.1-mini')
        self.assertEqual(self.ai.llm_client.chat.completions.create.call_count, 2)
        kwargs = self.ai.llm_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs['model'], 'gpt-4.1-mini')
        self.assertEqual(kwargs['temperature'], 0.2)
        self.assertEqual(kwargs['max_tokens'], 1200)

    def test_normaliza_acentos_solo_en_encabezados_completos(self):
        texto = """RM DE RODILLA DERECHA
INFORMACION CLINICA
Evaluacion clinica por dolor.
TECNICA:
Se realizo tecnica habitual.
COMENTARIO
Sin informacion adicional.
CONCLUSION
Desgarro meniscal.
"""

        texto_final, aplicado = self.ai._normalizar_acentos_encabezados(texto)

        self.assertTrue(aplicado)
        self.assertIn('INFORMACIÓN CLÍNICA\n', texto_final)
        self.assertIn('TÉCNICA:\n', texto_final)
        self.assertIn('CONCLUSIÓN\n', texto_final)
        self.assertIn('Se realizo tecnica habitual.', texto_final)
        self.assertIn('Sin informacion adicional.', texto_final)

    def test_edicion_localizada_reemplaza_solo_el_fragmento_indicado(self):
        informe = """RM DE RODILLA DERECHA

COMENTARIO
Derrame articular leve.
Meniscos de altura y señal normales.

CONCLUSIÓN
Derrame articular leve."""

        editado, operaciones = self.ai._aplicar_operaciones_edicion(informe, [{
            'tipo': 'reemplazar',
            'original': 'COMENTARIO\nDerrame articular leve.',
            'nuevo': 'COMENTARIO\nDerrame articular moderado.',
        }])

        self.assertIn('Derrame articular moderado.', editado)
        self.assertEqual(editado.count('Derrame articular leve.'), 1)
        self.assertIn('Meniscos de altura y señal normales.', editado)
        self.assertEqual(len(operaciones), 1)

    def test_edicion_con_ia_solicita_operaciones_json_y_las_aplica(self):
        respuesta = MagicMock()
        respuesta.choices[0].message.content = '''{
            "operaciones": [{
                "tipo": "reemplazar",
                "original": "Derrame leve.",
                "nuevo": "Derrame moderado."
            }],
            "resumen_cambios": ["Se corrigió la cuantía del derrame."]
        }'''
        self.ai.llm_enabled = True
        self.ai.llm_client = MagicMock()
        self.ai.llm_client.chat.completions.create.return_value = respuesta
        self.ai.llm_model = 'gpt-4.1-mini'
        self.ai.llm_fallback_model = None
        self.ai.llm_reasoning_effort = None

        resultado = self.ai.edit_medical_report(
            'COMENTARIO\nDerrame leve.',
            'Cambiá leve por moderado.',
            'Derrame leve.',
        )

        self.assertEqual(resultado['texto_editado'], 'COMENTARIO\nDerrame moderado.')
        self.assertEqual(resultado['resumen_cambios'], ['Se corrigió la cuantía del derrame.'])
        kwargs = self.ai.llm_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs['response_format'], {'type': 'json_object'})

    def test_edicion_por_voz_recibe_relacion_anatomica_relevante(self):
        respuesta = MagicMock()
        respuesta.choices[0].message.content = '''{
            "operaciones": [{
                "tipo": "reemplazar",
                "original": "Desgarro del LCA.",
                "nuevo": "Desgarro completo del LCA."
            }],
            "resumen_cambios": ["Se completo la descripcion."]
        }'''
        self.ai.llm_enabled = True
        self.ai.llm_client = MagicMock()
        self.ai.llm_client.chat.completions.create.return_value = respuesta
        self.ai.llm_model = 'gpt-4.1-mini'
        self.ai.llm_fallback_model = None
        self.ai.llm_reasoning_effort = None

        self.ai.edit_medical_report(
            'HALLAZGOS\nDesgarro del LCA.\nLigamento cruzado posterior conservado.',
            'Cambia el desgarro del LCA a completo.',
        )

        mensajes = self.ai.llm_client.chat.completions.create.call_args.kwargs['messages']
        prompt_usuario = mensajes[1]['content']
        self.assertIn(
            'Ligamentos cruzados incluye: Ligamento cruzado anterior, Ligamento cruzado posterior.',
            prompt_usuario,
        )

    def test_edicion_localizada_rechaza_fragmento_ambiguo(self):
        informe = 'Derrame leve.\nDerrame leve.'

        with self.assertRaisesMessage(ValueError, 'ambiguo'):
            self.ai._aplicar_operaciones_edicion(informe, [{
                'tipo': 'reemplazar',
                'original': 'Derrame leve.',
                'nuevo': 'Derrame moderado.',
            }])

    def test_edicion_localizada_rechaza_reescritura_amplia(self):
        informe = 'TITULO\nTECNICA\nTecnica original.\nHALLAZGOS\nHallazgo original.\nCONCLUSION\nConclusion original.'

        with self.assertRaisesMessage(ValueError, 'demasiado amplia'):
            self.ai._aplicar_operaciones_edicion(informe, [{
                'tipo': 'reemplazar',
                'original': informe,
                'nuevo': 'Informe completamente regenerado.',
            }])

    def test_edicion_localizada_mueve_linea_sin_regenerar_informe(self):
        informe = 'COMENTARIO\nMeniscos normales.\nLigamentos conservados.\nDerrame articular.'

        editado, _ = self.ai._aplicar_operaciones_edicion(informe, [{
            'tipo': 'mover_despues',
            'original': 'Ligamentos conservados.',
            'referencia': 'Derrame articular.',
        }])

        self.assertEqual(
            editado,
            'COMENTARIO\nMeniscos normales.\nDerrame articular.\nLigamentos conservados.',
        )

    def test_edicion_localizada_agrega_conclusion_solicitada(self):
        informe = 'RM DE RODILLA\n\nHALLAZGOS\nDesgarro del menisco interno.'

        editado, operaciones = self.ai._aplicar_operaciones_edicion(
            informe,
            [{
                'tipo': 'agregar_al_final',
                'nuevo': 'CONCLUSIÓN\nDesgarro del menisco interno.',
            }],
            instruccion='Agregá una conclusión con los hallazgos patológicos.',
        )

        self.assertEqual(
            editado,
            f'{informe}\n\nCONCLUSIÓN\nDesgarro del menisco interno.',
        )
        self.assertEqual(operaciones[0]['tipo'], 'agregar_al_final')

    def test_edicion_localizada_no_crea_seccion_sin_pedido_explicito(self):
        informe = 'RM DE RODILLA\n\nHALLAZGOS\nDesgarro del menisco interno.'

        with self.assertRaisesMessage(ValueError, 'no fue solicitada'):
            self.ai._aplicar_operaciones_edicion(
                informe,
                [{
                    'tipo': 'agregar_al_final',
                    'nuevo': 'CONCLUSIÓN\nDesgarro del menisco interno.',
                }],
                instruccion='Corregí la redacción del hallazgo.',
            )

    def test_edicion_localizada_no_duplica_seccion_existente(self):
        informe = 'HALLAZGOS\nDesgarro meniscal.\n\nCONCLUSIÓN\nDesgarro meniscal.'

        with self.assertRaisesMessage(ValueError, 'ya existe'):
            self.ai._aplicar_operaciones_edicion(
                informe,
                [{
                    'tipo': 'agregar_al_final',
                    'nuevo': 'CONCLUSIÓN\nDesgarro meniscal.',
                }],
                instruccion='Agregá una conclusión.',
            )

    def test_guardrail_restaurar_linea_no_mencionada(self):
        texto_original = "Rodilla derecha con desgarro del ligamento cruzado anterior y derrame articular."
        texto_mejorado = """RM DE RODILLA DERECHA

INFORMACIÃ“N CLÃNICA
Trauma.

TÃ‰CNICA
Se explorÃ³ la rodilla derecha.

COMENTARIO
Desgarro del ligamento cruzado anterior.
Derrame articular.

CONCLUSIÃ“N
Desgarro del LCA con derrame articular.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y seÃ±al normales.',
                'Ligamentos cruzados de trayecto y morfologÃ­a conservados.',
                'RÃ³tula centrada, sin lesiÃ³n visible.',
            ]
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertIn('Meniscos de altura y seÃ±al normales.', texto_final)
        self.assertIn('RÃ³tula centrada, sin lesiÃ³n visible.', texto_final)
        self.assertIn('Ligamento cruzado posterior conservado.', texto_final)
        self.assertNotIn('Ligamentos cruzados de trayecto y morfologÃ­a conservados.', texto_final)
        self.assertEqual(len(restauradas), 3)

    def test_guardrail_no_repetir_linea_ya_presente(self):
        texto_original = "Rodilla sin hallazgos patolÃ³gicos relevantes."
        texto_mejorado = """COMENTARIO
Meniscos de altura y seÃ±al normales.
RÃ³tula centrada, sin lesiÃ³n visible.

CONCLUSIÃ“N
Estudio dentro de parÃ¡metros normales.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y seÃ±al normales.',
                'RÃ³tula centrada, sin lesiÃ³n visible.',
            ]
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertEqual(texto_final.count('Meniscos de altura y seÃ±al normales.'), 1)
        self.assertEqual(texto_final.count('RÃ³tula centrada, sin lesiÃ³n visible.'), 1)
        self.assertEqual(restauradas, [])

    def test_detector_invencion_marca_termino_no_dictado(self):
        texto_original = "Dolor de rodilla derecha sin antecedente traumÃ¡tico."
        texto_mejorado = """COMENTARIO
Meniscos de altura y seÃ±al normales.
Desgarro del menisco interno.

CONCLUSIÃ“N
Desgarro meniscal.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y seÃ±al normales.',
                'RÃ³tula centrada, sin lesiÃ³n visible.',
            ]
        }

        analisis = self.ai._detectar_posible_invencion_estructurada(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
            modo='ESTRUCTURADO',
        )

        self.assertTrue(analisis['detectada'])
        self.assertIn('desgarro', analisis['terminos_sospechosos'])

    def test_detector_invencion_no_marca_termino_dictado(self):
        texto_original = "Dolor de rodilla con desgarro meniscal interno."
        texto_mejorado = """COMENTARIO
Desgarro del menisco interno.

CONCLUSIÃ“N
Desgarro meniscal.
"""
        plantilla = {'comentarios': []}

        analisis = self.ai._detectar_posible_invencion_estructurada(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
            modo='ESTRUCTURADO',
        )

        self.assertFalse(analisis['detectada'])

    def test_detector_invencion_no_marca_si_estructura_esta_en_dictado(self):
        texto_original = "Dolor de rodilla con menisco interno lesionado."
        texto_mejorado = """COMENTARIO
Desgarro del menisco interno.

CONCLUSIÃ“N
Desgarro meniscal.
"""
        plantilla = {'comentarios': []}

        analisis = self.ai._detectar_posible_invencion_estructurada(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
            modo='ESTRUCTURADO',
        )

        self.assertFalse(analisis['detectada'])

    def test_contrato_flexible_sin_conclusion_no_la_incluye(self):
        plantilla = {
            'estructura_documento': {
                'modo': 'estricta',
                'permitir_secciones_nuevas': False,
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'TECNICA', 'tipo': 'tecnica', 'contenido': 'Tecnica base'},
                    {
                        'nombre': 'HALLAZGOS',
                        'tipo': 'hallazgos',
                        'lineas_base': ['Meniscos de configuracion habitual.'],
                    },
                ],
            }
        }

        contrato = self.ai._construir_contrato_estructura_flexible(plantilla)

        self.assertIsNotNone(contrato)
        self.assertIn('HALLAZGOS', contrato['formato_salida'])
        self.assertNotIn('CONCLUSION\n', contrato['formato_salida'])
        self.assertNotIn('[1]', contrato['formato_salida'])
        self.assertIn('no crear CONCLUSION', contrato['reglas'])

    def test_bloque_contexto_clinico_instruye_lateralidad_e_indicacion(self):
        bloque = self.ai._construir_bloque_contexto_clinico({
            'lateralidad': 'DERECHA',
            'lado_tecnica': 'derecha',
            'region': 'RODILLA',
            'indicacion_clinica': 'Gonalgia derecha.',
        })

        self.assertIn('Lateralidad detectada: DERECHA', bloque)
        self.assertIn('usar: derecha', bloque)
        self.assertIn('Gonalgia derecha.', bloque)
        self.assertIn('No agregar INFORMACION CLINICA si la plantilla no la contiene', bloque)

    def test_guardrail_lateralidad_ambas_caderas_normaliza_titulo(self):
        texto_final, aplicado = self.ai._aplicar_guardrail_lateralidad_contexto(
            """RM DE CADERA BILATERAL

TECNICA
Se exploraron ambas caderas.
""",
            {
                'lateralidad': 'BILATERAL',
                'region': 'CADERA',
                'titulo_lateralidad': 'AMBAS CADERAS',
                'frase_lateralidad': 'ambas caderas',
            }
        )

        self.assertTrue(aplicado)
        self.assertIn('RM DE AMBAS CADERAS', texto_final)

    def test_plantilla_columna_incompatible_con_contexto_mano(self):
        plantilla = {
            'titulo': 'RM DE COLUMNA LUMBOSACRA',
            'seccion_tecnica': 'Se exploro la columna lumbosacra.',
            'comentarios': [
                'Correcta alineacion en el plano sagital.',
                'Cuerpos vertebrales y espacios discales de altura conservada.',
            ],
        }

        compatible = self.ai._plantilla_compatible_con_contexto(
            plantilla,
            {'region': 'MANO'}
        )

        self.assertFalse(compatible)

    def test_guardrail_restaura_linea_en_seccion_hallazgos_flexible(self):
        texto_original = "Rodilla con derrame articular."
        texto_mejorado = """RM DE RODILLA

TECNICA
Tecnica base

HALLAZGOS
Derrame articular.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de configuracion habitual.',
                'No se observa aumento del liquido articular.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'permitir_secciones_nuevas': False,
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'TECNICA', 'tipo': 'tecnica', 'contenido': 'Tecnica base'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertIn('HALLAZGOS', texto_final)
        self.assertIn('Meniscos de configuracion habitual.', texto_final)
        self.assertNotIn('No se observa aumento del liquido articular.', texto_final)
        self.assertEqual(restauradas, ['Meniscos de configuracion habitual.'])

    def test_guardrail_limpia_numeracion_en_hallazgos(self):
        texto_original = "Rodilla con derrame articular."
        texto_mejorado = """RM DE RODILLA

HALLAZGOS
[1] Meniscos de configuracion habitual.
[2] Derrame articular.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de configuracion habitual.',
                'No se observa aumento del liquido articular.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, _ = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertNotIn('[1]', texto_final)
        self.assertNotIn('[2]', texto_final)
        self.assertIn('Meniscos de configuracion habitual.', texto_final)

    def test_guardrail_no_duplica_linea_normal_equivalente(self):
        texto_original = "Columna lumbosacra sin hallazgos patologicos."
        texto_mejorado = """RM DE COLUMNA LUMBOSACRA

COMENTARIO
Alineacion sagital conservada.
Cuerpos vertebrales y espacios discales de altura conservada.
"""
        plantilla = {
            'comentarios': [
                'Correcta alineacion en el plano sagital.',
                'Cuerpos vertebrales y espacios discales de altura conservada.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE COLUMNA LUMBOSACRA'},
                    {'nombre': 'COMENTARIO', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertIn('Alineacion sagital conservada.', texto_final)
        self.assertNotIn('Correcta alineacion en el plano sagital.', texto_final)
        self.assertEqual(restauradas, [])

    def test_guardrail_conclusion_quita_normalidad_si_hay_patologia(self):
        texto_mejorado = """RM DE RODILLA DERECHA

COMENTARIO
Desgarro del ligamento cruzado anterior.
Ligamento cruzado posterior conservado.
Meniscos de altura y senal normales.

CONCLUSION
Desgarro del ligamento cruzado anterior en rodilla derecha con meniscos y resto de estructuras ligamentarias sin alteraciones.
"""

        texto_final, aplicado = self.ai._aplicar_guardrail_conclusion_patologica(texto_mejorado)

        self.assertTrue(aplicado)
        self.assertIn('CONCLUSION', texto_final)
        self.assertIn('Desgarro del ligamento cruzado anterior en rodilla derecha.', texto_final)
        self.assertNotIn('meniscos y resto de estructuras ligamentarias sin alteraciones', texto_final)

    def test_guardrail_no_restaura_linea_normal_de_parenquima_con_lesion_cerebral(self):
        texto_original = "Lesion nodular focal en region frontal izquierda."
        texto_mejorado = """RESONANCIA MAGNETICA DE CEREBRO

HALLAZGOS
Lesion nodular focal en la region frontal izquierda.
No se observan otras alteraciones en el resto del parenquima cerebral.
"""
        plantilla = {
            'comentarios': [
                'Sistema ventricular de forma, tamano y posicion conservados.',
                'No se observan alteraciones en la senal de la sustancia gris ni blanca encefalicas.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM CEREBRO'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertIn('Sistema ventricular de forma, tamano y posicion conservados.', texto_final)
        self.assertIn('No se observan otras alteraciones en el resto del parenquima cerebral.', texto_final)
        self.assertNotIn('No se observan alteraciones en la senal de la sustancia gris ni blanca encefalicas.', texto_final)
        self.assertEqual(restauradas, ['Sistema ventricular de forma, tamano y posicion conservados.'])

    def test_guardrail_reemplaza_linea_de_conjunto_por_resto_meniscal(self):
        texto_original = "Rodilla derecha con desgarro del menisco interno."
        texto_mejorado = """RM DE RODILLA DERECHA

HALLAZGOS
Desgarro del menisco interno.
"""
        plantilla = {
            'comentarios': [
                'Meniscos de altura y senal normales.',
                'Ligamentos cruzados de trayecto y morfologia conservados.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertIn('Desgarro del menisco interno.', texto_final)
        self.assertIn('Menisco externo de altura y señal conservadas.', texto_final)
        self.assertNotIn('Meniscos de altura y senal normales.', texto_final)
        self.assertIn('Ligamentos cruzados de trayecto y morfologia conservados.', texto_final)
        self.assertIn('Menisco externo de altura y señal conservadas.', restauradas)

        lineas = texto_final.splitlines()
        self.assertLess(
            lineas.index('Desgarro del menisco interno.'),
            lineas.index('Menisco externo de altura y señal conservadas.')
        )
    def test_guardrail_no_duplica_resto_si_ya_existe(self):
        texto_original = "Rodilla derecha con desgarro del ligamento cruzado anterior."
        texto_mejorado = """RM DE RODILLA DERECHA

HALLAZGOS
Desgarro del ligamento cruzado anterior.
Ligamento cruzado posterior conservado.
"""
        plantilla = {
            'comentarios': [
                'Ligamentos cruzados de trayecto y morfologia conservados.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, restauradas = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        self.assertEqual(texto_final.count('Ligamento cruzado posterior conservado.'), 1)
        self.assertNotIn('Ligamentos cruzados de trayecto y morfologia conservados.', texto_final)
        self.assertEqual(restauradas, [])

    def test_guardrail_inserta_resto_cruzado_debajo_del_hallazgo(self):
        texto_original = "Rodilla derecha con desgarro del ligamento cruzado anterior."
        texto_mejorado = """RM DE RODILLA DERECHA

HALLAZGOS
Meniscos de altura y senal normales.
Desgarro del ligamento cruzado anterior.
No se observa aumento del liquido articular.
"""
        plantilla = {
            'comentarios': [
                'Ligamentos cruzados de trayecto y morfologia conservados.',
            ],
            'estructura_documento': {
                'modo': 'estricta',
                'secciones': [
                    {'nombre': 'TITULO', 'tipo': 'titulo', 'contenido': 'RM DE RODILLA'},
                    {'nombre': 'HALLAZGOS', 'tipo': 'hallazgos', 'lineas_base': []},
                ],
            },
        }

        texto_final, _ = self.ai._aplicar_guardrails_estructurado(
            texto_original=texto_original,
            texto_mejorado=texto_mejorado,
            plantilla_actual=plantilla,
        )

        lineas = texto_final.splitlines()
        self.assertEqual(
            lineas.index('Ligamento cruzado posterior conservado.'),
            lineas.index('Desgarro del ligamento cruzado anterior.') + 1
        )


