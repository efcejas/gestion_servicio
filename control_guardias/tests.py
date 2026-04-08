import datetime

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import (
    AsignacionGuardia,
    AusenciaResidente,
    ConfiguracionTipoGuardia,
    CuotaMensualGuardia,
    Feriado,
    NotificacionGuardia,
    SolicitudCambioGuardia,
)

User = get_user_model()


def crear_residente(username='residente1', anio='R1'):
    return User.objects.create_user(
        username=username,
        password='testpass123',
        first_name='Juan',
        last_name='Pérez',
        rol='medico_residente',
        anio_residencia=anio,
        perfil_completo=True,
    )


def crear_tipo_guardia(nombre='Guardia nocturna', creado_por=None):
    return ConfiguracionTipoGuardia.objects.create(
        nombre=nombre,
        hora_inicio=datetime.time(20, 0),
        hora_fin=datetime.time(8, 0),
        dias_semana='L,M,X,J,V',
        creado_por=creado_por,
    )


class ConfiguracionTipoGuardiaTest(TestCase):
    def test_str_incluye_nombre_y_horario(self):
        tipo = crear_tipo_guardia()
        self.assertIn('Guardia nocturna', str(tipo))
        self.assertIn('20:00', str(tipo))

    def test_duracion_horas_turno_nocturno(self):
        tipo = crear_tipo_guardia()
        self.assertEqual(tipo.duracion_horas, 12.0)

    def test_duracion_horas_turno_diurno(self):
        tipo = ConfiguracionTipoGuardia.objects.create(
            nombre='Guardia diurna',
            hora_inicio=datetime.time(8, 0),
            hora_fin=datetime.time(20, 0),
            dias_semana='L,M,X,J,V',
        )
        self.assertEqual(tipo.duracion_horas, 12.0)


class FeriadoTest(TestCase):
    def test_crear_feriado(self):
        feriado = Feriado.objects.create(fecha=datetime.date(2026, 5, 25), descripcion='Día de la Patria')
        self.assertEqual(str(feriado), '25/05/2026 - Día de la Patria')

    def test_fecha_unica(self):
        from django.db import IntegrityError
        Feriado.objects.create(fecha=datetime.date(2026, 5, 25))
        with self.assertRaises(IntegrityError):
            Feriado.objects.create(fecha=datetime.date(2026, 5, 25))


class CuotaMensualGuardiaTest(TestCase):
    def test_guardias_efectivas_sin_atenuante(self):
        cuota = CuotaMensualGuardia.objects.create(anio_residencia='R1', guardias_por_mes=8)
        self.assertEqual(cuota.guardias_efectivas, 8)

    def test_guardias_efectivas_con_atenuante(self):
        cuota = CuotaMensualGuardia.objects.create(
            anio_residencia='R4', guardias_por_mes=8, atenuante_porcentaje=25
        )
        self.assertEqual(cuota.guardias_efectivas, 6)

    def test_guardias_efectivas_no_negativas(self):
        cuota = CuotaMensualGuardia.objects.create(
            anio_residencia='R4', guardias_por_mes=4, atenuante_porcentaje=100
        )
        self.assertEqual(cuota.guardias_efectivas, 0)


class AsignacionGuardiaTest(TestCase):
    def setUp(self):
        self.residente = crear_residente()
        self.tipo = crear_tipo_guardia()

    def test_crear_asignacion(self):
        asignacion = AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 10),
        )
        self.assertEqual(asignacion.estado, 'BORRADOR')
        self.assertFalse(asignacion.es_feriado)

    def test_es_feriado_se_asigna_automaticamente(self):
        Feriado.objects.create(fecha=datetime.date(2026, 5, 25))
        asignacion = AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 25),
        )
        self.assertTrue(asignacion.es_feriado)

    def test_unicidad_residente_fecha_tipo(self):
        from django.db import IntegrityError
        AsignacionGuardia.objects.create(
            residente=self.residente, tipo_guardia=self.tipo, fecha=datetime.date(2026, 5, 10)
        )
        with self.assertRaises(IntegrityError):
            AsignacionGuardia.objects.create(
                residente=self.residente, tipo_guardia=self.tipo, fecha=datetime.date(2026, 5, 10)
            )


