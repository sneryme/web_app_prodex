"""Журнал действий сотрудников (ТЗ FR-12.6; Положение о ролях, п. 5.3 и п. 8).

Единственная точка записи в `AuditEvent` — чтобы формат событий не расходился по вызывающим местам.

Что журналируется и что намеренно нет:

- **входы** (включая неудачные попытки) и **выходы** — `apps/identity/views.py`;
- **выгрузки** агрегатов — `apps/reporting/views.py`. У экспорта есть и `reporting.ExportArtifact`,
  но это разные сущности: артефакт — сам файл (что выгрузили), событие журнала — действие
  (кто и когда это сделал). Поэтому обе записи остаются;
- **изменения через `/admin/`** здесь НЕ дублируются: `django.contrib.admin` ведёт собственный
  журнал (`django_admin_log` / `LogEntry`) с объектом, автором и составом изменений;
- **просмотры дашборда** НЕ журналируются. Положение, п. 8, упоминает «журнал просмотров», но
  каждый GET дашборда — это отдельная запись, и один сеанс работы HR дал бы сотни строк. Это
  осознанное расхождение с Положением, а не упущение; если просмотры всё же понадобятся, их
  стоит писать огрублённо (одна запись на сотрудника/организацию в пределах окна) и сразу с
  политикой retention.

Пароли в `metadata` не попадают ни при каких условиях.
"""
from __future__ import annotations

from .models import AuditEvent

ACTION_LOGIN = "staff.login"
ACTION_LOGIN_FAILED = "staff.login_failed"
ACTION_LOGOUT = "staff.logout"
ACTION_EXPORT = "employer.export"


def record_event(*, action: str, actor=None, target_type: str = "", target_id="", metadata: dict | None = None):
    """actor=None — для событий без установленного сотрудника (неудачный вход)."""
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id="" if target_id is None else str(target_id),
        metadata=metadata or {},
    )
