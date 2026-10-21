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

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.organizations.models import Organization, Stream
from apps.participants.models import ConsentRecord, ParticipantToken
from apps.participants.services import active_questions, current_stage, record_consent, submit_answer


def _answer_stage(token, stage: str, wellness: float, rng: random.Random):
    """wellness: 0..1, выше — более здоровые/спокойные ответы на этом прохождении.

    Условие цикла — именно `current_stage(token) == stage`, а не "пока не None": один и тот же
    Question отвечается дважды (на входном и на итоговом), поэтому отфильтровать уже отвеченные
    нужно по конкретному этапу — иначе на итоговом вызове все вопросы покажутся "уже отвеченными"
    (из входного) и `next()` упадёт на пустой последовательности.
    """
    while current_stage(token) == stage:
        questions = active_questions()
        answered_ids = {a.question_id for a in token.answers.filter(stage=stage)}
        question = next(q for q in questions if q.id not in answered_ids)
        options = list(question.options.all())
        if options:
            # Варианты уже отсортированы по order; раскладываем по возрастанию "тяжести" (value)
            # и берём тот, что ближе к позиции, которую даёт wellness (ниже value — обычно лучше,
            # кроме eq5d_vas, но у него вариантов нет — это отдельная ветка ниже).
            sorted_options = sorted(options, key=lambda o: o.value)
            n = len(sorted_options)
            index = round((1 - wellness) * (n - 1) + rng.gauss(0, 0.6))
            index = max(0, min(n - 1, index))
            submit_answer(token, question_id=question.id, option_id=sorted_options[index].id, raw_value="")
        else:
            # EQ-5D VAS: свободный ввод 0–100, выше — лучше.
            value = round(wellness * 100 + rng.gauss(0, 8))
            value = max(0, min(100, value))
            submit_answer(token, question_id=question.id, option_id=None, raw_value=str(value))


def _seed_participant(organization, stream, rng: random.Random):
    token = ParticipantToken.objects.create(organization=organization, stream=stream)
    record_consent(token, ConsentRecord.TYPE_DATA_PROCESSING, "v1", True)

    baseline_wellness = rng.uniform(0.15, 0.5)
    followup_wellness = min(0.95, baseline_wellness + rng.uniform(0.2, 0.45))

    _answer_stage(token, "baseline", baseline_wellness, rng)
    _answer_stage(token, "followup", followup_wellness, rng)
    return token


class Command(BaseCommand):
    help = "Заполняет потоки 2026-H2 и 2026-pilot реалистичными завершёнными прохождениями для демо FR-09."

    @transaction.atomic
    def handle(self, *args, **options):
        if not active_questions():
            self.stdout.write(self.style.ERROR("Нет активных вопросов — сначала выполните seed_real_questionnaires."))
            return

        rng = random.Random(20260219)  # фиксированный seed — воспроизводимый прогон

        demo_org = Organization.objects.get(entry_code="demo-entry-code")
        stream_h2, _ = Stream.objects.get_or_create(
            organization=demo_org, code="2026-H2", defaults={"status": Stream.STATUS_ACTIVE}
        )
        created_h2 = 0
        if ParticipantToken.objects.filter(stream=stream_h2).count() == 0:
            for _ in range(8):
                _seed_participant(demo_org, stream_h2, rng)
                created_h2 += 1

        other_org, _ = Organization.objects.get_or_create(name="ООО Вектор Плюс")
        stream_pilot, _ = Stream.objects.get_or_create(
            organization=other_org, code="2026-pilot", defaults={"status": Stream.STATUS_ACTIVE}
        )
        created_pilot = 0
        if ParticipantToken.objects.filter(stream=stream_pilot).count() == 0:
            for _ in range(3):
                _seed_participant(other_org, stream_pilot, rng)
                created_pilot += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{demo_org.name}/{stream_h2.code}: добавлено {created_h2} участников (порог {stream_h2.min_group_size}). "
                f"{other_org.name}/{stream_pilot.code}: добавлено {created_pilot} участников (порог {stream_pilot.min_group_size})."
            )
        )