class NotificacionGuardiaTest(TestCase):
    def setUp(self):
        self.residente = crear_residente()

    def test_crear_notificacion_no_leida(self):
        notif = NotificacionGuardia.objects.create(
            destinatario=self.residente,
            tipo='ASIGNACION',
            mensaje='Te fue asignada una guardia.',
        )
        self.assertFalse(notif.leida)
        self.assertIn('●', str(notif))

    def test_notificacion_leida_muestra_check(self):
        notif = NotificacionGuardia.objects.create(
            destinatario=self.residente,
            tipo='PUBLICACION',
            mensaje='Guardias de mayo publicadas.',
            leida=True,
        )
        self.assertIn('✓', str(notif))


def crear_jefe(username='jefe1'):
    return User.objects.create_user(
        username=username,
        password='testpass123',
        first_name='Ana',
        last_name='López',
        rol='jefe_residentes',
        perfil_completo=True,
    )


# ---------------------------------------------------------------------------
# Fase 2: Tests del módulo de configuración
# ---------------------------------------------------------------------------

class ConfiguracionViewPermisosTest(TestCase):
    """Verifica que solo jefes/instructores/superusers acceden a la configuración."""

    def setUp(self):
        self.residente = crear_residente()
        self.jefe = crear_jefe()
        self.url = reverse('control_guardias:configuracion')

    def test_residente_no_puede_acceder_a_configuracion(self):
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_jefe_puede_acceder_a_configuracion(self):
        self.client.login(username='jefe1', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_anonimo_redirige_a_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)


class TipoGuardiaCRUDTest(TestCase):
    def setUp(self):
        self.jefe = crear_jefe()
        self.client.login(username='jefe1', password='testpass123')

    def test_crear_tipo_guardia(self):
        url = reverse('control_guardias:tipo_guardia_crear')
        data = {
            'nombre': 'Guardia de fin de semana',
            'hora_inicio': '08:00',
            'hora_fin': '20:00',
            'dias': ['S', 'D'],
            'aplica_feriados': True,
            'activo': True,
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('control_guardias:configuracion'))
        self.assertTrue(ConfiguracionTipoGuardia.objects.filter(nombre='Guardia de fin de semana').exists())
        tipo = ConfiguracionTipoGuardia.objects.get(nombre='Guardia de fin de semana')
        self.assertEqual(tipo.dias_semana, 'S,D')
        self.assertEqual(tipo.creado_por, self.jefe)

    def test_editar_tipo_guardia(self):
        tipo = crear_tipo_guardia(creado_por=self.jefe)
        url = reverse('control_guardias:tipo_guardia_editar', kwargs={'pk': tipo.pk})
        data = {
            'nombre': 'Guardia nocturna actualizada',
            'hora_inicio': '21:00',
            'hora_fin': '07:00',
            'dias': ['L', 'M', 'X'],
            'aplica_feriados': False,
            'activo': True,
        }
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('control_guardias:configuracion'))
        tipo.refresh_from_db()
        self.assertEqual(tipo.nombre, 'Guardia nocturna actualizada')
        self.assertEqual(tipo.dias_semana, 'L,M,X')

    def test_residente_no_puede_crear_tipo(self):
        residente = crear_residente()
        self.client.logout()
        self.client.login(username='residente1', password='testpass123')
        url = reverse('control_guardias:tipo_guardia_crear')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class FeriadoCRUDTest(TestCase):
    def setUp(self):
        self.jefe = crear_jefe()
        self.client.login(username='jefe1', password='testpass123')

    def test_crear_feriado_desde_configuracion(self):
        url = reverse('control_guardias:feriado_crear')
        data = {'fecha': '2026-10-12', 'descripcion': 'Día de la Hispanidad'}
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('control_guardias:configuracion') + '?tab=feriados')
        self.assertTrue(Feriado.objects.filter(fecha=datetime.date(2026, 10, 12)).exists())

    def test_eliminar_feriado(self):
        feriado = Feriado.objects.create(fecha=datetime.date(2026, 11, 20), descripcion='Test')
        url = reverse('control_guardias:feriado_eliminar', kwargs={'pk': feriado.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('control_guardias:configuracion') + '?tab=feriados')
        self.assertFalse(Feriado.objects.filter(pk=feriado.pk).exists())

    def test_crear_feriado_duplicado_falla(self):
        Feriado.objects.create(fecha=datetime.date(2026, 5, 25), descripcion='Original')
        url = reverse('control_guardias:feriado_crear')
        data = {'fecha': '2026-05-25', 'descripcion': 'Duplicado'}
        response = self.client.post(url, data)
        # Debe volver al formulario con error (no redirect)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feriado.objects.filter(fecha=datetime.date(2026, 5, 25)).count(), 1)


class CuotaMensualUpdateTest(TestCase):
    def setUp(self):
        self.jefe = crear_jefe()
        self.client.login(username='jefe1', password='testpass123')
        self.cuota = CuotaMensualGuardia.objects.create(
            anio_residencia='R3', guardias_por_mes=6, atenuante_porcentaje=0
        )

    def test_actualizar_cuota(self):
        url = reverse('control_guardias:cuota_editar', kwargs={'anio': self.cuota.anio_residencia})
        data = {'guardias_por_mes': 5, 'atenuante_porcentaje': '10.00'}
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('control_guardias:configuracion') + '?tab=cuotas')
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.guardias_por_mes, 5)
        self.assertEqual(self.cuota.guardias_efectivas, 4)  # 5 * (1 - 0.10) = 4.5 → int = 4


