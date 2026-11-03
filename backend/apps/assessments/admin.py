from django.contrib import admin

from .models import (
    AnswerOption,
    AnswerResponse,
    Question,
    QuestionnaireVersion,
    ScoringResult,
    TestBundle,
    TestBundleItem,
)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(QuestionnaireVersion)
class QuestionnaireVersionAdmin(admin.ModelAdmin):
    list_display = ["code", "version_label", "is_active", "license_reference", "created_at"]
    list_filter = ["code", "is_active"]
    inlines = [QuestionInline]


class TestBundleItemInline(admin.TabularInline):
    model = TestBundleItem
    extra = 0


@admin.register(TestBundle)
class TestBundleAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active", "created_at"]
    list_filter = ["is_active"]
    inlines = [TestBundleItemInline]


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["questionnaire_version", "order", "code", "indicator_code"]
    list_filter = ["questionnaire_version"]
    inlines = [AnswerOptionInline]


@admin.register(AnswerResponse)
class AnswerResponseAdmin(admin.ModelAdmin):
    # Только для инженерной отладки: индивидуальные ответы работодателю и PRODEX по умолчанию не выдаются (ТЗ п.3).
    list_display = ["token", "organization_id", "bundle", "stage", "question", "selected_option", "raw_value", "answer_time"]
    list_filter = ["stage", "question__questionnaire_version"]
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
