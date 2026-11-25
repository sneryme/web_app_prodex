from django.contrib import admin

from .models import (
    AnswerOption,
    AnswerResponse,
    Question,
    QuestionnaireVersion,
    ScoringResult,
    IIPBResult,
    TestBundle,
    TestBundleItem,
)


class FrozenMethodologyInline:
    """После первого ответа состав формы и ключи меняются только новой версией."""

    def _locked(self, obj):
        if obj is None:
            return False
        if isinstance(obj, QuestionnaireVersion):
            return AnswerResponse.objects.filter(question__questionnaire_version=obj).exists()
        if isinstance(obj, Question):
            return AnswerResponse.objects.filter(question__questionnaire_version_id=obj.questionnaire_version_id).exists()
        return obj.responses.exists()

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and not self._locked(obj)

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and not self._locked(obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not self._locked(obj)


class QuestionInline(FrozenMethodologyInline, admin.TabularInline):
    model = Question
    extra = 0


@admin.register(QuestionnaireVersion)
class QuestionnaireVersionAdmin(admin.ModelAdmin):
    list_display = ["code", "version_label", "is_active", "license_reference", "created_at"]
    list_filter = ["code", "is_active"]
    inlines = [QuestionInline]

    def get_readonly_fields(self, request, obj=None):
        return ["code", "version_label", "license_reference"] if obj and AnswerResponse.objects.filter(question__questionnaire_version=obj).exists() else []


class TestBundleItemInline(FrozenMethodologyInline, admin.TabularInline):
    model = TestBundleItem
    extra = 0


@admin.register(TestBundle)
class TestBundleAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "methodology", "is_active", "created_at"]
    list_filter = ["is_active"]
    inlines = [TestBundleItemInline]
    exclude = ["code"]

    def get_readonly_fields(self, request, obj=None):
        return ["methodology"] if obj and obj.responses.exists() else []


class AnswerOptionInline(FrozenMethodologyInline, admin.TabularInline):
    model = AnswerOption
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["questionnaire_version", "order", "code", "indicator_code"]
    list_filter = ["questionnaire_version"]
    inlines = [AnswerOptionInline]

    def get_readonly_fields(self, request, obj=None):
        locked = obj and AnswerResponse.objects.filter(question__questionnaire_version_id=obj.questionnaire_version_id).exists()
        return ["questionnaire_version", "order", "code", "text", "indicator_code"] if locked else []


@admin.register(AnswerResponse)
class AnswerResponseAdmin(admin.ModelAdmin):
    # Только для инженерной отладки: индивидуальные ответы работодателю и PRODEX по умолчанию не выдаются (ТЗ п.3).
    list_display = ["token", "organization_id", "bundle", "stage", "question", "selected_option", "raw_value", "answer_time"]
    list_filter = [
        "stage",
        "question__questionnaire_version",
        ("token__organization", admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ["token", "token__organization", "question", "selected_option"]

    @admin.display(description="\u0418\u0414 \u043e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0446\u0438\u0438", ordering="token__organization_id")
    def organization_id(self, obj):
        return obj.token.organization_id

    @admin.display(description="\u0412\u0440\u0435\u043c\u044f \u043e\u0442\u0432\u0435\u0442\u0430", ordering="answered_at")
    def answer_time(self, obj):
        return obj.answered_at


@admin.register(ScoringResult)
class ScoringResultAdmin(admin.ModelAdmin):
    list_display = ["token", "bundle", "stage", "indicator_code", "raw_score", "interpretation_zone", "computed_at"]
    list_filter = ["stage", "indicator_code"]


@admin.register(IIPBResult)
class IIPBResultAdmin(admin.ModelAdmin):
    list_display = ["token", "bundle", "stage", "version", "version_date", "index", "level", "measured_at"]
    list_filter = ["stage", "version", "level"]
    readonly_fields = [field.name for field in IIPBResult._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
