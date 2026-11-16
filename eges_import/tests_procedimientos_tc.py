from datetime import date

from django.test import TestCase, override_settings

from .models import EgesRow, NettermFila
from .services_estadisticas import construir_estadisticas_fuentes
from .services_validacion_produccion import preparar_validacion_produccion, confirmar_produccion
from .tests_produccion import FuentesSinteticasMixin


@override_settings(SECURE_SSL_REDIRECT=False)
class ProcedimientosTomografiaTest(FuentesSinteticasMixin, TestCase):
    def seleccion(self):
        return dict(batch_eges_ids=[self.batch.pk], lote_netterm_ids=[self.lote.pk],
                    fecha_desde=date(2026, 10, 1), fecha_hasta=date(2026, 10, 31))

    def registro(self, codigo, practica, *, estado='DEFINITIVO', eges=True, pedido='1', cantidad=1):
        fila_eges = self.eges(codigo_practica=codigo, practica=practica, servicio='Tomografia', cantidad=cantidad) if eges else None
        fila_nt = self.netterm(codigo=codigo, practica=practica, estado=estado, pedido=pedido,
                               servicio='Tomografia', modalidad_original='TC', modalidad_modelo='TC')
        return fila_eges, fila_nt

    def confirmar(self):
        preparacion = preparar_validacion_produccion(**self.seleccion())
        decisiones = {grupo['id']: {'accion': 'UNICO'} for grupo in preparacion['grupos_procedimientos']}
        return confirmar_produccion(**self.seleccion(), usuario=self.usuario,
                                    firma_esperada=preparacion['firma'], decisiones=decisiones)

    def test_puncion_biopsia_y_citologia_de_ambas_fuentes_suman_una(self):
        self.registro('900080', 'PUNCION BIOPSIA BAJO CONTROL TOMOGRAFICO')
        self.registro('150101', 'BIOPSIA POR INCISION O PUNCION')
        citologia, _ = self.registro('150111', 'CITOLOGIA EXFOLIATIVA DE LIQUIDOS', cantidad=4)
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertEqual(len(preparacion['grupos_procedimientos']), 1)
        self.assertEqual(preparacion['grupos_procedimientos'][0]['modalidad'], 'TC')
        self.assertEqual(len(preparacion['excepciones']), 2)
        validacion = self.confirmar()
        self.assertEqual(validacion.resultado_json['total_produccion'], 1)
        self.assertEqual(validacion.resultado_json['base_eges'], 1)
        self.assertEqual(validacion.resultado_json['practicas'][0]['procedimiento_guiado_modalidad'], 'TC')
        self.assertEqual(EgesRow.objects.count(), 3)
        self.assertEqual(NettermFila.objects.count(), 3)
        citologia.refresh_from_db()
        self.assertEqual(citologia.cantidad, 4)
        datos = construir_estadisticas_fuentes(**self.seleccion(), validacion_id=validacion.pk)
        self.assertEqual(datos['kpis']['practicas_realizadas'], 1)
        self.assertEqual(datos['modalidad']['modalidades'], ['TC'])
        self.assertFalse(datos['sub_eco']['labels'])

    def test_drenaje_tc_y_componente_pendiente_con_eges_informado_suman_una(self):
        self.registro('900082', 'DRENAJE PERCUTANEO BAJO TAC HELICOIDAL')
        self.registro('150101', 'BIOPSIA POR INCISION O PUNCION', estado='PENDIENTE')
        validacion = self.confirmar()
        self.assertEqual(validacion.resultado_json['total_produccion'], 1)
        self.assertEqual(validacion.resultado_json['agrupaciones_procedimientos'][0]['componentes_retirados_del_conteo'], 1)

    def test_biopsia_sin_practica_guiada_se_revisa_individualmente(self):
        self.registro('150101', 'BIOPSIA POR INCISION O PUNCION', eges=False)
        preparacion = preparar_validacion_produccion(**self.seleccion())
        self.assertFalse(preparacion['grupos_procedimientos'])
        self.assertEqual(preparacion['automaticas'], 0)
        self.assertEqual(len(preparacion['excepciones']), 1)

    def test_dos_pedidos_independientes_conservan_dos_procedimientos(self):
        for pedido in ('1', '2'):
            self.registro('900080', 'PUNCION BIOPSIA BAJO CONTROL TOMOGRAFICO', eges=False, pedido=pedido)
            self.registro('150101', 'BIOPSIA POR INCISION O PUNCION', eges=False, pedido=pedido)
        self.assertEqual(self.confirmar().resultado_json['total_produccion'], 2)

    def test_un_grupo_con_dos_principales_confirmado_unico_conserva_una(self):
        self.registro('900080', 'PUNCION BIOPSIA BAJO CONTROL TOMOGRAFICO')
        self.registro('900082', 'DRENAJE PERCUTANEO BAJO TAC HELICOIDAL')
        self.registro('150101', 'BIOPSIA POR INCISION O PUNCION')
        self.assertEqual(self.confirmar().resultado_json['total_produccion'], 1)
