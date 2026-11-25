"""Создаёт отдельного участника для проверки итогового ИИПБ без ожидания."""
from collections import Counter
from urllib.parse import urlencode

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.models import AnswerResponse, TestBundle
from apps.assessments.scoring import compute_scores_for_stage
from apps.organizations.models import Organization, Stream
from apps.participants.models import ParticipantToken
from apps.participants.services import active_questions, _sync_stage_progress

TEST_ORGANIZATION_CODE = "iipb-test-only"
TEST_ORGANIZATION_NAME = "Тестирование ИИПБ"
# Синтетический контрольный пример из методички: ИИПБ=66, II, Y1.
BASELINE_SCORES = {
    "hads_anxiety": 9, "hads_depression": 6, "situational_anxiety": 46, "trait_anxiety": 48,
    "eq5d_mobility": 1, "eq5d_self_care": 1, "eq5d_daily_activities": 2,
    "eq5d_pain": 2, "eq5d_anxiety_depression": 3, "eq5d_vas": 60,
}


class Command(BaseCommand):
    help = "Создаёт тестового участника с готовым входным замером и итоговым этапом без ожидания."

    def add_arguments(self, parser):
        parser.add_argument("--organization-code", help="Код существующей демоорганизации.")

    @transaction.atomic
    def handle(self, *args, **options):
        bundle = TestBundle.objects.filter(code=METHODOLOGY, methodology=METHODOLOGY, is_active=True).first()
        if bundle is None:
            raise CommandError("Сначала подключите методологию: python manage.py seed_iipb_methodology")
        organization_code = options.get("organization_code")
        if organization_code:
            organization = Organization.objects.filter(entry_code=organization_code, is_demo=True).first()
            if organization is None:
                raise CommandError("Демоорганизация с этим кодом не найдена.")
        else:
            organization, _ = Organization.objects.get_or_create(
                entry_code=TEST_ORGANIZATION_CODE,
                defaults={"name": TEST_ORGANIZATION_NAME, "is_demo": True},
            )
            if organization.name != TEST_ORGANIZATION_NAME or not organization.is_demo:
                raise CommandError("Код тестовой организации занят другой организацией.")
        organization.test_bundles.add(bundle)
        stream, _ = Stream.objects.get_or_create(
            organization=organization, code="test-followup",
            defaults={"name": "Проверка итогового тестирования", "status": Stream.STATUS_ACTIVE},
        )
        token = ParticipantToken.objects.create(organization=organization, stream=stream, is_test=True)
        questions = active_questions(bundle)
        remaining = BASELINE_SCORES.copy()
        counts = Counter(question.indicator_code for question in questions)
        if len(questions) != 60 or set(counts) != set(remaining):
            raise CommandError("Состав комплекта не соответствует тестовому примеру ИИПБ.")
        answers = []
        for question in questions:
            code = question.indicator_code
            variants = list(question.options.all())
            if variants:
                minimum, maximum = min(option.value for option in variants), max(option.value for option in variants)
                value = min(maximum, remaining[code] - (counts[code] - 1) * minimum)
                selected = next((option for option in variants if option.value == value), None)
                if selected is None:
                    raise CommandError("Варианты ответа не соответствуют тестовому примеру.")
                answer = AnswerResponse(token=token, bundle=bundle, stage="baseline", question=question, selected_option=selected)
            else:
                value = remaining[code]
                answer = AnswerResponse(token=token, bundle=bundle, stage="baseline", question=question, raw_value=str(value))
            answers.append(answer)
            remaining[code] -= value
            counts[code] -= 1
        if any(remaining.values()):
            raise CommandError("Не удалось подготовить полный входной замер.")
        AnswerResponse.objects.bulk_create(answers)
        compute_scores_for_stage(token, "baseline", bundle)
        _sync_stage_progress(token, bundle)
        if not token.iipb_results.filter(bundle=bundle, stage="baseline", index=66).exists():
            raise CommandError("Контрольный входной замер не рассчитан; участник не создан.")
        # Согласия здесь не создаются: проверяющий подтверждает их сам в интерфейсе.
        url = f"{settings.PARTICIPANT_FRONTEND_URL.rstrip('/')}?{urlencode({'token': token.token})}"
        self.stdout.write(self.style.SUCCESS("Тестовый участник создан. Входной замер готов; итоговый доступен без ожидания."))
        self.stdout.write(f"Ссылка: {url}")
        self.stdout.write(f"Код участника: {token.token}")
