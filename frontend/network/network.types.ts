// A backend egységes válaszburka; sikeres ágon a data mindig megvan.
export type ApiResponse<T> =
  | { status: "success"; message: string; data: T }
  | { status: "error"; message: string };

// A httpclient hibánál dob, így a hívó mindig a sikeres ágat kapja.
export type ApiSuccess<T> = Extract<ApiResponse<T>, { status: "success" }>;
