"""Подключает ИИПБ отдельным комплектом, сохраняя prodex-v1 и его историю."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.models import QuestionnaireVersion, TestBundle, TestBundleItem
from apps.organizations.models import Organization

from .seed_real_questionnaires import (
    EQ5D_VAS_TEXT, HADS_QUESTIONS, SITUATIONAL_OPTIONS, STAI_SITUATIONAL,
    STAI_TRAIT, TRAIT_OPTIONS, _set_questions,
)

# Цифровой черновик 5L. Точные формулировки и лицензии проверяются по бланку
# правообладателя до производственного применения (рекомендации, §§7.3 и 9).
EQ5D_5L = [
    ("mobility", "eq5d_mobility", "Подвижность", [
        "Я не испытываю трудностей при ходьбе", "Я испытываю небольшие трудности при ходьбе",
        "Я испытываю умеренные трудности при ходьбе", "Я испытываю сильные трудности при ходьбе", "Я не в состоянии ходить",
    ]),
    ("self_care", "eq5d_self_care", "Уход за собой", [
        "Я не испытываю трудностей с мытьём или одеванием", "Я испытываю небольшие трудности с мытьём или одеванием",
        "Я испытываю умеренные трудности с мытьём или одеванием", "Я испытываю сильные трудности с мытьём или одеванием",
        "Я не в состоянии самостоятельно мыться или одеваться",
    ]),
    ("daily_activities", "eq5d_daily_activities", "Привычная повседневная деятельность", [
        "Я не испытываю трудностей в моей привычной повседневной деятельности",
        "Я испытываю небольшие трудности в моей привычной повседневной деятельности",
        "Я испытываю умеренные трудности в моей привычной повседневной деятельности",
        "Я испытываю сильные трудности в моей привычной повседневной деятельности",
        "Я не в состоянии заниматься моей привычной повседневной деятельностью",
    ]),
    ("pain_discomfort", "eq5d_pain", "Боль / дискомфорт", [
        "Я не испытываю боли или дискомфорта", "Я испытываю небольшую боль или дискомфорт",
        "Я испытываю умеренную боль или дискомфорт", "Я испытываю сильную боль или дискомфорт",
        "Я испытываю крайне сильную боль или дискомфорт",
    ]),
    ("anxiety_depression", "eq5d_anxiety_depression", "Тревога / депрессия", [
        "Я не испытываю тревоги или депрессии", "Я испытываю небольшую тревогу или депрессию",
        "Я испытываю умеренную тревогу или депрессию", "Я испытываю сильную тревогу или депрессию",
        "Я испытываю крайне сильную тревогу или депрессию",
    ]),
]


class Command(BaseCommand):
    help = "Подключает ИИПБ v0.1 от 16.11.2026 всем организациям; сохраняет старые ответы и комплекты."

    @transaction.atomic
    def handle(self, *args, **options):
        eq = [(code, indicator, text, [(label, i) for i, label in enumerate(labels, 1)])
              for code, indicator, text, labels in EQ5D_5L]
        eq.append(("vas", "eq5d_vas", EQ5D_VAS_TEXT, []))
        hads = [(f"hads_{i}", indicator, text, answers)
                for i, (indicator, text, answers) in enumerate(HADS_QUESTIONS, 1)]
        # СТ: 10 обратных пунктов, +50; ЛТ: 7 обратных, +35.
        # В старой prodex-v1 пункт ЛТ-13 был ошибочно прямым. Исправление только в новой версии.
        stai = [(f"stai_s{i}", "situational_anxiety", text, list(zip(SITUATIONAL_OPTIONS, key)))
                for i, (text, key) in enumerate(STAI_SITUATIONAL, 1)]
        stai += [(f"stai_t{i}", "trait_anxiety", text,
                  list(zip(TRAIT_OPTIONS, [4, 3, 2, 1] if i == 13 else key)))
                 for i, (text, key) in enumerate(STAI_TRAIT, 1)]
        versions = []
        for code, questions in (("hads", hads), ("stai", stai), ("eq5d", eq)):
            version, created = QuestionnaireVersion.objects.get_or_create(
                code=code, version_label=METHODOLOGY,
                defaults={"is_active": True, "license_reference": "ИИПБ 0.1, 16.11.2026; цифровые бланки и лицензию подтвердить до production"},
            )
            if created:
                _set_questions(version, questions)
            elif version.questions.count() != len(questions):
                raise CommandError(f"Неполная версия {code}/{METHODOLOGY}; исправления требуют отдельной версии.")
            if not version.is_active:
                version.is_active = True
                version.save(update_fields=["is_active"])
            versions.append(version)
        bundle, _ = TestBundle.objects.get_or_create(
            code=METHODOLOGY,
            defaults={"name": "ИИПБ · HADS, Спилбергер–Ханин, EQ-5D-5L", "methodology": METHODOLOGY, "is_active": True},
        )
        if bundle.methodology != METHODOLOGY:
            raise CommandError("Код iipb-0.1 занят комплектом с другой методологией.")
        if not bundle.is_active:
            bundle.is_active = True
            bundle.save(update_fields=["is_active"])
        for order, version in enumerate(versions, 1):
            item, _ = TestBundleItem.objects.get_or_create(bundle=bundle, order=order, defaults={"questionnaire_version": version})
            if item.questionnaire_version_id != version.pk:
                raise CommandError("Состав комплекта iipb-0.1 изменён; создайте отдельную версию.")
        for organization in Organization.objects.all():
            organization.test_bundles.add(bundle)
        TestBundle.objects.filter(code__in=["prodex-v1", "dummy-bundle"]).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(
            "ИИПБ v0.1 подключён: HADS → СТ → ЛТ → EQ-5D-5L → VAS, 60 вопросов. "
            "Исторические комплекты доступны начавшим их участникам."
        ))
