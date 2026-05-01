/** Публичный URL FastAPI (без завершающего слэша). */
export function getPublicApiUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  const fallback = "http://127.0.0.1:8000";
  if (!raw || raw.trim() === "") return fallback;
  return raw.replace(/\/+$/, "");
}
