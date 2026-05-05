"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useLayoutEffect, useState } from "react";
import { LogOut, Megaphone, Users } from "lucide-react";

import { BillingWidget } from "@/components/billing-widget";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { PageLoader } from "@/components/page-loader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { clearToken, getToken } from "@/lib/auth";
import { useTranslations } from "@/lib/i18n/locale-provider";

const navItems = [
  {
    href: "/dashboard/campaigns",
    labelKey: "dashboard.nav.campaigns" as const,
    icon: Megaphone,
  },
  {
    href: "/dashboard/leads",
    labelKey: "dashboard.nav.leads" as const,
    icon: Users,
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const t = useTranslations();
  const [ready, setReady] = useState(false);

  useLayoutEffect(() => {
    if (!getToken()) {
      window.location.replace("/login");
      return;
    }
    setReady(true);
  }, []);

  function handleLogout() {
    clearToken();
    router.push("/login");
    router.refresh();
  }

  if (!ready) {
    return <PageLoader fullscreen />;
  }

  return (
    <div className="flex min-h-screen w-full">
      <aside className="hidden w-56 shrink-0 border-r border-border bg-sidebar text-sidebar-foreground md:flex md:flex-col">
        <div className="flex h-14 items-center border-b border-sidebar-border px-4">
          <span className="font-semibold tracking-tight">{t("dashboard.brand")}</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {navItems.map(({ href, labelKey, icon: Icon }) => {
            const active =
              pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/80 hover:text-sidebar-accent-foreground"
                )}
              >
                <Icon className="size-4 shrink-0" />
                {t(labelKey)}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-sidebar-border p-3 space-y-2">
          <BillingWidget />
          <LocaleSwitcher className="justify-center" />
          <Button
            variant="ghost"
            className="w-full justify-start gap-2 text-sidebar-foreground"
            type="button"
            onClick={handleLogout}
          >
            <LogOut className="size-4" />
            {t("dashboard.logout")}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between gap-2 border-b border-border px-4 md:hidden">
          <span className="font-semibold">{t("dashboard.brand")}</span>
          <div className="flex items-center gap-2">
            <LocaleSwitcher />
            <Button variant="outline" size="sm" type="button" onClick={handleLogout}>
              {t("dashboard.logout")}
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-[20px]">{children}</main>
      </div>
    </div>
  );
}
