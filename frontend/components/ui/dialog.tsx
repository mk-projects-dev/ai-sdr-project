"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  /** Extra classes for the modal panel (e.g. wider dialogs). */
  panelClassName?: string;
  children: ReactNode;
};

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  panelClassName,
  children,
}: DialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/50 backdrop-blur-[1px]"
        aria-label="Close dialog backdrop"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={cn(
          "relative z-10 w-full max-w-lg rounded-lg border border-border bg-background p-6 shadow-lg",
          panelClassName
        )}
      >
        <h2 id="dialog-title" className="text-lg font-semibold tracking-tight">
          {title}
        </h2>
        {description ? (
          <p id="dialog-description" className="mt-1 text-sm text-muted-foreground">
            {description}
          </p>
        ) : null}
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
