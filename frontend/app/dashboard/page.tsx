import { redirect } from "next/navigation";

/** Contacts are the primary workspace until Overview has real content. */
export default function DashboardHomePage() {
  redirect("/dashboard/leads");
}
