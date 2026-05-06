export type CampaignStatus = "draft" | "active" | "paused";

export interface Campaign {
  id: string;
  name: string;
  system_prompt: string;
  first_email_rules: string;
  follow_up_rules: string;
  status: CampaignStatus;
  /** Daily cap on first-outreach sends for this campaign (UTC calendar day). */
  max_emails_per_day: number;
  /** Random pause lower bound after each successful send (seconds). */
  send_delay_min_seconds: number;
  send_delay_max_seconds: number;
}

export type LeadStatus =
  | "new"
  | "contacted"
  | "replied"
  | "interested"
  | "rejected";

export interface Lead {
  id: string;
  campaign_id: string | null;
  campaign_name?: string | null;
  email: string;
  company_name: string | null;
  pain_point: string | null;
  website_url?: string | null;
  maps_url?: string | null;
  source?: string | null;
  status: LeadStatus;
  created_at: string;
}

export type EmailDirection = "outbound" | "inbound";

export interface EmailInteraction {
  id: string;
  direction: EmailDirection;
  subject: string;
  body: string;
  ai_intent: string | null;
  sent_at: string;
  input_tokens?: number;
  output_tokens?: number;
  cost?: number;
}

export interface LeadImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}
