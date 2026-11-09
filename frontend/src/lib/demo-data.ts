import type {
  AuditLog,
  Connector,
  ConnectorAsset,
  DataSource,
  Department,
  MailDelivery,
  MailExecutionSummary,
  MailSchedule,
  MailSettings,
  MailTemplate,
  Organisation,
  Snapshot,
  SyncJob,
  User,
} from "./types";

const NOW = "2026-11-09T09:30:00Z";
const SYNCED = "2026-11-09T02:00:00Z";

export const DEMO_EMAIL = "admin@dossier.dev";
export const DEMO_PASSWORD = "demo";
export const DEMO_TEMP_PASSWORD = "Demo-Temp-2026";

const management: Department = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Management",
  slug: "management",
  description: "Leadership and shared oversight.",
  is_active: true,
  created_at: "2026-01-12T10:00:00Z",
  updated_at: "2026-01-12T10:00:00Z",
};

const sales: Department = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Sales",
  slug: "sales",
  description: "New business and account growth.",
  is_active: true,
  created_at: "2026-01-12T10:05:00Z",
  updated_at: "2026-01-12T10:05:00Z",
};

const finance: Department = {
  id: "33333333-3333-4333-8333-333333333333",
  name: "Finance",
  slug: "finance",
  description: "Revenue, margin, and reporting.",
  is_active: true,
  created_at: "2026-01-12T10:06:00Z",
  updated_at: "2026-01-12T10:06:00Z",
};

const operations: Department = {
  id: "44444444-4444-4444-8444-444444444444",
  name: "Operations",
  slug: "operations",
  description: "Warehouse, logistics, and supplier coordination.",
  is_active: true,
  created_at: "2026-01-12T10:07:00Z",
  updated_at: "2026-01-12T10:07:00Z",
};

function departmentRef(department: Department) {
  return { id: department.id, name: department.name, slug: department.slug };
}

export const DEMO_USER: User = {
  id: "a1111111-1111-4111-8111-111111111111",
  email: DEMO_EMAIL,
  full_name: "Alex Morgan",
  role: "ADMIN",
  status: "ACTIVE",
  department_id: management.id,
  department: departmentRef(management),
  must_change_password: false,
  last_login_at: NOW,
  created_at: "2026-01-12T10:10:00Z",
  updated_at: "2026-01-12T10:10:00Z",
};

const users: User[] = [
  DEMO_USER,
  {
    id: "a2222222-2222-4222-8222-222222222222",
    email: "sam@northwind.test",
    full_name: "Sam Rivera",
    role: "USER",
    status: "ACTIVE",
    department_id: sales.id,
    department: departmentRef(sales),
    must_change_password: false,
    last_login_at: "2026-11-09T08:12:00Z",
    created_at: "2026-02-03T09:00:00Z",
    updated_at: "2026-02-03T09:00:00Z",
  },
  {
    id: "a3333333-3333-4333-8333-333333333333",
    email: "priya@northwind.test",
    full_name: "Priya Shah",
    role: "USER",
    status: "ACTIVE",
    department_id: sales.id,
    department: departmentRef(sales),
    must_change_password: false,
    last_login_at: "2026-11-08T16:40:00Z",
    created_at: "2026-02-03T09:05:00Z",
    updated_at: "2026-02-03T09:05:00Z",
  },
  {
    id: "a4444444-4444-4444-8444-444444444444",
    email: "fiona@northwind.test",
    full_name: "Fiona Chen",
    role: "USER",
    status: "ACTIVE",
    department_id: finance.id,
    department: departmentRef(finance),
    must_change_password: false,
    last_login_at: "2026-11-09T07:55:00Z",
    created_at: "2026-02-03T09:10:00Z",
    updated_at: "2026-02-03T09:10:00Z",
  },
  {
    id: "a5555555-5555-4555-8555-555555555555",
    email: "omar@northwind.test",
    full_name: "Omar Haddad",
    role: "USER",
    status: "ACTIVE",
    department_id: operations.id,
    department: departmentRef(operations),
    must_change_password: false,
    last_login_at: "2026-11-07T11:20:00Z",
    created_at: "2026-02-03T09:15:00Z",
    updated_at: "2026-02-03T09:15:00Z",
  },
  {
    id: "a6666666-6666-4666-8666-666666666666",
    email: "lee@northwind.test",
    full_name: "Lee Park",
    role: "USER",
    status: "DISABLED",
    department_id: sales.id,
    department: departmentRef(sales),
    must_change_password: false,
    last_login_at: "2026-10-28T14:02:00Z",
    created_at: "2026-03-14T09:00:00Z",
    updated_at: "2026-10-28T14:02:00Z",
  },
];

