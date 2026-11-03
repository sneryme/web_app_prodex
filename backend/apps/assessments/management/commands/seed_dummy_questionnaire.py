from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assessments.models import AnswerOption, Question, QuestionnaireVersion, TestBundle, TestBundleItem
from apps.organizations.models import Organization

# ЗАГЛУШКА, а не реальные EQ-5D/Спилбергер–Ханин/HADS: точные версии, формулировки и лицензии
# должен подтвердить методолог до релиза (ТЗ FR-05). Нужна, чтобы проверять маршрут FR-01…FR-08
# сквозным образом, не дожидаясь этого подтверждения.
#
# Упрощение сознательное: scoring (apps/assessments/scoring.py) просто суммирует выбранные баллы
# без реверс-кодирования отдельных пунктов, поэтому все вопросы здесь сформулированы «напрямую»
# (согласие = выраженность симптома/качества), а не в обратную сторону, как встречается в реальном
# STAI. Реверс-кодирование — методологический вопрос, а не то, что должна решать заглушка.
SEVERITY_OPTIONS = [(1, "Совсем нет"), (2, "Немного"), (3, "Умеренно"), (4, "Сильно")]
RATING_OPTIONS = [(1, "Плохо"), (2, "Удовлетворительно"), (3, "Хорошо"), (4, "Отлично")]

DUMMY_QUESTIONS = {
    QuestionnaireVersion.CODE_EQ5D: [
        ("mobility", "Есть ли у вас трудности с передвижением?", "eq5d_mobility", SEVERITY_OPTIONS),
        ("vas", "Как вы оцениваете своё здоровье сегодня?", "eq5d_vas", RATING_OPTIONS),
    ],
    QuestionnaireVersion.CODE_STAI: [
        ("situational_1", "Я сейчас встревожен(а).", "situational_anxiety", SEVERITY_OPTIONS),
        ("trait_1", "Обычно я тревожусь по мелочам.", "trait_anxiety", SEVERITY_OPTIONS),
    ],
    QuestionnaireVersion.CODE_HADS: [
        ("anxiety_1", "Я испытываю внутреннее напряжение.", "hads_anxiety", SEVERITY_OPTIONS),
        ("depression_1", "Мне трудно получать удовольствие от того, что раньше радовало.", "hads_depression", SEVERITY_OPTIONS),
    ],
}


class Command(BaseCommand):
    help = (
        "Создаёт временный опросник-заглушку для сквозной проверки маршрута участника. "
        "НЕ использовать как реальные EQ-5D/Спилбергер–Ханин/HADS."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        bundle, _ = TestBundle.objects.get_or_create(
            code="dummy-bundle",
            defaults={"name": "Заглушка: EQ-5D + Спилбергер–Ханин + HADS", "is_active": True},
        )
        if not bundle.is_active:
            bundle.is_active = True
            bundle.save(update_fields=["is_active"])

        for bundle_order, (code, questions) in enumerate(DUMMY_QUESTIONS.items(), start=1):
            version, _ = QuestionnaireVersion.objects.get_or_create(
                code=code,
                version_label="dummy-v0",
                defaults={"is_active": True, "license_reference": "ЗАГЛУШКА — не для продакшена"},
            )
            if not version.is_active:
                version.is_active = True
                version.save(update_fields=["is_active"])

            TestBundleItem.objects.update_or_create(
                bundle=bundle, order=bundle_order, defaults={"questionnaire_version": version}
            )

            for order, (question_code, text, indicator_code, question_options) in enumerate(questions, start=1):
                question, created = Question.objects.get_or_create(
                    questionnaire_version=version,
                    order=order,
                    defaults={"code": question_code, "text": text, "indicator_code": indicator_code},
                )
                if not created and (question.text != text or question.indicator_code != indicator_code):
                    question.text = text
                    question.indicator_code = indicator_code
                    question.save(update_fields=["text", "indicator_code"])

                for option_order, (value, label) in enumerate(question_options, start=1):
                    AnswerOption.objects.update_or_create(
                        question=question, order=option_order, defaults={"value": value, "label": label}
                    )

        demo_organization = Organization.objects.filter(entry_code="demo-entry-code").first()
        if demo_organization is not None:
            demo_organization.test_bundles.add(bundle)

        self.stdout.write(self.style.SUCCESS("Опросник-заглушка dummy-v0 и комплект dummy-bundle готовы."))
