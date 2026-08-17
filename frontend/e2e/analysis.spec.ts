import { expect, test } from "@playwright/test";

const schools = Array.from({ length: 10 }, (_, index) => ({
  educationOfficeCode: "B10",
  schoolCode: String(index),
  name: `${index}학교`,
  schoolType: "고등학교",
  region: "서울특별시",
}));

function sse(...events: object[]): string {
  return `${events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("")}`;
}

test("두 학교를 선택해 AG-UI 분석 결과를 표시한다", async ({ page }) => {
  await page.route("**/agent", async (route) => {
    const body = route.request().postDataJSON();
    const state = body.state;
    const snapshot =
      state.action === "load_candidates"
        ? {
            action: null,
            phase: "selecting",
            candidates: schools,
            selectedSchoolCodes: [],
            selectedDate: null,
            result: null,
            error: null,
          }
        : {
            ...state,
            action: null,
            phase: "completed",
            result: {
              analysisDate: state.selectedDate,
              evaluations: [
                {
                  area: "nutrition",
                  schoolA: {
                    score: 5,
                    evidence: ["영양정보 근거"],
                    strengths: [],
                    risks: [],
                    improvements: ["과일 추가"],
                  },
                  schoolB: {
                    score: 3,
                    evidence: ["영양정보 근거"],
                    strengths: [],
                    risks: [],
                    improvements: ["채소 추가"],
                  },
                  comparison: "0학교가 영양 균형에서 우수합니다.",
                  limitations: [],
                },
                {
                  area: "health",
                  schoolA: {
                    score: 4,
                    evidence: ["건강성 근거"],
                    strengths: [],
                    risks: [],
                    improvements: ["염분 조절"],
                  },
                  schoolB: {
                    score: 3,
                    evidence: ["건강성 근거"],
                    strengths: [],
                    risks: [],
                    improvements: ["튀김 축소"],
                  },
                  comparison: "0학교가 건강성에서 우수합니다.",
                  limitations: [],
                },
                {
                  area: "menu_quality",
                  schoolA: {
                    score: 4,
                    evidence: ["메뉴 구성 근거"],
                    strengths: [],
                    risks: [],
                    improvements: ["식재료 확대"],
                  },
                  schoolB: {
                    score: 3,
                    evidence: ["메뉴 구성 근거"],
                    strengths: [],
                    risks: [],
                    improvements: ["메뉴 조화 개선"],
                  },
                  comparison: "0학교의 메뉴 구성이 우수합니다.",
                  limitations: [],
                },
              ],
              schoolAScore: {
                school: schools[0],
                areas: [
                  { area: "nutrition", rating: 5, weight: 45, weightedScore: 45 },
                  { area: "health", rating: 4, weight: 30, weightedScore: 24 },
                  { area: "menu_quality", rating: 4, weight: 25, weightedScore: 20 },
                ],
                total: 89,
              },
              schoolBScore: {
                school: schools[1],
                areas: [
                  { area: "nutrition", rating: 3, weight: 45, weightedScore: 27 },
                  { area: "health", rating: 3, weight: 30, weightedScore: 18 },
                  { area: "menu_quality", rating: 3, weight: 25, weightedScore: 15 },
                ],
                total: 60,
              },
              judge: {
                winner: "school_a",
                headline: "0학교가 더 균형 잡힌 급식입니다.",
                rationale: ["세 영역 총점이 더 높습니다."],
                schoolAImprovements: ["과일을 추가합니다."],
                schoolBImprovements: ["채소 반찬을 늘립니다."],
                qualityNotes: [],
                limitations: ["NEIS 제공 데이터만 사용했습니다."],
              },
            },
            error: null,
          };
    await route.fulfill({
      contentType: "text/event-stream",
      body: sse(
        { type: "RUN_STARTED", threadId: body.threadId, runId: body.runId },
        { type: "STATE_SNAPSHOT", snapshot },
        { type: "RUN_FINISHED", threadId: body.threadId, runId: body.runId },
      ),
    });
  });

  await page.goto("/analysis");
  await expect(page.getByRole("group", { name: "학교 후보 10곳" })).toBeVisible();
  await page.getByRole("button", { name: /0학교/ }).click();
  await page.getByRole("button", { name: /1학교/ }).click();
  const today = new Date().toISOString().slice(0, 10);
  await page.getByLabel("분석 날짜").fill(today);
  await page.getByRole("button", { name: "분석 시작" }).click();

  await expect(
    page.getByRole("heading", { name: "0학교가 더 균형 잡힌 급식입니다." }),
  ).toBeVisible();
  await expect(page.getByText("89.0점")).toBeVisible();
  await expect(page.getByText("60.0점")).toBeVisible();
});
