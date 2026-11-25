"""Пересчёт исходных шкал отдельно по комплекту и этапу, без изменения снимков ИИПБ.

Исторические версии именованного комплекта остаются его источником истины.
Незавершённые или смешанные данные пропускаются; существующие результаты не удаляются.
"""
from django.core.management.base import BaseCommand

from apps.assessments.models import AnswerResponse, TestBundle
from apps.assessments.scoring import compute_scores_for_stage
from apps.participants.models import ParticipantToken
from apps.participants.services import active_questions


class Command(BaseCommand):
    help = "Пересчитывает полные этапы отдельно по комплектам, сохраняя историю и снимки ИИПБ."

    def handle(self, *args, **options):
        recomputed = skipped = 0
        groups = list(AnswerResponse.objects.values_list("token_id", "bundle_id", "stage").distinct())
        for token_id, bundle_id, stage in groups:
            token = ParticipantToken.objects.get(pk=token_id)
            bundle = TestBundle.objects.get(pk=bundle_id) if bundle_id is not None else None
            answers = AnswerResponse.objects.filter(token=token, bundle=bundle, stage=stage)
            expected = {question.pk for question in active_questions(bundle)}
            actual = set(answers.values_list("question_id", flat=True))
            if not expected or expected != actual:
                skipped += 1
                continue
            compute_scores_for_stage(token, stage, bundle=bundle)
            recomputed += 1
        self.stdout.write(self.style.SUCCESS(
            f"Пересчитано этапов: {recomputed}. Пропущено неполных/несопоставимых: {skipped}. Снимки ИИПБ сохранены."
        ))
