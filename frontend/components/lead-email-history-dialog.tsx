"use client";

import { useEffect, useState } from "react";
import { Loader2, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ApiError, apiJson } from "@/lib/api-client";
import { useTranslations } from "@/lib/i18n/locale-provider";
import type { EmailInteraction } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  leadId: string;
  leadEmail: string;
  variant?: "button" | "icon";
};

export function LeadEmailHistoryTrigger({
  leadId,
  leadEmail,
  variant = "button",
}: Props) {
  const t = useTranslations();
  const [open, setOpen] = useState(false);

  return (
    <>
      {variant === "icon" ? (
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={() => setOpen(true)}
          aria-label={t("emailHistory.openAria", { email: leadEmail })}
        >
          <Mail className="size-4" />
        </Button>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setOpen(true)}
        >
          <Mail className="mr-1.5 size-4" />
          {t("emailHistory.open")}
        </Button>
      )}
      <LeadEmailHistoryDialog
        leadId={leadId}
        leadEmail={leadEmail}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}

type DialogOnlyProps = {
  leadId: string;
  leadEmail: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function LeadEmailHistoryDialog({
  leadId,
  leadEmail,
  open,
  onOpenChange,
}: DialogOnlyProps) {
  const t = useTranslations();
  const [items, setItems] = useState<EmailInteraction[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setItems(null);
    (async () => {
      try {
        const data = await apiJson<EmailInteraction[]>(
          `/api/leads/${leadId}/interactions`
        );
        if (!cancelled) setItems(data);
      } catch (e) {
        if (!cancelled) {
          setError(
            e instanceof ApiError ? e.message : t("emailHistory.loadError")
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, leadId, t]);

  const dirLabel = (d: EmailInteraction["direction"]) =>
    d === "outbound" ? t("emailHistory.outbound") : t("emailHistory.inbound");

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("emailHistory.title")}
      description={t("emailHistory.description", { email: leadEmail })}
      panelClassName="max-h-[85vh] max-w-3xl overflow-hidden flex flex-col"
    >
      <div className="flex min-h-0 flex-1 flex-col gap-3">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            {t("common.loading")}
          </div>
        ) : null}
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        {!loading && !error && items && items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("emailHistory.empty")}</p>
        ) : null}
        {!loading && !error && items && items.length > 0 ? (
          <ul className="max-h-[55vh] space-y-3 overflow-y-auto pr-1 text-sm">
            {items.map((row) => (
              <li
                key={row.id}
                className={cn(
                  "rounded-lg border border-border p-3",
                  row.direction === "outbound"
                    ? "bg-muted/30"
                    : "bg-background"
                )}
              >
                <div className="flex flex-wrap items-baseline gap-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-xs font-medium",
                      row.direction === "outbound"
                        ? "bg-primary/15 text-primary"
                        : "bg-secondary text-secondary-foreground"
                    )}
                  >
                    {dirLabel(row.direction)}
                  </span>
                  <time className="text-xs text-muted-foreground">
                    {new Date(row.sent_at).toLocaleString(undefined, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </time>
                </div>
                <p className="mt-1 font-medium">{row.subject}</p>
                <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words font-sans text-xs text-muted-foreground">
                  {row.body}
                </pre>
                {row.ai_intent ? (
                  <p className="mt-2 border-t border-border pt-2 text-xs">
                    <span className="font-medium text-foreground">
                      {t("emailHistory.aiIntent")}:{" "}
                    </span>
                    <span className="text-muted-foreground">{row.ai_intent}</span>
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          {t("emailHistory.close")}
        </Button>
      </div>
    </Dialog>
  );
}
