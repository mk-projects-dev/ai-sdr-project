"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { PageLoader } from "@/components/page-loader";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiJson } from "@/lib/api-client";
import {
  parseBoundedInt,
  sanitizeUnsignedDigits,
} from "@/lib/parse-bounded-int";
import { useTranslations } from "@/lib/i18n/locale-provider";
import type { Campaign, CampaignStatus } from "@/lib/types";

export default function NewCampaignPage() {
  const router = useRouter();
  const t = useTranslations();
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [firstRules, setFirstRules] = useState("");
  const [followRules, setFollowRules] = useState("");
  const [status, setStatus] = useState<CampaignStatus>("draft");
  const [maxEmailsDraft, setMaxEmailsDraft] = useState("50");
  const [delayMinDraft, setDelayMinDraft] = useState("5");
  const [delayMaxDraft, setDelayMaxDraft] = useState("20");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [throttleErrors, setThrottleErrors] = useState<{
    maxEmails?: string;
    delayMin?: string;
    delayMax?: string;
  }>({});

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const maxDay = parseBoundedInt(maxEmailsDraft, 1, 2000);
    const mn = parseBoundedInt(delayMinDraft, 1, 1440);
    const mx = parseBoundedInt(delayMaxDraft, 1, 1440);
    if (maxDay === null || mn === null || mx === null) {
      setThrottleErrors({
        maxEmails:
          maxDay === null
            ? t("common.numericThrottleDailyCapInvalid")
            : undefined,
        delayMin:
          mn === null ? t("common.numericThrottleDelayMinInvalid") : undefined,
        delayMax:
          mx === null ? t("common.numericThrottleDelayMaxInvalid") : undefined,
      });
      return;
    }
    setThrottleErrors({});
    if (mn > mx) {
      setError(t("campaignNew.delayOrderError"));
      return;
    }
    setLoading(true);
    try {
      const created = await apiJson<Campaign>("/api/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name,
          system_prompt: systemPrompt,
          first_email_rules: firstRules,
          follow_up_rules: followRules,
          status,
          max_emails_per_day: maxDay,
          send_delay_min_seconds: mn * 60,
          send_delay_max_seconds: mx * 60,
        }),
      });
      router.push(`/dashboard/campaigns/${created.id}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignNew.saveError"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative w-full max-w-none space-y-6">
      {loading ? <PageLoader fullscreen /> : null}
      <div>
        <Link
          href="/dashboard/campaigns"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          {t("campaignNew.backToList")}
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">
          {t("campaignNew.title")}
        </h1>
      </div>

      <form onSubmit={onSubmit}>
        <Card>
          <CardHeader>
            <CardTitle>{t("campaignNew.cardTitle")}</CardTitle>
            <CardDescription>{t("campaignNew.cardDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6">
            <div className="grid gap-2">
              <Label htmlFor="name">{t("campaignNew.name")}</Label>
              <Input
                id="name"
                required
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                disabled={loading}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="status">{t("campaignNew.status")}</Label>
              <select
                id="status"
                value={status}
                onChange={(ev) =>
                  setStatus(ev.target.value as CampaignStatus)
                }
                disabled={loading}
                className="flex h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="draft">{t("campaign.status.draft")}</option>
                <option value="active">{t("campaign.status.active")}</option>
                <option value="paused">{t("campaign.status.paused")}</option>
              </select>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("campaignNew.throttleIntro")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("common.numericThrottleInputHint")}
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-2">
                <Label htmlFor="new_max_emails_per_day">
                  {t("campaignNew.maxEmailsPerDay")}
                </Label>
                <Input
                  id="new_max_emails_per_day"
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  aria-invalid={Boolean(throttleErrors.maxEmails)}
                  value={maxEmailsDraft}
                  onChange={(ev) => {
                    setMaxEmailsDraft(sanitizeUnsignedDigits(ev.target.value));
                    setThrottleErrors((prev) => ({
                      ...prev,
                      maxEmails: undefined,
                    }));
                  }}
                  disabled={loading}
                />
                {throttleErrors.maxEmails ? (
                  <p className="text-xs text-destructive" role="alert">
                    {throttleErrors.maxEmails}
                  </p>
                ) : null}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="new_delay_min_minutes">
                  {t("campaignNew.delayMinMinutes")}
                </Label>
                <Input
                  id="new_delay_min_minutes"
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  aria-invalid={Boolean(throttleErrors.delayMin)}
                  value={delayMinDraft}
                  onChange={(ev) => {
                    setDelayMinDraft(sanitizeUnsignedDigits(ev.target.value));
                    setThrottleErrors((prev) => ({
                      ...prev,
                      delayMin: undefined,
                    }));
                  }}
                  disabled={loading}
                />
                {throttleErrors.delayMin ? (
                  <p className="text-xs text-destructive" role="alert">
                    {throttleErrors.delayMin}
                  </p>
                ) : null}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="new_delay_max_minutes">
                  {t("campaignNew.delayMaxMinutes")}
                </Label>
                <Input
                  id="new_delay_max_minutes"
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  aria-invalid={Boolean(throttleErrors.delayMax)}
                  value={delayMaxDraft}
                  onChange={(ev) => {
                    setDelayMaxDraft(sanitizeUnsignedDigits(ev.target.value));
                    setThrottleErrors((prev) => ({
                      ...prev,
                      delayMax: undefined,
                    }));
                  }}
                  disabled={loading}
                />
                {throttleErrors.delayMax ? (
                  <p className="text-xs text-destructive" role="alert">
                    {throttleErrors.delayMax}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="system_prompt">{t("campaignNew.systemPrompt")}</Label>
              <Textarea
                id="system_prompt"
                required
                value={systemPrompt}
                onChange={(ev) => setSystemPrompt(ev.target.value)}
                disabled={loading}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="first_email_rules">{t("campaignNew.firstEmailRules")}</Label>
              <Textarea
                id="first_email_rules"
                required
                value={firstRules}
                onChange={(ev) => setFirstRules(ev.target.value)}
                disabled={loading}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="follow_up_rules">{t("campaignNew.followUpRules")}</Label>
              <Textarea
                id="follow_up_rules"
                required
                value={followRules}
                onChange={(ev) => setFollowRules(ev.target.value)}
                disabled={loading}
              />
            </div>
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </CardContent>
          <CardFooter className="gap-2">
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("campaignNew.saving")}
                </>
              ) : (
                t("campaignNew.saveCreate")
              )}
            </Button>
            <Link
              href="/dashboard/campaigns"
              className={cn(buttonVariants({ variant: "outline" }))}
            >
              {t("campaignNew.cancel")}
            </Link>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
}