const connectors: Connector[] = [
  {
    id: "c1111111-1111-4111-8111-111111111111",
    name: "Northwind Google Workspace",
    type: "GOOGLE_SHEETS",
    is_active: true,
    config: { spreadsheet_id: "1northwind-operations" },
    has_credentials: true,
    last_validated_at: "2026-11-08T18:00:00Z",
    last_validation_error: null,
    created_at: "2026-02-01T09:00:00Z",
    updated_at: "2026-11-08T18:00:00Z",
  },
  {
    id: "c2222222-2222-4222-8222-222222222222",
    name: "Northwind Zoho CRM",
    type: "ZOHO_CRM",
    is_active: true,
    config: { api_domain: "https://www.zohoapis.eu" },
    has_credentials: true,
    last_validated_at: "2026-11-08T18:02:00Z",
    last_validation_error: null,
    created_at: "2026-02-01T09:10:00Z",
    updated_at: "2026-11-08T18:02:00Z",
  },
  {
    id: "c3333333-3333-4333-8333-333333333333",
    name: "Warehouse Sheets (legacy)",
    type: "GOOGLE_SHEETS",
    is_active: false,
    config: { spreadsheet_id: "1legacy-warehouse" },
    has_credentials: false,
    last_validated_at: null,
    last_validation_error:
      "Credentials expired. Replace the service account key.",
    created_at: "2025-11-20T09:00:00Z",
    updated_at: "2026-09-01T09:00:00Z",
  },
];

const assets: Record<string, ConnectorAsset[]> = {
  "c1111111-1111-4111-8111-111111111111": [
    { external_id: "0", name: "Sales Pipeline", kind: "sheet", config: {} },
    { external_id: "1", name: "Finance Ledger", kind: "sheet", config: {} },
    { external_id: "2", name: "HR Roster", kind: "sheet", config: {} },
    { external_id: "3", name: "Campaigns", kind: "sheet", config: {} },
  ],
  "c2222222-2222-4222-8222-222222222222": [
    { external_id: "Deals", name: "Deals", kind: "crm_module", config: {} },
    {
      external_id: "Contacts",
      name: "Contacts",
      kind: "crm_module",
      config: {},
    },
    {
      external_id: "Accounts",
      name: "Accounts",
      kind: "crm_module",
      config: {},
    },
  ],
  "c3333333-3333-4333-8333-333333333333": [],
};

const sources: DataSource[] = [
  {
    id: "d1111111-1111-4111-8111-111111111111",
    connector_id: "c1111111-1111-4111-8111-111111111111",
    connector_name: "Northwind Google Workspace",
    connector_type: "GOOGLE_SHEETS",
    external_id: "0",
    name: "Sales Pipeline",
    kind: "sheet",
    config: {},
    is_active: true,
    schema_hash: "6f41c2a9b7d1",
    current_snapshot: {
      id: "e1111111-1111-4111-8111-111111111111",
      captured_at: SYNCED,
      status: "READY",
      record_count: 42,
    },
    created_at: "2026-02-02T09:00:00Z",
    updated_at: "2026-11-09T02:00:00Z",
  },
  {
    id: "d2222222-2222-4222-8222-222222222222",
    connector_id: "c2222222-2222-4222-8222-222222222222",
    connector_name: "Northwind Zoho CRM",
    connector_type: "ZOHO_CRM",
    external_id: "Deals",
    name: "Deals",
    kind: "crm_module",
    config: {},
    is_active: true,
    schema_hash: "8a12d4c0e3f7",
    current_snapshot: {
      id: "e2222222-2222-4222-8222-222222222222",
      captured_at: SYNCED,
      status: "READY",
      record_count: 128,
    },
    created_at: "2026-02-02T09:05:00Z",
    updated_at: "2026-11-09T02:00:00Z",
  },
  {
    id: "d3333333-3333-4333-8333-333333333333",
    connector_id: "c1111111-1111-4111-8111-111111111111",
    connector_name: "Northwind Google Workspace",
    connector_type: "GOOGLE_SHEETS",
    external_id: "1",
    name: "Finance Ledger",
    kind: "sheet",
    config: {},
    is_active: true,
    schema_hash: "2b73fa1189cd",
    current_snapshot: {
      id: "e3333333-3333-4333-8333-333333333333",
      captured_at: SYNCED,
      status: "READY",
      record_count: 67,
    },
    created_at: "2026-02-02T09:10:00Z",
    updated_at: "2026-11-09T02:00:00Z",
  },
  {
    id: "d4444444-4444-4444-8444-444444444444",
    connector_id: "c1111111-1111-4111-8111-111111111111",
    connector_name: "Northwind Google Workspace",
    connector_type: "GOOGLE_SHEETS",
    external_id: "2",
    name: "HR Roster",
    kind: "sheet",
    config: {},
    is_active: true,
    schema_hash: "c4e1b7a02d55",
    current_snapshot: {
      id: "e4444444-4444-4444-8444-444444444444",
      captured_at: SYNCED,
      status: "READY",
      record_count: 12,
    },
    created_at: "2026-02-02T09:15:00Z",
    updated_at: "2026-11-09T02:00:00Z",
  },
  {
    id: "d5555555-5555-4555-8555-555555555555",
    connector_id: "c2222222-2222-4222-8222-222222222222",
    connector_name: "Northwind Zoho CRM",
    connector_type: "ZOHO_CRM",
    external_id: "Contacts",
    name: "Contacts",
    kind: "crm_module",
    config: {},
    is_active: true,
    schema_hash: null,
    current_snapshot: null,
    created_at: "2026-11-08T15:00:00Z",
    updated_at: "2026-11-08T15:00:00Z",
  },
];

