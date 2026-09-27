export type Account = {
  id: string;
  email: string;
  role: 'victim' | 'ngo_investigator' | 'administrator';
  is_active: boolean;
  created_at: string;
};

export type Case = {
  id: string;
  owner_id: string;
  assigned_investigator_id: string | null;
  title: string;
  victim_statement: string | null;
  status: 'open' | 'in_review' | 'closed' | 'archived';
  created_at: string;
  updated_at: string | null;
};

export type SubmittedLink = {
  id: string;
  case_id: string;
  submitted_by: string;
  url: string;
  shared_text: string | null;
  evidence_id: string | null;
  created_at: string;
};

export type Evidence = {
  id: string;
  case_id: string;
  platform: string;
  original_url: string;
  capture_status: string;
  capture_error: string | null;
  capture_timestamp: string | null;
  hash_sha256: string | null;
  page_title: string | null;
  visible_author: string | null;
  visible_timestamp: string | null;
  visible_text: string | null;
  visible_comments: string | null;
  created_at: string;
};

export type EvidenceFile = {
  id: string;
  evidence_id: string;
  file_type: string;
  mime_type: string;
  size: number;
  hash_sha256: string;
  created_at: string;
};

export type Analysis = {
  id: string;
  evidence_id: string;
  model_name: string;
  summary: string;
  entities: string[];
  detected_threats: string[];
  detected_pii: string[];
  tags: string[];
  timeline: string[];
  created_at: string;
};

export type TimelineEvent = {
  timestamp: string;
  kind: string;
  reference_id: string;
  description: string;
};

export type CaseNote = {
  id: string;
  case_id: string;
  user_id: string;
  body: string;
  created_at: string;
};

export type Audit = {
  id: string;
  user_id: string | null;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  timestamp: string;
};
