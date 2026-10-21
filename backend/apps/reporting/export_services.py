"""Экспорт агрегатов дашборда работодателя в PDF/XLSX (ТЗ FR-10).

Источник данных — тот же payload, что `employer_services.organization_overview()` отдаёт
дашборду: ни токенов, ни ответов отдельных участников здесь нет и быть не может (ТЗ FR-10.1/
10.2), скрытие маленьких групп (ТЗ FR-09.4) учтено, потому что оно уже встроено в сам payload.

Сформированный файл дополнительно сохраняется как `reporting.ExportArtifact` (кто и когда
запросил) — простейший журнал экспортов; полноценный аудит (ТЗ FR-12.6, `identity.AuditEvent`)
сюда не входит.
"""
from __future__ import annotations

import io
from pathlib import Path

from django.core.files.base import ContentFile
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ExportArtifact

_DEJAVU_DIR = Path("/usr/share/fonts/truetype/dejavu")
_FONT_REGULAR = "DejaVuSans"
_FONT_BOLD = "DejaVuSans-Bold"
_fonts_registered = False


def _ensure_cyrillic_fonts():
    """Встроенные шрифты reportlab (Helvetica и т.п.) не содержат кириллицы — без явной
    регистрации TTF-шрифта русский текст в PDF превращается в пустые прямоугольники."""
    global _fonts_registered
    if _fonts_registered:
        return
    pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(_DEJAVU_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(_DEJAVU_DIR / "DejaVuSans-Bold.ttf")))
    _fonts_registered = True


def _stage_cell(block: dict) -> str:
    if block["is_suppressed"]:
        return f"скрыто (n={block['participant_count']})"
    distribution = ", ".join(f"{zone}: {count}" for zone, count in block.get("zone_distribution", {}).items())
    return f"среднее {block['mean']} (n={block['participant_count']}){' — ' + distribution if distribution else ''}"


def _trend_cell(trend: dict) -> str:
    if trend["is_suppressed"]:
        return f"скрыто (n={trend['paired_count']})"
    return f"улучшение {trend['improved']} / ухудшение {trend['worsened']} / без изменений {trend['stable']}"


def _title(overview: dict) -> str:
    title = overview["organization"]["name"]
    if overview["stream"]:
        title += f" / {overview['stream']['code']}"
    return title


# Таблица в один ряд со строками вида "среднее 9.5 (n=8) — норма: 8" на весь дашборд плохо
# читается и не фильтруется в Excel. Вместо неё — три отдельные подтаблицы (входной этап,
# итоговый этап, динамика) с собственными типизированными столбцами (числа отдельно от текста),
# плюс единый шрифт Times New Roman и оформление по запросу (без этого запроса был Calibri —
# шрифт по умолчанию openpyxl).
_XLSX_FONT_NAME = "Times New Roman"
_XLSX_FONT_BODY = Font(name=_XLSX_FONT_NAME, size=11)
_XLSX_FONT_BOLD = Font(name=_XLSX_FONT_NAME, size=11, bold=True)
_XLSX_FONT_TITLE = Font(name=_XLSX_FONT_NAME, size=16, bold=True, color="1B2738")
_XLSX_FONT_SECTION = Font(name=_XLSX_FONT_NAME, size=13, bold=True, color="1B2738")
_XLSX_FONT_HEADER = Font(name=_XLSX_FONT_NAME, size=11, bold=True, color="FFFFFF")
_XLSX_FILL_HEADER = PatternFill("solid", fgColor="1B2738")
_XLSX_FILL_SUPPRESSED = PatternFill("solid", fgColor="F2F2F2")
_XLSX_THIN_SIDE = Side(style="thin", color="BFBFBF")
_XLSX_BORDER_ALL = Border(left=_XLSX_THIN_SIDE, right=_XLSX_THIN_SIDE, top=_XLSX_THIN_SIDE, bottom=_XLSX_THIN_SIDE)
_XLSX_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
_XLSX_ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)


def _write_header_row(ws, row: int, headers: list[str]) -> None:
    for col, text in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=text)
        cell.font = _XLSX_FONT_HEADER
        cell.fill = _XLSX_FILL_HEADER
        cell.border = _XLSX_BORDER_ALL
        cell.alignment = _XLSX_ALIGN_CENTER
    ws.row_dimensions[row].height = 20


def _write_body_row(ws, row: int, values: list, *, wrap_columns: set[int], suppressed: bool = False) -> None:
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = _XLSX_FONT_BODY
        cell.border = _XLSX_BORDER_ALL
        cell.alignment = _XLSX_ALIGN_LEFT if col in wrap_columns else _XLSX_ALIGN_CENTER
        if suppressed:
            cell.fill = _XLSX_FILL_SUPPRESSED


