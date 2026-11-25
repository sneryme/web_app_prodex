"""Экспорт агрегатов дашборда работодателя в PDF/XLSX (ТЗ FR-10).

Источник данных — тот же payload, что `employer_services.organization_overview()` отдаёт
дашборду: ни токенов, ни ответов отдельных участников здесь нет и быть не может (ТЗ FR-10.1/
10.2), скрытие маленьких групп (ТЗ FR-09.4) учтено, потому что оно уже встроено в сам payload.

Сформированный файл дополнительно сохраняется как `reporting.ExportArtifact` (кто и когда
запросил) — простейший журнал экспортов; полноценный аудит (ТЗ FR-12.6, `identity.AuditEvent`)
сюда не входит.
"""
from __future__ import annotations

import csv
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


def _export_indicators(overview):
    iipb = overview.get("iipb")
    if not iipb:
        return overview["indicators"]
    return [{"indicator_code": "iipb", "label": f"ИИПБ v{iipb['version']}",
             "baseline": iipb["baseline"], "followup": iipb["followup"], "trend": iipb["trend"]}, *overview["indicators"]]


def _iipb_stage_metrics():
    return [
        ("Медиана ИИПБ, %", "median"), ("Участников с красными флагами", "red_flag_count"),
        ("Участников с жёлтыми флагами", "yellow_flag_count"),
        *[(f"Флаг {code}", f"flag:{code}") for code in ("R1", "R2", "R3", "Y1", "Y2", "Y3")],
        *[(f"ЛТ: {label}", f"trait:{label}") for label in ("низкая", "умеренная", "высокая")],
    ]


def _iipb_metric(block, key):
    if block["is_suppressed"]:
        return None
    if key.startswith("flag:"):
        return block.get("flag_distribution", {}).get(key.split(":", 1)[1], 0)
    if key.startswith("trait:"):
        return block.get("trait_distribution", {}).get(key.split(":", 1)[1], 0)
    return block.get(key)


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
    text = f"среднее {block['mean']} (n={block['participant_count']}){' — ' + distribution if distribution else ''}"
    if "median" in block:
        text += f"; медиана {block['median']}; с красными флагами {block['red_flag_count']}; с жёлтыми {block['yellow_flag_count']}"
        text += "; " + ", ".join(f"{code}: {n}" for code, n in block.get("flag_distribution", {}).items())
        text += "; ЛТ (фон): " + ", ".join(f"{label}: {n}" for label, n in block.get("trait_distribution", {}).items())
    return text


