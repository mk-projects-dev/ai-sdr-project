"use client";

import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useTranslations } from "@/lib/i18n/locale-provider";

export default function DashboardHomePage() {
  const t = useTranslations();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">
          {t("dashboard.overview.title")}
        </h1>
        <p className="mt-1 text-muted-foreground">
          {t("dashboard.overview.subtitle")}
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.overview.statusCardTitle")}</CardTitle>
          <CardDescription>
            {t("dashboard.overview.statusCardBody")}
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
