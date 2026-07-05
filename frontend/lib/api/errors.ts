import { isAxiosError } from "axios";

export async function getApiErrorMessage(
  error: unknown,
  fallback: string,
): Promise<string> {
  if (isAxiosError(error)) {
    const data = error.response?.data;

    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof (data as { detail: unknown }).detail === "string"
    ) {
      return (data as { detail: string }).detail;
    }

    if (data instanceof Blob) {
      try {
        const text = await data.text();
        const parsed = JSON.parse(text) as { detail?: unknown };
        if (typeof parsed.detail === "string") {
          return parsed.detail;
        }
      } catch {
        // Ignore non-JSON blob error bodies.
      }
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}