def _trend_cell(trend: dict) -> str:
    if trend["is_suppressed"]:
        return f"скрыто (n={trend['paired_count']})"
    text = f"улучшение {trend['improved']} / ухудшение {trend['worsened']} / без изменений {trend['stable']}"
    if "mean_delta" in trend:
        text += f"; средняя Δ {trend['mean_delta']} п.п.; медианная Δ {trend['median_delta']} п.п."
    return text


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
    """Build a workbook with a separate, analysis-friendly sheet for every indicator."""
    overview = {**overview, "indicators": _export_indicators(overview)}
    wb = Workbook()
    summary_ws = wb.active
    summary_ws.title = "Сводка"
    summary_ws.cell(row=1, column=1, value=_title(overview)).font = _XLSX_FONT_TITLE
    summary = [
        ("Организация", overview["organization"]["name"]),
        ("Поток", (overview.get("stream") or {}).get("name") or (overview.get("stream") or {}).get("code") or "Все потоки"),
        ("Комплект тестов", (overview.get("bundle") or {}).get("name") or (overview.get("bundle") or {}).get("code") or "Все комплекты"),
        ("Участников в охвате", overview["coverage"]["participants"]),
        ("Прошли входной этап", overview["completion"]["baseline_completed"]),
        ("Прошли итоговый этап", overview["completion"]["followup_completed"]),
    ]
    for row_num, (label, value) in enumerate(summary, start=3):
        summary_ws.cell(row=row_num, column=1, value=label).font = _XLSX_FONT_BOLD
        summary_ws.cell(row=row_num, column=2, value=value).font = _XLSX_FONT_BODY
    summary_ws.column_dimensions["A"].width = 32
    summary_ws.column_dimensions["B"].width = 48

    used_titles = {summary_ws.title.casefold()}
    for index, indicator in enumerate(overview["indicators"], start=1):
        # Excel forbids a few characters in worksheet names and limits names to 31 characters.
        base_title = "".join("_" if char in "[]:*?/\\" else char for char in indicator["label"]).strip("' ")
        base_title = (base_title or f"Показатель {index}")[:31]
        sheet_title = base_title
        suffix_num = 2
        while sheet_title.casefold() in used_titles:
            suffix = f" ({suffix_num})"
            sheet_title = f"{base_title[:31 - len(suffix)]}{suffix}"
            suffix_num += 1
        used_titles.add(sheet_title.casefold())
        ws = wb.create_sheet(sheet_title)
        ws.cell(row=1, column=1, value=indicator["label"]).font = _XLSX_FONT_TITLE
        ws.cell(row=2, column=1, value=_title(overview)).font = _XLSX_FONT_BODY

        baseline = indicator["baseline"]
        followup = indicator["followup"]
        zones = list(dict.fromkeys([
            *baseline.get("zone_distribution", {}).keys(),
            *followup.get("zone_distribution", {}).keys(),
        ]))
        headers = ["Этап", "Участников", "Среднее", *zones, "Статус"]
        _write_header_row(ws, 4, headers)
        for row_num, (stage_name, block) in enumerate(
            (("Входной этап", baseline), ("Итоговый этап", followup)), start=5
        ):
            suppressed = block["is_suppressed"]
            values = [stage_name, block["participant_count"], "" if suppressed else block["mean"]]
            values.extend(
                "" if suppressed else block.get("zone_distribution", {}).get(zone, 0)
                for zone in zones
            )
            values.append("Скрыты: малая группа" if suppressed else "Доступны")
            _write_body_row(ws, row_num, values, wrap_columns={1, len(headers)}, suppressed=suppressed)

        trend = indicator["trend"]
        trend_header_row = 8
        ws.cell(row=trend_header_row, column=1, value="Изменение между этапами").font = _XLSX_FONT_SECTION
        _write_header_row(ws, trend_header_row + 1, ["Пар участников", "Улучшение", "Ухудшение", "Без изменений", "Статус"])
        trend_suppressed = trend["is_suppressed"]
        trend_values = [
            trend["paired_count"],
            "" if trend_suppressed else trend["improved"],
            "" if trend_suppressed else trend["worsened"],
            "" if trend_suppressed else trend["stable"],
            "Скрыты: малая группа" if trend_suppressed else "Доступны",
        ]
        _write_body_row(ws, trend_header_row + 2, trend_values, wrap_columns={5}, suppressed=trend_suppressed)

        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 14
        for col_num in range(4, 4 + len(zones)):
            ws.column_dimensions[ws.cell(row=4, column=col_num).column_letter].width = 20
        ws.column_dimensions[ws.cell(row=4, column=len(headers)).column_letter].width = 24
        ws.freeze_panes = "B5"
        if indicator["indicator_code"] == "iipb":
            data = overview["iipb"]
            ws.cell(row=3, column=1, value=f"Версия {data['version']} от {data['version_date']}").font = _XLSX_FONT_BODY
            _write_header_row(ws, 13, ["Дополнительные показатели", "До курса", "После курса"])
            for row_num, (label, key) in enumerate(_iipb_stage_metrics(), 14):
                _write_body_row(ws, row_num, [label, _iipb_metric(baseline, key), _iipb_metric(followup, key)], wrap_columns={1})
            _write_header_row(ws, 27, ["Динамика ИИПБ", "Значение", "Статус"])
            for row_num, (label, key) in enumerate([("Средняя Δ, п.п.", "mean_delta"), ("Медианная Δ, п.п.", "median_delta")], 28):
                _write_body_row(ws, row_num, [label, None if trend_suppressed else trend[key], "Скрыто: малая группа" if trend_suppressed else "Доступно"], wrap_columns={1, 3}, suppressed=trend_suppressed)
            for row_num, text in enumerate([data["notice"], data["dynamics_notice"]], 32):
                ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=7)
                cell = ws.cell(row=row_num, column=1, value=text)
                cell.font, cell.alignment = _XLSX_FONT_BODY, _XLSX_ALIGN_LEFT
                ws.row_dimensions[row_num].height = 38
            ws.column_dimensions["A"].width = 44

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()