# ---------------------------------------------------------------------------
# Fase 3: Tests del servicio de distribución automática
# ---------------------------------------------------------------------------

from .services import (
    DistribucionError,
    cancelar_borrador,
    generar_distribucion,
    obtener_metricas_mes,
    publicar_borrador,
)


class ServicioDistribucionTest(TestCase):
    """Tests del algoritmo de distribución equitativa de guardias."""

    def setUp(self):
        self.jefe = crear_jefe()
        # 3 residentes R1, R2, R3
        self.r1 = crear_residente('r1', 'R1')
        self.r2 = crear_residente('r2', 'R2')
        self.r3 = crear_residente('r3', 'R3')
        # Tipo de guardia: lunes a viernes, de noche
        self.tipo = ConfiguracionTipoGuardia.objects.create(
            nombre='Guardia nocturna',
            hora_inicio=datetime.time(20, 0),
            hora_fin=datetime.time(8, 0),
            dias_semana='L,M,X,J,V',
            aplica_feriados=False,
        )
        # Cuotas: R1=3, R2=2, R3=2
        CuotaMensualGuardia.objects.create(anio_residencia='R1', guardias_por_mes=3)
        CuotaMensualGuardia.objects.create(anio_residencia='R2', guardias_por_mes=2)
        CuotaMensualGuardia.objects.create(anio_residencia='R3', guardias_por_mes=2)

    def test_distribucion_genera_borradores(self):
        """El servicio devuelve asignaciones en estado BORRADOR."""
        from .models import ConfiguracionTipoGuardia as CTG
        resultado = generar_distribucion(
            mes=5, anio=2026,
            tipos_guardia=CTG.objects.filter(pk=self.tipo.pk),
            creado_por=self.jefe,
        )
        self.assertGreater(resultado['asignaciones_creadas'], 0)
        borradores = AsignacionGuardia.objects.filter(estado='BORRADOR')
        self.assertEqual(borradores.count(), resultado['asignaciones_creadas'])

    def test_distribucion_respeta_cuota_maxima(self):
        """Ningún residente supera su cuota mensual."""
        from .models import ConfiguracionTipoGuardia as CTG
        generar_distribucion(
            mes=5, anio=2026,
            tipos_guardia=CTG.objects.filter(pk=self.tipo.pk),
            creado_por=self.jefe,
        )
        self.assertLessEqual(
            AsignacionGuardia.objects.filter(residente=self.r1, estado='BORRADOR').count(), 3
        )
        self.assertLessEqual(
            AsignacionGuardia.objects.filter(residente=self.r2, estado='BORRADOR').count(), 2
        )
        self.assertLessEqual(
            AsignacionGuardia.objects.filter(residente=self.r3, estado='BORRADOR').count(), 2
        )

    def test_distribucion_sin_dias_consecutivos(self):
        """Ningún residente tiene guardias en dos días consecutivos."""
        from .models import ConfiguracionTipoGuardia as CTG
        generar_distribucion(
            mes=5, anio=2026,
            tipos_guardia=CTG.objects.filter(pk=self.tipo.pk),
            creado_por=self.jefe,
        )
        for residente in [self.r1, self.r2, self.r3]:
            fechas = sorted(
                AsignacionGuardia.objects.filter(
                    residente=residente, estado='BORRADOR'
                ).values_list('fecha', flat=True)
            )
            for i in range(len(fechas) - 1):
                delta = (fechas[i + 1] - fechas[i]).days
                self.assertNotEqual(delta, 1,
                    msg=f"{residente.username} tiene guardias consecutivas: {fechas[i]} y {fechas[i+1]}")

    def test_sin_residentes_lanza_error(self):
        """DistribucionError si no hay residentes activos."""
        User.objects.filter(rol='medico_residente').update(is_active=False)
        from .models import ConfiguracionTipoGuardia as CTG
        with self.assertRaises(DistribucionError):
            generar_distribucion(
                mes=5, anio=2026,
                tipos_guardia=CTG.objects.filter(pk=self.tipo.pk),
                creado_por=self.jefe,
            )

    def test_borrador_existente_sin_reemplazar_lanza_error(self):
        """Error si ya hay borradores y no se solicitó reemplazar."""
        from .models import ConfiguracionTipoGuardia as CTG
        qs = CTG.objects.filter(pk=self.tipo.pk)
        generar_distribucion(mes=5, anio=2026, tipos_guardia=qs, creado_por=self.jefe)
        with self.assertRaises(DistribucionError):
            generar_distribucion(mes=5, anio=2026, tipos_guardia=qs, creado_por=self.jefe)

    def test_reemplazar_borradores(self):
        """Con reemplazar=True, elimina el borrador anterior y genera uno nuevo."""
        from .models import ConfiguracionTipoGuardia as CTG
        qs = CTG.objects.filter(pk=self.tipo.pk)
        generar_distribucion(mes=5, anio=2026, tipos_guardia=qs, creado_por=self.jefe)
        count_primera = AsignacionGuardia.objects.filter(estado='BORRADOR').count()
        # Segunda corrida con reemplazar=True
        generar_distribucion(mes=5, anio=2026, tipos_guardia=qs, creado_por=self.jefe,
                             reemplazar_borradores=True)
        count_segunda = AsignacionGuardia.objects.filter(estado='BORRADOR').count()
        # Deben existir borradores y no haberse duplicado
        self.assertGreater(count_segunda, 0)
        self.assertLessEqual(count_segunda, count_primera + 2)


