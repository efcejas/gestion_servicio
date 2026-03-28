"""
Tests del módulo control_stock.

Cobertura:
  - Modelos: LoteEnArea.vencido, vence_pronto, vence_en_dias
  - API registrar_movimiento: entrada, salida FEFO, descarte con lote_id
  - API vencimientos: filtro cantidad > 0, requiere fecha venc en entrada
  - Permisos: roles autorizados vs no autorizados
"""
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AreaServicio, LoteEnArea, MovimientoStock, Producto, StockPorArea

User = get_user_model()

URL_MOV       = reverse('control_stock:api_movimiento')
URL_VENC      = reverse('control_stock:vencimientos')
URL_DESCARTE  = reverse('control_stock:api_descarte_masivo')
URL_REPORTAR  = reverse('control_stock:api_reportar_lote')


# ── Fixtures comunes ──────────────────────────────────────────
def crear_usuario(rol='jefe_servicio', **kwargs):
    u = User.objects.create_user(
        username=kwargs.get('username', f'user_{rol}'),
        password='testpass123',
    )
    u.rol = rol
    u.perfil_completo = True  # evita redireccion del ProfileRequiredMiddleware
    u.save()
    return u


def crear_escenario_base():
    """Devuelve (area, producto, stock) listos para usar en tests."""
    area = AreaServicio.objects.create(nombre='Tomografía')
    producto = Producto.objects.create(
        codigo_barras='TEST-0001',
        nombre='Producto Test',
        categoria='descartable',
        unidad_medida='unidad',
        stock_minimo=2,
    )
    stock = StockPorArea.objects.create(producto=producto, area=area, cantidad=0)
    return area, producto, stock


# ══════════════════════════════════════════════════════════════
# 1. Tests de modelo
# ══════════════════════════════════════════════════════════════

class LoteEnAreaModelTests(TestCase):

    def setUp(self):
        self.area, self.producto, self.stock = crear_escenario_base()

    def _lote(self, dias_offset, cantidad=5):
        return LoteEnArea.objects.create(
            stock=self.stock,
            cantidad=cantidad,
            fecha_vencimiento=date.today() + timedelta(days=dias_offset),
        )

    def test_vencido_con_fecha_pasada(self):
        lote = self._lote(-1)
        self.assertTrue(lote.vencido)

    def test_no_vencido_con_fecha_futura(self):
        lote = self._lote(10)
        self.assertFalse(lote.vencido)

    def test_vence_pronto_dentro_de_30_dias(self):
        lote = self._lote(15)
        self.assertTrue(lote.vence_pronto)

    def test_vence_pronto_false_despues_de_30_dias(self):
        lote = self._lote(45)
        self.assertFalse(lote.vence_pronto)

    def test_vence_en_dias_custom(self):
        lote = self._lote(10)
        self.assertTrue(lote.vence_en_dias(15))
        self.assertFalse(lote.vence_en_dias(5))

    def test_vencido_no_es_vence_pronto(self):
        """Un lote ya vencido no debe contar como 'vence_pronto'."""
        lote = self._lote(-5)
        self.assertTrue(lote.vencido)
        self.assertFalse(lote.vence_pronto)

    def test_sin_fecha_vencimiento(self):
        lote = LoteEnArea.objects.create(stock=self.stock, cantidad=3)
        self.assertFalse(lote.vencido)
        self.assertFalse(lote.vence_pronto)


# ══════════════════════════════════════════════════════════════
# 2. Tests de API – registrar_movimiento
# ══════════════════════════════════════════════════════════════

