"use client";

import { forwardRef } from "react";

import { cn } from "@/lib/utils";

export const Checkbox = forwardRef<
  HTMLInputElement,
  React.ComponentPropsWithoutRef<"input">
>(function Checkbox({ className, type = "checkbox", ...props }, ref) {
  return (
    <input
      ref={ref}
      type={type}
      className={cn(
        "size-4 shrink-0 rounded border border-input bg-background text-primary shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
});
