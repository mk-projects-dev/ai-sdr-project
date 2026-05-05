"use client";

import { useCallback, useEffect, useState } from "react";
import { DollarSign } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ApiError, apiJson } from "@/lib/api-client";
import { useTranslations } from "@/lib/i18n/locale-provider";
import { cn } from "@/lib/utils";

type BillingSummary = {
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
};

function formatUsd(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(amount);
}

function formatTokensCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${Math.round(n / 1000)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

type BillingWidgetProps = {
  fullWidth?: boolean;
};

/** Сводка LiteLLM/Anthropic spend; нативный title вместо отдельного Tooltip-компонента. */
export function BillingWidget({ fullWidth = true }: BillingWidgetProps) {
  const t = useTranslations();
  const [data, setData] = useState<BillingSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
    }
    try {
      const j = await apiJson<BillingSummary>("/api/billing/summary");
      setData(j);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "…");
      if (!background) {
        setData(null);
      }
    } finally {
      if (!background) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => {
      void load(true);
    }, 30_000);
    return () => window.clearInterval(interval);
  }, [load]);

  const amountLabel = loading ? "…" : data ? formatUsd(data.total_cost) : "—";

  const hoverDetail =
    data && !error
      ? t("billingHoverDetail", {
          inputLabel: t("inputTokens"),
          inputVal: formatTokensCompact(data.total_input_tokens),
          outputLabel: t("outputTokens"),
          outputVal: formatTokensCompact(data.total_output_tokens),
        })
      : t("billingCost");

  return (
    <span
      className={cn(fullWidth && "block w-full")}
      title={error ? `${t("billingCost")}: ${error}` : hoverDetail}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className={cn(
          "justify-center gap-1.5 font-normal text-sidebar-foreground hover:text-sidebar-accent-foreground",
          fullWidth && "w-full",
          !fullWidth && "min-w-0 shrink-0 px-2",
        )}
        aria-label={t("billingCost")}
        disabled={loading && !data}
        onClick={() => void load()}
      >
        <DollarSign className="size-4 shrink-0 opacity-80" aria-hidden />
        <span className="tabular-nums">{amountLabel}</span>
      </Button>
    </span>
  );
}
