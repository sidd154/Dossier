"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CalendarClock,
  CheckCircle2,
  Circle,
  Database,
  FileText,
  Send,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { EmptyState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, queryString } from "@/lib/api";
import { formatDateTime, formatRelative } from "@/lib/format";
import type {
  DepartmentSources,
  MailExecutionSummary,
  MailSchedule,
  MailTemplate,
  Page,
  User,
} from "@/lib/types";

export default function DepartmentOverviewPage() {
  const params = useParams<{ id: string }>();
  const departmentId = params.id;

  const sources = useQuery({
    queryKey: ["department-sources", departmentId],
    queryFn: () =>
      api.get<DepartmentSources>(
        `/api/v1/admin/departments/${departmentId}/sources`,
      ),
    enabled: Boolean(departmentId),
  });
  const schedules = useQuery({
    queryKey: ["mail-schedules", "department", departmentId],
    queryFn: () =>
      api.get<Page<MailSchedule>>(
        `/api/v1/admin/mail/schedules${queryString({
          department_id: departmentId,
          page: 1,
          page_size: 100,
        })}`,
      ),
    enabled: Boolean(departmentId),
  });
  const members = useQuery({
    queryKey: ["users", "department-count", departmentId],
    queryFn: () =>
      api.get<Page<User>>(
        `/api/v1/admin/users${queryString({
          department_id: departmentId,
          status: "ACTIVE",
          page: 1,
          page_size: 1,
        })}`,
      ),
    enabled: Boolean(departmentId),
  });
  const executions = useQuery({
    queryKey: ["mail-executions", "department-preview", departmentId],
    queryFn: () =>
      api.get<Page<MailExecutionSummary>>(
        `/api/v1/admin/mail/executions${queryString({
          department_id: departmentId,
          page: 1,
          page_size: 5,
        })}`,
      ),
    enabled: Boolean(departmentId),
  });
  const templates = useQuery({
    queryKey: ["mail-templates", "active-count"],
    queryFn: () =>
      api.get<Page<MailTemplate>>(
        "/api/v1/admin/mail/templates?page=1&page_size=1&is_active=true",
      ),
  });

  const granted = (sources.data?.entries ?? []).filter(
    (entry) => entry.granted && entry.is_active,
  );
  const activeSchedules = (schedules.data?.items ?? []).filter(
    (schedule) => schedule.enabled,
  );
  const nextRun = activeSchedules
    .map((schedule) => schedule.next_run_at)
    .filter((value): value is string => Boolean(value))
    .sort()[0];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={Users}
          label="Active members"
          value={members.data?.total}
          hint="Receive this department's emails"
          loading={members.isLoading}
        />
        <Stat
          icon={Database}
          label="Granted sources"
          value={granted.length}
          hint="What emails may draw from"
          loading={sources.isLoading}
        />
        <Stat
          icon={Send}
          label="Scheduled emails"
          value={activeSchedules.length}
          hint="Enabled schedules"
          loading={schedules.isLoading}
        />
        <Stat
          icon={CalendarClock}
          label="Next send"
          value={undefined}
          text={nextRun ? formatDateTime(nextRun) : "Not scheduled"}
          hint={nextRun ? "Next delivery" : undefined}
          loading={schedules.isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <CheckCircle2 className="size-4 text-muted-foreground" />
              Get this department live
            </CardTitle>
            <CardDescription>
              Each step builds on the previous one.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            <Step done label="Department created" hint="You are here" />
            <Step
              done={granted.length > 0}
              label="Grant source access"
              hint={
                granted.length
                  ? `${granted.length} source${granted.length === 1 ? "" : "s"} granted`
                  : "Choose what this department may use"
              }
              href={`/departments/${departmentId}/sources`}
            />
            <Step
              done={Boolean(templates.data?.total)}
              label="Have an email template"
              hint={
                templates.data?.total
                  ? "At least one active template"
                  : "Write the prompt for the email"
              }
              href="/mail/templates"
            />
            <Step
              done={activeSchedules.length > 0}
              label="Schedule an email"
              hint={
                activeSchedules.length
                  ? `${activeSchedules.length} enabled`
                  : "Pick a template, sources, and a cadence"
              }
              href={`/departments/${departmentId}/emails`}
            />
            <Step
              done={(members.data?.total ?? 0) > 0}
              label="Add recipients"
              hint={
                members.data?.total
                  ? `${members.data.total} active member${members.data.total === 1 ? "" : "s"}`
                  : "Accounts in this department receive the mail"
              }
              href={`/departments/${departmentId}/members`}
            />
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileText className="size-4 text-muted-foreground" />
              Emails
            </CardTitle>
            <CardDescription>What this department receives.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {schedules.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : activeSchedules.length ? (
              <ul className="space-y-2">
                {activeSchedules.map((schedule) => (
                  <li
                    key={schedule.id}
                    className="flex items-center justify-between gap-2 rounded-lg border p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {schedule.name}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {schedule.template_name} · {cadence(schedule)}
                      </p>
                    </div>
                    <Button variant="ghost" size="icon" asChild>
                      <Link
                        href={`/departments/${departmentId}/emails`}
                        aria-label="Open emails"
                      >
                        <ArrowRight className="size-4" />
                      </Link>
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <Button variant="outline" className="w-full" asChild>
                <Link href={`/departments/${departmentId}/emails`}>
                  Create the first email
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">Recent executions</CardTitle>
            <CardDescription>
              The last runs for this department.
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/mail/executions?department_id=${departmentId}`}>
              View all
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {executions.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : executions.data?.items.length ? (
            <ul className="divide-y">
              {executions.data.items.map((execution) => (
                <li
                  key={execution.id}
                  className="flex items-center justify-between gap-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm">
                      {execution.schedule_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatRelative(execution.started_at)} · sent{" "}
                      {execution.sent_count}, failed {execution.failed_count},
                      skipped {execution.skipped_count}
                    </p>
                  </div>
                  <ExecutionBadge status={execution.status} />
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              icon={Send}
              title="No executions yet"
              description="Run a schedule or wait for its next slot."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  text,
  hint,
  loading,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value?: number;
  text?: string;
  hint?: string;
  loading: boolean;
}) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3 p-5">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          {loading ? (
            <Skeleton className="h-7 w-16" />
          ) : (
            <p className="text-2xl font-semibold tracking-tight tabular-nums">
              {text ?? value ?? 0}
            </p>
          )}
          {hint ? (
            <p className="text-xs text-muted-foreground">{hint}</p>
          ) : null}
        </div>
        <div className="grid size-9 place-items-center rounded-lg bg-accent text-accent-foreground">
          <Icon className="size-4" />
        </div>
      </CardContent>
    </Card>
  );
}

function Step({
  done,
  label,
  hint,
  href,
}: {
  done: boolean;
  label: string;
  hint: string;
  href?: string;
}) {
  const content = (
    <div className="flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-muted/50">
      {done ? (
        <CheckCircle2 className="size-5 shrink-0 text-emerald-600" />
      ) : (
        <Circle className="size-5 shrink-0 text-muted-foreground" />
      )}
      <div className="min-w-0 flex-1">
        <p className={done ? "text-sm font-medium" : "text-sm"}>{label}</p>
        <p className="truncate text-xs text-muted-foreground">{hint}</p>
      </div>
      {href && !done ? (
        <ArrowRight className="size-4 text-muted-foreground" />
      ) : null}
    </div>
  );

  if (!href || done) return content;
  return <Link href={href}>{content}</Link>;
}

function cadence(schedule: MailSchedule): string {
  const time = schedule.time_of_day.slice(0, 5);
  if (schedule.frequency === "WEEKLY") return `weekly at ${time}`;
  if (schedule.frequency === "MONTHLY") return `monthly at ${time}`;
  return `daily at ${time}`;
}

function ExecutionBadge({
  status,
}: {
  status: MailExecutionSummary["status"];
}) {
  const variant =
    status === "FAILED"
      ? "destructive"
      : status === "PARTIAL"
        ? "secondary"
        : status === "SUCCEEDED"
          ? "outline"
          : "secondary";
  return <Badge variant={variant}>{status}</Badge>;
}
