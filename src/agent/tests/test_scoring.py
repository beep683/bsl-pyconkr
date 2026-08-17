from app.schemas import (
    EvaluationArea,
    SchoolAssessment,
    SchoolCandidate,
    SpecialistEvaluation,
)
from app.scoring import AREA_WEIGHTS, calculate_school_scores, weighted_score


def candidate(code: str) -> SchoolCandidate:
    return SchoolCandidate(
        education_office_code="B10",
        school_code=code,
        name=f"{code}학교",
        school_type="고등학교",
        region="서울특별시",
    )


def evaluation(area: EvaluationArea, score_a: int, score_b: int) -> SpecialistEvaluation:
    def assessment(score: int) -> SchoolAssessment:
        return SchoolAssessment(
            score=score,
            evidence=["입력 데이터 근거"],
            improvements=["채소 구성을 보완합니다."],
        )

    return SpecialistEvaluation(
        area=area,
        school_a=assessment(score_a),
        school_b=assessment(score_b),
        comparison="학교별 차이를 비교했습니다.",
    )


def test_weights_total_one_hundred_and_scores_are_deterministic() -> None:
    assert sum(AREA_WEIGHTS.values()) == 100
    assert weighted_score(4, 45) == 36.0

    score_a, score_b = calculate_school_scores(
        candidate("1"),
        candidate("2"),
        [evaluation(area, 5, 3) for area in EvaluationArea],
    )

    assert score_a.total == 100
    assert score_b.total == 60
