from django.db import models


class QuestionnaireVersion(models.Model):
    """Утверждённая версия методики. Точные версии и лицензии подтверждаются методологом до релиза (ТЗ FR-05)."""

    CODE_EQ5D = "eq5d"
    CODE_STAI = "stai"  # Спилбергер–Ханин
    CODE_HADS = "hads"
    CODE_CHOICES = [
        (CODE_EQ5D, "EQ-5D"),
        (CODE_STAI, "Спилбергер–Ханин"),
        (CODE_HADS, "HADS"),
    ]

    code = models.CharField("Методика", max_length=16, choices=CODE_CHOICES)
    version_label = models.CharField("Версия", max_length=32)
    license_reference = models.CharField("Источник/лицензия", max_length=255, blank=True)
    is_active = models.BooleanField("Активна", default=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        unique_together = [("code", "version_label")]
        verbose_name = "Версия методики"
        verbose_name_plural = "Версии методик"

    def __str__(self):
        return f"{self.get_code_display()} {self.version_label}"


class TestBundle(models.Model):
    """Комплект тестов — именованный набор методик в заданном порядке (ТЗ FR-05.1).

    Раньше порядок методик был зашит константой `QUESTIONNAIRE_ORDER` в
    `apps/participants/services.py`; теперь это настоящая таблица, которой может управлять
    методолог (через admin), а не значение в коде. На один маршрут участника действует ровно
    один активный комплект (`is_active=True`) — выбор комплекта по организации/потоку не
    реализован, это естественная точка расширения на будущее.
    """

    __test__ = False  # имя класса совпадает с pytest-конвенцией "Test*" — это не тест-кейс

    code = models.SlugField("Код", max_length=64, unique=True)
    name = models.CharField("Название", max_length=255)
    is_active = models.BooleanField("Активен", default=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Комплект тестов"
        verbose_name_plural = "Комплекты тестов"

    def __str__(self):
        return self.name


class TestBundleItem(models.Model):
    """Методика внутри комплекта и её порядковый номер в маршруте участника."""

    __test__ = False

    bundle = models.ForeignKey(TestBundle, on_delete=models.CASCADE, related_name="items", verbose_name="Комплект")
    questionnaire_version = models.ForeignKey(
        "QuestionnaireVersion", on_delete=models.PROTECT, related_name="bundle_items", verbose_name="Методика"
    )
    order = models.PositiveSmallIntegerField("Порядок")

    class Meta:
        unique_together = [("bundle", "order"), ("bundle", "questionnaire_version")]
        ordering = ["bundle", "order"]
        verbose_name = "Методика в комплекте"
        verbose_name_plural = "Методики в комплекте"

    def __str__(self):
        return f"{self.bundle.code}:{self.order}:{self.questionnaire_version}"


class Question(models.Model):
    """Вопрос внутри версии методики. indicator_code — к какому из 5 отчётных показателей относится ответ."""

    questionnaire_version = models.ForeignKey(
        QuestionnaireVersion, on_delete=models.CASCADE, related_name="questions", verbose_name="Методика"
    )
    order = models.PositiveSmallIntegerField("Порядок")
    code = models.CharField("Код", max_length=64)
    text = models.TextField("Текст вопроса")
    indicator_code = models.CharField(
        "Код показателя",
        max_length=32,
        help_text=(
            "Например: eq5d_mobility, eq5d_vas, situational_anxiety, "
            "trait_anxiety, hads_anxiety, hads_depression."
        ),
    )

    class Meta:
        unique_together = [("questionnaire_version", "order")]
        ordering = ["questionnaire_version", "order"]
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"

    def __str__(self):
        return f"{self.questionnaire_version}:{self.code}"


class AnswerOption(models.Model):
    """Вариант ответа — крупная карточка на экране участника (ТЗ FR-06.1)."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="options", verbose_name="Вопрос")
    order = models.PositiveSmallIntegerField("Порядок")
    value = models.IntegerField("Балл")
    label = models.CharField("Текст варианта", max_length=255)

    class Meta:
        unique_together = [("question", "order")]
        ordering = ["question", "order"]
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответа"

    def __str__(self):
        return f"{self.question.code}:{self.label}"


class AnswerResponse(models.Model):
    """Ответ участника. Повторное сохранение того же вопроса идемпотентно (ТЗ FR-06.6)."""

    STAGE_CHOICES = [
        ("baseline", "Входное тестирование"),
        ("followup", "Итоговое тестирование"),
    ]

    token = models.ForeignKey(
        "participants.ParticipantToken", on_delete=models.CASCADE, related_name="answers", verbose_name="Токен"
    )
    stage = models.CharField("Этап", max_length=16, choices=STAGE_CHOICES)
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="responses", verbose_name="Вопрос")
    selected_option = models.ForeignKey(
        AnswerOption,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="responses",
        verbose_name="Выбранный вариант",
    )
    raw_value = models.CharField(
        "Числовое значение",
        max_length=32,
        blank=True,
        help_text="Для числовых шкал вроде EQ-5D VAS, где ответ — не карточка.",
    )
    answered_at = models.DateTimeField("Отвечено", auto_now=True)

    bundle = models.ForeignKey(
        "TestBundle", on_delete=models.PROTECT, null=True, blank=True, related_name="responses", verbose_name="Test bundle"
    )

    class Meta:
        unique_together = [("token", "bundle", "stage", "question")]
        verbose_name = "Ответ участника"
        verbose_name_plural = "Ответы участников"

    def __str__(self):
        return f"{self.token_id}:{self.stage}:{self.question.code}"


class ScoringResult(models.Model):
    """Посчитанный балл по показателю. Методики не объединяются в общий индекс (PROJECT_RULES №2)."""

    STAGE_CHOICES = AnswerResponse.STAGE_CHOICES

    bundle = models.ForeignKey(
        "TestBundle", on_delete=models.PROTECT, null=True, blank=True, related_name="scoring_results", verbose_name="Test bundle"
    )

    token = models.ForeignKey(
        "participants.ParticipantToken", on_delete=models.CASCADE, related_name="scoring_results", verbose_name="Токен"
    )
    stage = models.CharField("Этап", max_length=16, choices=STAGE_CHOICES)
    # Положение о ролях, п. 5.2: изменения методики публикуются только как новая версия и не
    # подменяют исторические результаты. Без этой ссылки балл не отличить от балла другой версии:
    # шкала HADS (0–21) и шкала опросника-заглушки (1–4) дают один и тот же `indicator_code`, и в
    # одном агрегате они смешиваются. PROTECT, а не SET_NULL: обнуление вернуло бы ту же
    # неоднозначность, из-за которой приходилось угадывать версию по числу ответов.
    questionnaire_version = models.ForeignKey(
        QuestionnaireVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scoring_results",
        verbose_name="Версия методики",
        help_text="Версия опросника, которой получен балл. Пусто только у исторических строк, чьи ответы уже удалены.",
    )
    indicator_code = models.CharField("Код показателя", max_length=32)
    raw_score = models.DecimalField("Балл", max_digits=6, decimal_places=2)
    interpretation_zone = models.CharField("Зона интерпретации", max_length=64, blank=True)
    computed_at = models.DateTimeField("Посчитано", auto_now=True)

    class Meta:
        unique_together = [("token", "bundle", "stage", "indicator_code")]
        verbose_name = "Результат подсчёта"
        verbose_name_plural = "Результаты подсчёта"

    def __str__(self):
        return f"{self.token_id}:{self.stage}:{self.indicator_code}={self.raw_score}"
