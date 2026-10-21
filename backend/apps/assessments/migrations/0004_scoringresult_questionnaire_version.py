import django.db.models.deletion
from django.db import migrations, models


def backfill_versions(apps, schema_editor):
    """Восстанавливает версию методики для уже посчитанных баллов.

    Источник — сами ответы: `AnswerResponse → Question → QuestionnaireVersion`. Это достоверно, а не
    эвристика: удалить версию с отвеченными вопросами нельзя (`Question → AnswerResponse` стоит
    PROTECT), поэтому у каждой живой строки происхождение сохранилось.

    Строки, у которых ответы одного показателя относятся к РАЗНЫМ версиям, удаляются. Балл в них
    посчитан по смешанной шкале (исторические данные, когда одновременно были активны и
    опросник-заглушка, и реальная методика), приписать его какой-то одной версии нельзя, а оставить
    как есть — значит продолжать молча смешивать несопоставимые шкалы в агрегате работодателя.
    Удаляется только производный кэш: `AnswerResponse`, согласия и прогресс этапов не трогаются —
    ровно та же логика, что у `manage.py recompute_scores`. Исключение здесь не поднимается
    намеренно: backend в docker-compose стартует как `migrate && runserver`, поэтому падение
    миграции не даёт контейнеру подняться вообще и вылечить данные уже нечем.
    """
    ScoringResult = apps.get_model("assessments", "ScoringResult")
    AnswerResponse = apps.get_model("assessments", "AnswerResponse")

    purged = []
    for result in ScoringResult.objects.all().iterator():
        version_ids = set(
            AnswerResponse.objects.filter(
                token_id=result.token_id, stage=result.stage, question__indicator_code=result.indicator_code
            ).values_list("question__questionnaire_version_id", flat=True)
        )
        if not version_ids:
            continue  # ответы уже удалены — происхождение не восстановимо, оставляем NULL
        if len(version_ids) > 1:
            purged.append((result.pk, result.indicator_code, sorted(version_ids)))
            result.delete()
            continue
        result.questionnaire_version_id = version_ids.pop()
        result.save(update_fields=["questionnaire_version"])

    if purged:
        print(
            f"\n  ВНИМАНИЕ: удалено {len(purged)} ScoringResult со смешанной шкалой (ответы из "
            f"нескольких версий опросника). Сами ответы участников сохранены — балл можно "
            f"пересчитать через manage.py recompute_scores.\n  Удалены (pk, показатель, версии): {purged}"
        )


def clear_versions(apps, schema_editor):
    apps.get_model("assessments", "ScoringResult").objects.update(questionnaire_version=None)


class Migration(migrations.Migration):

    dependencies = [
        ("assessments", "0003_alter_answeroption_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="scoringresult",
            name="questionnaire_version",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Версия опросника, которой получен балл. Пусто только у исторических строк, "
                    "чьи ответы уже удалены."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scoring_results",
                to="assessments.questionnaireversion",
                verbose_name="Версия методики",
            ),
        ),
        migrations.RunPython(backfill_versions, clear_versions),
    ]