class ApiRegistrarMovimientoTests(TestCase):

    def setUp(self):
        self.user = crear_usuario()
        self.client.login(username='user_jefe_servicio', password='testpass123')
        self.area, self.producto, self.stock = crear_escenario_base()

    def _post(self, payload):
        return self.client.post(
            URL_MOV,
            data=json.dumps(payload),
            content_type='application/json',
        )

    # -- Entrada --

    def test_entrada_crea_lote_y_actualiza_stock(self):
        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'entrada',
            'cantidad': 5,
            'fecha_vencimiento': str(date.today() + timedelta(days=90)),
        })
        self.assertEqual(resp.status_code, 200)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad, 5)
        self.assertEqual(LoteEnArea.objects.filter(stock=self.stock, activo=True).count(), 1)

    def test_entrada_sin_fecha_vencimiento_crea_lote_sin_fecha(self):
        """Backend acepta entradas sin fecha; la validación es en el frontend."""
        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'entrada',
            'cantidad': 3,
        })
        self.assertEqual(resp.status_code, 200)
        lote = LoteEnArea.objects.get(stock=self.stock)
        self.assertIsNone(lote.fecha_vencimiento)

    def test_entrada_acumula_lote_existente(self):
        """Segunda entrada con mismo lote/vencimiento acumula en el mismo LoteEnArea."""
        venc = str(date.today() + timedelta(days=60))
        self._post({'codigo_barras': 'TEST-0001', 'area_id': self.area.id,
                    'tipo': 'entrada', 'cantidad': 3, 'fecha_vencimiento': venc,
                    'numero_lote': 'L001'})
        self._post({'codigo_barras': 'TEST-0001', 'area_id': self.area.id,
                    'tipo': 'entrada', 'cantidad': 2, 'fecha_vencimiento': venc,
                    'numero_lote': 'L001'})
        self.assertEqual(LoteEnArea.objects.filter(stock=self.stock).count(), 1)
        lote = LoteEnArea.objects.get(stock=self.stock)
        self.assertEqual(lote.cantidad, 5)

    # -- Salida FEFO --

    def test_salida_fefo_consume_lote_mas_proximo(self):
        """FEFO: la salida debe descontar del lote que vence antes."""
        pronto = LoteEnArea.objects.create(
            stock=self.stock, cantidad=5,
            fecha_vencimiento=date.today() + timedelta(days=10))
        lejano = LoteEnArea.objects.create(
            stock=self.stock, cantidad=5,
            fecha_vencimiento=date.today() + timedelta(days=90))
        self.stock.cantidad = 10
        self.stock.save()

        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'uso',
            'cantidad': 3,
        })
        self.assertEqual(resp.status_code, 200)
        pronto.refresh_from_db()
        lejano.refresh_from_db()
        self.assertEqual(pronto.cantidad, 2)  # descontó del más próximo
        self.assertEqual(lejano.cantidad, 5)  # intacto

    def test_salida_falla_sin_stock_suficiente(self):
        self.stock.cantidad = 0
        self.stock.save()
        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'uso',
            'cantidad': 1,
        })
        self.assertNotEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('error', data)

    # -- Descarte --

    def test_descarte_requiere_motivo(self):
        LoteEnArea.objects.create(stock=self.stock, cantidad=3, activo=True)
        self.stock.cantidad = 3
        self.stock.save()
        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'descarte',
            'cantidad': 1,
            'observacion': '',
        })
        data = resp.json()
        self.assertIn('error', data)
        self.assertIn('motivo', data['error'].lower())

    def test_descarte_con_lote_id_resuelve_producto_y_area(self):
        """Descarte enviando solo lote_id (sin codigo_barras ni area_id)."""
        lote = LoteEnArea.objects.create(
            stock=self.stock, cantidad=3, activo=True,
            fecha_vencimiento=date.today() - timedelta(days=1))
        self.stock.cantidad = 3
        self.stock.save()

        resp = self._post({
            'lote_id': lote.id,
            'tipo': 'descarte',
            'cantidad': 3,
            'observacion': 'Lote vencido, auditoría',
        })
        self.assertEqual(resp.status_code, 200, resp.json())
        lote.refresh_from_db()
        self.assertEqual(lote.cantidad, 0)
        self.assertFalse(lote.activo)

    # -- Permisos --

    def test_usuario_sin_rol_no_puede_registrar(self):
        u = User.objects.create_user(username='sin_rol', password='testpass123')
        u.perfil_completo = True  # pasa el middleware, falla en _check_rol
        u.save()
        self.client.login(username='sin_rol', password='testpass123')
        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'entrada',
            'cantidad': 1,
        })
        self.assertEqual(resp.status_code, 403)

    def test_usuario_no_autorizado_no_puede_descartar(self):
        """Solo roles en ROLES_PUEDEN_DESCARTAR pueden registrar descartes."""
        crear_usuario(rol='medico_residente', username='residente')
        self.client.login(username='residente', password='testpass123')
        lote = LoteEnArea.objects.create(stock=self.stock, cantidad=5, activo=True)
        self.stock.cantidad = 5
        self.stock.save()
        resp = self._post({
            'codigo_barras': 'TEST-0001',
            'area_id': self.area.id,
            'tipo': 'descarte',
            'cantidad': 1,
            'observacion': 'intento no autorizado',
        })
        self.assertEqual(resp.status_code, 403)


# ══════════════════════════════════════════════════════════════
# 3. Tests de vista – vencimientos
# ══════════════════════════════════════════════════════════════

