import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.models import TestBundle
from apps.identity.models import StaffProfile
from apps.organizations.models import Organization, Stream
from apps.participants.services import active_questions

from .seed_employer_demo_streams import seed_stream


ENTRY_CODE = "iipb-presentation"
USERNAME = "iipb_demo"


class Command(BaseCommand):
    help = "Готовит отдельный демодашборд ИИПБ и учётную запись работодателя."

    def add_arguments(self, parser):
        parser.add_argument("--test-participant", action="store_true", help="Создать свежего тестового участника.")

    @transaction.atomic
    def handle(self, *args, **options):
        bundle = TestBundle.objects.filter(code=METHODOLOGY, methodology=METHODOLOGY, is_active=True).first()
        if bundle is None:
            raise CommandError("Сначала выполните seed_iipb_methodology.")
        questions = active_questions(bundle)
        if not questions:
            raise CommandError("В комплекте ИИПБ нет вопросов.")

        organization, _ = Organization.objects.select_for_update().get_or_create(
            entry_code=ENTRY_CODE, defaults={"name": "Демо ИИПБ", "is_demo": True},
        )
        if not organization.is_demo:
            raise CommandError("Код демо занят рабочей организацией.")
        organization.test_bundles.set([bundle])

        for code, name, size in (
            ("iipb-demo-main", "Основная группа", 8),
            ("iipb-demo-pilot", "Пилотная группа", 3),
        ):
            stream, _ = Stream.objects.get_or_create(
                organization=organization, code=code, defaults={"name": name, "status": Stream.STATUS_ACTIVE},
            )
            created = seed_stream(stream, bundle, questions, size)
            self.stdout.write(f"{stream.name}: добавлено участников — {created}.")

        user, created = get_user_model().objects.get_or_create(username=USERNAME)
        if created:
            StaffProfile.objects.create(user=user, role=StaffProfile.ROLE_ORG_ADMIN, organization=organization)
        elif not StaffProfile.objects.filter(user=user, role=StaffProfile.ROLE_ORG_ADMIN, organization=organization).exists():
            raise CommandError("Логин демо занят другой учётной записью.")

        password = os.environ.get("IIPB_DEMO_STAFF_PASSWORD")
        if created and not password:
            password = secrets.token_urlsafe(18)
            self.stdout.write(f"Пароль работодателя: {password}")
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])

        self.stdout.write(f"Демоорганизация: {ENTRY_CODE}. Логин работодателя: {USERNAME}.")
        if options["test_participant"]:
            call_command("create_test_participant", organization_code=ENTRY_CODE, stdout=self.stdout)
