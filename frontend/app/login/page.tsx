"use client";

import { FormEvent, useLayoutEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { PageLoader } from "@/components/page-loader";
import { Button } from "@/components/ui/button";
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
import { LocaleSwitcher } from "@/components/locale-switcher";
import { getPublicApiUrl } from "@/lib/api-config";
import { getToken, setToken } from "@/lib/auth";
import { useTranslations } from "@/lib/i18n/locale-provider";

interface LoginResponse {
  access_token: string;
  token_type: string;
}

export default function LoginPage() {
  const router = useRouter();
  const t = useTranslations();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sessionGate, setSessionGate] = useState<"pending" | "ok">("pending");

  useLayoutEffect(() => {
    if (getToken()) {
      router.replace("/dashboard");
    } else {
      setSessionGate("ok");
    }
  }, [router]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${getPublicApiUrl()}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const text = await res.text();
        let detail = t("login.errorInvalid");
        try {
          const j = JSON.parse(text) as { detail?: string };
          if (typeof j.detail === "string") detail = j.detail;
        } catch {
          /* ignore */
        }
        setError(detail);
        return;
      }
      const data = (await res.json()) as LoginResponse;
      setToken(data.access_token);
      router.push("/dashboard");
      router.refresh();
    } catch {
      setError(t("login.errorNetwork"));
    } finally {
      setLoading(false);
    }
  }

  if (sessionGate !== "ok") {
    return <PageLoader fullscreen />;
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <div className="absolute right-4 top-4 z-[110]">
        <LocaleSwitcher />
      </div>
      <Card className="w-full max-w-md shadow-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-semibold tracking-tight">
            {t("login.title")}
          </CardTitle>
          <CardDescription>{t("login.subtitle")}</CardDescription>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="email">{t("login.email")}</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(ev) => setEmail(ev.target.value)}
                disabled={loading}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(ev) => setPassword(ev.target.value)}
                disabled={loading}
              />
            </div>
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </CardContent>
          <CardFooter className="flex flex-col gap-4">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("login.submitting")}
                </>
              ) : (
                t("login.submit")
              )}
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              <Link href="/" className="underline underline-offset-4">
                {t("common.home")}
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
