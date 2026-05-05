"use client";

import { useLayoutEffect } from "react";
import { PageLoader } from "@/components/page-loader";
import { getToken } from "@/lib/auth";

export default function HomePage() {
  useLayoutEffect(() => {
    const dest = getToken() ? "/dashboard/leads" : "/login";
    window.location.replace(dest);
  }, []);

  return <PageLoader fullscreen />;
}
