export type UserRole = "ADMIN" | "USER";
export type AccountStatus = "ACTIVE" | "DISABLED";

export interface DepartmentSummary {
  id: string;
  name: string;
  slug: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: AccountStatus;
  department_id: string;
  department: DepartmentSummary | null;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreatedUser extends User {
  temporary_password: string;
}

export interface Department {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Organisation {
  id: string;
  name: string;
  description: string | null;
  industry: string | null;
  locations: string[];
  timezone: string;
  extra_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: number;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface PasswordResetResponse {
  temporary_password: string;
}

export type ConnectorType = "GOOGLE_SHEETS" | "ZOHO_CRM";
export type SnapshotStatus = "READY" | "PARTIAL" | "FAILED";
export type SyncStatus = "RUNNING" | "SUCCEEDED" | "PARTIAL" | "FAILED";
export type SyncTrigger = "SCHEDULED" | "MANUAL";

export interface Connector {
  id: string;
  name: string;
  type: ConnectorType;
  is_active: boolean;
  config: Record<string, unknown>;
  has_credentials: boolean;
  last_validated_at: string | null;
  last_validation_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectorAsset {
  external_id: string;
  name: string;
  kind: string;
  config: Record<string, unknown>;
}

export interface ConnectorValidationResult {
  ok: boolean;
  error: string | null;
  last_validated_at: string | null;
}

export interface SnapshotSummary {
  id: string;
  captured_at: string;
  status: SnapshotStatus;
  record_count: number;
}

export interface DataSource {
  id: string;
  connector_id: string;
  connector_name: string;
  connector_type: ConnectorType;
  external_id: string;
  name: string;
  kind: string;
  config: Record<string, unknown>;
  is_active: boolean;
  schema_hash: string | null;
  current_snapshot: SnapshotSummary | null;
  created_at: string;
  updated_at: string;
}

export interface SyncJob {
  id: string;
  data_source_id: string;
  status: SyncStatus;
  trigger: SyncTrigger;
  actor_user_id: string | null;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  record_count: number | null;
  snapshot_id: string | null;
}

export interface Snapshot {
  id: string;
  data_source_id: string;
  captured_at: string;
  status: SnapshotStatus;
  record_count: number;
  schema_hash: string | null;
  source_metadata: Record<string, unknown>;
}

export interface DepartmentSourceEntry {
  data_source_id: string;
  name: string;
  kind: string;
  connector_name: string;
  granted: boolean;
  is_active: boolean;
  last_sync_at: string | null;
  snapshot_status: SnapshotStatus | null;
}

export interface DepartmentSources {
  department_id: string;
  department_name: string;
  entries: DepartmentSourceEntry[];
}

export type SmtpSecurity = "NONE" | "STARTTLS" | "SSL";
export type MailFrequency = "DAILY" | "WEEKLY" | "MONTHLY";
export type MailExecutionStatus =
  "RUNNING" | "SUCCEEDED" | "PARTIAL" | "FAILED" | "SKIPPED";
export type MailDeliveryStatus = "SENT" | "FAILED" | "SKIPPED";
export type MailTrigger = "SCHEDULED" | "MANUAL";

export interface MailSettings {
  host: string;
  port: number;
  username: string | null;
  from_email: string;
  from_name: string | null;
  security: SmtpSecurity;
  has_password: boolean;
  last_tested_at: string | null;
  last_test_error: string | null;
  updated_at: string;
}

export interface MailTestResult {
  ok: boolean;
  error: string | null;
  last_tested_at: string | null;
}

export interface MailTemplate {
  id: string;
  name: string;
  description: string | null;
  subject_template: string;
  system_prompt: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MailPreview {
  ok: boolean;
  error: string | null;
  subject: string;
  body: string;
  sources_used: string[];
  sources_excluded: string[];
}

export interface MailSchedule {
  id: string;
  name: string;
  template_id: string;
  template_name: string;
  department_id: string;
  department_name: string;
  enabled: boolean;
  frequency: MailFrequency;
  time_of_day: string;
  weekday: number | null;
  day_of_month: number | null;
  timezone: string;
  row_limit: number;
  next_run_at: string | null;
  last_run_at: string | null;
  source_ids: string[];
  source_names: string[];
  created_at: string;
  updated_at: string;
}

export interface MailExecution {
  id: string;
  schedule_id: string;
  trigger: MailTrigger;
  scheduled_for: string;
  status: MailExecutionStatus;
  started_at: string;
  finished_at: string | null;
  recipient_count: number;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  error: string | null;
}

export interface MailExecutionSummary extends MailExecution {
  schedule_name: string;
  department_name: string;
}

export interface MailDelivery {
  id: string;
  execution_id?: string;
  email: string;
  status: MailDeliveryStatus;
  error: string | null;
  message_id: string | null;
  subject: string | null;
  body: string | null;
  department_id: string | null;
  recipient_user_id: string | null;
  sent_at: string | null;
}

export interface MailExecutionDetail extends MailExecutionSummary {
  deliveries: MailDelivery[];
}
