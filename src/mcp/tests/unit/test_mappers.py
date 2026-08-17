from lunch_mcp.mappers import map_meal, map_school


def test_maps_school_identifiers_and_meal_details() -> None:
    school = map_school(
        {
            "SCHUL_NM": "예시고등학교",
            "ATPT_OFCDC_SC_NM": "서울특별시교육청",
            "ATPT_OFCDC_SC_CODE": "B10",
            "SD_SCHUL_CODE": "7010536",
            "SCHUL_KND_SC_NM": "고등학교",
            "LCTN_SC_NM": "서울특별시",
        }
    )
    meal = map_meal(
        {
            "MLSV_YMD": "20260817",
            "DDISH_NM": "현미밥<br/>된장국 (5.6)",
            "CAL_INFO": "742.6 Kcal",
            "MLSV_FGR": "520",
            "NTR_INFO": "단백질(g) : 25.1",
            "ORPLC_INFO": "쌀 : 국내산",
        }
    )

    assert school.education_office_name == "서울특별시교육청"
    assert school.education_office_code == "B10"
    assert meal.menu_items[1].allergen_codes == ["5", "6"]
    assert meal.calories_kcal == 742.6
    assert meal.servings == 520
    assert meal.nutrition[0].unit == "g"
    assert meal.origins[0].origin == "국내산"
