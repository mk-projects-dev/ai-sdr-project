"use client";

import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  FileDown,
  Globe,
  Loader2,
  MapPin,
  Upload,
} from "lucide-react";

import { PageLoader } from "@/components/page-loader";
import { Button, buttonVariants } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { LeadEmailHistoryTrigger } from "@/components/lead-email-history-dialog";
import { LeadCompanyCell } from "@/components/lead-company-cell";
import { cn } from "@/lib/utils";
import { ApiError, apiFetch, apiJson } from "@/lib/api-client";
import { useTranslations } from "@/lib/i18n/locale-provider";
import type {
  Campaign,
  Lead,
  LeadImportResult,
  LeadStatus,
} from "@/lib/types";

type SortColumn =
  | "created_at"
  | "company"
  | "email"
  | "pain"
  | "status"
  | "campaign";

const STATUS_RANK: Record<LeadStatus, number> = {
  new: 0,
  contacted: 1,
  replied: 2,
  interested: 3,
  rejected: 4,
};

const ALL_LEAD_STATUSES: LeadStatus[] = [
  "new",
  "contacted",
  "replied",
  "interested",
  "rejected",
];

/** Uses browser locale and local timezone (API sends UTC ISO strings). */
function formatLeadDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

/** Matches backend `csv_leads.py` canonical headers (comma or semicolon also accepted on upload). */
const LEADS_IMPORT_TEMPLATE_FILENAME = "leads_import_template.csv";

function LeadSourceLinks({
  lead,
  websiteLabel,
  mapsLabel,
}: {
  lead: Lead;
  websiteLabel: string;
  mapsLabel: string;
}) {
  const web = lead.website_url?.trim();
  const maps = lead.maps_url?.trim();
  if (!web && !maps) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  const webHref = web
    ? web.startsWith("http://") || web.startsWith("https://")
      ? web
      : `https://${web}`
    : null;
  return (
    <div className="flex flex-wrap items-center gap-0.5">
      {webHref ? (
        <a
          href={webHref}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            buttonVariants({ variant: "ghost", size: "icon" }),
            "size-8 shrink-0 text-muted-foreground hover:text-foreground",
          )}
          title={websiteLabel}
          aria-label={websiteLabel}
        >
          <Globe className="size-4" aria-hidden />
        </a>
      ) : null}
      {maps ? (
        <a
          href={maps}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            buttonVariants({ variant: "ghost", size: "icon" }),
            "size-8 shrink-0 text-muted-foreground hover:text-foreground",
          )}
          title={mapsLabel}
          aria-label={mapsLabel}
        >
          <MapPin className="size-4" aria-hidden />
        </a>
      ) : null}
    </div>
  );
}

