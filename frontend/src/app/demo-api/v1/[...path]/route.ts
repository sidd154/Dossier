import { NextRequest, NextResponse } from "next/server";

import {
  createDemoStore,
  DEMO_TEMP_PASSWORD,
  DEMO_USER,
} from "@/lib/demo-data";
import type {
  Connector,
  DataSource,
  Department,
  MailDelivery,
  MailSchedule,
  MailTemplate,
  SyncJob,
  User,
} from "@/lib/types";

const enabled = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const NOW = new Date().toISOString();
let store = createDemoStore();

type Ctx = { params: Promise<{ path: string[] }> };
type Body = Record<string, any>;

function json(data: unknown, status = 200) {
  return NextResponse.json(data, { status });
}

function failure(detail: string, status: number, code?: string) {
  return json({ detail, ...(code ? { code } : {}) }, status);
}

function authed(request: NextRequest) {
  return request.cookies.get("access_token")?.value === "demo";
}

async function readBody(request: NextRequest): Promise<Body> {
  try {
    return (await request.json()) as Body;
  } catch {
    return {};
  }
}

function pageOf<T>(items: T[], params: URLSearchParams, fallback = 25) {
  const page = Math.max(1, Number(params.get("page") ?? 1));
  const pageSize = Math.max(1, Number(params.get("page_size") ?? fallback));
  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize),
    total: items.length,
    page,
    page_size: pageSize,
  };
}

function sessionBody() {
  return {
    access_token: "demo",
    token_type: "bearer",
    expires_in: 604800,
    user: store.users.find((user) => user.id === DEMO_USER.id) ?? DEMO_USER,
  };
}

function withSession(data: unknown) {
  const response = json(data);
  const options = {
    httpOnly: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: 604800,
    secure: process.env.NODE_ENV === "production",
  };
  response.cookies.set("access_token", "demo", options);
  response.cookies.set("refresh_token", "demo", options);
  return response;
}

function clearSession() {
  const response = new NextResponse(null, { status: 204 });
  response.cookies.set("access_token", "", { path: "/", maxAge: 0 });
  response.cookies.set("refresh_token", "", { path: "/", maxAge: 0 });
  return response;
}

function departmentOf(id: string): Department | undefined {
  return store.departments.find((department) => department.id === id);
}

