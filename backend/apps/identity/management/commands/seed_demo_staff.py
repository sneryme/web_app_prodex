from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.identity.models import StaffProfile
from apps.organizations.models import Organization

# Пароли нарочно простые и захардкожены — это сугубо локальная демо-команда (как
# seed_demo_organization/seed_employer_demo_streams), не способ создать боевого пользователя.
DEMO_PASSWORD = "prodex-demo-2026"


class Command(BaseCommand):
    help = "Создаёт демо-учётки сотрудников для входа на дашборд работодателя (ТЗ FR-12-lite)."

    def _create_staff(self, username: str, role: str, organization=None):
        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username)
        # Пароль переустанавливаем при каждом прогоне (не только при первом создании) — иначе
        # команда не идемпотентна: повторный запуск после смены DEMO_PASSWORD или ручного
        # вмешательства в БД тихо оставляет старый хэш.
        user.set_password(DEMO_PASSWORD)
        user.save()
        # update_or_create, а не get_or_create с defaults: роль и организацию тоже надо
        # переустанавливать при каждом прогоне, иначе учётка, созданная до смены состава ролей,
        # тихо остаётся со старой ролью.
        StaffProfile.objects.update_or_create(user=user, defaults={"role": role, "organization": organization})
        return username

    def handle(self, *args, **options):
        demo_org, _ = Organization.objects.get_or_create(
            entry_code="demo-entry-code", defaults={"name": "Демо-организация PRODEX"}
        )
        vektor_org, _ = Organization.objects.get_or_create(name="ООО Вектор Плюс")

        # Две роли, но три учётки: нужны два администратора в РАЗНЫХ организациях, чтобы было на
        # чём проверять изоляцию (ТЗ FR-09.1/FR-12.2) — vektor_org иначе остаётся без сотрудника.
        created = [
            self._create_staff("hr_demo", StaffProfile.ROLE_ORG_ADMIN, demo_org),
            self._create_staff("coordinator_demo", StaffProfile.ROLE_ORG_ADMIN, vektor_org),
            self._create_staff("prodex_demo", StaffProfile.ROLE_PRODEX_ADMIN, None),
        ]

        self.stdout.write(self.style.SUCCESS(f"Пароль для всех демо-учёток: {DEMO_PASSWORD}"))
        for username in created:
            self.stdout.write(f"  - {username}")