function downloadLeadsImportTemplateCsv() {
  const bom = "\uFEFF";
  const header = "email,company_name,pain_point,website\n";
  const blob = new Blob([bom + header], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = LEADS_IMPORT_TEMPLATE_FILENAME;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function LeadsPoolPage() {
  const t = useTranslations();
  const tRef = useRef(t);
  tRef.current = t;

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

  const [leads, setLeads] = useState<Lead[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [csvOpen, setCsvOpen] = useState(false);
  const [parserOpen, setParserOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);

  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);

  const [parserLocation, setParserLocation] = useState("");
  const [parserKeyword, setParserKeyword] = useState("");
  const [parserLimit, setParserLimit] = useState(10);
  const [isParsing, setIsParsing] = useState(false);
  const [parserPolling, setParserPolling] = useState(false);

  /** ISO время старта текущего запуска с сервера (`POST /api/parser/run`), для сопоставления с `GET /api/parser/status`. */
  const parserRunStartedAtRef = useRef<string | null>(null);

  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [assigning, setAssigning] = useState(false);

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sortColumn, setSortColumn] = useState<SortColumn>("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [statusFilters, setStatusFilters] = useState<Set<LeadStatus>>(
    () => new Set(ALL_LEAD_STATUSES)
  );
  const [emailFilter, setEmailFilter] = useState("");

  const loadLeads = useCallback(async () => {
    const data = await apiJson<Lead[]>("/api/leads");
    setLeads(data);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    const timeoutId = window.setTimeout(() => ctrl.abort(), 45_000);
    (async () => {
      try {
        const [leadsData, campsData] = await Promise.all([
          apiJson<Lead[]>("/api/leads", { signal: ctrl.signal }),
          apiJson<Campaign[]>("/api/campaigns", { signal: ctrl.signal }),
        ]);
        if (!cancelled) {
          setLeads(leadsData);
          setCampaigns(campsData);
        }
      } catch (e) {
        if (!cancelled) {
          const aborted =
            (e instanceof DOMException || e instanceof Error) &&
            e.name === "AbortError";
          setError(
            e instanceof ApiError
              ? e.message
              : aborted
                ? tRef.current("leadsPage.loadTimeout")
                : tRef.current("leadsPage.loadError")
          );
        }
      } finally {
        window.clearTimeout(timeoutId);
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      ctrl.abort();
    };
  }, []);

  useEffect(() => {
    if (!parserPolling) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [parserPolling]);

  useEffect(() => {
    if (!parserPolling) return;

    const startedIso = parserRunStartedAtRef.current;
    if (!startedIso) {
      setParserPolling(false);
      return;
    }

    const pollMs = 2000;
    const maxMs = 4 * 60 * 1000;
    const fetchDeadlineMs = 14_000;
    const wallStart = Date.now();
    const timers: {
      intervalId?: number;
      firstId?: number;
      watchdogId?: number;
    } = {};
    let cancelled = false;

    const cleanupTimers = () => {
      if (timers.watchdogId !== undefined) window.clearTimeout(timers.watchdogId);
      if (timers.firstId !== undefined) window.clearTimeout(timers.firstId);
      if (timers.intervalId !== undefined) window.clearInterval(timers.intervalId);
      timers.watchdogId = undefined;
      timers.firstId = undefined;
      timers.intervalId = undefined;
    };

    const finishOk = (created: number) => {
      if (cancelled) return;
      cancelled = true;
      cleanupTimers();
      parserRunStartedAtRef.current = null;
      setParserPolling(false);
      if (created > 0) {
        setImportMessage(
          tRef.current("leadsPage.parserDoneNew", { count: created }),
        );
      } else {
        setImportMessage(tRef.current("leadsPage.parserDoneZero"));
      }
    };

    const finishTimeout = () => {
      if (cancelled) return;
      cancelled = true;
      cleanupTimers();
      parserRunStartedAtRef.current = null;
      setParserPolling(false);
      void loadLeads();
      setImportMessage(tRef.current("leadsPage.parserPollingTimeout"));
    };

    /** Жёсткий предел по времени: не зависим от зависших fetch (иначе лоадер не уходит). */
    timers.watchdogId = window.setTimeout(() => finishTimeout(), maxMs);

    async function fetchJsonWithDeadline<T>(path: string): Promise<T> {
      const ctrl = new AbortController();
      const tid = window.setTimeout(() => ctrl.abort(), fetchDeadlineMs);
      try {
        return await apiJson<T>(path, { signal: ctrl.signal });
      } finally {
        window.clearTimeout(tid);
      }
    }

    const tick = async () => {
      if (cancelled) return;
      if (Date.now() - wallStart > maxMs) {
        finishTimeout();
        return;
      }
      try {
        const status = await fetchJsonWithDeadline<{
          busy: boolean;
          last_finished_at: string | null;
          last_created_count: number;
        }>("/api/parser/status");

        try {
          const leadsData = await fetchJsonWithDeadline<Lead[]>("/api/leads");
          if (!cancelled) setLeads(leadsData);
        } catch {
          /* вторично */
        }

        const startTs = Date.parse(startedIso);
        const finishedAt = status.last_finished_at;
        const finishedTs = finishedAt ? Date.parse(finishedAt) : NaN;
        const runLooksFinished =
          !status.busy &&
          Boolean(finishedAt) &&
          !Number.isNaN(startTs) &&
          !Number.isNaN(finishedTs) &&
          finishedTs >= startTs - 2000;

        if (runLooksFinished) {
          finishOk(status.last_created_count);
          return;
        }
      } catch {
        /* до watchdog продолжаем опрос */
      }
    };

    timers.firstId = window.setTimeout(() => void tick(), 400);
    timers.intervalId = window.setInterval(() => void tick(), pollMs);

    return () => {
      cancelled = true;
      cleanupTimers();
    };
  }, [parserPolling, loadLeads]);

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  const emailFilterNorm = emailFilter.trim().toLowerCase();

  const filteredLeads = useMemo(() => {
    return leads.filter((l) => {
      if (!statusFilters.has(l.status)) return false;
      if (
        emailFilterNorm &&
        !l.email.toLowerCase().includes(emailFilterNorm)
      ) {
        return false;
      }
      return true;
    });
  }, [leads, statusFilters, emailFilterNorm]);

  const sortedLeads = useMemo(() => {
    const copy = [...filteredLeads];
    const dir = sortDir === "asc" ? 1 : -1;

    const tieBreak = (a: Lead, b: Lead, primary: number): number => {
      if (primary !== 0) return primary * dir;
      return b.created_at.localeCompare(a.created_at);
    };

    copy.sort((a, b) => {
      switch (sortColumn) {
        case "status":
          return tieBreak(a, b, STATUS_RANK[a.status] - STATUS_RANK[b.status]);
        case "email":
          return tieBreak(a, b, a.email.localeCompare(b.email));
        case "company": {
          const ca = (a.company_name ?? "").trim().toLowerCase();
          const cb = (b.company_name ?? "").trim().toLowerCase();
          return tieBreak(a, b, ca.localeCompare(cb, undefined, { sensitivity: "base" }));
        }
        case "pain": {
          const pa = a.pain_point ?? "";
          const pb = b.pain_point ?? "";
          return tieBreak(a, b, pa.localeCompare(pb, undefined, { sensitivity: "base" }));
        }
        case "campaign": {
          const ca = a.campaign_name ?? "";
          const cb = b.campaign_name ?? "";
          return tieBreak(a, b, ca.localeCompare(cb, undefined, { sensitivity: "base" }));
        }
        case "created_at":
          return dir * a.created_at.localeCompare(b.created_at);
      }
    });
    return copy;
  }, [filteredLeads, sortColumn, sortDir]);

  function toggleAll(checked: boolean) {
    if (!checked) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(sortedLeads.map((l) => l.id)));
  }

  function toggleStatusFilter(status: LeadStatus, checked: boolean) {
    setStatusFilters((prev) => {
      const next = new Set(prev);
      if (checked) next.add(status);
      else next.delete(status);
      return next;
    });
  }

  function resetFilters() {
    setStatusFilters(new Set(ALL_LEAD_STATUSES));
    setEmailFilter("");
  }

  const allStatusesSelected = ALL_LEAD_STATUSES.every((s) =>
    statusFilters.has(s)
  );

  function onSortColumn(column: SortColumn) {
    if (sortColumn === column) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDir(column === "created_at" ? "desc" : "asc");
  }

  function SortableHead({
    column,
    label,
    className,
  }: {
    column: SortColumn;
    label: string;
    className?: string;
  }) {
    const active = sortColumn === column;
    return (
      <TableHead
        className={className}
        aria-sort={
          active
            ? sortDir === "asc"
              ? "ascending"
              : "descending"
            : "none"
        }
      >
        <button
          type="button"
          className={cn(
            "-mx-2 inline-flex max-w-full items-center gap-1 rounded px-2 py-1 text-left font-medium hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          )}
          onClick={() => onSortColumn(column)}
        >
          <span className="truncate">{label}</span>
          {active ? (
            sortDir === "asc" ? (
              <ChevronUp className="size-4 shrink-0 opacity-70" aria-hidden />
            ) : (
              <ChevronDown className="size-4 shrink-0 opacity-70" aria-hidden />
            )
          ) : (
            <ChevronsUpDown
              className="size-3.5 shrink-0 opacity-35"
              aria-hidden
            />
          )}
        </button>
      </TableHead>
    );
  }

  const allSelected =
    sortedLeads.length > 0 &&
    sortedLeads.every((l) => selectedIds.has(l.id));
  const someSelected = selectedIds.size > 0;

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
      const res = await apiFetch("/api/leads/import", {
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
        t("leadsPage.importSummary", {
          created: result.created,
          skipped: result.skipped,
          errors: result.errors.length,
        })
      );
      await loadLeads();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("leadsPage.importError"));
    } finally {
      setImporting(false);
    }
  }

  async function onRunParser(e: FormEvent) {
    e.preventDefault();
    if (parserPolling) return;
    setError(null);
    setImportMessage(null);
    const loc = parserLocation.trim();
    const kw = parserKeyword.trim();
    if (!loc || !kw) {
      setError(t("leadsPage.parserValidationEmpty"));
      return;
    }
    let lim = Number(parserLimit);
    if (!Number.isFinite(lim) || lim < 1) lim = 10;
    lim = Math.min(50, Math.max(1, Math.floor(lim)));

    setIsParsing(true);
    try {
      const data = await apiJson<{ status: string; started_at: string }>(
        "/api/parser/run",
        {
          method: "POST",
          body: JSON.stringify({
            location: loc,
            keyword: kw,
            limit: lim,
          }),
        },
      );
      if (data.status === "started" && data.started_at) {
        parserRunStartedAtRef.current = data.started_at;
        setParserLocation("");
        setParserKeyword("");
        setParserLimit(10);
        setParserOpen(false);
        setParserPolling(true);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(t("leadsPage.parserAlreadyRunning"));
      } else {
        setError(
          err instanceof ApiError ? err.message : t("leadsPage.parserError"),
        );
      }
    } finally {
      setIsParsing(false);
    }
  }

  async function onBulkAssign(e: FormEvent) {
    e.preventDefault();
    if (!selectedCampaignId || selectedIds.size === 0) return;
    const leadIds = Array.from(selectedIds);
    const assignedCount = leadIds.length;
    setAssigning(true);
    setError(null);
    try {
      await apiJson<{ updated: number }>("/api/leads/bulk-assign", {
        method: "POST",
        body: JSON.stringify({
          lead_ids: leadIds,
          campaign_id: selectedCampaignId,
        }),
      });
      setAssignOpen(false);
      setSelectedIds(new Set());
      setSelectedCampaignId("");
      await loadLeads();
      try {
        const campsData = await apiJson<Campaign[]>("/api/campaigns");
        setCampaigns(campsData);
      } catch {
        /* статусы кампаний вторичны после успешного assign */
      }
      setImportMessage(t("leadsPage.assignSuccess", { count: assignedCount }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("leadsPage.assignError"));
    } finally {
      setAssigning(false);
    }
  }

  if (loading) {
    return <PageLoader fullscreen />;
  }

  return (
    <div className="w-full max-w-none space-y-6">
      {parserPolling ? (
        <div
          className="fixed inset-0 z-[130] flex flex-col items-center justify-center gap-4 bg-background/95 px-6 text-center backdrop-blur-sm"
          role="status"
          aria-live="polite"
          aria-busy="true"
        >
          <Loader2 className="size-10 animate-spin text-primary" aria-hidden />
          <div className="max-w-md space-y-2">
            <p className="text-base font-semibold">{t("leadsPage.parserPollingTitle")}</p>
            <p className="text-sm text-muted-foreground">
              {t("leadsPage.parserPollingHint")}
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              parserRunStartedAtRef.current = null;
              setParserPolling(false);
              void loadLeads();
              setImportMessage(t("leadsPage.parserPollingDismissed"));
            }}
          >
            {t("leadsPage.parserPollingCancel")}
          </Button>
        </div>
      ) : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {t("leadsPage.title")}
          </h1>
          <p className="mt-1 text-muted-foreground">{t("leadsPage.subtitle")}</p>
        </div>
        <div className="flex flex-shrink-0 flex-wrap gap-2">
          <Button
            type="button"
            onClick={downloadLeadsImportTemplateCsv}
          >
            <FileDown className="mr-2 size-4" />
            {t("leadsPage.downloadTemplateCsv")}
          </Button>
          <Button type="button" onClick={() => setCsvOpen(true)}>
            <Upload className="mr-2 size-4" />
            {t("leadsPage.uploadCsv")}
          </Button>
          <Button
            type="button"
            disabled={parserPolling}
            onClick={() => setParserOpen(true)}
          >
            <MapPin className="mr-2 size-4" />
            {t("leadsPage.runParser")}
          </Button>
        </div>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {importMessage ? (
        <p className="text-sm text-muted-foreground" role="status">
          {importMessage}
        </p>
      ) : null}

      {someSelected ? (
        <div
          className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/40 px-4 py-3"
          role="region"
          aria-label={t("leadsPage.bulkSelected", { count: selectedIds.size })}
        >
          <span className="text-sm font-medium">
            {t("leadsPage.bulkSelected", { count: selectedIds.size })}
          </span>
          <Button type="button" size="sm" onClick={() => setAssignOpen(true)}>
            {t("leadsPage.assignCampaign")}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setSelectedIds(new Set())}
          >
            {t("leadsPage.clearSelection")}
          </Button>
        </div>
      ) : null}

      {leads.length > 0 ? (
        <div
          className="rounded-lg border border-border bg-muted/20 px-4 py-3"
          role="search"
          aria-label={t("leadsPage.filterRegionAria")}
        >
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="grid flex-1 gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                {t("leadsPage.filterStatusLabel")}
              </span>
              <div className="flex flex-wrap gap-x-4 gap-y-2">
                {ALL_LEAD_STATUSES.map((st) => (
                  <label
                    key={st}
                    className="flex cursor-pointer items-center gap-2 text-sm"
                  >
                    <Checkbox
                      checked={statusFilters.has(st)}
                      onChange={(ev) =>
                        toggleStatusFilter(st, ev.target.checked)
                      }
                    />
                    <span>{leadStatusLabel[st]}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="grid w-full gap-2 sm:max-w-xs lg:w-72">
              <Label htmlFor="leads_email_filter" className="text-xs font-medium text-muted-foreground">
                {t("leadsPage.filterEmailLabel")}
              </Label>
              <Input
                id="leads_email_filter"
                type="search"
                value={emailFilter}
                onChange={(ev) => setEmailFilter(ev.target.value)}
                placeholder={t("leadsPage.filterEmailPlaceholder")}
                autoComplete="off"
              />
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
            <p className="text-xs text-muted-foreground">
              {t("leadsPage.filterShowing", {
                shown: sortedLeads.length,
                total: leads.length,
              })}
            </p>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              disabled={allStatusesSelected && emailFilter.trim() === ""}
            >
              {t("leadsPage.filterReset")}
            </Button>
          </div>
        </div>
      ) : null}

      <div className="rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  aria-label={t("leadsPage.selectAll")}
                  checked={allSelected}
                  onChange={(ev) => toggleAll(ev.target.checked)}
                />
              </TableHead>
              <SortableHead column="company" label={t("leadsPage.tableCompany")} />
              <TableHead className="w-[4.5rem] whitespace-normal">
                {t("leadsPage.tableSource")}
              </TableHead>
              <SortableHead column="email" label={t("leadsPage.tableEmail")} />
              <SortableHead column="pain" label={t("leadsPage.tablePain")} />
              <SortableHead column="status" label={t("leadsPage.tableStatus")} />
              <SortableHead column="campaign" label={t("leadsPage.tableCampaign")} />
              <SortableHead
                column="created_at"
                label={t("leadsPage.tableCreated")}
                className="whitespace-nowrap"
              />
              <TableHead className="w-12 text-center">
                {t("leadsPage.tableEmails")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {leads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-muted-foreground">
                  {t("leadsPage.empty")}
                </TableCell>
              </TableRow>
            ) : sortedLeads.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className="text-muted-foreground">
                  {t("leadsPage.filterEmpty")}
                </TableCell>
              </TableRow>
            ) : (
              sortedLeads.map((l) => (
                <TableRow key={l.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={l.email}
                      checked={selectedIds.has(l.id)}
                      onChange={(ev) => toggleOne(l.id, ev.target.checked)}
                    />
                  </TableCell>
                  <TableCell>
                    <LeadCompanyCell
                      lead={l}
                      emptyLabel={t("common.notAvailable")}
                    />
                  </TableCell>
                  <TableCell className="align-middle">
                    <LeadSourceLinks
                      lead={l}
                      websiteLabel={t("sourceLink")}
                      mapsLabel={t("viewInMaps")}
                    />
                  </TableCell>
                  <TableCell>{l.email}</TableCell>
                  <TableCell
                    className="min-w-[12rem] max-w-xl whitespace-normal break-words text-muted-foreground"
                    title={l.pain_point ?? ""}
                  >
                    {l.pain_point ?? t("common.notAvailable")}
                  </TableCell>
                  <TableCell>{leadStatusLabel[l.status] ?? l.status}</TableCell>
                  <TableCell>
                    {l.campaign_name ?? t("leadsPage.noCampaign")}
                  </TableCell>
                  <TableCell
                    className="whitespace-nowrap text-xs text-muted-foreground"
                    title={l.created_at}
                  >
                    {formatLeadDateTime(l.created_at)}
                  </TableCell>
                  <TableCell className="text-center">
                    <LeadEmailHistoryTrigger
                      leadId={l.id}
                      leadEmail={l.email}
                      variant="icon"
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog
        open={csvOpen}
        onOpenChange={setCsvOpen}
        title={t("leadsPage.csvDialogTitle")}
        description={t("leadsPage.csvDialogDescription")}
      >
        <div className="flex flex-col gap-4">
          <label
            className={cn(
              buttonVariants(),
              importing && "pointer-events-none opacity-50",
              "cursor-pointer justify-center"
            )}
          >
            {importing ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                {t("leadsPage.importing")}
              </>
            ) : (
              <>
                <Upload className="mr-2 size-4" />
                {t("leadsPage.chooseCsv")}
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
          <Button type="button" variant="ghost" onClick={() => setCsvOpen(false)}>
            {t("leadsPage.close")}
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={parserOpen}
        onOpenChange={setParserOpen}
        title={t("leadsPage.parserDialogTitle")}
        description={t("leadsPage.parserDialogDescription")}
      >
        <form className="grid gap-4" onSubmit={onRunParser}>
          <div className="grid gap-2">
            <Label htmlFor="pool_parser_location">{t("leadsPage.parserLocationLabel")}</Label>
            <Input
              id="pool_parser_location"
              value={parserLocation}
              onChange={(ev) => setParserLocation(ev.target.value)}
              placeholder={t("leadsPage.parserLocationPlaceholder")}
              disabled={isParsing || parserPolling}
              autoComplete="off"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="pool_parser_keyword">{t("leadsPage.parserKeywordLabel")}</Label>
            <Input
              id="pool_parser_keyword"
              value={parserKeyword}
              onChange={(ev) => setParserKeyword(ev.target.value)}
              placeholder={t("leadsPage.parserKeywordPlaceholder")}
              disabled={isParsing || parserPolling}
              autoComplete="off"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="pool_parser_limit">{t("leadsPage.parserLimitLabel")}</Label>
            <Input
              id="pool_parser_limit"
              type="number"
              min={1}
              max={50}
              value={parserLimit}
              onChange={(ev) => {
                const raw = ev.target.value;
                if (raw === "") {
                  setParserLimit(10);
                  return;
                }
                const n = parseInt(raw, 10);
                setParserLimit(Number.isFinite(n) ? Math.min(50, Math.max(1, n)) : 10);
              }}
              disabled={isParsing || parserPolling}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={isParsing || parserPolling}>
              {isParsing ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("leadsPage.parserRunning")}
                </>
              ) : (
                t("leadsPage.parserRunButton")
              )}
            </Button>
            <Button type="button" onClick={() => setParserOpen(false)}>
              {t("leadsPage.cancel")}
            </Button>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={assignOpen}
        onOpenChange={(o) => {
          setAssignOpen(o);
          if (!o) setSelectedCampaignId("");
        }}
        title={t("leadsPage.assignDialogTitle")}
        description={t("leadsPage.assignDialogDescription")}
      >
        <form className="grid gap-4" onSubmit={onBulkAssign}>
          <div className="grid gap-2">
            <Label htmlFor="bulk_campaign">{t("leadsPage.selectCampaign")}</Label>
            <select
              id="bulk_campaign"
              required
              value={selectedCampaignId}
              onChange={(ev) => setSelectedCampaignId(ev.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">{t("leadsPage.selectCampaignPlaceholder")}</option>
              {campaigns.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={assigning || !selectedCampaignId}>
              {assigning ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("leadsPage.assigning")}
                </>
              ) : (
                t("leadsPage.confirmAssign")
              )}
            </Button>
            <Button type="button" onClick={() => setAssignOpen(false)}>
              {t("leadsPage.cancel")}
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}