const grants: Record<string, string[]> = {
  [management.id]: [
    "d1111111-1111-4111-8111-111111111111",
    "d3333333-3333-4333-8333-333333333333",
  ],
  [sales.id]: [
    "d1111111-1111-4111-8111-111111111111",
    "d2222222-2222-4222-8222-222222222222",
  ],
  [finance.id]: ["d3333333-3333-4333-8333-333333333333"],
  [operations.id]: [],
};

const templates: MailTemplate[] = [
  {
    id: "f1111111-1111-4111-8111-111111111111",
    name: "Weekly pipeline brief",
    description: "A short Monday brief for the sales team.",
    subject_template: "{{ organisation.name }} — pipeline brief for {{ date }}",
    system_prompt:
      "Write a concise weekly pipeline update for the sales team. Start with the total value of open deals, then list the three largest open deals with owner, stage, and amount. Finish with one sentence about what needs attention.",
    is_active: true,
    created_at: "2026-02-10T09:00:00Z",
    updated_at: "2026-11-01T09:00:00Z",
  },
  {
    id: "f2222222-2222-4222-8222-222222222222",
    name: "Finance month-end",
    description: "Month-end summary for finance.",
    subject_template: "{{ department.name }} month-end — {{ date }}",
    system_prompt:
      "Write a month-end finance summary. Cover revenue, margin, and the largest movements. Keep it under 250 words and avoid speculation.",
    is_active: true,
    created_at: "2026-02-10T09:05:00Z",
    updated_at: "2026-10-20T09:00:00Z",
  },
  {
    id: "f3333333-3333-4333-8333-333333333333",
    name: "Operations digest",
    description: "Warehouse and supplier notes.",
    subject_template: "{{ organisation.name }} operations — {{ date }}",
    system_prompt:
      "Write a short operations digest covering supplier status and warehouse load.",
    is_active: false,
    created_at: "2026-04-02T09:00:00Z",
    updated_at: "2026-09-01T09:00:00Z",
  },
];

