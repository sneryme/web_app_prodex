from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.assessments.iipb import METHODOLOGY
from apps.assessments.models import AnswerResponse, QuestionnaireVersion, ScoringResult, TestBundle, TestBundleItem
from apps.organizations.models import Organization
from apps.participants.models import ConsentRecord, ParticipantToken


class Command(BaseCommand):
    help = "Показывает план удаления прежних комплектов и связанных результатов. Запись требует --apply."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--organization-id", type=int, action="append", default=[],
                            help="ID проверенной старой организации. Можно повторять.")

    @transaction.atomic
    def handle(self, *args, **options):
        bundles = TestBundle.objects.filter(code__in=("prodex-v1", "dummy-bundle"), methodology="")
        versions = QuestionnaireVersion.objects.filter(version_label__in=("prodex-v1", "dummy-v0")).exclude(
            pk__in=TestBundleItem.objects.exclude(bundle__in=bundles).values("questionnaire_version_id")
        )
        old_answer = Q(bundle__in=bundles) | Q(bundle__isnull=True, question__questionnaire_version__in=versions)
        old_score = Q(bundle__in=bundles) | Q(bundle__isnull=True, questionnaire_version__in=versions)
        legacy_answers = AnswerResponse.objects.filter(old_answer)
        legacy_scores = ScoringResult.objects.filter(old_score)
        legacy_tokens = ParticipantToken.objects.filter(
            Q(pk__in=legacy_answers.values("token_id")) | Q(pk__in=legacy_scores.values("token_id"))
        )
        retained_tokens = ParticipantToken.objects.filter(
            Q(pk__in=AnswerResponse.objects.exclude(old_answer).values("token_id"))
            | Q(pk__in=ScoringResult.objects.exclude(old_score).values("token_id"))
            | Q(iipb_results__isnull=False)
            | Q(consents__text_version=METHODOLOGY)
        ).distinct()
        old_only_tokens = legacy_tokens.exclude(pk__in=retained_tokens)
        affected = Organization.objects.filter(
            Q(test_bundles__in=bundles) | Q(pk__in=legacy_tokens.values("organization_id"))
        ).distinct()
        org_ids = set(options["organization_id"])
        selected = Organization.objects.filter(pk__in=org_ids)
        if set(affected.filter(pk__in=org_ids).values_list("pk", flat=True)) != org_ids:
            raise CommandError("Все указанные организации должны присутствовать в плане старой методологии.")
        if ParticipantToken.objects.filter(organization__in=selected).exclude(pk__in=old_only_tokens).exists():
            raise CommandError("У выбранной организации есть участники с ИИПБ или неопределённой историей.")

        self.stdout.write(
            f"Старых комплектов: {bundles.count()}, версий опросников: {versions.count()}, "
            f"ответов: {legacy_answers.count()}, расчётов: {legacy_scores.count()}, "
            f"участников только со старой историей: {old_only_tokens.count()}."
        )
        for org in affected.order_by("pk"):
            current_count = retained_tokens.filter(organization=org).count()
            unclassified_count = org.participant_tokens.exclude(pk__in=legacy_tokens).exclude(pk__in=retained_tokens).count()
            self.stdout.write(f"Организация {org.pk}: {org.name}. Сохранить участников: {current_count + unclassified_count}.")
        if not options["apply"]:
            self.stdout.write("Предварительный просмотр. Для удаления требуется --apply.")
            return

        # Материализуем ID до удаления записей, по которым определяли историю.
        old_ids = list(old_only_tokens.values_list("pk", flat=True))
        mixed_ids = list(legacy_tokens.filter(pk__in=retained_tokens).values_list("pk", flat=True))
        legacy_answers.delete()
        legacy_scores.delete()
        ParticipantToken.objects.filter(pk__in=old_ids).delete()
        ConsentRecord.objects.filter(token_id__in=mixed_ids, text_version="v1").delete()
        ParticipantToken.objects.filter(pk__in=mixed_ids).exclude(report_payload__isnull=True).filter(
            report_payload__cards__isnull=False, report_payload__iipb__isnull=True,
        ).update(report_payload=None, report_generated_at=None)
        selected.delete()
        bundles.delete()
        versions.delete()
        self.stdout.write(self.style.SUCCESS("Выбранные данные прежней методологии удалены."))
