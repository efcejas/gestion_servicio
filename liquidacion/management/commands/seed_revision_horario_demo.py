from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from liquidacion.models import (
    Estudios,
    RegistroEstudio,
    RegistroEstudiosPorMedico,
    SesionContable,
    SolicitudRevisionHorarioRegistro,
)


class Command(BaseCommand):
    help = (
        "Carga datos demo idempotentes para probar Fase A de solicitud de revision "
        "de horario usando usuarios existentes por rol."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite ejecutar aun cuando DEBUG=False (solo si sabes lo que estas haciendo).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options.get("force", False)

        if not settings.DEBUG and not force:
            raise CommandError(
                "Ejecucion bloqueada: DEBUG=False. Usa --force solo en entornos controlados."
            )

        self._ensure_required_tables()

        users = self._get_required_users()
        sesion, sesion_status = self._get_or_create_sesion_actual()
        estudios = self._get_or_create_estudios_demo()

        base_date = timezone.localdate()
        dt_intra = timezone.make_aware(datetime.combine(base_date, datetime.min.time().replace(hour=10, minute=0)))
        dt_extra = timezone.make_aware(datetime.combine(base_date, datetime.min.time().replace(hour=20, minute=30)))
        dt_before_17 = timezone.make_aware(datetime.combine(base_date, datetime.min.time().replace(hour=16, minute=45)))
        dt_next_day = timezone.make_aware(
            datetime.combine(base_date + timedelta(days=1), datetime.min.time().replace(hour=9, minute=20))
        )

        registros_result = []

        # 1) Residente: ECO INTRA
        reg_residente_intra, estado = self._get_or_create_registro_demo(
            medico=users["medico_residente"],
            sesion=sesion,
            estudio=estudios["eco"],
            caso_key="residente_eco_intra",
            horario="INTRA",
            fecha_registro=dt_intra,
            fecha_informe=base_date,
        )
        registros_result.append(("residente_eco_intra", reg_residente_intra, estado))

        # 2) Residente: ECO EXTRA
        reg_residente_extra, estado = self._get_or_create_registro_demo(
            medico=users["medico_residente"],
            sesion=sesion,
            estudio=estudios["eco"],
            caso_key="residente_eco_extra",
            horario="EXTRA",
            fecha_registro=dt_extra,
            fecha_informe=base_date,
        )
        registros_result.append(("residente_eco_extra", reg_residente_extra, estado))

        # 3) Residente: DOPPLER NA
        reg_residente_doppler, estado = self._get_or_create_registro_demo(
            medico=users["medico_residente"],
            sesion=sesion,
            estudio=estudios["doppler"],
            caso_key="residente_doppler_na",
            horario="NA",
            fecha_registro=dt_extra,
            fecha_informe=base_date,
        )
        registros_result.append(("residente_doppler_na", reg_residente_doppler, estado))

        # 4) Jefe: ECO antes de 17h (candidato revision)
        reg_jefe_candidato, estado = self._get_or_create_registro_demo(
            medico=users["jefe_residentes"],
            sesion=sesion,
            estudio=estudios["eco"],
            caso_key="jefe_eco_candidato",
            horario="INTRA",
            fecha_registro=dt_before_17,
            fecha_informe=base_date,
        )
        registros_result.append(("jefe_eco_candidato", reg_jefe_candidato, estado))

        # 5) Instructor: ECO al dia siguiente (candidato revision)
        reg_instructor_candidato, estado = self._get_or_create_registro_demo(
            medico=users["instructor_residentes"],
            sesion=sesion,
            estudio=estudios["eco"],
            caso_key="instructor_eco_candidato",
            horario="EXTRA",
            fecha_registro=dt_next_day,
            fecha_informe=base_date,
        )
        registros_result.append(("instructor_eco_candidato", reg_instructor_candidato, estado))

        solicitud_demo, solicitud_estado = self._get_or_create_solicitud_pendiente(
            registro=reg_jefe_candidato,
            solicitado_por=users["jefe_residentes"],
            horario_solicitado="EXTRA",
            fecha_hora_real_declarada=dt_extra,
            motivo="DEMO FASE A: caso candidato a revision de horario",
        )

        self._print_summary(
            users=users,
            sesion=sesion,
            sesion_status=sesion_status,
            estudios=estudios,
            registros_result=registros_result,
            solicitud_demo=solicitud_demo,
            solicitud_estado=solicitud_estado,
        )

    def _ensure_required_tables(self):
        required_tables = {
            "liquidacion_registroestudiospormedico": "RegistroEstudiosPorMedico",
            "liquidacion_registro_estudio": "RegistroEstudio",
            "liquidacion_sesioncontable": "SesionContable",
            "liquidacion_solicitudrevisionhorarioregistro": "SolicitudRevisionHorarioRegistro",
        }
        existing = set(connection.introspection.table_names())
        missing = [label for table_name, label in required_tables.items() if table_name not in existing]
        if missing:
            raise CommandError(
                "Faltan tablas requeridas para la demo: "
                f"{', '.join(missing)}. Ejecuta 'python manage.py migrate' y vuelve a intentar."
            )

    def _get_required_users(self):
        User = get_user_model()
        required_roles = ["medico_residente", "jefe_residentes", "instructor_residentes"]

        users = {}
        missing = []

        for rol in required_roles:
            user = User.objects.filter(rol=rol).order_by("id").first()
            if not user:
                missing.append(rol)
            else:
                users[rol] = user

        if missing:
            raise CommandError(
                "Faltan usuarios de prueba para roles obligatorios: "
                f"{', '.join(missing)}. Crea esos usuarios y vuelve a ejecutar."
            )

        return users

    def _get_or_create_sesion_actual(self):
        hoy = timezone.localdate()
        sesion = SesionContable.objects.filter(mes=hoy.month, año=hoy.year).first()

        if sesion:
            if sesion.estado not in ["ABIERTA", "REVISION"]:
                raise CommandError(
                    "No se puede preparar demo: la sesion contable actual "
                    f"({hoy.month}/{hoy.year}) esta en estado {sesion.estado}. "
                    "Debe estar ABIERTA o REVISION."
                )
            return sesion, "reutilizada"

        sesion = SesionContable.objects.create(mes=hoy.month, año=hoy.year, estado="ABIERTA")
        return sesion, "creada"

    def _get_or_create_estudios_demo(self):
        eco_defaults = {
            "tipo": "ECO",
            "conteo_regiones": 1,
            "conteo_regiones_default": 1,
            "precio_unico": False,
            "precio_cober": 10000,
            "precio_otras_os": 12000,
            "activo": True,
        }
        doppler_defaults = {
            "tipo": "DOP",
            "conteo_regiones": 1,
            "conteo_regiones_default": 1,
            "precio_unico": False,
            "precio_cober": 15000,
            "precio_otras_os": 17000,
            "activo": True,
        }

        eco, _ = Estudios.objects.get_or_create(nombre="ECO general demo", defaults=eco_defaults)
        doppler, _ = Estudios.objects.get_or_create(nombre="Doppler demo", defaults=doppler_defaults)

        if not eco.activo:
            eco.activo = True
            eco.save(update_fields=["activo"])

        if not doppler.activo:
            doppler.activo = True
            doppler.save(update_fields=["activo"])

        return {"eco": eco, "doppler": doppler}

    def _get_or_create_registro_demo(
        self,
        medico,
        sesion,
        estudio,
        caso_key,
        horario,
        fecha_registro,
        fecha_informe,
    ):
        dni_demo = self._dni_for_case(caso_key)
        nombre = "DEMO"
        apellido = f"REV_{caso_key.upper()}"

        registro, created = RegistroEstudiosPorMedico.objects.get_or_create(
            medico=medico,
            dni_paciente=dni_demo,
            fecha_del_informe=fecha_informe,
            defaults={
                "sesion_contable": sesion,
                "nombre_paciente": nombre,
                "apellido_paciente": apellido,
                "fecha_registro": fecha_registro,
                "tipo_obra_social": "COBER",
                "horario": horario,
                "cantidad_regiones": 1,
                "monto_calculado": 0,
                "motivo_modificacion": "DEMO FASE A revision horario",
            },
        )

        if not created:
            updated_fields = []
            if registro.sesion_contable_id != sesion.id:
                registro.sesion_contable = sesion
                updated_fields.append("sesion_contable")
            if registro.nombre_paciente != nombre:
                registro.nombre_paciente = nombre
                updated_fields.append("nombre_paciente")
            if registro.apellido_paciente != apellido:
                registro.apellido_paciente = apellido
                updated_fields.append("apellido_paciente")
            if registro.horario != horario:
                registro.horario = horario
                updated_fields.append("horario")
            if registro.fecha_registro != fecha_registro:
                registro.fecha_registro = fecha_registro
                updated_fields.append("fecha_registro")
            if registro.tipo_obra_social != "COBER":
                registro.tipo_obra_social = "COBER"
                updated_fields.append("tipo_obra_social")
            if updated_fields:
                registro.save(update_fields=updated_fields)

        # Asegurar relación y monto consistente usando lógica existente del modelo
        RegistroEstudio.objects.get_or_create(
            registro=registro,
            estudio=estudio,
            defaults={"cantidad": 1, "contexto": "SERVICIO"},
        )

        if registro.cantidad_regiones != 1:
            registro.cantidad_regiones = 1
            registro.save(update_fields=["cantidad_regiones"])

        monto_calculado = registro.calcular_monto()
        if registro.monto_calculado != monto_calculado:
            registro.monto_calculado = monto_calculado
            registro.save(update_fields=["monto_calculado"])

        return registro, ("creado" if created else "reutilizado")

    def _get_or_create_solicitud_pendiente(
        self,
        registro,
        solicitado_por,
        horario_solicitado,
        fecha_hora_real_declarada,
        motivo,
    ):
        solicitud = SolicitudRevisionHorarioRegistro.objects.filter(
            registro=registro,
            estado=SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE,
        ).first()

        if solicitud:
            return solicitud, "reutilizada"

        solicitud = SolicitudRevisionHorarioRegistro.objects.create(
            registro=registro,
            solicitado_por=solicitado_por,
            horario_solicitado=horario_solicitado,
            fecha_hora_real_declarada=fecha_hora_real_declarada,
            motivo_solicitud=motivo,
            estado=SolicitudRevisionHorarioRegistro.ESTADO_PENDIENTE,
        )
        return solicitud, "creada"

    def _dni_for_case(self, caso_key):
        mapping = {
            "residente_eco_intra": "99000001",
            "residente_eco_extra": "99000002",
            "residente_doppler_na": "99000003",
            "jefe_eco_candidato": "99000004",
            "instructor_eco_candidato": "99000005",
        }
        return mapping[caso_key]

    def _print_summary(
        self,
        users,
        sesion,
        sesion_status,
        estudios,
        registros_result,
        solicitud_demo,
        solicitud_estado,
    ):
        self.stdout.write("\n" + "=" * 78)
        self.stdout.write(self.style.SUCCESS("SEED DEMO FASE A - REVISION HORARIO"))
        self.stdout.write("=" * 78)

        self.stdout.write("\nUsuarios encontrados:")
        for rol in ["medico_residente", "jefe_residentes", "instructor_residentes"]:
            u = users[rol]
            self.stdout.write(f"- {rol}: id={u.id} username={u.username}")

        self.stdout.write(
            f"\nSesion contable ({sesion_status}): id={sesion.id} "
            f"mes={sesion.mes} año={sesion.año} estado={sesion.estado}"
        )

        self.stdout.write("\nEstudios demo:")
        self.stdout.write(f"- ECO general demo: id={estudios['eco'].id}")
        self.stdout.write(f"- Doppler demo: id={estudios['doppler'].id}")

        self.stdout.write("\nRegistros demo:")
        for caso_key, registro, estado in registros_result:
            self.stdout.write(
                f"- {caso_key}: {estado} id={registro.id} medico_id={registro.medico_id} "
                f"horario={registro.horario} monto={registro.monto_calculado}"
            )

        self.stdout.write(
            f"\nSolicitud pendiente demo: {solicitud_estado} id={solicitud_demo.id} "
            f"registro_id={solicitud_demo.registro_id} estado={solicitud_demo.estado}"
        )

        try:
            lista_url = reverse("liquidacion:registroestudios_list")
            self.stdout.write("\nURLs utiles:")
            self.stdout.write(f"- Lista de registros: {lista_url}")
            for caso_key, registro, _ in registros_result:
                solicitud_url = reverse(
                    "liquidacion:solicitud_revision_horario_nueva",
                    kwargs={"registro_pk": registro.id},
                )
                self.stdout.write(f"- Solicitar revision ({caso_key}): {solicitud_url}")
        except Exception:
            self.stdout.write("\nURLs utiles: no se pudieron resolver en este contexto.")

        self.stdout.write("\n" + "=" * 78)
