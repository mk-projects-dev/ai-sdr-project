"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Pause, Pencil, Play, Plus, Trash2 } from "lucide-react";

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
import { ApiError, apiJson } from "@/lib/api-client";
import { useTranslations } from "@/lib/i18n/locale-provider";
import type { Campaign, CampaignStatus } from "@/lib/types";

export default function CampaignsPage() {
  const t = useTranslations();
  const tRef = useRef(t);
  tRef.current = t;
  const statusLabel = useMemo(
    () =>
      ({
        draft: t("campaign.status.draft"),
        active: t("campaign.status.active"),
        paused: t("campaign.status.paused"),
      }) satisfies Record<CampaignStatus, string>,
    [t]
  );

  const [items, setItems] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [statusUpdatingId, setStatusUpdatingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiJson<Campaign[]>("/api/campaigns");
        if (!cancelled) setItems(data);
      } catch (e) {
        if (!cancelled)
          setError(
            e instanceof ApiError ? e.message : tRef.current("campaigns.loadError")
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function patchCampaignStatus(campaignId: string, status: CampaignStatus) {
    setError(null);
    setStatusUpdatingId(campaignId);
    try {
      const updated = await apiJson<Campaign>(`/api/campaigns/${campaignId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setItems((prev) =>
        prev.map((c) => (c.id === campaignId ? updated : c))
      );
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : t("campaigns.statusUpdateError")
      );
    } finally {
      setStatusUpdatingId(null);
    }
  }

  async function deleteCampaignRow(campaignId: string, campaignName: string) {
    if (
      !confirm(
        t("campaigns.confirmDeleteCampaign", { name: campaignName })
      )
    )
      return;
    setError(null);
    setDeletingId(campaignId);
    try {
      await apiJson(`/api/campaigns/${campaignId}`, { method: "DELETE" });
      setItems((prev) => prev.filter((c) => c.id !== campaignId));
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : t("campaigns.deleteCampaignError")
      );
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return <PageLoader fullscreen />;
  }

  return (
    <div className="w-full max-w-none space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {t("campaigns.title")}
          </h1>
          <p className="mt-1 text-muted-foreground">{t("campaigns.subtitle")}</p>
        </div>
        <div className="flex flex-shrink-0 flex-wrap gap-2">
          <Link
            href="/dashboard/campaigns/new"
            className={cn(buttonVariants())}
          >
            <Plus className="mr-2 size-4" />
            {t("campaigns.newCampaign")}
          </Link>
        </div>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("campaigns.listTitle")}</CardTitle>
          <CardDescription>{t("campaigns.listDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("campaigns.empty")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="pb-2 pr-4 font-medium">{t("campaigns.tableName")}</th>
                    <th className="pb-2 pr-4 font-medium">{t("campaigns.tableStatus")}</th>
                    <th className="pb-2 text-right font-medium">
                      {t("campaigns.tableActions")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr key={c.id} className="border-b border-border/60">
                      <td className="py-3 pr-4">
                        <Link
                          href={`/dashboard/campaigns/${c.id}`}
                          className="font-medium text-primary underline-offset-4 hover:underline"
                        >
                          {c.name}
                        </Link>
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {statusLabel[c.status] ?? c.status}
                      </td>
                      <td className="py-3">
                        <div className="flex flex-wrap items-center justify-end gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="icon-sm"
                            disabled={
                              c.status === "active" ||
                              statusUpdatingId !== null ||
                              deletingId !== null
                            }
                            aria-label={t("campaigns.playAria")}
                            title={t("campaigns.playAria")}
                            onClick={() => patchCampaignStatus(c.id, "active")}
                          >
                            {statusUpdatingId === c.id ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <Play className="size-4 fill-current" aria-hidden />
                            )}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="icon-sm"
                            disabled={
                              c.status === "paused" ||
                              statusUpdatingId !== null ||
                              deletingId !== null
                            }
                            aria-label={t("campaigns.pauseAria")}
                            title={t("campaigns.pauseAria")}
                            onClick={() => patchCampaignStatus(c.id, "paused")}
                          >
                            {statusUpdatingId === c.id ? (
                              <Loader2 className="size-4 animate-spin" />
                            ) : (
                              <Pause className="size-4" aria-hidden />
                            )}
                          </Button>
                          <Link
                            href={`/dashboard/campaigns/${c.id}`}
                            className={cn(
                              buttonVariants({ variant: "outline", size: "icon-sm" })
                            )}
                            aria-label={t("campaigns.editAria")}
                            title={t("campaigns.editAria")}
                          >
                            <Pencil className="size-4" aria-hidden />
                          </Link>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            className="text-destructive hover:text-destructive"
                            disabled={
                              deletingId !== null || statusUpdatingId !== null
                            }
                            aria-label={t("campaigns.deleteCampaign")}
                            onClick={() => deleteCampaignRow(c.id, c.name)}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </div>
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