const schedules: MailSchedule[] = [
  {
    id: "e1111111-2222-4333-8444-555555555555",
    name: "Sales pipeline brief",
    template_id: "f1111111-1111-4111-8111-111111111111",
    template_name: "Weekly pipeline brief",
    department_id: sales.id,
    department_name: "Sales",
    enabled: true,
    frequency: "DAILY",
    time_of_day: "09:00:00",
    weekday: null,
    day_of_month: null,
    timezone: "Europe/London",
    row_limit: 50,
    next_run_at: "2026-11-10T09:00:00Z",
    last_run_at: "2026-11-09T09:00:00Z",
    source_ids: [
      "d1111111-1111-4111-8111-111111111111",
      "d2222222-2222-4222-8222-222222222222",
    ],
    source_names: ["Sales Pipeline", "Deals"],
    created_at: "2026-02-11T09:00:00Z",
    updated_at: "2026-11-01T09:00:00Z",
  },
  {
    id: "e2222222-3333-4444-8555-666666666666",
    name: "Finance month-end",
    template_id: "f2222222-2222-4222-8222-222222222222",
    template_name: "Finance month-end",
    department_id: finance.id,
    department_name: "Finance",
    enabled: true,
    frequency: "MONTHLY",
    time_of_day: "08:00:00",
    weekday: null,
    day_of_month: 1,
    timezone: "Europe/London",
    row_limit: 100,
    next_run_at: "2026-12-01T08:00:00Z",
    last_run_at: "2026-11-01T08:00:00Z",
    source_ids: ["d3333333-3333-4333-8333-333333333333"],
    source_names: ["Finance Ledger"],
    created_at: "2026-02-11T09:05:00Z",
    updated_at: "2026-10-15T09:00:00Z",
  },
  {
    id: "e3333333-4444-4555-8666-777777777777",
    name: "Operations weekly",
    template_id: "f3333333-3333-4333-8333-333333333333",
    template_name: "Operations digest",
    department_id: operations.id,
    department_name: "Operations",
    enabled: false,
    frequency: "WEEKLY",
    time_of_day: "07:30:00",
    weekday: 0,
    day_of_month: null,
    timezone: "Europe/London",
    row_limit: 50,
    next_run_at: null,
    last_run_at: null,
    source_ids: ["d5555555-5555-4555-8555-555555555555"],
    source_names: ["Contacts"],
    created_at: "2026-04-02T09:10:00Z",
    updated_at: "2026-09-01T09:00:00Z",
  },
];

const executions: MailExecutionSummary[] = [
  {
    id: "b1111111-1111-4111-8111-111111111111",
    schedule_id: "e1111111-2222-4333-8444-555555555555",
    schedule_name: "Sales pipeline brief",
    department_name: "Sales",
    trigger: "SCHEDULED",
    scheduled_for: "2026-11-09T09:00:00Z",
    status: "SUCCEEDED",
    started_at: "2026-11-09T09:00:01Z",
    finished_at: "2026-11-09T09:00:19Z",
    recipient_count: 2,
    sent_count: 2,
    failed_count: 0,
    skipped_count: 0,
    error: null,
  },
  {
    id: "b2222222-2222-4222-8222-222222222222",
    schedule_id: "e1111111-2222-4333-8444-555555555555",
    schedule_name: "Sales pipeline brief",
    department_name: "Sales",
    trigger: "MANUAL",
    scheduled_for: "2026-11-08T15:10:00Z",
    status: "PARTIAL",
    started_at: "2026-11-08T15:10:02Z",
    finished_at: "2026-11-08T15:10:31Z",
    recipient_count: 2,
    sent_count: 1,
    failed_count: 1,
    skipped_count: 0,
    error: "One delivery failed",
  },
  {
    id: "b3333333-3333-4333-8333-333333333333",
    schedule_id: "e2222222-3333-4444-8555-666666666666",
    schedule_name: "Finance month-end",
    department_name: "Finance",
    trigger: "SCHEDULED",
    scheduled_for: "2026-11-01T08:00:00Z",
    status: "SUCCEEDED",
    started_at: "2026-11-01T08:00:01Z",
    finished_at: "2026-11-01T08:00:14Z",
    recipient_count: 1,
    sent_count: 1,
    failed_count: 0,
    skipped_count: 0,
    error: null,
  },
];

const salesBody = `Hello Sam Rivera,

Open pipeline stands at $71,100 across four active deals.

- Soylent upgrade — Alex Kim — Negotiation — $31,000
- Acme expansion — Sam Rivera — Negotiation — $18,500
- Umbrella services — Priya Shah — Discovery — $12,000

Acme expansion has the nearest close date and needs a decision this week.

— Northwind Trading`;

const financeBody = `Hello Fiona Chen,

October closed at $412,800 in revenue, with gross margin at 38.2%.

The largest movement was a $46,000 increase in wholesale distribution, offset by a
$12,400 decline in returns. No material anomalies were recorded.

— Northwind Trading`;

