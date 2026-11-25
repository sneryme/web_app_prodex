"""Сверка ИИПБ с формулами исходного Excel без изменения файла.

python -m pip install openpyxl formulas
python scripts/check_iipb_calculator.py <путь к ИИПБ_калькулятор.xlsx> --samples 500

Исполняются формулы самого калькулятора (пакет formulas), а не их повторная
реализация. Проверка не заменяет валидацию методики или запуск Microsoft Excel.
"""
import argparse
from functools import lru_cache
from pathlib import Path
import random
import sys

import formulas
import numpy as np
import openpyxl
from openpyxl.utils.cell import range_boundaries

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from apps.assessments.iipb import RANGES, calculate_iipb


def verify(path, samples):
    workbook = openpyxl.load_workbook(path)
    sheets = {sheet.title.upper(): sheet for sheet in workbook}
    compiled = {}
    calculator = "КАЛЬКУЛЯТОР"

    def excel_result(values):
        inputs = {f"D{row}": values[code] for row, code in enumerate(RANGES, 8)}

        @lru_cache(None)
        def evaluate(reference, sheet_name=calculator):
            if "!" in reference:
                name, reference = reference.rsplit("!", 1)
                sheet_name = name.strip("'").upper()
            reference = reference.replace("$", "")
            sheet = sheets[sheet_name]
            if ":" in reference:
                c0, r0, c1, r1 = range_boundaries(reference)
                return np.array([[evaluate(sheet.cell(r, c).coordinate, sheet_name) for c in range(c0, c1 + 1)] for r in range(r0, r1 + 1)])
            if sheet_name == calculator and reference in inputs:
                return inputs[reference]
            cell = sheet[reference]
            if cell.data_type != "f":
                return cell.value
            key = (sheet_name, reference)
            if key not in compiled:
                compiled[key] = formulas.Parser().ast(cell.value)[1].compile()
            function = compiled[key]
            value = function(*(evaluate(key, sheet_name) for key in function.inputs))
            return value.item() if isinstance(value, np.ndarray) and value.size == 1 else value

        return {"index": evaluate("D32"), "level": evaluate("D33"),
                "red": evaluate("D36"), "yellow": evaluate("D37"), "trait": evaluate("D38")}

    generator = random.Random(16112026)
    cases = [dict(zip(RANGES, [9, 6, 46, 48, 1, 1, 2, 2, 3, 60])),
             dict(zip(RANGES, [6, 4, 35, 47, 1, 1, 1, 2, 2, 75]))]
    cases += [{key: generator.randint(low, high) for key, (low, high) in RANGES.items()} for _ in range(samples)]
    for code, (low, high) in RANGES.items():
        for value in (low, high):
            cases.append({key: (value if key == code else minimum) for key, (minimum, _) in RANGES.items()})
    for values in cases:
        expected, actual = excel_result(values), calculate_iipb(values)
        assert actual["index"] == expected["index"], (values, expected, actual)
        assert actual["level"] == expected["level"]
        assert [f["code"] for f in actual["red_flags"]] == [code for code in ("R1", "R2", "R3") if code in str(expected["red"])]
        assert [f["code"] for f in actual["yellow_flags"]] == [code for code in ("Y1", "Y2", "Y3") if code in str(expected["yellow"])]
        assert actual["trait_marker"]["label"] == expected["trait"]
    print(f"OK: {len(cases)} наборов совпали с формулами исходного Excel (ИИПБ, уровень, флаги, ЛТ).")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--samples", type=int, default=500)
    args = parser.parse_args()
    verify(args.workbook, args.samples)
