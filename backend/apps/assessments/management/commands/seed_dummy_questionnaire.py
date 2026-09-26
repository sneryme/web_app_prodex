from django.core.management.base import BaseCommand
from django.db import transaction

from apps.assessments.models import AnswerOption, Question, QuestionnaireVersion

# ЗАГЛУШКА, а не реальные EQ-5D/Спилбергер–Ханин/HADS: точные версии, формулировки и лицензии
# должен подтвердить методолог до релиза (ТЗ FR-05). Нужна, чтобы проверять маршрут FR-01…FR-06
# сквозным образом, не дожидаясь этого подтверждения.
DUMMY_QUESTIONS = {
    QuestionnaireVersion.CODE_EQ5D: [
        ("mobility", "Есть ли у вас трудности с передвижением?", "eq5d_mobility"),
        ("vas", "Как вы оцениваете своё здоровье сегодня?", "eq5d_vas"),
    ],
    QuestionnaireVersion.CODE_STAI: [
        ("situational_1", "Я сейчас спокоен(на).", "situational_anxiety"),
        ("trait_1", "Обычно я тревожусь по мелочам.", "trait_anxiety"),
    ],
    QuestionnaireVersion.CODE_HADS: [
        ("anxiety_1", "Я испытываю внутреннее напряжение.", "hads_anxiety"),
        ("depression_1", "Мне трудно получать удовольствие от того, что раньше радовало.", "hads_depression"),
    ],
}

OPTIONS = [(1, "Совсем нет"), (2, "Немного"), (3, "Умеренно"), (4, "Сильно")]


class Command(BaseCommand):
    help = (
        "Создаёт временный опросник-заглушку для сквозной проверки маршрута участника. "
        "НЕ использовать как реальные EQ-5D/Спилбергер–Ханин/HADS."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        for code, questions in DUMMY_QUESTIONS.items():
            version, _ = QuestionnaireVersion.objects.get_or_create(
                code=code,
                version_label="dummy-v0",
                defaults={"is_active": True, "license_reference": "ЗАГЛУШКА — не для продакшена"},
            )
            if not version.is_active:
                version.is_active = True
                version.save(update_fields=["is_active"])

            for order, (question_code, text, indicator_code) in enumerate(questions, start=1):
                question, _ = Question.objects.get_or_create(
                    questionnaire_version=version,
                    order=order,
                    defaults={"code": question_code, "text": text, "indicator_code": indicator_code},
                )
                for option_order, (value, label) in enumerate(OPTIONS, start=1):
                    AnswerOption.objects.get_or_create(
                        question=question, order=option_order, defaults={"value": value, "label": label}
                    )

        self.stdout.write(self.style.SUCCESS("Опросник-заглушка dummy-v0 готов."))
