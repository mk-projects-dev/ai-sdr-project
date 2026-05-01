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
import { Loader2, Trash2, Upload } from "lucide-react";

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
import { ApiError, apiFetch, apiJson } from "@/lib/api-client";
import { useTranslations } from "@/lib/i18n/locale-provider";
import type {
  Campaign,
  CampaignStatus,
  Lead,
  LeadImportResult,
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
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [firstRules, setFirstRules] = useState("");
  const [followRules, setFollowRules] = useState("");
  const [status, setStatus] = useState<CampaignStatus>("draft");

  const loadAll = useCallback(async () => {
    const [c, ls] = await Promise.all([
      apiJson<Campaign>(`/api/campaigns/${id}`),
      apiJson<Lead[]>(`/api/campaigns/${id}/leads`),
    ]);
    setCampaign(c);
    setName(c.name);
    setSystemPrompt(c.system_prompt);
    setFirstRules(c.first_email_rules);
    setFollowRules(c.follow_up_rules);
    setStatus(c.status);
    setLeads(ls);
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
        if (!cancelled)
          setError(
            e instanceof ApiError
              ? e.message
              : tRef.current("campaignDetail.loadError")
          );
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
    setSaving(true);
    try {
      const updated = await apiJson<Campaign>(`/api/campaigns/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name,
          system_prompt: systemPrompt,
          first_email_rules: firstRules,
          follow_up_rules: followRules,
          status,
        }),
      });
      setCampaign(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignDetail.saveError"));
    } finally {
      setSaving(false);
    }
  }

  async function onCsv(ev: React.ChangeEvent<HTMLInputElement>) {
    const file = ev.target.files?.[0];
    ev.target.value = "";
    if (!file) return;
    setImportMessage(null);
    setError(null);
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch(`/api/campaigns/${id}/leads/import`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        let msg = res.statusText;
        try {
          const j = (await res.json()) as { detail?: string };
          if (typeof j.detail === "string") msg = j.detail;
        } catch {
          /* ignore */
        }
        throw new ApiError(msg, res.status);
      }
      const result = (await res.json()) as LeadImportResult;
      setImportMessage(
        t("campaignDetail.importSummary", {
          created: result.created,
          skipped: result.skipped,
          errors: result.errors.length,
        })
      );
      await loadAll();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignDetail.importError"));
    } finally {
      setImporting(false);
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

  async function removeCampaign() {
    if (!confirm(t("campaignDetail.confirmDeleteCampaign"))) return;
    setError(null);
    try {
      await apiJson(`/api/campaigns/${id}`, { method: "DELETE" });
      router.push("/dashboard/campaigns");
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("campaignDetail.deleteCampaignError"));
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

  const pageBusy = saving || importing;

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
    <div className="relative mx-auto max-w-5xl space-y-8">
      {pageBusy ? <PageLoader fullscreen /> : null}
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
            <Button
              type="button"
              variant="destructive"
              onClick={removeCampaign}
            >
              <Trash2 className="mr-2 size-4" />
              {t("campaignDetail.deleteCampaign")}
            </Button>
          </CardContent>
        </Card>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>{t("campaignDetail.csvTitle")}</CardTitle>
          <CardDescription>{t("campaignDetail.csvDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <label
              className={cn(
                buttonVariants({ variant: "outline" }),
                importing && "pointer-events-none opacity-50",
                "cursor-pointer"
              )}
            >
              {importing ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("campaignDetail.importing")}
                </>
              ) : (
                <>
                  <Upload className="mr-2 size-4" />
                  {t("campaignDetail.chooseCsv")}
                </>
              )}
              <input
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                disabled={importing}
                onChange={onCsv}
              />
            </label>
          </div>
          {importMessage ? (
            <p className="text-sm text-muted-foreground">{importMessage}</p>
          ) : null}
        </CardContent>
      </Card>

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
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tableNameCol")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tableCompany")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tablePain")}</th>
                    <th className="pb-2 pr-3 font-medium">{t("campaignDetail.tableStatus")}</th>
                    <th className="pb-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {leads.map((l) => (
                    <tr key={l.id} className="border-b border-border/60">
                      <td className="py-2 pr-3 align-middle">{l.email}</td>
                      <td className="py-2 pr-3 align-middle">
                        {l.first_name ?? t("common.notAvailable")}
                      </td>
                      <td className="py-2 pr-3 align-middle">
                        {l.company_name ?? t("common.notAvailable")}
                      </td>
                      <td className="max-w-[180px] truncate py-2 pr-3 align-middle text-muted-foreground" title={l.pain_point ?? ""}>
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
