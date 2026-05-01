"use client";

import { Button } from "@/components/ui/button";
import { useLocale } from "@/lib/i18n/locale-provider";
import type { Locale } from "@/lib/i18n/locale-provider";

const locales: { code: Locale; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "ru", label: "RU" },
];

export function LocaleSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useLocale();

  return (
    <div className={`flex items-center gap-1 ${className ?? ""}`}>
      <span className="sr-only">{t("common.language")}</span>
      {locales.map(({ code, label }) => (
        <Button
          key={code}
          type="button"
          variant={locale === code ? "default" : "outline"}
          size="sm"
          className="h-8 min-w-[2.25rem] px-2 text-xs"
          onClick={() => setLocale(code)}
          aria-pressed={locale === code}
        >
          {label}
        </Button>
      ))}
    </div>
  );
}
