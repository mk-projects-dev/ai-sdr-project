"use client";

import en from "@/messages/en.json";
import ru from "@/messages/ru.json";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { interpolate } from "./interpolate";
import { isRemoteI18nEnabled, translateMyMemory } from "./remote-translate";

export type Locale = "en" | "ru";

const STORAGE_LOCALE = "aisdr_locale";
const STORAGE_MACHINE = "aisdr_i18n_mc";

const dictionaries: Record<Locale, Record<string, unknown>> = {
  en: en as Record<string, unknown>,
  ru: ru as Record<string, unknown>,
};

function getByPath(obj: unknown, path: string): string | undefined {
  const parts = path.split(".");
  let cur: unknown = obj;
  for (const p of parts) {
    if (cur === null || cur === undefined || typeof cur !== "object") {
      return undefined;
    }
    cur = (cur as Record<string, unknown>)[p];
  }
  return typeof cur === "string" ? cur : undefined;
}

type TFn = (
  key: string,
  vars?: Record<string, string | number>
) => string;

type LocaleContextValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: TFn;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const raw = localStorage.getItem(STORAGE_LOCALE);
    if (raw === "ru" || raw === "en") return raw;
  } catch {
    /* ignore */
  }
  return "en";
}

function readMachineCache(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = sessionStorage.getItem(STORAGE_MACHINE);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      const out: Record<string, string> = {};
      for (const [k, v] of Object.entries(parsed)) {
        if (typeof v === "string") out[k] = v;
      }
      return out;
    }
  } catch {
    /* ignore */
  }
  return {};
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [machineCache, setMachineCache] = useState<Record<string, string>>({});
  const pendingRef = useRef(new Set<string>());
  const hydratedRef = useRef(false);

  useEffect(() => {
    setLocaleState(readStoredLocale());
    setMachineCache(readMachineCache());
    hydratedRef.current = true;
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    try {
      sessionStorage.setItem(STORAGE_MACHINE, JSON.stringify(machineCache));
    } catch {
      /* ignore */
    }
  }, [machineCache]);

  useEffect(() => {
    try {
      document.documentElement.lang = locale;
    } catch {
      /* ignore */
    }
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_LOCALE, l);
    } catch {
      /* ignore */
    }
  }, []);

  const fillMissing = useCallback(
    async (key: string, englishText: string) => {
      if (locale !== "ru" || !isRemoteI18nEnabled()) return;
      if (pendingRef.current.has(key)) return;
      pendingRef.current.add(key);
      try {
        const tr = await translateMyMemory(englishText, "en", "ru");
        if (tr) {
          setMachineCache((prev) => ({ ...prev, [key]: tr }));
        }
      } finally {
        pendingRef.current.delete(key);
      }
    },
    [locale]
  );

  const t = useCallback<TFn>(
    (key, vars) => {
      const machine = machineCache[key];
      if (machine) return interpolate(machine, vars);

      const dict = dictionaries[locale];
      const enDict = dictionaries.en;
      let raw = getByPath(dict, key);
      if (!raw && locale !== "en") {
        raw = getByPath(enDict, key);
        if (raw && locale === "ru") {
          queueMicrotask(() => void fillMissing(key, raw!));
        }
      }
      return interpolate(raw ?? key, vars);
    },
    [locale, machineCache, fillMissing]
  );

  const value = useMemo(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t]
  );

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) {
    throw new Error("useLocale must be used within LocaleProvider");
  }
  return ctx;
}

export function useTranslations(): TFn {
  return useLocale().t;
}
