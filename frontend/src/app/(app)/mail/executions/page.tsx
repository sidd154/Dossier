"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ScrollText } from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  MailDelivery,
  MailExecutionDetail,
  MailExecutionStatus,
  MailExecutionSummary,
  MailSchedule,
  Page,
} from "@/lib/types";

const PAGE_SIZE = 20;

export default function MailExecutionsPage() {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [scheduleFilter, setScheduleFilter] = useState("ALL");
  const [departmentFilter, setDepartmentFilter] = useState("ALL");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get(
      "department_id",
    );
    if (initial) setDepartmentFilter(initial);
  }, []);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, scheduleFilter, departmentFilter]);

  const departments = useQuery({
    queryKey: ["departments", "executions-filter"],
    queryFn: () =>
      api.get<Page<Department>>("/api/v1/admin/departments?page=1&page_size=100"),
  });

  const schedules = useQuery({
    queryKey: ["mail-schedules", "filter"],
    queryFn: () =>
      api.get<Page<MailSchedule>>(
        "/api/v1/admin/mail/schedules?page=1&page_size=100",
      ),
  });

  const params = {
    status: statusFilter === "ALL" ? undefined : statusFilter,
    schedule_id: scheduleFilter === "ALL" ? undefined : scheduleFilter,
    department_id: departmentFilter === "ALL" ? undefined : departmentFilter,
    page,
    page_size: PAGE_SIZE,
  };

  const query = useQuery({
    queryKey: ["mail-executions", params],
    queryFn: () =>
      api.get<Page<MailExecutionSummary>>(
        `/api/v1/admin/mail/executions${queryString(params)}`,
      ),
    refetchInterval: (result) =>
      result.state.data?.items.some((item) => item.status === "RUNNING")
        ? 4000
        : false,
  });

  const detail = useQuery({
    queryKey: ["mail-execution", selectedId],
    queryFn: () =>
      api.get<MailExecutionDetail>(
        `/api/v1/admin/mail/executions/${selectedId}`,
      ),
    enabled: Boolean(selectedId),
  });

  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        title="Executions"
        description="Every attempt to send a schedule, with a per-recipient result."
      />

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
            <SelectTrigger className="w-full sm:w-52">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All departments</SelectItem>
              {(departments.data?.items ?? []).map((department) => (
                <SelectItem key={department.id} value={department.id}>
                  {department.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All statuses</SelectItem>
              <SelectItem value="SUCCEEDED">Succeeded</SelectItem>
              <SelectItem value="PARTIAL">Partial</SelectItem>
              <SelectItem value="FAILED">Failed</SelectItem>
              <SelectItem value="SKIPPED">Skipped</SelectItem>
              <SelectItem value="RUNNING">Running</SelectItem>
            </SelectContent>
          </Select>
          <Select value={scheduleFilter} onValueChange={setScheduleFilter}>
            <SelectTrigger className="w-full sm:w-64">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All schedules</SelectItem>
              {(schedules.data?.items ?? []).map((schedule) => (
                <SelectItem key={schedule.id} value={schedule.id}>
                  {schedule.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {query.isError ? (
            <ErrorState
              message={errorMessage(query.error)}
              onRetry={() => void query.refetch()}
            />
          ) : query.isLoading ? (
            <div className="divide-y">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="flex items-center gap-4 px-4 py-3">
                  <Skeleton className="h-4 w-36" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-5 w-20" />
                </div>
              ))}
            </div>
          ) : query.data && query.data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Started</TableHead>
                    <TableHead>Department</TableHead>
                    <TableHead>Schedule</TableHead>
                    <TableHead>Trigger</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead className="text-right">Sent</TableHead>
                    <TableHead className="text-right">Failed</TableHead>
                    <TableHead className="text-right">Skipped</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.map((execution) => (
                    <TableRow
                      key={execution.id}
                      className="cursor-pointer"
                      onClick={() => setSelectedId(execution.id)}
                    >
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {formatDateTime(execution.started_at)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {execution.department_name}
                      </TableCell>
                      <TableCell className="text-sm">
                        {execution.schedule_name}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {execution.trigger}
                      </TableCell>
                      <TableCell>
                        <ExecutionBadge status={execution.status} />
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {execution.sent_count}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {execution.failed_count}
                      </TableCell>
                      <TableCell className="text-right text-sm tabular-nums">
                        {execution.skipped_count}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  {total} executions
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() =>
                      setPage((current) => Math.max(1, current - 1))
                    }
                  >
                    <ChevronLeft className="size-4" />
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= pageCount}
                    onClick={() =>
                      setPage((current) => Math.min(pageCount, current + 1))
                    }
                  >
                    Next
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              icon={ScrollText}
              title="No executions yet"
              description="Run a schedule manually, or wait for its next slot."
            />
          )}
        </CardContent>
      </Card>

      <Dialog
        open={Boolean(selectedId)}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null);
        }}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {detail.data?.schedule_name ?? "Execution"}
            </DialogTitle>
            <DialogDescription>
              {detail.data
                ? `${formatDateTime(detail.data.started_at)} · ${detail.data.trigger}`
                : null}
            </DialogDescription>
          </DialogHeader>

          {detail.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : detail.isError ? (
            <ErrorState
              message={errorMessage(detail.error)}
              onRetry={() => void detail.refetch()}
            />
          ) : detail.data ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Metric
                  label="Recipients"
                  value={detail.data.recipient_count}
                />
                <Metric label="Sent" value={detail.data.sent_count} />
                <Metric label="Failed" value={detail.data.failed_count} />
                <Metric label="Skipped" value={detail.data.skipped_count} />
              </div>

              {detail.data.error ? (
                <p className="rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
                  {detail.data.error}
                </p>
              ) : null}

              <div className="overflow-hidden rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Recipient</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Detail</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detail.data.deliveries.map((delivery) => (
                      <TableRow key={delivery.id}>
                        <TableCell className="text-sm">
                          {delivery.email}
                        </TableCell>
                        <TableCell>
                          <DeliveryBadge delivery={delivery} />
                        </TableCell>
                        <TableCell className="max-w-md text-xs">
                          {delivery.error ? (
                            <span className="text-destructive">
                              {delivery.error}
                            </span>
                          ) : delivery.subject ? (
                            <details>
                              <summary className="cursor-pointer text-muted-foreground">
                                {delivery.subject}
                              </summary>
                              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-muted/40 p-2">
                                {delivery.body}
                              </pre>
                            </details>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ExecutionBadge({ status }: { status: MailExecutionStatus }) {
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

function DeliveryBadge({ delivery }: { delivery: MailDelivery }) {
  const variant =
    delivery.status === "FAILED"
      ? "destructive"
      : delivery.status === "SENT"
        ? "outline"
        : "secondary";
  return <Badge variant={variant}>{delivery.status}</Badge>;
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
