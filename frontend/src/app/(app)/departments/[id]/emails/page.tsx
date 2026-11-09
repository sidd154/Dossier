"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, MoreHorizontal, Play, Plus, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import {
  MailScheduleDialog,
  type MailScheduleValues,
} from "@/components/admin/mail-schedule-dialog";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiRequestError, api, queryString } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type {
  Department,
  DepartmentSources,
  MailSchedule,
  MailTemplate,
  Organisation,
  Page,
} from "@/lib/types";

const WEEKDAYS = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export default function DepartmentEmailsPage() {
  const params = useParams<{ id: string }>();
  const departmentId = params.id;
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<MailSchedule | null>(null);
  const [deleting, setDeleting] = useState<MailSchedule | null>(null);

  const department = useQuery({
    queryKey: ["department", departmentId],
    queryFn: () =>
      api.get<Department>(`/api/v1/admin/departments/${departmentId}`),
    enabled: Boolean(departmentId),
  });
  const organisation = useQuery({
    queryKey: ["organisation"],
    queryFn: () => api.get<Organisation>("/api/v1/admin/organisation"),
  });
  const templates = useQuery({
    queryKey: ["mail-templates", "picker", "active"],
    queryFn: () =>
      api.get<Page<MailTemplate>>(
        "/api/v1/admin/mail/templates?page=1&page_size=100&is_active=true",
      ),
  });
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

  const ready =
    Boolean(department.data) &&
    Boolean(templates.data) &&
    Boolean(sources.data) &&
    !templates.isLoading &&
    !sources.isLoading;

  const refresh = () => {
    void queryClient.invalidateQueries({
      queryKey: ["mail-schedules", "department", departmentId],
    });
    void queryClient.invalidateQueries({ queryKey: ["audit"] });
  };

  const createMutation = useMutation({
    mutationFn: (values: MailScheduleValues) =>
      api.post<MailSchedule>("/api/v1/admin/mail/schedules", {
        ...values,
        department_id: departmentId,
      }),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Email scheduled");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: MailScheduleValues }) =>
      api.patch<MailSchedule>(`/api/v1/admin/mail/schedules/${id}`, values),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Email updated");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const runMutation = useMutation({
    mutationFn: (schedule: MailSchedule) =>
      api.post<{ execution_id: string }>(
        `/api/v1/admin/mail/schedules/${schedule.id}/run`,
      ),
    onSuccess: () => {
      toast.success("Execution queued");
      void queryClient.invalidateQueries({ queryKey: ["mail-executions"] });
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const toggleMutation = useMutation({
    mutationFn: ({
      schedule,
      enabled,
    }: {
      schedule: MailSchedule;
      enabled: boolean;
    }) =>
      api.patch<MailSchedule>(`/api/v1/admin/mail/schedules/${schedule.id}`, {
        enabled,
      }),
    onSuccess: (_data, variables) => {
      toast.success(variables.enabled ? "Email enabled" : "Email paused");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (schedule: MailSchedule) =>
      api.delete(`/api/v1/admin/mail/schedules/${schedule.id}`),
    onSuccess: () => {
      toast.success("Email deleted");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  return (
    <div>
      <PageHeader
        title="Emails"
        description="Each email is generated for this department and sent to its active members."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" asChild>
              <Link href={`/mail/executions?department_id=${departmentId}`}>
                Executions
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button onClick={openCreate} disabled={!ready}>
              <Plus className="size-4" />
              New email
            </Button>
          </div>
        }
      />

      {schedules.isError ? (
        <Card>
          <ErrorState
            message={errorMessage(schedules.error)}
            onRetry={() => void schedules.refetch()}
          />
        </Card>
      ) : schedules.isLoading ? (
        <Card>
          <CardContent className="space-y-2 p-4">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-14 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : schedules.data && schedules.data.items.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Cadence</TableHead>
                  <TableHead>Next send</TableHead>
                  <TableHead>Last send</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.data.items.map((schedule) => (
                  <TableRow key={schedule.id}>
                    <TableCell>
                      <p className="text-sm font-medium">{schedule.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {schedule.template_name} ·{" "}
                        {schedule.source_names.length} source
                        {schedule.source_names.length === 1 ? "" : "s"}
                      </p>
                    </TableCell>
                    <TableCell className="text-sm">
                      {cadence(schedule)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {schedule.enabled
                        ? formatDateTime(schedule.next_run_at)
                        : "Paused"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(schedule.last_run_at)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={schedule.enabled ? "outline" : "secondary"}
                      >
                        {schedule.enabled ? "Active" : "Paused"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Actions for ${schedule.name}`}
                          >
                            <MoreHorizontal className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                          <DropdownMenuItem
                            disabled={runMutation.isPending}
                            onSelect={() => runMutation.mutate(schedule)}
                          >
                            <Play className="size-4" />
                            Send now
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() => {
                              setEditing(schedule);
                              setFormOpen(true);
                            }}
                          >
                            Edit email
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onSelect={() =>
                              toggleMutation.mutate({
                                schedule,
                                enabled: !schedule.enabled,
                              })
                            }
                          >
                            {schedule.enabled ? "Pause" : "Enable"}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            variant="destructive"
                            onSelect={() => setDeleting(schedule)}
                          >
                            Delete email
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={Send}
            title="No emails scheduled"
            description={
              ready
                ? "Pick a template, the sources this department may use, and a cadence."
                : "Add a template and grant source access before scheduling an email."
            }
            action={
              <Button variant="outline" onClick={openCreate} disabled={!ready}>
                <Plus className="size-4" />
                New email
              </Button>
            }
          />
        </Card>
      )}

      <MailScheduleDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        schedule={editing}
        department={department.data ?? null}
        templates={templates.data?.items ?? []}
        sources={sources.data?.entries ?? []}
        defaultTimezone={organisation.data?.timezone ?? "UTC"}
        pending={createMutation.isPending || updateMutation.isPending}
        onSubmit={(values) => {
          if (editing) updateMutation.mutate({ id: editing.id, values });
          else createMutation.mutate(values);
        }}
      />

      <AlertDialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its execution history is removed. Emails already sent are not
              recalled.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleting) deleteMutation.mutate(deleting);
                setDeleting(null);
              }}
            >
              Delete email
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function cadence(schedule: MailSchedule): string {
  const time = schedule.time_of_day.slice(0, 5);
  if (schedule.frequency === "WEEKLY") {
    return `${WEEKDAYS[schedule.weekday ?? 0]} at ${time}`;
  }
  if (schedule.frequency === "MONTHLY") {
    return `Day ${schedule.day_of_month ?? 1} at ${time}`;
  }
  return `Daily at ${time}`;
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
