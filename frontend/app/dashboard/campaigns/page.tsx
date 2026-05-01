"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Plus } from "lucide-react";

import { PageLoader } from "@/components/page-loader";
import { buttonVariants } from "@/components/ui/button";
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

  if (loading) {
    return <PageLoader fullscreen />;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">
            {t("campaigns.title")}
          </h1>
          <p className="mt-1 text-muted-foreground">{t("campaigns.subtitle")}</p>
        </div>
        <Link
          href="/dashboard/campaigns/new"
          className={cn(buttonVariants())}
        >
          <Plus className="mr-2 size-4" />
          {t("campaigns.newCampaign")}
        </Link>
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
                    <th className="pb-2 font-medium" />
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
                      <td className="py-3 text-right">
                        <Link
                          href={`/dashboard/campaigns/${c.id}`}
                          className={cn(
                            buttonVariants({ variant: "outline", size: "sm" })
                          )}
                        >
                          {t("campaigns.tableOpen")}
                        </Link>
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