const deliveries: MailDelivery[] = [
  {
    id: "b4444444-4444-4444-8444-444444444444",
    execution_id: "b1111111-1111-4111-8111-111111111111",
    email: "sam@northwind.test",
    status: "SENT",
    error: null,
    message_id: "<demo-1@northwind.test>",
    subject: "Northwind Trading — pipeline brief for Monday, 09 November 2026",
    body: salesBody,
    department_id: sales.id,
    recipient_user_id: "a2222222-2222-4222-8222-222222222222",
    sent_at: "2026-11-09T09:00:18Z",
  },
  {
    id: "b5555555-5555-4555-8555-555555555555",
    execution_id: "b1111111-1111-4111-8111-111111111111",
    email: "priya@northwind.test",
    status: "SENT",
    error: null,
    message_id: "<demo-2@northwind.test>",
    subject: "Northwind Trading — pipeline brief for Monday, 09 November 2026",
    body: salesBody.replace("Hello Sam Rivera", "Hello Priya Shah"),
    department_id: sales.id,
    recipient_user_id: "a3333333-3333-4333-8333-333333333333",
    sent_at: "2026-11-09T09:00:19Z",
  },
  {
    id: "b6666666-6666-4666-8666-666666666666",
    execution_id: "b2222222-2222-4222-8222-222222222222",
    email: "sam@northwind.test",
    status: "SENT",
    error: null,
    message_id: "<demo-3@northwind.test>",
    subject: "Northwind Trading — pipeline brief for Sunday, 08 November 2026",
    body: salesBody,
    department_id: sales.id,
    recipient_user_id: "a2222222-2222-4222-8222-222222222222",
    sent_at: "2026-11-08T15:10:30Z",
  },
  {
    id: "b7777777-7777-4777-8777-777777777777",
    execution_id: "b2222222-2222-4222-8222-222222222222",
    email: "priya@northwind.test",
    status: "FAILED",
    error: "SMTPException: connection timed out after 30 seconds",
    message_id: null,
    subject: null,
    body: null,
    department_id: sales.id,
    recipient_user_id: "a3333333-3333-4333-8333-333333333333",
    sent_at: null,
  },
  {
    id: "b8888888-8888-4888-8888-888888888888",
    execution_id: "b3333333-3333-4333-8333-333333333333",
    email: "fiona@northwind.test",
    status: "SENT",
    error: null,
    message_id: "<demo-4@northwind.test>",
    subject: "Finance month-end — Sunday, 01 November 2026",
    body: financeBody,
    department_id: finance.id,
    recipient_user_id: "a4444444-4444-4444-8444-444444444444",
    sent_at: "2026-11-01T08:00:13Z",
  },
];

const settings: MailSettings = {
  host: "smtp.example.com",
  port: 587,
  username: "briefs",
  from_email: "briefs@northwind.test",
  from_name: "Northwind Trading",
  security: "STARTTLS",
  has_password: true,
  last_tested_at: "2026-11-08T17:55:00Z",
  last_test_error: null,
  updated_at: "2026-11-08T17:55:00Z",
};

const organisation: Organisation = {
  id: "00000000-0000-4000-8000-000000000001",
  name: "Northwind Trading",
  description:
    "A mid-sized distribution business supplying independent retailers across Europe.",
  industry: "Distribution",
  locations: ["London", "Lisbon", "Rotterdam"],
  timezone: "Europe/London",
  extra_metadata: {},
  created_at: "2026-01-12T10:00:00Z",
  updated_at: "2026-11-01T14:20:00Z",
};

const audit: AuditLog[] = [
  {
    id: 8,
    actor_user_id: DEMO_USER.id,
    action: "mail_schedule.updated",
    entity_type: "mail_schedule",
    entity_id: "e1111111-2222-4333-8444-555555555555",
    before: { row_limit: 25 },
    after: { row_limit: 50 },
    ip: "203.0.113.24",
    user_agent: "Mozilla/5.0",
    created_at: "2026-11-01T09:00:00Z",
  },
  {
    id: 7,
    actor_user_id: DEMO_USER.id,
    action: "department.permissions_updated",
    entity_type: "department",
    entity_id: finance.id,
    before: { granted: [] },
    after: { granted: ["d3333333-3333-4333-8333-333333333333"] },
    ip: "203.0.113.24",
    user_agent: "Mozilla/5.0",
    created_at: "2026-10-30T11:20:00Z",
  },
  {
    id: 6,
    actor_user_id: DEMO_USER.id,
    action: "connector.validated",
    entity_type: "connector",
    entity_id: "c2222222-2222-4222-8222-222222222222",
    before: null,
    after: { ok: true },
    ip: "203.0.113.24",
    user_agent: "Mozilla/5.0",
    created_at: "2026-10-29T16:05:00Z",
  },
  {
    id: 5,
    actor_user_id: DEMO_USER.id,
    action: "user.created",
    entity_type: "user",
    entity_id: "a5555555-5555-4555-8555-555555555555",
    before: null,
    after: { email: "omar@northwind.test", role: "USER" },
    ip: "203.0.113.24",
    user_agent: "Mozilla/5.0",
    created_at: "2026-10-28T10:00:00Z",
  },
  {
    id: 4,
    actor_user_id: DEMO_USER.id,
    action: "data_source.created",
    entity_type: "data_source",
    entity_id: "d5555555-5555-4555-8555-555555555555",
    before: null,
    after: { name: "Contacts" },
    ip: "203.0.113.24",
    user_agent: "Mozilla/5.0",
    created_at: "2026-10-27T14:30:00Z",
  },
];