# ---------------------------------------------------------------------------
# Fase 4: Calendario FullCalendar
# ---------------------------------------------------------------------------

class CalendarioViewTests(TestCase):
    """Tests de la vista del calendario y la API de eventos."""

    def setUp(self):
        self.residente = crear_residente('res_cal', 'R2')
        self.jefe = crear_jefe('jefe_cal')
        self.tipo = ConfiguracionTipoGuardia.objects.create(
            nombre='Noche',
            hora_inicio=datetime.time(20, 0),
            hora_fin=datetime.time(8, 0),
            dias_semana='L,M,X,J,V',
            activo=True,
            creado_por=self.jefe,
        )
        # Una guardia publicada del residente
        self.guardia_pub = AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 4),
            estado='PUBLICADA',
            creada_por=self.jefe,
        )
        # Una guardia borrador del residente
        self.guardia_bor = AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 5),
            estado='BORRADOR',
            creada_por=self.jefe,
        )

    # ── Vista del calendario ─────────────────────────────────────────────────

    def test_calendario_requiere_login(self):
        """Redirige a login si no authenticated."""
        url = reverse('control_guardias:calendario')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])

    def test_residente_puede_ver_calendario(self):
        """Residente autenticado ve el calendario (200 OK)."""
        self.client.force_login(self.residente)
        response = self.client.get(reverse('control_guardias:calendario'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'calendar')

    def test_jefe_puede_ver_calendario(self):
        """Jefe autenticado ve el calendario con selector de residente."""
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('control_guardias:calendario'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'filtroResidente')

    def test_residente_no_ve_selector_de_residente(self):
        """El <select> de residente no se renderiza para residentes (solo el JS lo referencia)."""
        self.client.force_login(self.residente)
        response = self.client.get(reverse('control_guardias:calendario'))
        self.assertNotContains(response, '<select id="filtroResidente"')

    # ── API de eventos ───────────────────────────────────────────────────────

    def test_api_residente_solo_ve_sus_publicadas(self):
        """Residente en la API solo obtiene sus guardias PUBLICADAS."""
        self.client.force_login(self.residente)
        response = self.client.get(reverse('control_guardias:guardias_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [ev['id'] for ev in data]
        # Debe ver la publicada
        self.assertIn(str(self.guardia_pub.pk), ids)
        # NO debe ver el borrador
        self.assertNotIn(str(self.guardia_bor.pk), ids)

    def test_api_jefe_ve_publicadas_y_borradores(self):
        """Jefe en la API ve PUBLICADAS y BORRADORES."""
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('control_guardias:guardias_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [ev['id'] for ev in data]
        self.assertIn(str(self.guardia_pub.pk), ids)
        self.assertIn(str(self.guardia_bor.pk), ids)

    def test_api_jefe_puede_filtrar_por_residente(self):
        """Jefe puede filtrar la API por residente_id."""
        otro_residente = crear_residente('otro_res', 'R3')
        guardia_otro = AsignacionGuardia.objects.create(
            residente=otro_residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 6),
            estado='PUBLICADA',
            creada_por=self.jefe,
        )
        self.client.force_login(self.jefe)
        url = reverse('control_guardias:guardias_api') + f'?residente_id={self.residente.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [ev['id'] for ev in data]
        # Solo ve las del residente filtrado
        self.assertIn(str(self.guardia_pub.pk), ids)
        self.assertNotIn(str(guardia_otro.pk), ids)

    def test_api_colores_por_estado(self):
        """BORRADOR es gris, PUBLICADA feriado es ámbar, PUBLICADA normal es azul."""
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('control_guardias:guardias_api'))
        data = response.json()
        por_id = {ev['id']: ev for ev in data}
        # Borrador → gris
        self.assertEqual(por_id[str(self.guardia_bor.pk)]['backgroundColor'], '#6b7280')
        # Publicada normal → azul
        self.assertEqual(por_id[str(self.guardia_pub.pk)]['backgroundColor'], '#3b82f6')

    def test_api_requiere_autenticacion(self):
        """API redirige si no autenticado."""
        response = self.client.get(reverse('control_guardias:guardias_api'))
        self.assertEqual(response.status_code, 302)


class ServicioPublicarCancelarTest(TestCase):
    def setUp(self):
        self.jefe = crear_jefe()
        self.residente = crear_residente()
        self.tipo = ConfiguracionTipoGuardia.objects.create(
            nombre='Guardia test',
            hora_inicio=datetime.time(20, 0),
            hora_fin=datetime.time(8, 0),
            dias_semana='L,M,X,J,V',
        )
        # Crear 3 borradores manualmente
        for dia in [6, 7, 8]:
            AsignacionGuardia.objects.create(
                residente=self.residente,
                tipo_guardia=self.tipo,
                fecha=datetime.date(2026, 5, dia),
                estado='BORRADOR',
                creada_por=self.jefe,
            )

    def test_publicar_borrador_cambia_estado(self):
        count = publicar_borrador(5, 2026)
        self.assertEqual(count, 3)
        self.assertEqual(AsignacionGuardia.objects.filter(estado='PUBLICADA').count(), 3)
        self.assertEqual(AsignacionGuardia.objects.filter(estado='BORRADOR').count(), 0)

    def test_cancelar_borrador_elimina_asignaciones(self):
        count = cancelar_borrador(5, 2026)
        self.assertEqual(count, 3)
        self.assertEqual(AsignacionGuardia.objects.filter(estado='BORRADOR').count(), 0)

    def test_publicar_no_afecta_otros_meses(self):
        # Agregar un borrador de otro mes
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 6, 1),
            estado='BORRADOR',
            creada_por=self.jefe,
        )
        publicar_borrador(5, 2026)
        # El de junio sigue en borrador
        self.assertTrue(
            AsignacionGuardia.objects.filter(estado='BORRADOR', fecha__month=6).exists()
        )