function departmentRef(id: string) {
  const department = departmentOf(id);
  return department
    ? { id: department.id, name: department.name, slug: department.slug }
    : null;
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function departmentSources(departmentId: string) {
  const granted = new Set(store.grants[departmentId] ?? []);
  return {
    department_id: departmentId,
    department_name: departmentOf(departmentId)?.name ?? "Department",
    entries: store.sources.map((source) => ({
      data_source_id: source.id,
      name: source.name,
      kind: source.kind,
      connector_name: source.connector_name,
      granted: granted.has(source.id),
      is_active: source.is_active,
      last_sync_at: source.current_snapshot?.captured_at ?? null,
      snapshot_status: source.current_snapshot?.status ?? null,
    })),
  };
}

function allowedSources(departmentId: string, sourceIds: string[]) {
  const granted = new Set(store.grants[departmentId] ?? []);
  const requested = store.sources.filter((source) =>
    sourceIds.includes(source.id),
  );
  return {
    used: requested.filter(
      (source) => granted.has(source.id) && source.is_active,
    ),
    excluded: requested.filter((source) => !granted.has(source.id)),
  };
}

function preview(
  template: MailTemplate,
  departmentId: string,
  sourceIds: string[],
) {
  const department = departmentOf(departmentId);
  if (!department) return failure("Department not found", 404);
  const { used, excluded } = allowedSources(departmentId, sourceIds);
  if (!used.length) {
    return failure(
      "This department cannot access any of the selected sources",
      409,
      "no_permitted_sources",
    );
  }
  const names = used.map((source) => source.name).join(" and ");
  const body = `Hello Sample Recipient,

Here is the demo ${department.name.toLowerCase()} update. It was generated from ${names}.

Open pipeline: $71,100 across four active deals.

- Soylent upgrade - Alex Kim - Negotiation - $31,000
- Acme expansion - Sam Rivera - Negotiation - $18,500
- Umbrella services - Priya Shah - Discovery - $12,000

Acme expansion has the nearest close date and needs a decision this week.

This is sample data. The real deployment generates this body with your configured model.

- ${store.organisation.name}`;

  return json({
    ok: true,
    error: null,
    subject: `${store.organisation.name} - ${department.name} update for 09 November 2026`,
    body,
    sources_used: used.map((source) => source.name),
    sources_excluded: excluded.map((source) => source.name),
  });
}

async function handleAuth(
  request: NextRequest,
  path: string[],
  method: string,
) {
  const [action] = path;

  if (action === "login" && method === "POST") {
    await readBody(request);
    return withSession(sessionBody());
  }
  if (action === "refresh" && method === "POST") {
    if (request.cookies.get("refresh_token")?.value !== "demo") {
      return failure("Not authenticated", 401, "unauthenticated");
    }
    return withSession(sessionBody());
  }
  if (action === "logout" && method === "POST") {
    return clearSession();
  }
  if (action === "me" && method === "GET") {
    if (!authed(request)) {
      return failure("Not authenticated", 401, "unauthenticated");
    }
    return json(store.users.find((user) => user.id === DEMO_USER.id));
  }
  if (action === "change-password" && method === "POST") {
    return withSession(sessionBody());
  }
  return failure("Not found", 404);
}

async function handleDepartments(
  request: NextRequest,
  path: string[],
  method: string,
  params: URLSearchParams,
) {
  const [id, sub] = path;

  if (!id) {
    if (method === "GET") {
      const q = (params.get("q") ?? "").toLowerCase();
      const active = params.get("is_active");
      let items = store.departments;
      if (q) {
        items = items.filter(
          (department) =>
            department.name.toLowerCase().includes(q) ||
            department.slug.includes(q),
        );
      }
      if (active !== null) {
        items = items.filter(
          (department) => department.is_active === (active === "true"),
        );
      }
      return json(pageOf(items, params));
    }
    if (method === "POST") {
      const body = await readBody(request);
      const name = String(body.name ?? "").trim();
      if (!name) return failure("Enter a name", 422);
      const department: Department = {
        id: crypto.randomUUID(),
        name,
        slug: slugify(name),
        description: body.description ?? null,
        is_active: body.is_active ?? true,
        created_at: NOW,
        updated_at: NOW,
      };
      store.departments.push(department);
      store.grants[department.id] = [];
      return json(department, 201);
    }
    return failure("Method not allowed", 405);
  }

  const department = departmentOf(id);
  if (!department) return failure("Department not found", 404);

  if (sub === "sources") {
    if (method === "GET") return json(departmentSources(id));
    if (method === "PUT") {
      const body = await readBody(request);
      const ids = Array.isArray(body.data_source_ids)
        ? body.data_source_ids.map(String)
        : [];
      store.grants[id] = ids;
      return json(departmentSources(id));
    }
    return failure("Method not allowed", 405);
  }

  if (sub) return failure("Not found", 404);

  if (method === "GET") return json(department);
  if (method === "PATCH") {
    const body = await readBody(request);
    Object.assign(department, {
      ...(body.name !== undefined ? { name: String(body.name) } : {}),
      ...(body.slug !== undefined ? { slug: String(body.slug) } : {}),
      ...(body.description !== undefined
        ? { description: body.description }
        : {}),
      ...(body.is_active !== undefined
        ? { is_active: Boolean(body.is_active) }
        : {}),
      updated_at: NOW,
    });
    return json(department);
  }
  if (method === "DELETE") {
    store.departments = store.departments.filter((item) => item.id !== id);
    delete store.grants[id];
    return new NextResponse(null, { status: 204 });
  }
  return failure("Method not allowed", 405);
}

async function handleUsers(
  request: NextRequest,
  path: string[],
  method: string,
  params: URLSearchParams,
) {
  const [id, sub] = path;

  if (!id) {
    if (method === "GET") {
      const q = (params.get("q") ?? "").toLowerCase();
      const departmentId = params.get("department_id");
      const role = params.get("role");
      const status = params.get("status");
      let items = store.users;
      if (q) {
        items = items.filter(
          (user) =>
            user.email.toLowerCase().includes(q) ||
            user.full_name.toLowerCase().includes(q),
        );
      }
      if (departmentId) {
        items = items.filter((user) => user.department_id === departmentId);
      }
      if (role) items = items.filter((user) => user.role === role);
      if (status) items = items.filter((user) => user.status === status);
      return json(pageOf(items, params));
    }
    if (method === "POST") {
      const body = await readBody(request);
      const departmentId = String(body.department_id ?? "");
      if (!departmentOf(departmentId)) {
        return failure("Department not found", 404);
      }
      if (
        store.users.some(
          (user) =>
            user.email.toLowerCase() === String(body.email ?? "").toLowerCase(),
        )
      ) {
        return failure("Email already in use", 409, "email_in_use");
      }
      const user: User = {
        id: crypto.randomUUID(),
        email: String(body.email ?? "").toLowerCase(),
        full_name: String(body.full_name ?? ""),
        role: body.role === "ADMIN" ? "ADMIN" : "USER",
        status: "ACTIVE",
        department_id: departmentId,
        department: departmentRef(departmentId),
        must_change_password: true,
        last_login_at: null,
        created_at: NOW,
        updated_at: NOW,
      };
      store.users.push(user);
      return json({ ...user, temporary_password: DEMO_TEMP_PASSWORD }, 201);
    }
    return failure("Method not allowed", 405);
  }

  const user = store.users.find((item) => item.id === id);
  if (!user) return failure("User not found", 404);

  if (sub === "reset-password" && method === "POST") {
    return json({ temporary_password: DEMO_TEMP_PASSWORD });
  }
  if (sub) return failure("Not found", 404);

  if (method === "GET") return json(user);
  if (method === "PATCH") {
    const body = await readBody(request);
    Object.assign(user, {
      ...(body.full_name !== undefined
        ? { full_name: String(body.full_name) }
        : {}),
      ...(body.role !== undefined ? { role: body.role } : {}),
      ...(body.status !== undefined ? { status: body.status } : {}),
      ...(body.department_id !== undefined
        ? {
            department_id: String(body.department_id),
            department: departmentRef(String(body.department_id)),
          }
        : {}),
      updated_at: NOW,
    });
    return json(user);
  }
  if (method === "DELETE") {
    user.status = "DISABLED";
    user.updated_at = NOW;
    return new NextResponse(null, { status: 204 });
  }
  return failure("Method not allowed", 405);
}

async function handleConnectors(
  request: NextRequest,
  path: string[],
  method: string,
  params: URLSearchParams,
) {
  const [id, sub] = path;

  if (!id) {
    if (method === "GET") {
      const q = (params.get("q") ?? "").toLowerCase();
      const type = params.get("type");
      const active = params.get("is_active");
      let items = store.connectors;
      if (q)
        items = items.filter((item) => item.name.toLowerCase().includes(q));
      if (type) items = items.filter((item) => item.type === type);
      if (active !== null) {
        items = items.filter((item) => item.is_active === (active === "true"));
      }
      return json(pageOf(items, params));
    }
    if (method === "POST") {
      const body = await readBody(request);
      const connector: Connector = {
        id: crypto.randomUUID(),
        name: String(body.name ?? "Connector"),
        type: body.type === "ZOHO_CRM" ? "ZOHO_CRM" : "GOOGLE_SHEETS",
        is_active: body.is_active ?? true,
        config: body.config ?? {},
        has_credentials: Boolean(
          body.credentials && Object.keys(body.credentials).length,
        ),
        last_validated_at: null,
        last_validation_error: null,
        created_at: NOW,
        updated_at: NOW,
      };
      store.connectors.push(connector);
      store.assets[connector.id] = [];
      return json(connector, 201);
    }
    return failure("Method not allowed", 405);
  }

  const connector = store.connectors.find((item) => item.id === id);
  if (!connector) return failure("Connector not found", 404);

  if (sub === "validate" && method === "POST") {
    connector.last_validated_at = NOW;
    connector.last_validation_error = null;
    return json({ ok: true, error: null, last_validated_at: NOW });
  }
  if (sub === "assets" && method === "GET") {
    return json(store.assets[id] ?? []);
  }
  if (sub) return failure("Not found", 404);

  if (method === "GET") return json(connector);
  if (method === "PATCH") {
    const body = await readBody(request);
    Object.assign(connector, {
      ...(body.name !== undefined ? { name: String(body.name) } : {}),
      ...(body.config !== undefined ? { config: body.config } : {}),
      ...(body.is_active !== undefined
        ? { is_active: Boolean(body.is_active) }
        : {}),
      ...(body.credentials !== undefined ? { has_credentials: true } : {}),
      updated_at: NOW,
    });
    return json(connector);
  }
  if (method === "DELETE") {
    store.connectors = store.connectors.filter((item) => item.id !== id);
    store.sources = store.sources.filter((item) => item.connector_id !== id);
    delete store.assets[id];
    return new NextResponse(null, { status: 204 });
  }
  return failure("Method not allowed", 405);
}

async function handleDataSources(
  request: NextRequest,
  path: string[],
  method: string,
  params: URLSearchParams,
) {
  const [id, sub] = path;

  if (!id) {
    if (method === "GET") {
      const q = (params.get("q") ?? "").toLowerCase();
      const connectorId = params.get("connector_id");
      const active = params.get("is_active");
      let items = store.sources;
      if (q) {
        items = items.filter(
          (item) =>
            item.name.toLowerCase().includes(q) ||
            item.external_id.toLowerCase().includes(q),
        );
      }
      if (connectorId) {
        items = items.filter((item) => item.connector_id === connectorId);
      }
      if (active !== null) {
        items = items.filter((item) => item.is_active === (active === "true"));
      }
      return json(pageOf(items, params));
    }
    if (method === "POST") {
      const body = await readBody(request);
      const connector = store.connectors.find(
        (item) => item.id === String(body.connector_id),
      );
      if (!connector) return failure("Connector not found", 404);
      const asset = (store.assets[connector.id] ?? []).find(
        (item) => item.external_id === String(body.external_id),
      );
      if (!asset)
        return failure("That asset was not found on the connector", 404);
      if (
        store.sources.some(
          (item) =>
            item.connector_id === connector.id &&
            item.external_id === asset.external_id,
        )
      ) {
        return failure(
          "This source is already registered",
          409,
          "source_exists",
        );
      }
      const source: DataSource = {
        id: crypto.randomUUID(),
        connector_id: connector.id,
        connector_name: connector.name,
        connector_type: connector.type,
        external_id: asset.external_id,
        name: String(body.name ?? asset.name),
        kind: asset.kind,
        config: asset.config,
        is_active: true,
        schema_hash: null,
        current_snapshot: null,
        created_at: NOW,
        updated_at: NOW,
      };
      store.sources.push(source);
      return json(source, 201);
    }
    return failure("Method not allowed", 405);
  }

  const source = store.sources.find((item) => item.id === id);
  if (!source) return failure("Data source not found", 404);

  if (sub === "sync" && method === "POST") {
    const job: SyncJob = {
      id: crypto.randomUUID(),
      data_source_id: id,
      status: "SUCCEEDED",
      trigger: "MANUAL",
      actor_user_id: DEMO_USER.id,
      started_at: NOW,
      finished_at: NOW,
      error: null,
      record_count: source.current_snapshot?.record_count ?? 0,
      snapshot_id: source.current_snapshot?.id ?? null,
    };
    store.syncJobs.unshift(job);
    return json(job);
  }
  if (sub === "snapshots" && method === "GET") {
    return json(
      pageOf(
        store.snapshots.filter((item) => item.data_source_id === id),
        params,
      ),
    );
  }
  if (sub === "sync-jobs" && method === "GET") {
    return json(
      pageOf(
        store.syncJobs.filter((item) => item.data_source_id === id),
        params,
      ),
    );
  }
  if (sub) return failure("Not found", 404);

  if (method === "GET") return json(source);
  if (method === "PATCH") {
    const body = await readBody(request);
    Object.assign(source, {
      ...(body.name !== undefined ? { name: String(body.name) } : {}),
      ...(body.is_active !== undefined
        ? { is_active: Boolean(body.is_active) }
        : {}),
      ...(body.config !== undefined ? { config: body.config } : {}),
      updated_at: NOW,
    });
    return json(source);
  }
  if (method === "DELETE") {
    store.sources = store.sources.filter((item) => item.id !== id);
    return new NextResponse(null, { status: 204 });
  }
  return failure("Method not allowed", 405);
}

async function handleMail(
  request: NextRequest,
  path: string[],
  method: string,
  params: URLSearchParams,
) {
  const [resource, id, sub] = path;

  if (resource === "settings") {
    if (id === "test" && method === "POST") {
      return json({ ok: true, error: null, last_tested_at: NOW });
    }
    if (id) return failure("Not found", 404);
    if (method === "GET") {
      if (!store.settings)
        return failure("SMTP settings are not configured", 404);
      return json(store.settings);
    }
    if (method === "PATCH") {
      const body = await readBody(request);
      if (!store.settings) {
        store.settings = {
          host: "smtp.example.com",
          port: 587,
          username: null,
          from_email: "briefs@northwind.test",
          from_name: "Northwind Trading",
          security: "STARTTLS",
          has_password: false,
          last_tested_at: null,
          last_test_error: null,
          updated_at: NOW,
        };
      }
      Object.assign(store.settings, {
        ...(body.host !== undefined ? { host: String(body.host) } : {}),
        ...(body.port !== undefined ? { port: Number(body.port) } : {}),
        ...(body.username !== undefined ? { username: body.username } : {}),
        ...(body.from_email !== undefined
          ? { from_email: String(body.from_email) }
          : {}),
        ...(body.from_name !== undefined ? { from_name: body.from_name } : {}),
        ...(body.security !== undefined ? { security: body.security } : {}),
        ...(body.password !== undefined ? { has_password: true } : {}),
        ...(body.clear_password ? { has_password: false } : {}),
        updated_at: NOW,
      });
      return json(store.settings);
    }
    return failure("Method not allowed", 405);
  }

  if (resource === "templates") {
    if (!id) {
      if (method === "GET") {
        const q = (params.get("q") ?? "").toLowerCase();
        const active = params.get("is_active");
        let items = store.templates;
        if (q)
          items = items.filter((item) => item.name.toLowerCase().includes(q));
        if (active !== null) {
          items = items.filter(
            (item) => item.is_active === (active === "true"),
          );
        }
        return json(pageOf(items, params));
      }
      if (method === "POST") {
        const body = await readBody(request);
        const template: MailTemplate = {
          id: crypto.randomUUID(),
          name: String(body.name ?? "Template"),
          description: body.description ?? null,
          subject_template: String(body.subject_template ?? ""),
          system_prompt: String(body.system_prompt ?? ""),
          is_active: body.is_active ?? true,
          created_at: NOW,
          updated_at: NOW,
        };
        store.templates.push(template);
        return json(template, 201);
      }
      return failure("Method not allowed", 405);
    }
    const template = store.templates.find((item) => item.id === id);
    if (!template) return failure("Mail template not found", 404);

    if (sub === "preview" && method === "POST") {
      const body = await readBody(request);
      return preview(
        template,
        String(body.department_id ?? ""),
        Array.isArray(body.source_ids) ? body.source_ids.map(String) : [],
      );
    }
    if (sub === "test-send" && method === "POST") {
      const body = await readBody(request);
      return preview(
        template,
        String(body.department_id ?? ""),
        Array.isArray(body.source_ids) ? body.source_ids.map(String) : [],
      );
    }
    if (sub) return failure("Not found", 404);
    if (method === "GET") return json(template);
    if (method === "PATCH") {
      const body = await readBody(request);
      Object.assign(template, {
        ...(body.name !== undefined ? { name: String(body.name) } : {}),
        ...(body.description !== undefined
          ? { description: body.description }
          : {}),
        ...(body.subject_template !== undefined
          ? { subject_template: String(body.subject_template) }
          : {}),
        ...(body.system_prompt !== undefined
          ? { system_prompt: String(body.system_prompt) }
          : {}),
        ...(body.is_active !== undefined
          ? { is_active: Boolean(body.is_active) }
          : {}),
        updated_at: NOW,
      });
      return json(template);
    }
    if (method === "DELETE") {
      store.templates = store.templates.filter((item) => item.id !== id);
      return new NextResponse(null, { status: 204 });
    }
    return failure("Method not allowed", 405);
  }

  if (resource === "schedules") {
    if (!id) {
      if (method === "GET") {
        const departmentId = params.get("department_id");
        const q = (params.get("q") ?? "").toLowerCase();
        const enabled = params.get("enabled");
        let items = store.schedules;
        if (departmentId) {
          items = items.filter((item) => item.department_id === departmentId);
        }
        if (q)
          items = items.filter((item) => item.name.toLowerCase().includes(q));
        if (enabled !== null) {
          items = items.filter((item) => item.enabled === (enabled === "true"));
        }
        return json(pageOf(items, params));
      }
      if (method === "POST") {
        const body = await readBody(request);
        const department = departmentOf(String(body.department_id ?? ""));
        const template = store.templates.find(
          (item) => item.id === String(body.template_id),
        );
        if (!department) return failure("Department not found", 404);
        if (!template) return failure("Mail template not found", 404);
        const sourceIds: string[] = Array.isArray(body.source_ids)
          ? body.source_ids.map(String)
          : [];
        const selected = store.sources.filter((item) =>
          sourceIds.includes(item.id),
        );
        const schedule: MailSchedule = {
          id: crypto.randomUUID(),
          name: String(body.name ?? "Email"),
          template_id: template.id,
          template_name: template.name,
          department_id: department.id,
          department_name: department.name,
          enabled: body.enabled ?? true,
          frequency: body.frequency ?? "DAILY",
          time_of_day: String(body.time_of_day ?? "09:00:00"),
          weekday: body.weekday ?? null,
          day_of_month: body.day_of_month ?? null,
          timezone: String(body.timezone ?? "UTC"),
          row_limit: Number(body.row_limit ?? 50),
          next_run_at: (body.enabled ?? true) ? "2026-11-10T09:00:00Z" : null,
          last_run_at: null,
          source_ids: selected.map((item) => item.id),
          source_names: selected.map((item) => item.name),
          created_at: NOW,
          updated_at: NOW,
        };
        store.schedules.push(schedule);
        return json(schedule, 201);
      }
      return failure("Method not allowed", 405);
    }
    const schedule = store.schedules.find((item) => item.id === id);
    if (!schedule) return failure("Mail schedule not found", 404);

    if (sub === "run" && method === "POST") {
      const members = store.users.filter(
        (user) =>
          user.department_id === schedule.department_id &&
          user.status === "ACTIVE",
      );
      const execution = {
        id: crypto.randomUUID(),
        schedule_id: schedule.id,
        schedule_name: schedule.name,
        department_name: schedule.department_name,
        trigger: "MANUAL" as const,
        scheduled_for: NOW,
        status: "SUCCEEDED" as const,
        started_at: NOW,
        finished_at: NOW,
        recipient_count: members.length,
        sent_count: members.length,
        failed_count: 0,
        skipped_count: 0,
        error: null,
      };
      store.executions.unshift(execution);
      members.forEach((member, index) => {
        store.deliveries.unshift({
          id: crypto.randomUUID(),
          execution_id: execution.id,
          email: member.email,
          status: "SENT",
          error: null,
          message_id: `<demo-run-${index}@northwind.test>`,
          subject: `${store.organisation.name} - ${schedule.department_name} update`,
          body: `Hello ${member.full_name},\n\nThis demo email was generated from ${schedule.source_names.join(" and ")}.\n\n- ${store.organisation.name}`,
          department_id: member.department_id,
          recipient_user_id: member.id,
          sent_at: NOW,
        });
      });
      schedule.last_run_at = NOW;
      return json({ execution_id: execution.id, status: "RUNNING" }, 202);
    }
    if (sub) return failure("Not found", 404);
    if (method === "GET") return json(schedule);
    if (method === "PATCH") {
      const body = await readBody(request);
      Object.assign(schedule, {
        ...(body.name !== undefined ? { name: String(body.name) } : {}),
        ...(body.enabled !== undefined
          ? {
              enabled: Boolean(body.enabled),
              next_run_at: body.enabled ? "2026-11-10T09:00:00Z" : null,
            }
          : {}),
        ...(body.frequency !== undefined ? { frequency: body.frequency } : {}),
        ...(body.time_of_day !== undefined
          ? { time_of_day: String(body.time_of_day) }
          : {}),
        ...(body.weekday !== undefined ? { weekday: body.weekday } : {}),
        ...(body.day_of_month !== undefined
          ? { day_of_month: body.day_of_month }
          : {}),
        ...(body.timezone !== undefined
          ? { timezone: String(body.timezone) }
          : {}),
        ...(body.row_limit !== undefined
          ? { row_limit: Number(body.row_limit) }
          : {}),
        updated_at: NOW,
      });
      if (Array.isArray(body.source_ids)) {
        const selected = store.sources.filter((item) =>
          body.source_ids.map(String).includes(item.id),
        );
        schedule.source_ids = selected.map((item) => item.id);
        schedule.source_names = selected.map((item) => item.name);
      }
      return json(schedule);
    }
    if (method === "DELETE") {
      store.schedules = store.schedules.filter((item) => item.id !== id);
      return new NextResponse(null, { status: 204 });
    }
    return failure("Method not allowed", 405);
  }

  if (resource === "executions") {
    if (!id) {
      const scheduleId = params.get("schedule_id");
      const departmentId = params.get("department_id");
      const status = params.get("status");
      let items = store.executions;
      if (scheduleId) {
        items = items.filter((item) => item.schedule_id === scheduleId);
      }
      if (departmentId) {
        const scheduleIds = new Set(
          store.schedules
            .filter((item) => item.department_id === departmentId)
            .map((item) => item.id),
        );
        items = items.filter((item) => scheduleIds.has(item.schedule_id));
      }
      if (status) items = items.filter((item) => item.status === status);
      return json(pageOf(items, params));
    }
    const execution = store.executions.find((item) => item.id === id);
    if (!execution) return failure("Mail execution not found", 404);
    return json({
      ...execution,
      deliveries: store.deliveries.filter(
        (delivery) => delivery.execution_id === execution.id,
      ),
    });
  }

  return failure("Not found", 404);
}

async function handleAdmin(
  request: NextRequest,
  path: string[],
  method: string,
  params: URLSearchParams,
) {
  const [resource] = path;
  const rest = path.slice(1);

  if (resource === "departments") {
    return handleDepartments(request, rest, method, params);
  }
  if (resource === "users") {
    return handleUsers(request, rest, method, params);
  }
  if (resource === "connectors") {
    return handleConnectors(request, rest, method, params);
  }
  if (resource === "data-sources") {
    return handleDataSources(request, rest, method, params);
  }
  if (resource === "sync-jobs") {
    return json(pageOf(store.syncJobs, params));
  }
  if (resource === "organisation") {
    if (method === "GET") return json(store.organisation);
    if (method === "PATCH") {
      const body = await readBody(request);
      Object.assign(store.organisation, {
        ...(body.name !== undefined ? { name: String(body.name) } : {}),
        ...(body.description !== undefined
          ? { description: body.description }
          : {}),
        ...(body.industry !== undefined ? { industry: body.industry } : {}),
        ...(body.locations !== undefined ? { locations: body.locations } : {}),
        ...(body.timezone !== undefined
          ? { timezone: String(body.timezone) }
          : {}),
        updated_at: NOW,
      });
      return json(store.organisation);
    }
    return failure("Method not allowed", 405);
  }
  if (resource === "audit-logs") {
    const entityType = params.get("entity_type");
    const action = params.get("action");
    let items = store.audit;
    if (entityType) {
      items = items.filter((item) => item.entity_type === entityType);
    }
    if (action) items = items.filter((item) => item.action === action);
    return json(pageOf(items, params));
  }
  if (resource === "mail") {
    return handleMail(request, rest, method, params);
  }
  return failure("Not found", 404);
}

async function handle(request: NextRequest, path: string[]) {
  if (!enabled) return failure("Not found", 404);

  try {
    const [first, ...rest] = path;
    if (first === "auth") {
      return await handleAuth(request, rest, request.method);
    }
    if (first === "admin") {
      if (!authed(request)) {
        return failure("Not authenticated", 401, "unauthenticated");
      }
      return await handleAdmin(
        request,
        rest,
        request.method,
        request.nextUrl.searchParams,
      );
    }
    return failure("Not found", 404);
  } catch (error) {
    return failure(
      error instanceof Error ? error.message : "Demo API error",
      500,
    );
  }
}

export async function GET(request: NextRequest, context: Ctx) {
  return handle(request, (await context.params).path);
}

export async function POST(request: NextRequest, context: Ctx) {
  return handle(request, (await context.params).path);
}

export async function PATCH(request: NextRequest, context: Ctx) {
  return handle(request, (await context.params).path);
}

export async function PUT(request: NextRequest, context: Ctx) {
  return handle(request, (await context.params).path);
}

export async function DELETE(request: NextRequest, context: Ctx) {
  return handle(request, (await context.params).path);
}
