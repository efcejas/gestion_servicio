import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import (
    AsignacionGuardia,
    AusenciaDocumento,
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

    def test_distribucion_excluye_residente_con_ausencia_en_rango(self):
        """Un residente ausente en el período no debe recibir guardias en ese rango."""
        from .models import ConfiguracionTipoGuardia as CTG

        AusenciaResidente.objects.create(
            residente=self.r1,
            fecha_inicio=datetime.date(2026, 5, 1),
            fecha_fin=datetime.date(2026, 5, 31),
            motivo='LICENCIA',
            descripcion='Ausencia completa del mes para validar exclusión en distribución',
        )

        generar_distribucion(
            mes=5,
            anio=2026,
            tipos_guardia=CTG.objects.filter(pk=self.tipo.pk),
            creado_por=self.jefe,
        )

        self.assertEqual(
            AsignacionGuardia.objects.filter(residente=self.r1, estado='BORRADOR').count(),
            0,
            msg='R1 no debería recibir guardias BORRADOR en mayo por ausencia reportada todo el mes.',
        )

    def test_distribucion_excluye_dentro_de_ausencia_parcial_y_permite_fuera(self):
        """Con ausencia parcial, no asigna dentro del rango y sí puede asignar fuera."""
        from .models import ConfiguracionTipoGuardia as CTG

        # Dejamos solo R1 con cuota para forzar asignaciones fuera del rango ausente.
        CuotaMensualGuardia.objects.filter(anio_residencia__in=['R2', 'R3']).delete()
        CuotaMensualGuardia.objects.filter(anio_residencia='R1').update(guardias_por_mes=5)

        AusenciaResidente.objects.create(
            residente=self.r1,
            fecha_inicio=datetime.date(2026, 5, 11),
            fecha_fin=datetime.date(2026, 5, 20),
            motivo='LICENCIA',
            descripcion='Ausencia parcial para validar exclusión en rango y asignación fuera de rango.',
        )

        generar_distribucion(
            mes=5,
            anio=2026,
            tipos_guardia=CTG.objects.filter(pk=self.tipo.pk),
            creado_por=self.jefe,
        )

        fechas_r1 = list(
            AsignacionGuardia.objects.filter(residente=self.r1, estado='BORRADOR')
            .values_list('fecha', flat=True)
        )
        self.assertGreater(
            len(fechas_r1),
            0,
            msg='R1 debería recibir al menos una guardia fuera del rango de ausencia parcial.',
        )
        self.assertTrue(
            all(f < datetime.date(2026, 5, 11) or f > datetime.date(2026, 5, 20) for f in fechas_r1),
            msg='R1 no debe tener guardias BORRADOR entre el 11/05 y el 20/05.',
        )

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

    def test_distribucion_evita_guardias_a_dos_dias_cuando_hay_candidatos_disponibles(self):
        """
        Si hay candidatos sin penalización disponibles, el residente con guardia a 2 días
        de distancia no debería ser elegido para ese slot.

        Escenario controlado:
          - Solo 2 residentes: r1 (ya asignado el lunes 4), r2 (sin asignaciones).
          - Cuota: ambos 1 guardia.
          - El miércoles 6 (2 días después) debe asignarse a r2 y no a r1.
        """
        from .models import ConfiguracionTipoGuardia as CTG

        # Cuota 1 para cada residente en este test
        CuotaMensualGuardia.objects.filter(anio_residencia__in=['R1', 'R2', 'R3']).delete()
        CuotaMensualGuardia.objects.create(anio_residencia='R1', guardias_por_mes=1)
        CuotaMensualGuardia.objects.create(anio_residencia='R2', guardias_por_mes=1)
        CuotaMensualGuardia.objects.create(anio_residencia='R3', guardias_por_mes=0)

        # r1 ya tiene una guardia publicada el lunes 4/mayo
        AsignacionGuardia.objects.create(
            residente=self.r1,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 4),   # lunes
            estado='PUBLICADA',
            creada_por=self.jefe,
        )

        qs = CTG.objects.filter(pk=self.tipo.pk)
        generar_distribucion(mes=5, anio=2026, tipos_guardia=qs, creado_por=self.jefe)

        # r1 agotó su cuota con la guardia publicada y además tiene penalización el miércoles 6
        # r2 tiene cuota disponible y sin penalización → debe ser elegido
        guardia_mie = AsignacionGuardia.objects.filter(
            fecha=datetime.date(2026, 5, 6),   # miércoles
            estado='BORRADOR',
        ).first()
        if guardia_mie:
            self.assertEqual(guardia_mie.residente, self.r2,
                msg="El miércoles 6 debería asignarse a r2 (sin penalización), no a r1 (guardia el lunes 4)")

    def test_distribucion_cercania_es_blanda_asigna_si_no_hay_mejor_candidato(self):
        """
        La penalización por cercanía es BLANDA: si el único candidato disponible
        tiene una guardia a 2 días de distancia, la cuota del residente se completa
        igual. Verifica que la restricción NO actúa como hard block.
        """
        from .models import ConfiguracionTipoGuardia as CTG

        # Solo r1 activo con cuota 5
        self.r2.is_active = False
        self.r2.save()
        self.r3.is_active = False
        self.r3.save()

        CuotaMensualGuardia.objects.filter(anio_residencia='R1').update(guardias_por_mes=5)
        CuotaMensualGuardia.objects.filter(anio_residencia__in=['R2', 'R3']).delete()

        # r1 ya tiene una guardia publicada el lunes 4/mayo;
        # esto creará slots "penalizados por cercanía" el mié 6 y vie 8.
        AsignacionGuardia.objects.create(
            residente=self.r1,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 4),
            estado='PUBLICADA',
            creada_por=self.jefe,
        )

        qs = CTG.objects.filter(pk=self.tipo.pk)
        generar_distribucion(mes=5, anio=2026, tipos_guardia=qs, creado_por=self.jefe)

        # r1 debe recibir su cuota completa de 5 borradores aunque algunos slots
        # estén penalizados por cercanía. La penalización blanda NUNCA debe bloquear
        # un slot cuando r1 es el único candidato disponible.
        asignados = AsignacionGuardia.objects.filter(residente=self.r1, estado='BORRADOR').count()
        self.assertEqual(asignados, 5,
            msg=(
                f"r1 debería recibir 5 borradores (recibió {asignados}). "
                "La penalización por cercanía NO debe actuar como hard block."
            )
        )


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

    def test_residente_ve_toggle_para_guardias_del_servicio(self):
        self.client.force_login(self.residente)
        response = self.client.get(reverse('control_guardias:calendario'))
        self.assertContains(response, 'Mostrar guardias del servicio')

    def test_calendario_recibe_mes_anio_inicial_desde_query(self):
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('control_guardias:calendario'), {'mes': '5', 'anio': '2026'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['calendario_initial_date'], '2026-05-01')

    def test_calendario_query_invalida_no_define_fecha_inicial(self):
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('control_guardias:calendario'), {'mes': '99', 'anio': 'abcd'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['calendario_initial_date'], '')

    def test_calendario_con_return_to_valido_vuelve_al_borrador(self):
        self.client.force_login(self.jefe)
        return_to = reverse('control_guardias:distribucion_borrador', kwargs={'mes': 5, 'anio': 2026})
        response = self.client.get(
            reverse('control_guardias:calendario'),
            {'mes': '5', 'anio': '2026', 'return_to': return_to},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['calendario_return_url'], return_to)
        self.assertEqual(response.context['calendario_back_label'], 'Volver al borrador')

    def test_calendario_con_return_to_invalido_usa_inicio(self):
        self.client.force_login(self.jefe)
        response = self.client.get(
            reverse('control_guardias:calendario'),
            {'return_to': 'https://evil.example/back'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['calendario_return_url'], reverse('control_guardias:index'))
        self.assertEqual(response.context['calendario_back_label'], 'Ir al inicio')

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
        """BORRADOR es gris, PUBLICADA usa color de paleta según pk del residente."""
        from .views import _RESIDENTE_PALETTE
        self.client.force_login(self.jefe)
        response = self.client.get(reverse('control_guardias:guardias_api'))
        data = response.json()
        por_id = {ev['id']: ev for ev in data}
        # Borrador → siempre gris
        self.assertEqual(por_id[str(self.guardia_bor.pk)]['backgroundColor'], '#6b7280')
        # Publicada → color de paleta según pk del residente
        color_esperado = _RESIDENTE_PALETTE[self.residente.pk % len(_RESIDENTE_PALETTE)]
        self.assertEqual(por_id[str(self.guardia_pub.pk)]['backgroundColor'], color_esperado)

    def test_api_residente_puede_ver_todas_las_publicadas_si_lo_pide(self):
        otro_residente = crear_residente('otro_cal', 'R3')
        guardia_otro = AsignacionGuardia.objects.create(
            residente=otro_residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 6),
            estado='PUBLICADA',
            creada_por=self.jefe,
        )

        self.client.force_login(self.residente)
        response = self.client.get(reverse('control_guardias:guardias_api'), {'ver_todas': '1'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [ev['id'] for ev in data]
        self.assertIn(str(self.guardia_pub.pk), ids)
        self.assertIn(str(guardia_otro.pk), ids)
        evento_otro = next(ev for ev in data if ev['id'] == str(guardia_otro.pk))
        self.assertFalse(evento_otro['extendedProps']['es_mia'])

    def test_api_marca_guardia_con_cambio_pendiente(self):
        otro_residente = crear_residente('otro_pend', 'R3')
        guardia_otro = AsignacionGuardia.objects.create(
            residente=otro_residente,
            tipo_guardia=self.tipo,
            fecha=datetime.date(2026, 5, 8),
            estado='PUBLICADA',
            creada_por=self.jefe,
        )
        SolicitudCambioGuardia.objects.create(
            solicitante=self.residente,
            receptor=otro_residente,
            guardia_solicitante=self.guardia_pub,
            guardia_receptor=guardia_otro,
            estado='PENDIENTE_JEFE',
        )

        self.client.force_login(self.residente)
        response = self.client.get(reverse('control_guardias:guardias_api'), {'ver_todas': '1'})
        self.assertEqual(response.status_code, 200)
        data = {ev['id']: ev for ev in response.json()}

        self.assertTrue(data[str(self.guardia_pub.pk)]['extendedProps']['cambio_pendiente'])
        self.assertEqual(
            data[str(self.guardia_pub.pk)]['extendedProps']['cambio_pendiente_label'],
            'Cambio pendiente de aprobación',
        )
        self.assertEqual(data[str(self.guardia_pub.pk)]['backgroundColor'], '#f59e0b')

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

    def test_publicar_crea_notificacion_publicacion_para_residente(self):
        publicar_borrador(5, 2026)
        self.assertTrue(
            NotificacionGuardia.objects.filter(
                destinatario=self.residente,
                tipo='PUBLICACION',
            ).exists()
        )

    def test_publicar_envia_email_si_residente_tiene_mail(self):
        self.residente.email = 'residente_pub@example.com'
        self.residente.save(update_fields=['email'])

        publicar_borrador(5, 2026)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('residente_pub@example.com', mail.outbox[0].to)

    def test_publicar_email_incluye_link_directo_al_sistema(self):
        self.residente.email = 'residente_pub@example.com'
        self.residente.save(update_fields=['email'])

        publicar_borrador(5, 2026)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/control_guardias/mis-guardias/', mail.outbox[0].body)


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

    def test_publicar_borrador_redirige_a_calendario_del_mes_publicado(self):
        self.client.login(username='jefe1', password='testpass123')

        tipo = ConfiguracionTipoGuardia.objects.create(
            nombre='Guardia redireccion',
            hora_inicio=datetime.time(20, 0),
            hora_fin=datetime.time(8, 0),
            dias_semana='L,M,X,J,V',
        )
        AsignacionGuardia.objects.create(
            residente=self.residente,
            tipo_guardia=tipo,
            fecha=datetime.date(2026, 5, 10),
            estado='BORRADOR',
            creada_por=self.jefe,
        )

        url = reverse('control_guardias:distribucion_publicar', kwargs={'mes': 5, 'anio': 2026})
        response = self.client.post(url)
        self.assertRedirects(response, reverse('control_guardias:calendario') + '?mes=5&anio=2026')


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

    def test_envia_email_a_gestor_si_tiene_mail(self):
        self.jefe.email = 'jefe@example.com'
        self.jefe.save(update_fields=['email'])

        self.reportar_ausencia(
            self.residente,
            self.hoy,
            self.hoy,
            'ENFERMEDAD',
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('[Guardias]', mail.outbox[0].subject)
        self.assertIn('jefe@example.com', mail.outbox[0].to)

    def test_guarda_certificado_adjuntado(self):
        archivo = SimpleUploadedFile(
            'certificado.pdf',
            b'%PDF-1.4 archivo de prueba',
            content_type='application/pdf',
        )
        ausencia = self.reportar_ausencia(
            self.residente,
            self.hoy,
            self.hoy,
            'ENFERMEDAD',
            certificado=archivo,
        )

        self.assertTrue(bool(ausencia.certificado))
        self.assertIn('certificado.pdf', ausencia.certificado.name)

    def test_guarda_documentos_adicionales(self):
        doc1 = SimpleUploadedFile(
            'extra1.pdf',
            b'%PDF-1.4 documento 1',
            content_type='application/pdf',
        )
        doc2 = SimpleUploadedFile(
            'extra2.jpg',
            b'\xff\xd8\xff imagen 2',
            content_type='image/jpeg',
        )

        ausencia = self.reportar_ausencia(
            self.residente,
            self.hoy,
            self.hoy,
            'ENFERMEDAD',
            certificados_adicionales=[doc1, doc2],
        )

        self.assertEqual(AusenciaDocumento.objects.filter(ausencia=ausencia).count(), 2)


class AusenciaResidenteFormTest(TestCase):
    def test_rechaza_mas_de_cinco_documentos_adicionales(self):
        from .forms import AusenciaResidenteForm

        residente = crear_residente('res_form_limite')
        files = [
            SimpleUploadedFile(f'extra{i}.pdf', b'%PDF-1.4 data', content_type='application/pdf')
            for i in range(1, 7)
        ]
        data = {
            'fecha_inicio': '2026-04-10',
            'fecha_fin': '2026-04-11',
            'motivo': 'ENFERMEDAD',
            'descripcion': 'test',
        }
        form = AusenciaResidenteForm(data=data)
        form.files.setlist('certificados_adicionales', files)

        self.assertFalse(form.is_valid())
        self.assertIn('certificados_adicionales', form.errors)


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


class SugerirReemplazoTest(TestCase):
    """Tests de la función sugerir_reemplazo()."""

    def setUp(self):
        from .services import sugerir_reemplazo
        self.sugerir = sugerir_reemplazo
        self.jefe = crear_jefe()
        self.ausente = crear_residente('ausente', 'R1')
        self.candidato1 = crear_residente('candidato1', 'R2')
        self.candidato2 = crear_residente('candidato2', 'R3')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        self.hoy = datetime.date(2026, 6, 15)  # fecha fija para reproducibilidad

    def _guardia(self, residente, fecha):
        return crear_guardia_publicada(residente, fecha, tipo=self.tipo)

    def test_excluye_al_residente_ausente(self):
        guardia = self._guardia(self.ausente, self.hoy)
        candidatos, _ = self.sugerir(guardia)
        pks = [c['residente'].pk for c in candidatos]
        self.assertNotIn(self.ausente.pk, pks)

    def test_incluye_candidatos_disponibles(self):
        guardia = self._guardia(self.ausente, self.hoy)
        candidatos, sugerido = self.sugerir(guardia)
        pks = [c['residente'].pk for c in candidatos]
        self.assertIn(self.candidato1.pk, pks)
        self.assertIn(self.candidato2.pk, pks)
        self.assertIsNotNone(sugerido)

    def test_excluye_candidato_con_guardia_mismo_dia(self):
        guardia = self._guardia(self.ausente, self.hoy)
        self._guardia(self.candidato1, self.hoy)  # candidato1 ocupado
        candidatos, _ = self.sugerir(guardia)
        pks = [c['residente'].pk for c in candidatos]
        self.assertNotIn(self.candidato1.pk, pks)
        self.assertIn(self.candidato2.pk, pks)

    def test_excluye_candidato_con_guardia_dia_anterior(self):
        guardia = self._guardia(self.ausente, self.hoy)
        self._guardia(self.candidato1, self.hoy - datetime.timedelta(days=1))
        candidatos, _ = self.sugerir(guardia)
        pks = [c['residente'].pk for c in candidatos]
        self.assertNotIn(self.candidato1.pk, pks)

    def test_excluye_candidato_con_guardia_dia_siguiente(self):
        guardia = self._guardia(self.ausente, self.hoy)
        self._guardia(self.candidato1, self.hoy + datetime.timedelta(days=1))
        candidatos, _ = self.sugerir(guardia)
        pks = [c['residente'].pk for c in candidatos]
        self.assertNotIn(self.candidato1.pk, pks)

    def test_candidatos_ordenados_por_menor_carga(self):
        guardia = self._guardia(self.ausente, self.hoy)
        # candidato2 tiene una guardia extra ese mes → aparece segundo
        for delta in (-5, -10):
            self._guardia(self.candidato2, self.hoy + datetime.timedelta(days=delta))
        candidatos, sugerido = self.sugerir(guardia)
        pks = [c['residente'].pk for c in candidatos]
        self.assertEqual(pks[0], self.candidato1.pk)  # menos carga
        self.assertEqual(sugerido.pk, self.candidato1.pk)

    def test_retorna_listas_vacias_cuando_no_hay_candidatos(self):
        guardia = self._guardia(self.ausente, self.hoy)
        # Bloquear a todos los candidatos el mismo día
        self._guardia(self.candidato1, self.hoy)
        self._guardia(self.candidato2, self.hoy)
        candidatos, sugerido = self.sugerir(guardia)
        self.assertEqual(candidatos, [])
        self.assertIsNone(sugerido)

    def test_guardias_mes_count_correcto(self):
        guardia = self._guardia(self.ausente, self.hoy)
        self._guardia(self.candidato1, self.hoy - datetime.timedelta(days=5))
        self._guardia(self.candidato1, self.hoy - datetime.timedelta(days=10))
        candidatos, _ = self.sugerir(guardia)
        info_c1 = next(c for c in candidatos if c['residente'].pk == self.candidato1.pk)
        self.assertEqual(info_c1['guardias_mes'], 2)


class ResolverAusenciaConReasignacionTest(TestCase):
    """Tests de resolver_ausencia() con el parámetro reasignaciones."""

    def setUp(self):
        from .services import reportar_ausencia, resolver_ausencia
        self.reportar = reportar_ausencia
        self.resolver = resolver_ausencia
        self.jefe = crear_jefe()
        self.ausente = crear_residente('ausente_r', 'R1')
        self.reemplazante = crear_residente('reemplazante_r', 'R2')
        self.tipo = crear_tipo_guardia(creado_por=self.jefe)
        self.hoy = datetime.date.today()

    def _ausencia_con_guardia(self):
        guardia = crear_guardia_publicada(self.ausente, self.hoy, tipo=self.tipo)
        ausencia = self.reportar(self.ausente, self.hoy, self.hoy, 'ENFERMEDAD')
        ausencia.guardias_afectadas.add(guardia)
        return ausencia, guardia

    def test_guardia_original_queda_reasignada(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe, reasignaciones={guardia.pk: self.reemplazante.pk})
        guardia.refresh_from_db()
        self.assertEqual(guardia.estado, 'REASIGNADA')

    def test_crea_nueva_guardia_publicada_para_reemplazante(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe, reasignaciones={guardia.pk: self.reemplazante.pk})
        nueva = AsignacionGuardia.objects.filter(
            residente=self.reemplazante,
            fecha=self.hoy,
            tipo_guardia=self.tipo,
            estado='PUBLICADA',
        )
        self.assertTrue(nueva.exists())

    def test_sin_reasignacion_guardia_queda_ausente(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe, reasignaciones={})
        guardia.refresh_from_db()
        self.assertEqual(guardia.estado, 'AUSENTE')

    def test_reasignaciones_none_marca_guardia_como_ausente(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe)  # reasignaciones=None
        guardia.refresh_from_db()
        self.assertEqual(guardia.estado, 'AUSENTE')

    def test_ausencia_queda_resuelta(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe, reasignaciones={guardia.pk: self.reemplazante.pk})
        ausencia.refresh_from_db()
        self.assertEqual(ausencia.estado, 'RESUELTA')

    def test_notifica_al_reemplazante(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe, reasignaciones={guardia.pk: self.reemplazante.pk})
        self.assertTrue(
            NotificacionGuardia.objects.filter(destinatario=self.reemplazante).exists()
        )

    def test_notifica_al_ausente(self):
        ausencia, guardia = self._ausencia_con_guardia()
        self.resolver(ausencia, self.jefe, reasignaciones={guardia.pk: self.reemplazante.pk})
        self.assertTrue(
            NotificacionGuardia.objects.filter(destinatario=self.ausente).exists()
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

    def test_envia_email_al_receptor_si_tiene_mail(self):
        self.residente2.email = 'residente2@example.com'
        self.residente2.save(update_fields=['email'])

        self.solicitar_cambio(self.residente1, self.g1, self.g2)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('residente2@example.com', mail.outbox[0].to)

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

    def test_solicitante_puede_cancelar_pendiente_jefe(self):
        """Solicitante puede cancelar incluso cuando está en PENDIENTE_JEFE."""
        from .services import aceptar_cambio_receptor
        solicitud = self.solicitar(self.residente1, self.g1, self.g2)
        aceptar_cambio_receptor(solicitud, self.residente2)
        # Ahora está en PENDIENTE_JEFE
        self.assertEqual(solicitud.estado, 'PENDIENTE_JEFE')
        # El solicitante aún puede cancelar
        self.cancelar(solicitud, self.residente1)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'CANCELADA')

    def test_no_cancelar_si_aprobada_o_rechazada(self):
        """No se puede cancelar si ya fue aprobada o rechazada."""
        from .services import aceptar_cambio_receptor, rechazar_cambio_jefe
        
        # Test con aprobada
        solicitud1 = self.solicitar(self.residente1, self.g1, self.g2)
        aceptar_cambio_receptor(solicitud1, self.residente2)
        aprobar_cambio(solicitud1, self.jefe)  # Simula aprobación
        with self.assertRaises(self.CambioGuardiaError):
            self.cancelar(solicitud1, self.residente1)


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

    def test_residente_reporta_ausencia_via_post_con_documento(self):
        self.client.login(username='residente1', password='testpass123')
        doc = SimpleUploadedFile('doc1.pdf', b'%PDF-1.4 doc1', content_type='application/pdf')
        response = self.client.post(
            reverse('control_guardias:ausencia_reportar'),
            {
                'fecha_inicio': self.hoy.isoformat(),
                'fecha_fin': self.hoy.isoformat(),
                'motivo': 'OTRO',
                'descripcion': 'con adjunto',
                'certificados_adicionales': doc,
            },
        )
        self.assertRedirects(response, reverse('control_guardias:ausencias'))
        ausencia = AusenciaResidente.objects.filter(residente=self.residente).latest('reportada_en')
        self.assertEqual(AusenciaDocumento.objects.filter(ausencia=ausencia).count(), 1)

    def test_residente_no_puede_resolver_ausencia(self):
        from .services import reportar_ausencia
        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.client.login(username='residente1', password='testpass123')
        url = reverse('control_guardias:ausencia_resolver', kwargs={'pk': ausencia.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_jefe_resuelve_ausencia_y_vuelve_con_foco(self):
        from .services import reportar_ausencia

        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.client.login(username='jefe1', password='testpass123')

        url = reverse('control_guardias:ausencia_resolver', kwargs={'pk': ausencia.pk})
        response = self.client.post(url, {
            'return_to': reverse('control_guardias:ausencias'),
            'focus': str(ausencia.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:ausencias')}?focus={ausencia.pk}",
        )

    def test_return_to_inseguro_en_resolver_ausencia_hace_fallback_local(self):
        from .services import reportar_ausencia

        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.client.login(username='jefe1', password='testpass123')

        url = reverse('control_guardias:ausencia_resolver', kwargs={'pk': ausencia.pk})
        response = self.client.post(url, {
            'return_to': 'https://evil.example/steal',
            'focus': str(ausencia.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:ausencias')}?focus={ausencia.pk}",
        )

    def test_residente_puede_cancelar_ausencia_pendiente(self):
        from .services import reportar_ausencia, cancelar_ausencia
        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        self.assertEqual(ausencia.estado, 'PENDIENTE')
        
        cancelar_ausencia(ausencia, self.residente)
        ausencia.refresh_from_db()
        
        self.assertEqual(ausencia.estado, 'RESUELTA')
        self.assertEqual(ausencia.resuelta_por, self.residente)

    def test_otro_residente_no_puede_cancelar_ausencia_ajena(self):
        from .services import reportar_ausencia, cancelar_ausencia
        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        
        with self.assertRaises(DistribucionError) as cm:
            cancelar_ausencia(ausencia, self.otro_residente)
        
        self.assertIn("Solo el residente", str(cm.exception))

    def test_no_cancelar_ausencia_resuelta(self):
        from .services import reportar_ausencia, cancelar_ausencia
        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        ausencia.estado = 'RESUELTA'
        ausencia.resuelta_por = self.jefe
        ausencia.save()
        
        with self.assertRaises(DistribucionError) as cm:
            cancelar_ausencia(ausencia, self.residente)
        
        self.assertIn("a\u00fan no fue resuelta", str(cm.exception))

    def test_residente_cancela_ausencia_via_post(self):
        from .services import reportar_ausencia
        ausencia = reportar_ausencia(self.residente, self.hoy, self.hoy, 'PERSONAL')
        
        self.client.login(username='residente1', password='testpass123')
        url = reverse('control_guardias:ausencia_cancelar', kwargs={'pk': ausencia.pk})
        response = self.client.post(url, {
            'return_to': reverse('control_guardias:ausencias'),
            'focus': str(ausencia.pk),
        })
        
        self.assertRedirects(
            response,
            f"{reverse('control_guardias:ausencias')}?focus={ausencia.pk}",
        )
        
        ausencia.refresh_from_db()
        self.assertEqual(ausencia.estado, 'RESUELTA')


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
        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={self.g1.pk}",
        )
        self.assertTrue(SolicitudCambioGuardia.objects.filter(
            solicitante=self.residente1, receptor=self.residente2).exists())

    def test_residente_solicita_cambio_y_vuelve_a_mis_guardias_con_foco(self):
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:solicitar_cambio', kwargs={'guardia_pk': self.g1.pk})
        response = self.client.post(url, {
            'guardia_receptor': self.g2.pk,
            'return_to': reverse('control_guardias:mis_guardias'),
            'focus': str(self.g1.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:mis_guardias')}?focus={self.g1.pk}",
        )

    def test_solicitar_cambio_desde_calendario_precarga_guardia_objetivo(self):
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:solicitar_cambio', kwargs={'guardia_pk': self.g1.pk})
        response = self.client.get(url, {'target_guardia': str(self.g2.pk)})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['guardia_objetivo'], self.g2)
        self.assertContains(response, self.g2.residente.get_full_name())

    def test_solicitar_cambio_con_return_to_inseguro_hace_fallback_cambios(self):
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:solicitar_cambio', kwargs={'guardia_pk': self.g1.pk})
        response = self.client.post(url, {
            'guardia_receptor': self.g2.pk,
            'return_to': 'https://evil.example/hijack',
            'focus': str(self.g1.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={self.g1.pk}",
        )

    def test_no_se_puede_solicitar_cambio_de_guardia_ajena(self):
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:solicitar_cambio', kwargs={'guardia_pk': self.g2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_jefe_revisa_cambio_y_vuelve_con_foco(self):
        from .services import aceptar_cambio_receptor, solicitar_cambio

        solicitud = solicitar_cambio(self.residente1, self.g1, self.g2)
        aceptar_cambio_receptor(solicitud, self.residente2)

        self.client.login(username='jefe1', password='testpass123')
        url = reverse('control_guardias:cambio_revisar', kwargs={'pk': solicitud.pk})
        response = self.client.post(url, {
            'accion': 'rechazar',
            'notas': 'No corresponde por cobertura',
            'return_to': reverse('control_guardias:cambios'),
            'focus': str(solicitud.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={solicitud.pk}",
        )

    def test_revisar_cambio_con_return_to_inseguro_hace_fallback_local(self):
        from .services import aceptar_cambio_receptor, solicitar_cambio

        solicitud = solicitar_cambio(self.residente1, self.g1, self.g2)
        aceptar_cambio_receptor(solicitud, self.residente2)

        self.client.login(username='jefe1', password='testpass123')
        url = reverse('control_guardias:cambio_revisar', kwargs={'pk': solicitud.pk})
        response = self.client.post(url, {
            'accion': 'rechazar',
            'notas': 'No corresponde por cobertura',
            'return_to': 'https://evil.example/phishing',
            'focus': str(solicitud.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={solicitud.pk}",
        )

    def test_receptor_responde_cambio_y_vuelve_con_foco(self):
        from .services import solicitar_cambio

        solicitud = solicitar_cambio(self.residente1, self.g1, self.g2)
        self.client.login(username='res2', password='testpass123')
        url = reverse('control_guardias:cambio_responder', kwargs={'pk': solicitud.pk})
        response = self.client.post(url, {
            'accion': 'aceptar',
            'return_to': reverse('control_guardias:cambios'),
            'focus': str(solicitud.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={solicitud.pk}",
        )

    def test_solicitante_cancela_cambio_y_vuelve_con_foco(self):
        from .services import solicitar_cambio

        solicitud = solicitar_cambio(self.residente1, self.g1, self.g2)
        self.client.login(username='res1', password='testpass123')
        url = reverse('control_guardias:cambio_cancelar', kwargs={'pk': solicitud.pk})
        response = self.client.post(url, {
            'return_to': reverse('control_guardias:cambios'),
            'focus': str(solicitud.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={solicitud.pk}",
        )

    def test_responder_cambio_con_return_to_inseguro_hace_fallback_local(self):
        from .services import solicitar_cambio

        solicitud = solicitar_cambio(self.residente1, self.g1, self.g2)
        self.client.login(username='res2', password='testpass123')
        url = reverse('control_guardias:cambio_responder', kwargs={'pk': solicitud.pk})
        response = self.client.post(url, {
            'accion': 'aceptar',
            'return_to': 'https://evil.example/redirect',
            'focus': str(solicitud.pk),
        })

        self.assertRedirects(
            response,
            f"{reverse('control_guardias:cambios')}?focus={solicitud.pk}",
        )