class DistribucionViewTest(TestCase):
    """Tests de permisos y flujo básico de la vista de distribución."""

    def setUp(self):
        self.jefe = crear_jefe()
        self.residente = crear_residente()
        self.url = reverse('control_guardias:distribucion')

    def test_residente_no_puede_acceder(self):
        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_jefe_puede_acceder(self):
        self.client.login(username='jefe1', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Generar distribución')


# ---------------------------------------------------------------------------
# Fase 5: Tests de Ausencias y Cambios de guardia
# ---------------------------------------------------------------------------

def crear_guardia_publicada(residente, fecha, tipo=None, jefe=None):
    """Helper: crea una AsignacionGuardia en estado PUBLICADA."""
    if tipo is None:
        tipo = crear_tipo_guardia(creado_por=jefe)
    return AsignacionGuardia.objects.create(
        residente=residente,
        tipo_guardia=tipo,
        fecha=fecha,
        estado='PUBLICADA',
    )


class ReportarAusenciaServiceTest(TestCase):
    """Tests de la función reportar_ausencia() en services.py."""

    def setUp(self):
        from .services import reportar_ausencia
        self.reportar_ausencia = reportar_ausencia
        self.jefe = crear_jefe()
        self.residente = crear_residente()
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        self.hoy = datetime.date.today()

    def test_crea_ausencia_con_estado_pendiente(self):
        ausencia = self.reportar_ausencia(
            self.residente,
            self.hoy,
            self.hoy + datetime.timedelta(days=2),
            'ENFERMEDAD',
        )
        self.assertEqual(ausencia.estado, 'PENDIENTE')
        self.assertEqual(ausencia.residente, self.residente)

    def test_vincula_guardias_publicadas_en_rango(self):
        g1 = crear_guardia_publicada(self.residente, self.hoy, tipo=self.tipo)
        g2 = crear_guardia_publicada(self.residente, self.hoy + datetime.timedelta(days=1), tipo=self.tipo)
        # Guardia fuera del rango
        crear_guardia_publicada(self.residente, self.hoy + datetime.timedelta(days=5), tipo=self.tipo)

        ausencia = self.reportar_ausencia(
            self.residente,
            self.hoy,
            self.hoy + datetime.timedelta(days=1),
            'ENFERMEDAD',
        )
        pks = list(ausencia.guardias_afectadas.values_list('pk', flat=True))
        self.assertIn(g1.pk, pks)
        self.assertIn(g2.pk, pks)
        self.assertEqual(len(pks), 2)

    def test_notifica_a_gestores(self):
        self.reportar_ausencia(
            self.residente,
            self.hoy,
            self.hoy,
            'PERSONAL',
        )
        self.assertTrue(
            NotificacionGuardia.objects.filter(destinatario=self.jefe).exists()
        )


class ResolverAusenciaServiceTest(TestCase):
    """Tests de la función resolver_ausencia()."""

    def setUp(self):
        from .services import reportar_ausencia, resolver_ausencia
        self.reportar = reportar_ausencia
        self.resolver = resolver_ausencia
        self.jefe = crear_jefe()
        self.residente = crear_residente()
        self.hoy = datetime.date.today()

    def test_cambia_estado_a_resuelta(self):
        ausencia = self.reportar(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.resolver(ausencia, self.jefe)
        ausencia.refresh_from_db()
        self.assertEqual(ausencia.estado, 'RESUELTA')
        self.assertEqual(ausencia.resuelta_por, self.jefe)

    def test_notifica_al_residente(self):
        ausencia = self.reportar(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.resolver(ausencia, self.jefe)
        self.assertTrue(
            NotificacionGuardia.objects.filter(destinatario=self.residente).exists()
        )


class SolicitarCambioServiceTest(TestCase):
    """Tests de la función solicitar_cambio()."""

    def setUp(self):
        from .services import solicitar_cambio, CambioGuardiaError
        self.solicitar_cambio = solicitar_cambio
        self.CambioGuardiaError = CambioGuardiaError
        self.jefe = crear_jefe()
        self.residente1 = crear_residente('res1')
        self.residente2 = crear_residente('res2')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        self.hoy = datetime.date.today()
        self.g1 = crear_guardia_publicada(self.residente1, self.hoy, tipo=self.tipo)
        self.g2 = crear_guardia_publicada(self.residente2, self.hoy + datetime.timedelta(days=1), tipo=self.tipo)

    def test_crea_solicitud_pendiente_receptor(self):
        solicitud = self.solicitar_cambio(self.residente1, self.g1, self.g2)
        self.assertEqual(solicitud.estado, 'PENDIENTE_RECEPTOR')
        self.assertEqual(solicitud.solicitante, self.residente1)
        self.assertEqual(solicitud.receptor, self.residente2)

    def test_notifica_al_receptor(self):
        self.solicitar_cambio(self.residente1, self.g1, self.g2)
        self.assertTrue(
            NotificacionGuardia.objects.filter(destinatario=self.residente2).exists()
        )

    def test_error_si_guardia_no_es_del_solicitante(self):
        with self.assertRaises(self.CambioGuardiaError):
            self.solicitar_cambio(self.residente1, self.g2, self.g1)

    def test_error_si_misma_guardia(self):
        with self.assertRaises(self.CambioGuardiaError):
            self.solicitar_cambio(self.residente1, self.g1, self.g1)

    def test_error_si_guardia_no_publicada(self):
        self.g1.estado = 'BORRADOR'
        self.g1.save()
        with self.assertRaises(self.CambioGuardiaError):
            self.solicitar_cambio(self.residente1, self.g1, self.g2)


class FlujoCambioCompletoTest(TestCase):
    """Test del flujo completo: PENDIENTE_RECEPTOR → PENDIENTE_JEFE → APROBADA."""

    def setUp(self):
        from .services import (
            solicitar_cambio, aceptar_cambio_receptor, aprobar_cambio,
        )
        self.solicitar = solicitar_cambio
        self.aceptar = aceptar_cambio_receptor
        self.aprobar = aprobar_cambio
        self.jefe = crear_jefe()
        self.residente1 = crear_residente('res1')
        self.residente2 = crear_residente('res2')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        hoy = datetime.date.today()
        self.g1 = crear_guardia_publicada(self.residente1, hoy, tipo=self.tipo)
        self.g2 = crear_guardia_publicada(self.residente2, hoy + datetime.timedelta(days=1), tipo=self.tipo)

    def test_flujo_completo_aprobacion(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.aceptar(solicitud, self.residente2)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'PENDIENTE_JEFE')

        self.aprobar(solicitud, self.jefe, notas='OK')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'APROBADA')
        self.assertEqual(solicitud.revisado_por, self.jefe)

    def test_aprobacion_intercambia_residentes(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.aceptar(solicitud, self.residente2)
        self.aprobar(solicitud, self.jefe)

        self.g1.refresh_from_db()
        self.g2.refresh_from_db()
        self.assertEqual(self.g1.residente, self.residente2)
        self.assertEqual(self.g2.residente, self.residente1)

    def test_aprobacion_notifica_a_ambos_residentes(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.aceptar(solicitud, self.residente2)
        self.aprobar(solicitud, self.jefe)

        self.assertTrue(NotificacionGuardia.objects.filter(
            destinatario=self.residente1, tipo='CAMBIO_APROBADO').exists())
        self.assertTrue(NotificacionGuardia.objects.filter(
            destinatario=self.residente2, tipo='CAMBIO_APROBADO').exists())


class RechazarCambioTest(TestCase):
    """Tests de rechazo por receptor y por jefe."""

    def setUp(self):
        from .services import (
            solicitar_cambio, aceptar_cambio_receptor,
            rechazar_cambio_receptor, rechazar_cambio_jefe, CambioGuardiaError,
        )
        self.solicitar = solicitar_cambio
        self.aceptar = aceptar_cambio_receptor
        self.rechazar_receptor = rechazar_cambio_receptor
        self.rechazar_jefe = rechazar_cambio_jefe
        self.CambioGuardiaError = CambioGuardiaError
        self.jefe = crear_jefe()
        self.residente1 = crear_residente('res1')
        self.residente2 = crear_residente('res2')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        hoy = datetime.date.today()
        self.g1 = crear_guardia_publicada(self.residente1, hoy, tipo=self.tipo)
        self.g2 = crear_guardia_publicada(self.residente2, hoy + datetime.timedelta(days=1), tipo=self.tipo)

    def test_receptor_rechaza_queda_rechazada(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.rechazar_receptor(solicitud, self.residente2)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'RECHAZADA')

    def test_receptor_rechaza_notifica_solicitante(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.rechazar_receptor(solicitud, self.residente2)
        self.assertTrue(NotificacionGuardia.objects.filter(
            destinatario=self.residente1, tipo='CAMBIO_RECHAZADO').exists())

    def test_jefe_rechaza_queda_rechazada(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.aceptar(solicitud, self.residente2)
        self.rechazar_jefe(solicitud, self.jefe, notas='No procede')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'RECHAZADA')
        self.assertEqual(solicitud.notas_jefe, 'No procede')

    def test_error_receptor_incorrecto(self):
        otro = crear_residente('otro')
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        with self.assertRaises(self.CambioGuardiaError):
            self.rechazar_receptor(solicitud, otro)


class CancelarCambioTest(TestCase):
    """Tests de cancelación por el solicitante."""

    def setUp(self):
        from .services import solicitar_cambio, cancelar_cambio, CambioGuardiaError
        self.solicitar = solicitar_cambio
        self.cancelar = cancelar_cambio
        self.CambioGuardiaError = CambioGuardiaError
        self.jefe = crear_jefe()
        self.residente1 = crear_residente('res1')
        self.residente2 = crear_residente('res2')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        hoy = datetime.date.today()
        self.g1 = crear_guardia_publicada(self.residente1, hoy, tipo=self.tipo)
        self.g2 = crear_guardia_publicada(self.residente2, hoy + datetime.timedelta(days=1), tipo=self.tipo)

    def test_solicitante_puede_cancelar_pendiente_receptor(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        self.cancelar(solicitud, self.residente1)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'CANCELADA')

    def test_no_solicitante_no_puede_cancelar(self):
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        with self.assertRaises(self.CambioGuardiaError):
            self.cancelar(solicitud, self.residente2)

    def test_no_cancelar_si_pendiente_jefe(self):
        from .services import aceptar_cambio_receptor
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        aceptar_cambio_receptor(solicitud, self.residente2)
        with self.assertRaises(self.CambioGuardiaError):
            self.cancelar(solicitud, self.residente1)


class AusenciasViewTest(TestCase):
    """Tests de permisos y datos en las vistas de ausencias."""

    def setUp(self):
        self.jefe = crear_jefe()
        self.residente = crear_residente()
        self.otro_residente = crear_residente('otro')
        self.hoy = datetime.date.today()

    def test_residente_ve_solo_sus_ausencias(self):
        from .services import reportar_ausencia
        reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        reportar_ausencia(self.otro_residente, self.hoy, self.hoy, 'ENFERMEDAD')

        self.client.login(username='residente1', password='testpass123')
        response = self.client.get(reverse('control_guardias:ausencias'))
        self.assertEqual(response.status_code, 200)
        ausencias = response.context['ausencias']
        self.assertTrue(all(a.residente == self.residente for a in ausencias))

    def test_jefe_ve_todas_las_ausencias(self):
        from .services import reportar_ausencia
        reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        reportar_ausencia(self.otro_residente, self.hoy, self.hoy, 'ENFERMEDAD')

        self.client.login(username='jefe1', password='testpass123')
        response = self.client.get(reverse('control_guardias:ausencias'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ausencias'].count(), 2)

    def test_residente_reporta_ausencia_via_post(self):
        self.client.login(username='residente1', password='testpass123')
        response = self.client.post(reverse('control_guardias:ausencia_reportar'), {
            'fecha_inicio': self.hoy.isoformat(),
            'fecha_fin': self.hoy.isoformat(),
            'motivo': 'OTRO',
            'descripcion': '',
        })
        self.assertRedirects(response, reverse('control_guardias:ausencias'))
        self.assertTrue(AusenciaResidente.objects.filter(residente=self.residente).exists())

    def test_residente_no_puede_resolver_ausencia(self):
        from .services import reportar_ausencia
        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.client.login(username='residente1', password='testpass123')
        url = reverse('control_guardias:ausencia_resolver', kwargs={'pk': ausencia.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


class CambiosViewTest(TestCase):
    """Tests de permisos y acceso a las vistas de cambios."""

    def setUp(self):
        self.jefe = crear_jefe()
        self.residente1 = crear_residente('res1')
        self.residente2 = crear_residente('res2')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        hoy = datetime.date.today()
        self.g1 = crear_guardia_publicada(self.residente1, hoy, tipo=self.tipo)
        self.g2 = crear_guardia_publicada(self.residente2, hoy + datetime.timedelta(days=1), tipo=self.tipo)

    def test_residente_puede_ver_cambios(self):
        self.client.login(username='res1', password='testpass123')
        response = self.client.get(reverse('control_guardias:cambios'))
        self.assertEqual(response.status_code, 200)

    def test_residente_solicita_cambio_via_view(self):
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:solicitar_cambio', kwargs={'guardia_pk': self.g1.pk})
        response = self.client.post(url, {'guardia_receptor': self.g2.pk})
        self.assertRedirects(response, reverse('control_guardias:cambios'))
        self.assertTrue(SolicitudCambioGuardia.objects.filter(
            solicitante=self.residente1, receptor=self.residente2).exists())

    def test_no_se_puede_solicitar_cambio_de_guardia_ajena(self):
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:solicitar_cambio', kwargs={'guardia_pk': self.g2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

