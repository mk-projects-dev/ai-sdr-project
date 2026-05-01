"use client";

import { Loader2 } from "lucide-react";

import { useTranslations } from "@/lib/i18n/locale-provider";
import { cn } from "@/lib/utils";

type PageLoaderProps = {
  /** `true` — весь viewport (блокирует сайдбар и навигацию). `false` — только родитель с `position: relative`. */
  fullscreen?: boolean;
  className?: string;
};

export function PageLoader({ fullscreen = true, className }: PageLoaderProps) {
  const t = useTranslations();

  const inner = (
    <>
      <Loader2
        className="size-8 animate-spin text-primary"
        aria-hidden
      />
      <p className="mt-4 text-sm font-medium text-muted-foreground">
        {t("common.loading")}
      </p>
    </>
  );

  if (fullscreen) {
    return (
      <div
        className={cn(
          "fixed inset-0 z-[100] flex flex-col items-center justify-center bg-background/90 backdrop-blur-[2px]",
          className
        )}
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        {inner}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "absolute inset-0 z-30 flex flex-col items-center justify-center rounded-lg bg-background/95 backdrop-blur-sm",
        className
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      {inner}
    </div>
  );
}
