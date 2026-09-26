import pytest
from django.db import IntegrityError

from .models import License, Organization, Stream


@pytest.mark.django_db
def test_stream_code_is_unique_per_organization():
    org = Organization.objects.create(name="ООО Ромашка")
    Stream.objects.create(organization=org, code="2026-Q1")
    with pytest.raises(IntegrityError):
        Stream.objects.create(organization=org, code="2026-Q1")


@pytest.mark.django_db
def test_stream_default_min_group_size_is_conservative():
    org = Organization.objects.create(name="ООО Ромашка")
    stream = Stream.objects.create(organization=org, code="2026-Q1")
    # Значение временное (до подтверждения бизнесом, ТЗ FR-09.4/FR-10.3), но по умолчанию не должно быть 0/1,
    # чтобы случайно не публиковать агрегаты по слишком маленьким группам.
    assert stream.min_group_size >= 2


@pytest.mark.django_db
def test_license_defaults_to_active_status():
    org = Organization.objects.create(name="ООО Ромашка")
    license_ = License.objects.create(organization=org, starts_at="2026-01-01", ends_at="2026-12-31")
    assert license_.status == License.STATUS_ACTIVE
