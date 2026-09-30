from django.core.management.base import BaseCommand

from apps.organizations.models import Organization, Stream


class Command(BaseCommand):
    help = "Создаёт демо-организацию с известным entry_code для локальной разработки и e2e-тестов."

    def handle(self, *args, **options):
        organization, _ = Organization.objects.get_or_create(
            entry_code="demo-entry-code", defaults={"name": "Демо-организация PRODEX"}
        )
        stream, _ = Stream.objects.get_or_create(
            organization=organization, code="demo-stream", defaults={"status": Stream.STATUS_ACTIVE}
        )
        if stream.status != Stream.STATUS_ACTIVE:
            stream.status = Stream.STATUS_ACTIVE
            stream.save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS(f"entry_code={organization.entry_code}"))
