from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def allowed_analysis_dates(now: datetime | None = None) -> tuple[date, date]:
    current = (now or datetime.now(SEOUL)).astimezone(SEOUL).date()
    first_this_month = current.replace(day=1)
    first_previous_month = (first_this_month - timedelta(days=1)).replace(day=1)
    return first_previous_month, current


def validate_analysis_date(value: date, now: datetime | None = None) -> None:
    minimum, maximum = allowed_analysis_dates(now)
    if value < minimum or value > maximum:
        raise ValueError(
            f"분석 날짜는 {minimum.isoformat()}부터 {maximum.isoformat()}까지 선택할 수 있습니다."
        )
