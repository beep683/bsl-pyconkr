from datetime import date

from pydantic import BaseModel, Field


class School(BaseModel):
    name: str
    education_office_name: str
    education_office_code: str
    school_code: str
    school_type: str
    region: str


class SchoolSearchResult(BaseModel):
    schools: list[School]
    total_count: int


class MenuItem(BaseModel):
    name: str
    allergen_codes: list[str]


class NutritionItem(BaseModel):
    name: str
    amount: float
    unit: str


class OriginItem(BaseModel):
    ingredient: str
    origin: str


class Meal(BaseModel):
    date: date
    menu_items: list[MenuItem] = Field(min_length=1)
    calories_kcal: float | None
    servings: int | None
    nutrition: list[NutritionItem]
    origins: list[OriginItem]


class MealRangeResult(BaseModel):
    school: School
    start_date: date
    end_date: date
    meals: list[Meal] = Field(min_length=1)
