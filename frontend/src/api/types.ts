export interface School {
  educationOfficeCode: string;
  schoolCode: string;
  name: string;
  schoolType: string;
  region: string;
}

export interface SchoolSearchResponse {
  items: School[];
  page: number;
  pageSize: number;
  totalCount: number;
}

export interface MenuItem {
  name: string;
  allergenCodes: string[];
}

export interface NutritionItem {
  name: string;
  amount: number;
  unit: string;
}

export interface OriginItem {
  ingredient: string;
  origin: string;
}

export interface Meal {
  date: string;
  mealType: "lunch";
  menuItems: MenuItem[];
  caloriesKcal: number | null;
  servings: number | null;
  nutrition: NutritionItem[];
  origins: OriginItem[];
}

export interface MealDay {
  date: string;
  status: "available" | "noData";
  meal: Meal | null;
}

export interface MealRangeResponse {
  school: School;
  from: string;
  to: string;
  days: MealDay[];
}

interface ErrorResponse {
  error?: {
    message?: string;
  };
}

export class ApiError extends Error {}

export async function apiFetch<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    let body: ErrorResponse = {};
    try {
      body = (await response.json()) as ErrorResponse;
    } catch {
      // The status-derived message below remains actionable for non-JSON failures.
    }
    throw new ApiError(body.error?.message ?? "요청을 처리하지 못했습니다.");
  }
  return (await response.json()) as T;
}
