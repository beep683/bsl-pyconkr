import {
  Badge,
  Button,
  Card,
  FluentProvider,
  Input,
  Spinner,
  webLightTheme,
} from "@fluentui/react-components";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import "react-day-picker/style.css";

import {
  ApiError,
  apiFetch,
  type MealRangeResponse,
  type School,
  type SchoolSearchResponse,
} from "./api/types";
import AnalysisPage from "./analysis/AnalysisPage";
import { getAllowedDates, getInitialRange, toDateString } from "./datePolicy";
import "./styles.css";

interface CompleteDateRange {
  from: Date;
  to: Date;
}

function useDebouncedValue(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timeout);
  }, [delay, value]);
  return debounced;
}

function StepIndicator({ current }: { current: number }) {
  const labels = ["학교 선택", "날짜 선택", "결과 확인"];
  return (
    <ol className="steps" aria-label="급식 조회 단계">
      {labels.map((label, index) => (
        <li className={current >= index + 1 ? "active" : ""} key={label}>
          <span>{index + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  );
}

function MealResults({ result }: { result: MealRangeResponse }) {
  const availableCount = result.days.filter(
    (day) => day.status === "available",
  ).length;
  return (
    <section className="results" aria-labelledby="results-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">조회 완료</p>
          <h2 id="results-heading">{result.school.name}의 중식</h2>
          <p>
            {result.from} ~ {result.to}
          </p>
        </div>
        <Badge appearance="filled" color="informative">
          {availableCount}일 제공
        </Badge>
      </div>
      {availableCount === 0 && (
        <div className="status-panel">
          선택한 기간에 중식 정보가 없습니다. 다른 날짜를 선택해 주세요.
        </div>
      )}
      <div className="meal-grid">
        {result.days.map((day) => (
          <Card className="meal-card" key={day.date}>
            <div className="meal-date">
              <time dateTime={day.date}>{day.date}</time>
              <Badge
                appearance="tint"
                color={day.status === "available" ? "success" : "subtle"}
              >
                {day.status === "available" ? "중식" : "급식 없음"}
              </Badge>
            </div>
            {day.meal ? (
              <>
                <ul className="menu-list">
                  {day.meal.menuItems.map((item, index) => (
                    <li key={`${item.name}-${index}`}>
                      {item.name}
                      {item.allergenCodes.length > 0 && (
                        <small> 알레르기 {item.allergenCodes.join(", ")}</small>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="meal-meta">
                  <span>
                    열량{" "}
                    {day.meal.caloriesKcal === null
                      ? "정보 없음"
                      : `${day.meal.caloriesKcal} kcal`}
                  </span>
                  {day.meal.servings !== null && (
                    <span>{day.meal.servings}명분</span>
                  )}
                </div>
                {(day.meal.nutrition.length > 0 ||
                  day.meal.origins.length > 0) && (
                  <details>
                    <summary>영양정보와 원산지 자세히 보기</summary>
                    {day.meal.nutrition.length > 0 && (
                      <>
                        <h3>영양정보</h3>
                        <ul>
                          {day.meal.nutrition.map((item) => (
                            <li key={`${item.name}-${item.unit}`}>
                              {item.name}: {item.amount}
                              {item.unit}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {day.meal.origins.length > 0 && (
                      <>
                        <h3>원산지</h3>
                        <ul>
                          {day.meal.origins.map((item) => (
                            <li key={`${item.ingredient}-${item.origin}`}>
                              {item.ingredient}: {item.origin}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </details>
                )}
              </>
            ) : (
              <p className="empty-day">이 날짜에는 중식 정보가 없습니다.</p>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}

function MealsPage() {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.normalize("NFKC").trim();
  const debouncedQuery = useDebouncedValue(normalizedQuery, 300);
  const [selectedSchool, setSelectedSchool] = useState<School | null>(null);
  const [range, setRange] = useState<DateRange | undefined>(getInitialRange());
  const [validationError, setValidationError] = useState("");
  const queryClient = useQueryClient();
  const bounds = useMemo(() => getAllowedDates(), []);

  const schoolSearch = useQuery({
    queryKey: ["schools", debouncedQuery, 1, 20],
    queryFn: ({ signal }) =>
      apiFetch<SchoolSearchResponse>(
        `/api/v1/schools?query=${encodeURIComponent(debouncedQuery)}&page=1&pageSize=20`,
        signal,
      ),
    enabled: debouncedQuery.length >= 2,
    retry: false,
  });

  const mealSearch = useMutation({
    mutationFn: async ({
      school,
      selectedRange,
    }: {
      school: School;
      selectedRange: CompleteDateRange;
    }) => {
      const from = toDateString(selectedRange.from);
      const to = toDateString(selectedRange.to);
      return queryClient.fetchQuery({
        queryKey: [
          "meals",
          school.educationOfficeCode,
          school.schoolCode,
          from,
          to,
        ],
        queryFn: ({ signal }) =>
          apiFetch<MealRangeResponse>(
            `/api/v1/meals?educationOfficeCode=${encodeURIComponent(school.educationOfficeCode)}` +
              `&schoolCode=${encodeURIComponent(school.schoolCode)}&from=${from}&to=${to}`,
            signal,
          ),
      });
    },
  });

  const submit = () => {
    setValidationError("");
    mealSearch.reset();
    if (!selectedSchool) {
      setValidationError("급식을 조회할 학교를 먼저 선택해 주세요.");
      return;
    }
    if (!range?.from || !range.to) {
      setValidationError("시작일과 종료일을 모두 선택해 주세요.");
      return;
    }
    if (range.to < range.from) {
      setValidationError("종료일은 시작일보다 빠를 수 없습니다.");
      return;
    }
    if (range.from < bounds.minimum || range.to > bounds.maximum) {
      setValidationError("이번 달과 직전 달의 날짜만 선택할 수 있습니다.");
      return;
    }
    mealSearch.mutate({
      school: selectedSchool,
      selectedRange: { from: range.from, to: range.to },
    });
  };

  const currentStep = mealSearch.data ? 3 : selectedSchool ? 2 : 1;

  return (
    <main>
      <section className="hero">
        <div>
          <p className="eyebrow">오늘 우리 학교 메뉴는?</p>
          <h1>급식 배틀</h1>
          <p className="hero-copy">
            학교를 찾고 날짜를 고르면 NEIS가 제공하는 중식 정보를 한눈에
            보여드려요.
          </p>
        </div>
        <div className="lunch-tray" aria-hidden="true">
          <span>🍚</span>
          <span>🥗</span>
          <span>🍲</span>
        </div>
      </section>

      <StepIndicator current={currentStep} />

      <section className="setup-card" aria-labelledby="school-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STEP 1</p>
            <h2 id="school-heading">학교를 찾아보세요</h2>
          </div>
          {selectedSchool && (
            <Button
              appearance="subtle"
              onClick={() => setSelectedSchool(null)}
            >
              학교 변경
            </Button>
          )}
        </div>
        {selectedSchool ? (
          <div className="selected-school" aria-live="polite">
            <div>
              <Badge color="success">선택 완료</Badge>
              <strong>{selectedSchool.name}</strong>
              <span>
                {selectedSchool.schoolType} · {selectedSchool.region}
              </span>
            </div>
          </div>
        ) : (
          <>
            <label htmlFor="school-query">학교 이름</label>
            <Input
              id="school-query"
              value={query}
              onChange={(_, data) => setQuery(data.value)}
              placeholder="예: 서울고등학교"
              size="large"
            />
            {normalizedQuery.length < 2 && (
              <p className="hint">학교 이름을 두 글자 이상 입력해 주세요.</p>
            )}
            {schoolSearch.isFetching && (
              <Spinner size="small" label="학교를 검색하는 중입니다." />
            )}
            {schoolSearch.isError && (
              <div className="status-panel error" role="alert">
                {(schoolSearch.error as ApiError).message}
                <Button size="small" onClick={() => schoolSearch.refetch()}>
                  다시 시도
                </Button>
              </div>
            )}
            {schoolSearch.data?.items.length === 0 && (
              <div className="status-panel">
                검색 결과가 없습니다. 학교 이름을 확인해 주세요.
              </div>
            )}
            <div
              className="school-list"
              role="listbox"
              aria-label="학교 검색 결과"
            >
              {schoolSearch.data?.items.map((school) => (
                <button
                  className="school-option"
                  key={`${school.educationOfficeCode}-${school.schoolCode}`}
                  onClick={() => setSelectedSchool(school)}
                  role="option"
                  aria-selected="false"
                  type="button"
                >
                  <strong>{school.name}</strong>
                  <span>
                    {school.schoolType} · {school.region}
                  </span>
                  <em>선택하기</em>
                </button>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="setup-card" aria-labelledby="date-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STEP 2</p>
            <h2 id="date-heading">조회 기간을 선택하세요</h2>
          </div>
          <Button appearance="subtle" onClick={() => setRange(undefined)}>
            날짜 초기화
          </Button>
        </div>
        <p className="selected-range" aria-live="polite">
          선택 기간: {range?.from ? toDateString(range.from) : "시작일"} ~{" "}
          {range?.to ? toDateString(range.to) : "종료일"}
        </p>
        <p className="hint">
          {toDateString(bounds.minimum)}부터 {toDateString(bounds.maximum)}까지
          선택할 수 있습니다.
        </p>
        <div className="calendar-wrap">
          <DayPicker
            mode="range"
            numberOfMonths={2}
            selected={range}
            onSelect={setRange}
            disabled={{ before: bounds.minimum, after: bounds.maximum }}
            startMonth={bounds.minimum}
            endMonth={bounds.maximum}
            defaultMonth={new Date()}
            required={false}
          />
        </div>
        {validationError && (
          <p className="validation-error" role="alert">
            {validationError}
          </p>
        )}
        <Button
          appearance="primary"
          className="submit-button"
          disabled={mealSearch.isPending}
          onClick={submit}
          size="large"
        >
          {mealSearch.isPending ? "중식 정보를 불러오는 중..." : "중식 조회하기"}
        </Button>
      </section>

      {mealSearch.isError && (
        <div className="status-panel error" role="alert">
          {(mealSearch.error as ApiError).message}
          <Button onClick={submit}>다시 시도</Button>
        </div>
      )}
      {mealSearch.data && <MealResults result={mealSearch.data} />}
    </main>
  );
}

export default function App() {
  const analysisPage = window.location.pathname === "/analysis";
  return (
    <FluentProvider theme={webLightTheme}>
      <header className="app-header">
        <a href="/" className="brand">
          <span aria-hidden="true">🏆</span> 급식 배틀
        </a>
        <nav aria-label="주요 메뉴">
          <a href="/" aria-current={analysisPage ? undefined : "page"}>
            급식 조회
          </a>
          <a href="/analysis" aria-current={analysisPage ? "page" : undefined}>
            급식 분석
          </a>
        </nav>
      </header>
      {analysisPage ? <AnalysisPage /> : <MealsPage />}
      <footer>급식 정보는 NEIS 공개 데이터에 기반합니다.</footer>
    </FluentProvider>
  );
}
