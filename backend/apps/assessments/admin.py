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
    list_display = ["token", "stage", "question", "selected_option", "raw_value", "answered_at"]
    list_filter = ["stage", "question__questionnaire_version"]


@admin.register(ScoringResult)
class ScoringResultAdmin(admin.ModelAdmin):
    list_display = ["token", "stage", "indicator_code", "raw_score", "interpretation_zone", "computed_at"]
    list_filter = ["stage", "indicator_code"]
