"""Тесты содержимого экспорта (ТЗ FR-10.1/10.2/10.3) — отдельно от test_views.py (там только
HTTP-уровень: статусы, content-type, факт записи ExportArtifact)."""
import io

import pytest
from openpyxl import load_workbook

from apps.reporting import export_services


def _overview(suppressed: bool) -> dict:
    baseline = (
        {"participant_count": 2, "is_suppressed": True}
        if suppressed
        else {"participant_count": 8, "is_suppressed": False, "mean": 9.5, "zone_distribution": {"норма": 8}}
    )
    return {
        "organization": {"id": 1, "name": "ООО Ромашка"},
        "stream": {"id": 1, "code": "2026-pilot", "name": ""},
        "coverage": {"participants": baseline["participant_count"]},
        "completion": {"baseline_completed": baseline["participant_count"], "followup_completed": 0},
        "indicators": [
            {
                "indicator_code": "hads_anxiety",
                "label": "Тревога (HADS)",
                "baseline": baseline,
                "followup": {"participant_count": 0, "is_suppressed": True},
                "trend": {"paired_count": 0, "is_suppressed": True},
            }
        ],
    }


def test_xlsx_export_marks_suppressed_small_groups_instead_of_showing_a_mean():
    body = export_services.build_xlsx(_overview(suppressed=True))
    wb = load_workbook(io.BytesIO(body))
    ws = wb["Тревога (HADS)"]
    assert wb["Сводка"]["B6"].value == 2
    assert ws["B5"].value == 2
    assert ws["C5"].value is None
    assert ws["D5"].value == "Скрыты: малая группа"


def test_xlsx_export_shows_mean_and_distribution_for_a_group_above_threshold():
    body = export_services.build_xlsx(_overview(suppressed=False))
    wb = load_workbook(io.BytesIO(body))
    ws = wb["Тревога (HADS)"]
    assert ws["C4"].value == "Среднее"
    assert ws["C5"].value == 9.5
    assert ws["D4"].value == "норма"
    assert ws["D5"].value == 8


@pytest.mark.parametrize("suppressed", [True, False])
def test_pdf_export_builds_a_non_empty_document(suppressed):
    # У reportlab нет простого обратного парсинга текста без доп. зависимостей — здесь только
    # проверка, что документ вообще строится (включая кириллицу через DejaVuSans, см.
    # export_services._ensure_cyrillic_fonts) без исключений и не пустой. Содержимое для обоих
    # случаев (скрыто/не скрыто) уже покрыто тестами xlsx выше — вход в build_pdf тот же payload.
    body = export_services.build_pdf(_overview(suppressed=suppressed))
    assert body.startswith(b"%PDF")
    assert len(body) > 1000
