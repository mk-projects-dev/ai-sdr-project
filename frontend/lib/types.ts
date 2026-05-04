export type CampaignStatus = "draft" | "active" | "paused";

export interface Campaign {
  id: string;
  name: string;
  system_prompt: string;
  first_email_rules: string;
  follow_up_rules: string;
  status: CampaignStatus;
}

export type LeadStatus =
  | "new"
  | "contacted"
  | "replied"
  | "interested"
  | "rejected";

export interface Lead {
  id: string;
  campaign_id: string;
  email: string;
  first_name: string | null;
  company_name: string | null;
  pain_point: string | null;
  source?: string | null;
  status: LeadStatus;
  created_at: string;
}

export interface LeadImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}
