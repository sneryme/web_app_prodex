"""Выдаёт демо-лицензии организациям, созданным `seed_demo_staff`/`seed_employer_demo_streams`,
чтобы на экране PRODEX Admin (ТЗ FR-11.3) было видно оба статуса — действующую лицензию и
истёкшую, а не "лицензии нет" для всех демо-клиентов.

Удаляет и создаёт заново при каждом прогоне (а не get_or_create) — у License нет естественного
уникального ключа на организацию, и дата начала "today - N дней" меняется день от дня, так что
ключ по датам не был бы идемпотентным.
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.organizations.models import License, Organization


class Command(BaseCommand):
    help = "Создаёт демо-лицензии (ТЗ FR-11.3): активную для demo-организации, истёкшую для ООО Вектор Плюс."

    def handle(self, *args, **options):
        today = timezone.localdate()
        demo_org = Organization.objects.get(entry_code="demo-entry-code")
        other_org, _ = Organization.objects.get_or_create(name="ООО Вектор Плюс")

        License.objects.filter(organization__in=[demo_org, other_org]).delete()
        License.objects.create(
            organization=demo_org,
            starts_at=today - datetime.timedelta(days=30),
            ends_at=today + datetime.timedelta(days=335),
            status=License.STATUS_ACTIVE,
        )
        License.objects.create(
            organization=other_org,
            starts_at=today - datetime.timedelta(days=400),
            ends_at=today - datetime.timedelta(days=35),
            status=License.STATUS_EXPIRED,
        )

        self.stdout.write(self.style.SUCCESS(f"{demo_org.name}: активная лицензия. {other_org.name}: истёкшая лицензия."))
