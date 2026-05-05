"use client";

import Link from "next/link";
import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useParams, useRouter } from "next/navigation";
import { Loader2, Trash2 } from "lucide-react";

import { LeadEmailHistoryTrigger } from "@/components/lead-email-history-dialog";
import { LeadCompanyCell } from "@/components/lead-company-cell";
import { PageLoader } from "@/components/page-loader";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
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
import type {
  Campaign,
  CampaignStatus,
  Lead,
  LeadStatus,
} from "@/lib/types";

export default function CampaignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const t = useTranslations();
  const tRef = useRef(t);
  tRef.current = t;
  const campaignStatusLabel = useMemo(
    () =>
      ({
        draft: t("campaign.status.draft"),
        active: t("campaign.status.active"),
        paused: t("campaign.status.paused"),
      }) satisfies Record<CampaignStatus, string>,
    [t]
  );
  const leadStatusLabel = useMemo(
    () =>
      ({
        new: t("lead.status.new"),
        contacted: t("lead.status.contacted"),
        replied: t("lead.status.replied"),
        interested: t("lead.status.interested"),
        rejected: t("lead.status.rejected"),
      }) satisfies Record<LeadStatus, string>,
    [t]
  );

  const id = typeof params.id === "string" ? params.id : "";

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [firstRules, setFirstRules] = useState("");
  const [followRules, setFollowRules] = useState("");
  const [status, setStatus] = useState<CampaignStatus>("draft");
  const [maxEmailsDraft, setMaxEmailsDraft] = useState("");
  const [delayMinDraft, setDelayMinDraft] = useState("");
  const [delayMaxDraft, setDelayMaxDraft] = useState("");
  const [throttleErrors, setThrottleErrors] = useState<{
    maxEmails?: string;
    delayMin?: string;
    delayMax?: string;
  }>({});

  const loadAll = useCallback(async () => {
    const ctrl = new AbortController();
    const timeoutId = window.setTimeout(() => ctrl.abort(), 45_000);
    try {
      const [c, ls] = await Promise.all([
        apiJson<Campaign>(`/api/campaigns/${id}`, { signal: ctrl.signal }),
        apiJson<Lead[]>(`/api/campaigns/${id}/leads`, { signal: ctrl.signal }),
      ]);
      setCampaign(c);
      setName(c.name);
      setSystemPrompt(c.system_prompt);
      setFirstRules(c.first_email_rules);
      setFollowRules(c.follow_up_rules);
      setStatus(c.status);
      setMaxEmailsDraft(
        String(Math.min(2000, Math.max(1, Math.floor(c.max_emails_per_day ?? 50))))
      );
      setDelayMinDraft(
        String(
          Math.min(
            1440,
            Math.max(1, Math.round((c.send_delay_min_seconds ?? 300) / 60)),
          ),
        ),
      );
      setDelayMaxDraft(
        String(
          Math.min(
            1440,
            Math.max(1, Math.round((c.send_delay_max_seconds ?? 1200) / 60)),
          ),
        ),
      );
      setThrottleErrors({});
      setLeads(ls);
    } finally {
      window.clearTimeout(timeoutId);
    }
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setCampaign(null);
    setLeads([]);
    setError(null);
    let cancelled = false;
    (async () => {
      try {
        await loadAll();
      } catch (e) {
        if (!cancelled) {
          const aborted =
            (e instanceof DOMException || e instanceof Error) &&
            e.name === "AbortError";
          setError(
            e instanceof ApiError
              ? e.message
              : aborted
                ? tRef.current("campaignDetail.loadTimeout")
                : tRef.current("campaignDetail.loadError")
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, loadAll]);

  async function onSaveCampaign(e: FormEvent) {
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
      setError(t("campaignDetail.delayOrderError"));
      return;
    }
    setSaving(true);
    try {
      await apiJson<Campaign>(`/api/campaigns/${id}`, {
        method: "PATCH",
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
      router.push("/dashboard/campaigns");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignDetail.saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function updateLeadStatus(leadId: string, newStatus: LeadStatus) {
    setError(null);
    try {
      await apiJson<Lead>(`/api/leads/${leadId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      setLeads((prev) =>
        prev.map((l) =>
          l.id === leadId ? { ...l, status: newStatus } : l
        )
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignDetail.updateError"));
    }
  }

  async function removeLead(leadId: string) {
    if (!confirm(t("campaignDetail.confirmDeleteLead"))) return;
    setError(null);
    try {
      await apiJson(`/api/leads/${leadId}`, { method: "DELETE" });
      setLeads((prev) => prev.filter((l) => l.id !== leadId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignDetail.deleteLeadError"));
    }
  }

  if (!id) {
    return (
      <p className="text-muted-foreground">{t("campaignDetail.invalidLink")}</p>
    );
  }

  if (loading) {
    return <PageLoader fullscreen />;
  }

  if (!campaign) {
    return (
      <div className="space-y-4">
        <p className="text-destructive">{error ?? t("campaignDetail.notFound")}</p>
        <Link
          href="/dashboard/campaigns"
          className={cn(buttonVariants({ variant: "outline" }))}
        >
          {t("campaignDetail.backToList")}
        </Link>
      </div>
    );
  }

  return (
    <div className="relative w-full max-w-none space-y-8">
      <div>
        <Link
          href="/dashboard/campaigns"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          {t("campaignDetail.backToList")}
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight">
          {campaign.name}
        </h1>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <form onSubmit={onSaveCampaign}>
        <Card>
          <CardHeader>
            <CardTitle>{t("campaignDetail.editTitle")}</CardTitle>
            <CardDescription>{t("campaignDetail.editDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6">
            <div className="grid gap-2">
              <Label htmlFor="name">{t("campaignDetail.name")}</Label>
              <Input
                id="name"
                required
                value={name}
                onChange={(ev) => setName(ev.target.value)}
                disabled={saving}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="status">{t("campaignDetail.status")}</Label>
              <select
                id="status"
                value={status}
                onChange={(ev) =>
                  setStatus(ev.target.value as CampaignStatus)
                }
                disabled={saving}
                className="flex h-9 w-full max-w-xs rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {(Object.keys(campaignStatusLabel) as CampaignStatus[]).map(
                  (k) => (
                    <option key={k} value={k}>
                      {campaignStatusLabel[k]}
                    </option>
                  )
                )}
              </select>
            </div>
            <p className="text-xs text-muted-foreground">
              {t("campaignDetail.throttleIntro")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("common.numericThrottleInputHint")}
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="grid gap-2">
                <Label htmlFor="max_emails_per_day">
                  {t("campaignDetail.maxEmailsPerDay")}
                </Label>
                <Input
                  id="max_emails_per_day"
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
                  disabled={saving}
                />
                {throttleErrors.maxEmails ? (
                  <p className="text-xs text-destructive" role="alert">
                    {throttleErrors.maxEmails}
                  </p>
                ) : null}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="delay_min_minutes">
                  {t("campaignDetail.delayMinMinutes")}
                </Label>
                <Input
                  id="delay_min_minutes"
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
                  disabled={saving}
                />
                {throttleErrors.delayMin ? (
                  <p className="text-xs text-destructive" role="alert">
                    {throttleErrors.delayMin}
                  </p>
                ) : null}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="delay_max_minutes">
                  {t("campaignDetail.delayMaxMinutes")}
                </Label>
                <Input
                  id="delay_max_minutes"
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
                  disabled={saving}
                />
                {throttleErrors.delayMax ? (
                  <p className="text-xs text-destructive" role="alert">
                    {throttleErrors.delayMax}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="system_prompt">{t("campaignDetail.systemPrompt")}</Label>
              <Textarea
                id="system_prompt"
                required
                value={systemPrompt}
                onChange={(ev) => setSystemPrompt(ev.target.value)}
                disabled={saving}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="first_email_rules">{t("campaignDetail.firstEmailRules")}</Label>
              <Textarea
                id="first_email_rules"
                required
                value={firstRules}
                onChange={(ev) => setFirstRules(ev.target.value)}
                disabled={saving}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="follow_up_rules">{t("campaignDetail.followUpRules")}</Label>
              <p className="text-xs text-muted-foreground">
                {t("campaignDetail.followUpRulesHint")}
              </p>
              <Textarea
                id="follow_up_rules"
                required
                value={followRules}
                onChange={(ev) => setFollowRules(ev.target.value)}
                disabled={saving}
              />
            </div>
          </CardContent>
          <CardContent className="flex flex-wrap gap-2 border-t border-border pt-6">
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("campaignDetail.saving")}
                </>
              ) : (
                t("campaignDetail.saveChanges")
              )}
            </Button>
          </CardContent>
        </Card>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>{t("campaignDetail.leadsTitle")}</CardTitle>
          <CardDescription>{t("campaignDetail.leadsDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          {leads.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("campaignDetail.leadsEmpty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tableEmail")}</th>
                    <th className="pb-2 pr-3 font-medium">
                      {t("leadsPage.tableCompany")}
                    </th>
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tablePain")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tableStatus")}</th>
                    <th className="pb-2 pr-3 text-center font-medium">
                      {t("campaignDetail.tableEmails")}
                    </th>
                    <th className="pb-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {leads.map((l) => (
                    <tr key={l.id} className="border-b border-border/60">
                      <td className="py-2 pr-3 align-middle">{l.email}</td>
                      <td className="py-2 pr-3 align-middle">
                        <LeadCompanyCell
                          lead={l}
                          emptyLabel={t("common.notAvailable")}
                        />
                      </td>
                      <td className="min-w-[12rem] max-w-xl whitespace-normal break-words py-2 pr-3 align-middle text-muted-foreground" title={l.pain_point ?? ""}>
                        {l.pain_point ?? t("common.notAvailable")}
                      </td>
                      <td className="py-2 pr-3 align-middle">
                        <select
                          value={l.status}
                          onChange={(ev) =>
                            updateLeadStatus(
                              l.id,
                              ev.target.value as LeadStatus
                            )
                          }
                          className="max-w-full rounded-md border border-input bg-transparent px-2 py-1 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          {(Object.keys(leadStatusLabel) as LeadStatus[]).map(
                            (k) => (
                              <option key={k} value={k}>
                                {leadStatusLabel[k]}
                              </option>
                            )
                          )}
                        </select>
                      </td>
                      <td className="py-2 pr-3 text-center align-middle">
                        <LeadEmailHistoryTrigger
                          leadId={l.id}
                          leadEmail={l.email}
                          variant="icon"
                        />
                      </td>
                      <td className="py-2 text-right align-middle">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          className="text-destructive hover:text-destructive"
                          onClick={() => removeLead(l.id)}
                          aria-label={t("campaignDetail.deleteLeadAria")}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
