"""Сеет полные (входной+итоговый этап) реалистичные прохождения в два потока, чтобы на
дашборде работодателя (ТЗ FR-09) было что показать и с чем сравнить:

- demo-org/2026-H2: 8 участников (>= порога публикации) — показывает, что фильтр по потоку
  реально меняет цифры (ТЗ FR-09.3) в сравнении с demo-stream.
- ООО Вектор Плюс/2026-pilot: 3 участника (< порога публикации по умолчанию, 5) — показывает
  скрытие маленькой группы (ТЗ FR-09.4).

Ответы не фиксированы одним и тем же вариантом на всех вопросах (как в сквозных smoke-тестах) —
каждому участнику присваивается случайный уровень самочувствия на входе и чуть лучший на итоге,
чтобы получилось правдоподобное (не вырожденное) распределение по зонам.
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.iipb_services import is_iipb
from apps.assessments.models import AnswerResponse, TestBundle
from apps.assessments.scoring import compute_scores_for_stage
from apps.organizations.models import Organization, Stream
from apps.participants.models import ConsentRecord, ParticipantToken
from apps.participants.services import active_questions, record_consent


def _seed_stage(token, bundle, questions, stage, measured_at, wellness, rng):
    answers = []
    for question in questions:
        options = sorted(question.options.all(), key=lambda option: option.value)
        selected_option = None
        raw_value = ""
        if options:
            max_index = len(options) - 1
            index = round((1 - wellness) * max_index + rng.gauss(0, 0.6))
            selected_option = options[max(0, min(max_index, index))]
        else:
            value = round(wellness * 100 + rng.gauss(0, 8))
            raw_value = str(max(0, min(100, value)))
        answers.append(AnswerResponse(
            token=token, bundle=bundle, stage=stage, question=question,
            selected_option=selected_option, raw_value=raw_value,
        ))

    AnswerResponse.objects.bulk_create(answers)
    # auto_now пишет время вставки. Снимок ИИПБ берёт дату замера из ответов.
    token.answers.filter(bundle=bundle, stage=stage).update(answered_at=measured_at)
    compute_scores_for_stage(token, stage, bundle)


def _seed_participant(stream, bundle, questions, rng):
    followup_at = timezone.now()
    baseline_at = followup_at - timedelta(days=7) if is_iipb(bundle) else followup_at
    token = ParticipantToken.objects.create(
        organization=stream.organization,
        stream=stream,
        baseline_status=ParticipantToken.PROGRESS_COMPLETED,
        baseline_started_at=baseline_at,
        baseline_completed_at=baseline_at,
        followup_status=ParticipantToken.PROGRESS_COMPLETED,
        followup_started_at=followup_at,
        followup_completed_at=followup_at,
    )
    ParticipantToken.objects.filter(pk=token.pk).update(created_at=baseline_at)
    if is_iipb(bundle):
        record_consent(token, ConsentRecord.TYPE_INFORMED_NOTICE, bundle.methodology, True)
    record_consent(token, ConsentRecord.TYPE_DATA_PROCESSING, bundle.methodology or "v1", True)
    token.consents.update(accepted_at=baseline_at)

    baseline_wellness = rng.uniform(0.15, 0.5)
    followup_wellness = min(0.95, baseline_wellness + rng.uniform(0.2, 0.45))

    _seed_stage(token, bundle, questions, ParticipantToken.STAGE_BASELINE, baseline_at, baseline_wellness, rng)
    _seed_stage(token, bundle, questions, ParticipantToken.STAGE_FOLLOWUP, followup_at, followup_wellness, rng)
    if is_iipb(bundle) and token.iipb_results.filter(bundle=bundle).count() != 2:
        raise CommandError(f"Не удалось рассчитать оба демозамера ИИПБ для комплекта {bundle.code}.")


def seed_stream(stream, bundle, questions, size):
    if AnswerResponse.objects.filter(token__stream=stream, bundle=bundle).exists():
        return 0
    rng = random.Random(f"20260219:{stream.code}")
    for _ in range(size):
        _seed_participant(stream, bundle, questions, rng)
    return size


class Command(BaseCommand):
    help = "Заполняет потоки 2026-H2 и 2026-pilot реалистичными завершёнными прохождениями для демо FR-09."

    def add_arguments(self, parser):
        parser.add_argument("--bundle", default=METHODOLOGY, help=f"Код комплекта (по умолчанию {METHODOLOGY}).")

    @transaction.atomic
    def handle(self, *args, **options):
        bundle = TestBundle.objects.filter(code=options["bundle"]).first()
        if bundle is None:
            raise CommandError(f"Комплект {options['bundle']} не найден. Сначала загрузите его опросники.")
        questions = active_questions(bundle)
        if not questions:
            raise CommandError(f"В комплекте {bundle.code} нет доступных вопросов.")

        demo_org = Organization.objects.select_for_update().filter(entry_code="demo-entry-code").first()
        if demo_org is None:
            raise CommandError("Сначала выполните seed_demo_organization.")

        other_org, _ = Organization.objects.get_or_create(name="ООО Вектор Плюс")
        for organization, code, size in ((demo_org, "2026-H2", 8), (other_org, "2026-pilot", 3)):
            organization.test_bundles.add(bundle)
            stream, _ = Stream.objects.get_or_create(
                organization=organization, code=code, defaults={"name": code, "status": Stream.STATUS_ACTIVE}
            )
            created = seed_stream(stream, bundle, questions, size)
            self.stdout.write(self.style.SUCCESS(
                f"{organization.name}/{code} ({bundle.code}): добавлено {created} участников "
                f"(порог {stream.min_group_size})."
            ))
