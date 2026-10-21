"""Пересчитывает ScoringResult текущей логикой `scoring.py` и убирает баллы снятых версий методик.

Нужна, когда меняются формулы или границы зон: `raw_score` — это просто сумма уже сохранённых
ответов и сам не меняется, а вот `interpretation_zone` у старых записей остаётся посчитанной по
логике, действовавшей в момент прохождения теста, и без этой команды не обновится.

Раньше команда отличала «балл по реальной методике» от «балла по опроснику-заглушке» хрупкой
эвристикой: сравнивала число ответов на этапе с ТЕКУЩИМ общим числом вопросов. Теперь
`ScoringResult.questionnaire_version` хранит версию явно (Положение о ролях, п. 5.2), поэтому
признак версии точный. Число ответов при этом по-прежнему проверяется, но уже для другого —
для полноты этапа:

- этап полный и отвечен действующими версиями → пересчитываем;
- в этапе есть ответы снятых с публикации версий → удаляем баллы (агрегат работодателя их всё
  равно не показывает, см. `employer_services._published_results`, но держать в БД производный
  кэш несопоставимой шкалы незачем);
- этап неполный → удаляем баллы: сумма половины этапа просто меньше, а не «лучше», её нельзя ни
  сравнивать, ни усреднять;
- смешанная шкала (ответы одного показателя из разных версий) → `compute_scores_for_stage` такой
  показатель пропускает и пишет warning, запись не создаётся.

Сами ответы (`AnswerResponse`), согласия и прогресс этапов не трогаются — удаляется только
производный кэш балла и зоны.
"""
from django.core.management.base import BaseCommand

from apps.assessments.models import AnswerResponse, ScoringResult
from apps.assessments.scoring import compute_scores_for_stage
from apps.participants.models import ParticipantToken
from apps.participants.services import active_questions

STAGES = (ParticipantToken.STAGE_BASELINE, ParticipantToken.STAGE_FOLLOWUP)


class Command(BaseCommand):
    help = "Пересчитывает ScoringResult текущей логикой и удаляет баллы снятых с публикации версий методик."

    def handle(self, *args, **options):
        total_questions = len(active_questions())
        if not total_questions:
            self.stdout.write(self.style.WARNING("Нет активных вопросов — нечего пересчитывать."))
            return

        recomputed = 0
        purged = 0

        for token in ParticipantToken.objects.all():
            for stage in STAGES:
                answered = AnswerResponse.objects.filter(token=token, stage=stage)
                answered_count = answered.count()
                if not answered_count:
                    continue

                # Снятая с публикации версия среди ответов — шкала несопоставима с действующей.
                has_retired_answers = answered.filter(question__questionnaire_version__is_active=False).exists()
                # Незавершённый этап считать нельзя: балл показателя — это сумма ответов, и у
                # половины отвеченного этапа она просто меньше, а не «хуже». Такую сумму нельзя
                # ни сравнивать с чужой, ни усреднять. Ровно та же проверка стоит в
                # `services._maybe_score_stage` — расчёт запускается только на полном этапе.
                is_complete = answered_count >= total_questions

                if has_retired_answers or not is_complete:
                    deleted, _ = ScoringResult.objects.filter(token=token, stage=stage).delete()
                    purged += deleted
                    continue

                compute_scores_for_stage(token, stage)
                recomputed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Пересчитано этапов: {recomputed}. Удалено устаревших ScoringResult: {purged}.")
        )