const syncJobs: SyncJob[] = [
  {
    id: "c9999999-9999-4999-8999-999999999999",
    data_source_id: "d1111111-1111-4111-8111-111111111111",
    status: "SUCCEEDED",
    trigger: "SCHEDULED",
    actor_user_id: null,
    started_at: "2026-11-09T02:00:01Z",
    finished_at: "2026-11-09T02:00:06Z",
    error: null,
    record_count: 42,
    snapshot_id: "e1111111-1111-4111-8111-111111111111",
  },
  {
    id: "c8888888-8888-4888-8888-888888888888",
    data_source_id: "d2222222-2222-4222-8222-222222222222",
    status: "SUCCEEDED",
    trigger: "SCHEDULED",
    actor_user_id: null,
    started_at: "2026-11-09T02:00:07Z",
    finished_at: "2026-11-09T02:00:21Z",
    error: null,
    record_count: 128,
    snapshot_id: "e2222222-2222-4222-8222-222222222222",
  },
  {
    id: "c7777777-7777-4777-8777-777777777777",
    data_source_id: "d3333333-3333-4333-8333-333333333333",
    status: "SUCCEEDED",
    trigger: "SCHEDULED",
    actor_user_id: null,
    started_at: "2026-11-09T02:00:22Z",
    finished_at: "2026-11-09T02:00:28Z",
    error: null,
    record_count: 67,
    snapshot_id: "e3333333-3333-4333-8333-333333333333",
  },
];

const snapshots: Snapshot[] = [
  {
    id: "e1111111-1111-4111-8111-111111111111",
    data_source_id: "d1111111-1111-4111-8111-111111111111",
    captured_at: SYNCED,
    status: "READY",
    record_count: 42,
    schema_hash: "6f41c2a9b7d1",
    source_metadata: {
      columns: ["Deal", "Owner", "Stage", "Amount", "Close Date"],
    },
  },
  {
    id: "e1111111-1111-4111-8111-000000000001",
    data_source_id: "d1111111-1111-4111-8111-111111111111",
    captured_at: "2026-11-08T02:00:00Z",
    status: "READY",
    record_count: 40,
    schema_hash: "6f41c2a9b7d1",
    source_metadata: {
      columns: ["Deal", "Owner", "Stage", "Amount", "Close Date"],
    },
  },
  {
    id: "e2222222-2222-4222-8222-222222222222",
    data_source_id: "d2222222-2222-4222-8222-222222222222",
    captured_at: SYNCED,
    status: "READY",
    record_count: 128,
    schema_hash: "8a12d4c0e3f7",
    source_metadata: { columns: ["Deal Name", "Stage", "Amount", "Owner"] },
  },
  {
    id: "e3333333-3333-4333-8333-333333333333",
    data_source_id: "d3333333-3333-4333-8333-333333333333",
    captured_at: SYNCED,
    status: "READY",
    record_count: 67,
    schema_hash: "2b73fa1189cd",
    source_metadata: { columns: ["Account", "Period", "Amount", "Margin"] },
  },
];

export interface DemoStore {
  organisation: Organisation;
  departments: Department[];
  users: User[];
  connectors: Connector[];
  assets: Record<string, ConnectorAsset[]>;
  sources: DataSource[];
  grants: Record<string, string[]>;
  templates: MailTemplate[];
  schedules: MailSchedule[];
  executions: MailExecutionSummary[];
  deliveries: MailDelivery[];
  settings: MailSettings | null;
  audit: AuditLog[];
  syncJobs: SyncJob[];
  snapshots: Snapshot[];
}

export function createDemoStore(): DemoStore {
  return JSON.parse(
    JSON.stringify({
      organisation,
      departments: [management, sales, finance, operations],
      users,
      connectors,
      assets,
      sources,
      grants,
      templates,
      schedules,
      executions,
      deliveries,
      settings,
      audit,
      syncJobs,
      snapshots,
    }),
  ) as DemoStore;
}
