"use client";

import type { Lead } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  lead: Pick<Lead, "company_name">;
  emptyLabel: string;
  className?: string;
};

export function LeadCompanyCell({ lead, emptyLabel, className }: Props) {
  const co = lead.company_name?.trim();
  if (!co) {
    return (
      <div className={cn("text-muted-foreground", className)}>{emptyLabel}</div>
    );
  }
  return <div className={cn("font-medium", className)}>{co}</div>;
}
