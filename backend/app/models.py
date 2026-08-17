from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class School(ApiModel):
    education_office_code: str
    school_code: str
    name: str
    school_type: str
    region: str


class SchoolSearchResponse(ApiModel):
    items: list[School]
    page: int
    page_size: int
    total_count: int


class MenuItem(ApiModel):
    name: str
    allergen_codes: list[str]


class NutritionItem(ApiModel):
    name: str
    amount: float
    unit: str


class OriginItem(ApiModel):
    ingredient: str
    origin: str


class Meal(ApiModel):
    date: date
    meal_type: Literal["lunch"] = "lunch"
    menu_items: list[MenuItem] = Field(min_length=1)
    calories_kcal: float | None
    servings: int | None
    nutrition: list[NutritionItem]
    origins: list[OriginItem]


class MealDay(ApiModel):
    date: date
    status: Literal["available", "noData"]
    meal: Meal | None


class MealRangeResponse(ApiModel):
    school: School
    from_: date = Field(alias="from")
    to: date
    days: list[MealDay]


class ErrorDetail(ApiModel):
    field: str | None
    reason: str


class ErrorBody(ApiModel):
    code: str
    message: str
    details: list[ErrorDetail]
    request_id: str


class ErrorResponse(ApiModel):
    error: ErrorBody
