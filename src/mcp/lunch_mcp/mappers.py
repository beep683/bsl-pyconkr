import html
import math
import re
from datetime import datetime
from typing import Any

from .errors import AppError
from .models import Meal, MenuItem, NutritionItem, OriginItem, School

BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)
ALLERGEN_PATTERN = re.compile(r"\s*\(([\d.\s]+)\)\s*$")
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
NUTRITION_PATTERN = re.compile(
    r"^\s*(?P<name>[^(:]+?)\s*(?:\((?P<unit>[^)]+)\))?\s*:\s*"
    r"(?P<amount>-?\d+(?:\.\d+)?)\s*(?P<tail>[^\d\s].*)?$"
)


def split_lines(value: str | None) -> list[str]:
    if not value:
        return []
    plain = html.unescape(BREAK_PATTERN.sub("\n", value))
    return [line.strip() for line in plain.splitlines() if line.strip()]


def map_school(row: dict[str, Any]) -> School:
    field_map = {
        "name": "SCHUL_NM",
        "education_office_name": "ATPT_OFCDC_SC_NM",
        "education_office_code": "ATPT_OFCDC_SC_CODE",
        "school_code": "SD_SCHUL_CODE",
        "school_type": "SCHUL_KND_SC_NM",
        "region": "LCTN_SC_NM",
    }
    values = {name: str(row.get(source, "")).strip() for name, source in field_map.items()}
    if any(not value for value in values.values()):
        raise AppError("NEIS_INVALID_RESPONSE", "학교 응답 형식이 올바르지 않습니다.")
    return School(**values)


def parse_menu(value: str | None) -> list[MenuItem]:
    items: list[MenuItem] = []
    for line in split_lines(value):
        match = ALLERGEN_PATTERN.search(line)
        codes = match.group(1).split(".") if match else []
        name = line[: match.start()].strip() if match else line
        if name:
            items.append(
                MenuItem(name=name, allergen_codes=[code.strip() for code in codes if code.strip()])
            )
    return items


def parse_optional_number(value: str | int | float | None) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
    else:
        match = NUMBER_PATTERN.search(value.replace(",", ""))
        if not match:
            return None
        parsed = float(match.group())
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def parse_nutrition(value: str | None) -> list[NutritionItem]:
    items: list[NutritionItem] = []
    for line in split_lines(value):
        match = NUTRITION_PATTERN.match(line)
        if not match:
            continue
        amount = float(match.group("amount"))
        unit = (match.group("unit") or match.group("tail") or "").strip()
        if math.isfinite(amount) and unit:
            items.append(
                NutritionItem(name=match.group("name").strip(), amount=amount, unit=unit)
            )
    return items


def parse_origins(value: str | None) -> list[OriginItem]:
    items: list[OriginItem] = []
    for line in split_lines(value):
        ingredient, separator, origin = line.partition(":")
        if separator and ingredient.strip() and origin.strip():
            items.append(OriginItem(ingredient=ingredient.strip(), origin=origin.strip()))
    return items


def map_meal(row: dict[str, Any]) -> Meal:
    raw_date = str(row.get("MLSV_YMD", ""))
    menu_items = parse_menu(row.get("DDISH_NM"))
    try:
        meal_date = datetime.strptime(raw_date, "%Y%m%d").date()
    except ValueError as exc:
        raise AppError("NEIS_INVALID_RESPONSE", "급식 응답 날짜 형식이 올바르지 않습니다.") from exc
    if not menu_items:
        raise AppError("NEIS_INVALID_RESPONSE", "급식 메뉴 응답 형식이 올바르지 않습니다.")
    servings = parse_optional_number(row.get("MLSV_FGR"))
    return Meal(
        date=meal_date,
        menu_items=menu_items,
        calories_kcal=parse_optional_number(row.get("CAL_INFO")),
        servings=int(servings) if servings is not None and servings.is_integer() else None,
        nutrition=parse_nutrition(row.get("NTR_INFO")),
        origins=parse_origins(row.get("ORPLC_INFO")),
    )
