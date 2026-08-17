import { expect, test } from "@playwright/test";

test("학교 검색에서 날짜별 중식 결과까지 조회한다", async ({ page }) => {
  const school = {
    educationOfficeCode: "B10",
    schoolCode: "7010536",
    name: "예시고등학교",
    schoolType: "고등학교",
    region: "서울특별시",
  };
  await page.route("**/api/v1/schools?**", (route) =>
    route.fulfill({
      json: { items: [school], page: 1, pageSize: 20, totalCount: 1 },
    }),
  );
  await page.route("**/api/v1/meals?**", (route) => {
    const url = new URL(route.request().url());
    const from = url.searchParams.get("from");
    const to = url.searchParams.get("to");
    return route.fulfill({
      json: {
        school,
        from,
        to,
        days: [
          {
            date: from,
            status: "available",
            meal: {
              date: from,
              mealType: "lunch",
              menuItems: [{ name: "현미밥", allergenCodes: [] }],
              caloriesKcal: 742.6,
              servings: 520,
              nutrition: [],
              origins: [],
            },
          },
        ],
      },
    });
  });

  await page.goto("/");
  await page.getByLabel("학교 이름").fill("예시");
  await page.getByRole("option", { name: /예시고등학교/ }).click();
  await page.getByRole("button", { name: "중식 조회하기" }).click();

  await expect(page.getByRole("heading", { name: "예시고등학교의 중식" })).toBeVisible();
  await expect(page.getByText("현미밥")).toBeVisible();
  await expect(page.getByText("742.6 kcal")).toBeVisible();
});
