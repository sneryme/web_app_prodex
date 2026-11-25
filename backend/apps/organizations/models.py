import secrets

from django.db import models


def generate_entry_code():
    return secrets.token_urlsafe(8)


def generate_stream_code():
    """Generate a short opaque code used internally to identify a stream."""
    return secrets.token_urlsafe(6)


class Organization(models.Model):
    """Юридическое лицо-клиент PRODEX (ТЗ: единица лицензирования Digital)."""

    name = models.CharField("Название", max_length=255)
    legal_name = models.CharField("Юридическое название", max_length=255, blank=True)
    is_demo = models.BooleanField("Демоорганизация", default=False)
    specialist_contact = models.TextField("Контакт специалиста для маршрутизации", blank=True)
    physician_contact = models.TextField("Контакт терапевта для маршрутизации", blank=True)
    test_bundles = models.ManyToManyField(
        "assessments.TestBundle",
        blank=True,
        related_name="organizations",
        verbose_name="Test bundles",
        help_text="Bundles available to participants in this organization.",
    )
    entry_code = models.CharField(
        "Код входа",
        max_length=32,
        unique=True,
        default=generate_entry_code,
        help_text="Код в корпоративной ссылке/QR, по которому участник получает токен (ТЗ FR-01).",
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Организация"
        verbose_name_plural = "Организации"

    def __str__(self):
        return self.name


class License(models.Model):
    """Лицензия Digital: одному юрлицу на 12 месяцев (ТЗ FR-11.3)."""

    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_SUSPENDED = "suspended"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Активна"),
        (STATUS_EXPIRED, "Истекла"),
        (STATUS_SUSPENDED, "Приостановлена"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="licenses", verbose_name="Организация")
    starts_at = models.DateField("Дата начала")
    ends_at = models.DateField("Дата окончания")
    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Лицензия"
        verbose_name_plural = "Лицензии"

    def __str__(self):
        return f"{self.organization.name} {self.starts_at:%Y-%m-%d}–{self.ends_at:%Y-%m-%d}"


class Stream(models.Model):
    """Поток участников — группа, проходящая курс вместе (ТЗ FR-09.3: сравнение потоков)."""

    STATUS_PLANNED = "planned"
    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_PLANNED, "Планируется"),
        (STATUS_ACTIVE, "Активен"),
        (STATUS_CLOSED, "Завершён"),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="streams", verbose_name="Организация")
    code = models.CharField("Код", max_length=64, blank=True)
    name = models.CharField("Название", max_length=255, blank=True)
    status = models.CharField("Статус", max_length=16, choices=STATUS_CHOICES, default=STATUS_PLANNED)
    planned_start = models.DateField("Плановое начало", null=True, blank=True)
    planned_end = models.DateField("Плановое окончание", null=True, blank=True)
    min_group_size = models.PositiveSmallIntegerField(
        "Минимальный размер группы",
        default=5,
        help_text=(
            "Минимальный размер группы для публикации агрегатов работодателю. "
            "Значение по умолчанию временное, до подтверждения бизнесом (ТЗ FR-09.4, FR-10.3)."
        ),
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        unique_together = [("organization", "code")]
        verbose_name = "Поток"
        verbose_name_plural = "Потоки"

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                code = generate_stream_code()
                if not Stream.objects.filter(organization_id=self.organization_id, code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        label = self.name
        if not label:
            label = f"Поток {self.pk}" if self.pk else "Новый поток"
        return f"{self.organization.name} / {label}"