def _stage_table(ws, start_row: int, title: str, stage_key: str, overview: dict) -> int:
    ws.cell(row=start_row, column=1, value=title).font = _XLSX_FONT_SECTION
    header_row = start_row + 1
    _write_header_row(ws, header_row, ["Показатель", "N", "Среднее", "Распределение по зонам"])

    row = header_row + 1
    for indicator in overview["indicators"]:
        block = indicator[stage_key]
        if block["is_suppressed"]:
            values = [indicator["label"], block["participant_count"], "скрыто (малая группа)", "скрыто (малая группа)"]
        else:
            distribution = ", ".join(f"{zone}: {count}" for zone, count in block.get("zone_distribution", {}).items())
            values = [indicator["label"], block["participant_count"], block["mean"], distribution]
        _write_body_row(ws, row, values, wrap_columns={1, 4}, suppressed=block["is_suppressed"])
        row += 1
    return row + 1  # одна пустая строка перед следующим разделом


def _trend_table(ws, start_row: int, overview: dict) -> int:
    ws.cell(row=start_row, column=1, value="Динамика «вход → итог»").font = _XLSX_FONT_SECTION
    header_row = start_row + 1
    _write_header_row(ws, header_row, ["Показатель", "Пар", "Улучшение", "Ухудшение", "Без изменений"])

    row = header_row + 1
    for indicator in overview["indicators"]:
        trend = indicator["trend"]
        if trend["is_suppressed"]:
            values = [indicator["label"], trend["paired_count"], "скрыто", "скрыто", "скрыто"]
        else:
            values = [indicator["label"], trend["paired_count"], trend["improved"], trend["worsened"], trend["stable"]]
        _write_body_row(ws, row, values, wrap_columns={1}, suppressed=trend["is_suppressed"])
        row += 1
    return row + 1


def build_xlsx(overview: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Дашборд"

    ws.cell(row=1, column=1, value=_title(overview)).font = _XLSX_FONT_TITLE

    ws.cell(row=3, column=1, value="Участников в охвате").font = _XLSX_FONT_BOLD
    ws.cell(row=3, column=2, value=overview["coverage"]["participants"]).font = _XLSX_FONT_BODY
    ws.cell(row=4, column=1, value="Прошли входной этап").font = _XLSX_FONT_BOLD
    ws.cell(row=4, column=2, value=overview["completion"]["baseline_completed"]).font = _XLSX_FONT_BODY
    ws.cell(row=5, column=1, value="Прошли итоговый этап").font = _XLSX_FONT_BOLD
    ws.cell(row=5, column=2, value=overview["completion"]["followup_completed"]).font = _XLSX_FONT_BODY

    row = _stage_table(ws, 7, "Входной этап", "baseline", overview)
    row = _stage_table(ws, row, "Итоговый этап", "followup", overview)
    _trend_table(ws, row, overview)

    for letter, width in zip("ABCDE", [34, 10, 16, 46, 16]):
        ws.column_dimensions[letter].width = width
    ws.freeze_panes = "A8"  # заголовок первой подтаблицы всегда виден при прокрутке

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def build_pdf(overview: dict) -> bytes:
    _ensure_cyrillic_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Дашборд работодателя")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = _FONT_BOLD if "Bold" in style.name or style.name == "Title" else _FONT_REGULAR

    story = [Paragraph(_title(overview), styles["Title"]), Spacer(1, 6 * mm)]

    summary_rows = [
        ["Участников в охвате", str(overview["coverage"]["participants"])],
        ["Прошли входной этап", str(overview["completion"]["baseline_completed"])],
        ["Прошли итоговый этап", str(overview["completion"]["followup_completed"])],
    ]
    summary_table = Table(summary_rows, colWidths=[80 * mm, 40 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 8 * mm))

    rows = [["Показатель", "Входной этап", "Итоговый этап", "Динамика"]]
    for indicator in overview["indicators"]:
        rows.append(
            [
                Paragraph(indicator["label"], styles["BodyText"]),
                Paragraph(_stage_cell(indicator["baseline"]), styles["BodyText"]),
                Paragraph(_stage_cell(indicator["followup"]), styles["BodyText"]),
                Paragraph(_trend_cell(indicator["trend"]), styles["BodyText"]),
            ]
        )
    table = Table(rows, colWidths=[35 * mm, 45 * mm, 45 * mm, 45 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), _FONT_REGULAR),
                ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B2738")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Показатели не объединяются в общий индекс. Индивидуальные ответы и токены "
            "участников в экспорт не входят.",
            styles["Italic"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def record_export(*, organization, stream, kind: str, body: bytes, filename: str, staff_profile) -> ExportArtifact:
    artifact = ExportArtifact(organization=organization, stream=stream, kind=kind, requested_by=staff_profile)
    artifact.file.save(filename, ContentFile(body), save=True)
    return artifact
