/**
 * Optional fallback when a key is missing in `ru.json`: translate EN text via MyMemory free API.
 * Rate limits apply; disabled when NEXT_PUBLIC_REMOTE_I18N=false (e.g. offline / CI).
 *
 * MyMemory: https://mymemory.translated.net/doc/spec.php
 */
export function isRemoteI18nEnabled(): boolean {
  if (typeof process === "undefined") return false;
  return process.env.NEXT_PUBLIC_REMOTE_I18N !== "false";
}

export async function translateMyMemory(
  text: string,
  from: string,
  to: string
): Promise<string | null> {
  if (!text.trim()) return text;
  const url = new URL("https://api.mymemory.translated.net/get");
  url.searchParams.set("q", text.slice(0, 500));
  url.searchParams.set("langpair", `${from}|${to}`);
  try {
    const res = await fetch(url.toString(), { cache: "no-store" });
    if (!res.ok) return null;
    const data = (await res.json()) as {
      responseStatus?: number;
      responseData?: { translatedText?: string };
    };
    const translated = data.responseData?.translatedText?.trim();
    if (!translated) return null;
    return translated;
  } catch {
    return null;
  }
}