class VencimientosViewTests(TestCase):

    def setUp(self):
        self.user = crear_usuario()
        self.client.login(username='user_jefe_servicio', password='testpass123')
        self.area, self.producto, self.stock = crear_escenario_base()

    def test_vencidos_aparecen_en_lista(self):
        lote = LoteEnArea.objects.create(
            stock=self.stock, cantidad=2, activo=True,
            fecha_vencimiento=date.today() - timedelta(days=5))
        self.stock.cantidad = 2
        self.stock.save()
        resp = self.client.get(URL_VENC + '?dias=90')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(lote, [i['lote'] for i in resp.context['items']])

    def test_lote_sin_stock_no_aparece(self):
        """cantidad=0 no debe aparecer aunque esté dentro del período."""
        lote = LoteEnArea.objects.create(
            stock=self.stock, cantidad=0, activo=True,
            fecha_vencimiento=date.today() - timedelta(days=1))
        resp = self.client.get(URL_VENC + '?dias=90')
        lotes_en_lista = [i['lote'] for i in resp.context['items']]
        self.assertNotIn(lote, lotes_en_lista)

    def test_lote_sin_fecha_vencimiento_no_aparece(self):
        LoteEnArea.objects.create(stock=self.stock, cantidad=5, activo=True)
        self.stock.cantidad = 5
        self.stock.save()
        resp = self.client.get(URL_VENC + '?dias=90')
        self.assertEqual(len(resp.context['items']), 0)

    def test_superuser_puede_descartar(self):
        su = User.objects.create_superuser(username='admin', password='adminpass')
        self.client.login(username='admin', password='adminpass')
        resp = self.client.get(URL_VENC)
        self.assertTrue(resp.context['puede_descartar'])

    def test_rol_sin_permiso_no_puede_descartar(self):
        crear_usuario(rol='medico_residente', username='residente2')
        self.client.login(username='residente2', password='testpass123')
        resp = self.client.get(URL_VENC)
        self.assertFalse(resp.context['puede_descartar'])

    def test_lote_lejano_no_aparece_con_filtro_corto(self):
        """Lote a 60 días no aparece cuando el filtro es 30 días."""
        LoteEnArea.objects.create(
            stock=self.stock, cantidad=3, activo=True,
            fecha_vencimiento=date.today() + timedelta(days=60))
        self.stock.cantidad = 3
        self.stock.save()
        resp = self.client.get(URL_VENC + '?dias=30')
        self.assertEqual(len(resp.context['items']), 0)


# ══════════════════════════════════════════════════════════════
# 4. Tests de API – reportar y descarte masivo
# ══════════════════════════════════════════════════════════════

class ApiReportarDescarteMasivoTests(TestCase):

    def setUp(self):
        self.user = crear_usuario()
        self.client.login(username='user_jefe_servicio', password='testpass123')
        self.area, self.producto, self.stock = crear_escenario_base()
        self.lote = LoteEnArea.objects.create(
            stock=self.stock, cantidad=3, activo=True,
            fecha_vencimiento=date.today() - timedelta(days=1))
        self.stock.cantidad = 3
        self.stock.save()

    def _post(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type='application/json')

    def test_reportar_lote_marca_campo(self):
        resp = self._post(URL_REPORTAR, {'lote_id': self.lote.id})
        self.assertEqual(resp.status_code, 200)
        self.lote.refresh_from_db()
        self.assertTrue(self.lote.reportado_para_descarte)

    def test_reportar_guarda_usuario_y_fecha(self):
        self._post(URL_REPORTAR, {'lote_id': self.lote.id})
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.reportado_por, self.user)
        self.assertIsNotNone(self.lote.reportado_en)

    def test_descarte_masivo_descarta_lotes(self):
        resp = self._post(URL_DESCARTE, {
            'lote_ids': [self.lote.id],
            'observacion': 'Auditoría mensual de vencidos',
        })
        self.assertEqual(resp.status_code, 200)
        self.lote.refresh_from_db()
        self.assertFalse(self.lote.activo)
        self.assertEqual(self.lote.cantidad, 0)

    def test_descarte_masivo_crea_movimiento(self):
        self._post(URL_DESCARTE, {
            'lote_ids': [self.lote.id],
            'observacion': 'Test descarte',
        })
        self.assertTrue(
            MovimientoStock.objects.filter(
                lote=self.lote, tipo='descarte').exists())

    def test_descarte_masivo_requiere_motivo(self):
        resp = self._post(URL_DESCARTE, {'lote_ids': [self.lote.id], 'observacion': ''})
        data = resp.json()
        self.assertIn('error', data)

    def test_descarte_masivo_sin_permiso_retorna_403(self):
        crear_usuario(rol='medico_residente', username='res3')
        self.client.login(username='res3', password='testpass123')
        resp = self._post(URL_DESCARTE, {
            'lote_ids': [self.lote.id],
            'motivo': 'test',
        })
        self.assertEqual(resp.status_code, 403)