def build_csv(overview: dict) -> bytes:
    """Build an Excel-friendly UTF-8 CSV with one numeric column per zone and stage."""
    overview = {**overview, "indicators": _export_indicators(overview)}
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")

    zones = list(dict.fromkeys(
        zone
        for indicator in overview["indicators"]
        for stage_key in ("baseline", "followup")
        for zone in indicator[stage_key].get("zone_distribution", {})
    ))
    headers = [
        "Организация",
        "Поток",
        "Комплект",
        "Участников в охвате",
        "Прошли входной этап",
        "Прошли итоговый этап",
        "Показатель",
        "Входной этап: участников",
        "Входной этап: среднее",
        *[f"Входной этап: {zone}" for zone in zones],
        "Входной этап: результаты скрыты",
        "Итоговый этап: участников",
        "Итоговый этап: среднее",
        *[f"Итоговый этап: {zone}" for zone in zones],
        "Итоговый этап: результаты скрыты",
        "Пар для динамики",
        "Улучшение",
        "Ухудшение",
        "Без изменений",
        "Динамика скрыта",
    ]
    if overview.get("iipb"):
        headers += ["Версия ИИПБ", "Дата версии ИИПБ"]
        headers += [f"{stage}: {label}" for stage in ("До курса", "После курса") for label, _ in _iipb_stage_metrics()]
        headers += ["Средняя Δ ИИПБ, п.п.", "Медианная Δ ИИПБ, п.п."]
    writer.writerow(headers)

    organization = overview["organization"]["name"]
    stream = overview.get("stream")
    stream_name = (stream.get("name") or stream.get("code")) if stream else ""
    bundle = overview.get("bundle")
    bundle_name = (bundle.get("name") or bundle.get("code")) if bundle else ""
    summary = overview["coverage"]["participants"], overview["completion"]

    def safe_cell(value):
        if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{value}"
        return value

    for indicator in overview["indicators"]:
        baseline = indicator["baseline"]
        followup = indicator["followup"]
        trend = indicator["trend"]
        baseline_suppressed = baseline["is_suppressed"]
        followup_suppressed = followup["is_suppressed"]
        trend_suppressed = trend["is_suppressed"]
        values = [
            safe_cell(organization),
            safe_cell(stream_name),
            safe_cell(bundle_name),
            summary[0],
            summary[1]["baseline_completed"],
            summary[1]["followup_completed"],
            safe_cell(indicator["label"]),
            baseline["participant_count"],
            "" if baseline_suppressed else baseline["mean"],
            *[
                "" if baseline_suppressed else baseline.get("zone_distribution", {}).get(zone, 0)
                for zone in zones
            ],
            "Да" if baseline_suppressed else "Нет",
            followup["participant_count"],
            "" if followup_suppressed else followup["mean"],
            *[
                "" if followup_suppressed else followup.get("zone_distribution", {}).get(zone, 0)
                for zone in zones
            ],
            "Да" if followup_suppressed else "Нет",
            trend["paired_count"],
            "" if trend_suppressed else trend["improved"],
            "" if trend_suppressed else trend["worsened"],
            "" if trend_suppressed else trend["stable"],
            "Да" if trend_suppressed else "Нет",
        ]
        if overview.get("iipb"):
            if indicator["indicator_code"] == "iipb":
                data = overview["iipb"]
                values += [data["version"], data["version_date"]]
                values += [_iipb_metric(block, key) for block in (baseline, followup) for _, key in _iipb_stage_metrics()]
                values += [None if trend_suppressed else trend[key] for key in ("mean_delta", "median_delta")]
            else:
                values += [None] * (4 + 2 * len(_iipb_stage_metrics()))
        writer.writerow(values)

    return ("\ufeff" + output.getvalue()).encode("utf-8")

def build_pdf(overview: dict) -> bytes:
    overview = {**overview, "indicators": _export_indicators(overview)}
    _ensure_cyrillic_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Дашборд работодателя")
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = _FONT_BOLD if "Bold" in style.name or style.name == "Title" else _FONT_REGULAR

    story = [Paragraph(_title(overview), styles["Title"]), Spacer(1, 6 * mm)]
    if overview.get("iipb"):
        data = overview["iipb"]
        story.extend([
            Paragraph(f"Методология ИИПБ v{data['version']} от {data['version_date']}", styles["BodyText"]),
            Spacer(1, 4 * mm),
        ])

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
            (overview["iipb"]["notice"] + " " + overview["iipb"]["dynamics_notice"] + " " if overview.get("iipb") else "Результаты представлены по отдельным шкалам. ") + "Индивидуальные ответы и токены "
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
