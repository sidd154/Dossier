"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ScrollText, Search } from "lucide-react";
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
import { Input } from "@/components/ui/input";
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
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiRequestError, api, queryString } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AuditLog, Page, User } from "@/lib/types";

const PAGE_SIZE = 20;

export default function AuditPage() {
  const [entityType, setEntityType] = useState("ALL");
  const [action, setAction] = useState("");
  const debouncedAction = useDebouncedValue(action);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditLog | null>(null);

  useEffect(() => {
    setPage(1);
  }, [entityType, debouncedAction]);

  const params = {
    entity_type: entityType === "ALL" ? undefined : entityType,
    action: debouncedAction,
    page,
    page_size: PAGE_SIZE,
  };

  const query = useQuery({
    queryKey: ["audit", params],
    queryFn: () =>
      api.get<Page<AuditLog>>(`/api/v1/admin/audit-logs${queryString(params)}`),
  });

  const usersQuery = useQuery({
    queryKey: ["users", "audit-actors"],
    queryFn: () =>
      api.get<Page<User>>("/api/v1/admin/users?page=1&page_size=100"),
  });

  const actors = new Map(
    (usersQuery.data?.items ?? []).map((user) => [user.id, user.full_name]),
  );

  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        title="Audit log"
        description="An append-only record of every administrative change."
      />

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Filter by action, e.g. user.created"
              value={action}
              onChange={(event) => setAction(event.target.value)}
            />
          </div>
          <Select value={entityType} onValueChange={setEntityType}>
            <SelectTrigger className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All entities</SelectItem>
              <SelectItem value="user">Users</SelectItem>
              <SelectItem value="department">Departments</SelectItem>
              <SelectItem value="organisation">Organisation</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {query.isError ? (
            <ErrorState
              message={
                query.error instanceof ApiRequestError
                  ? query.error.message
                  : "Could not load the audit log."
              }
              onRetry={() => void query.refetch()}
            />
          ) : query.isLoading ? (
            <div className="divide-y">
              {Array.from({ length: 8 }).map((_, index) => (
                <div key={index} className="flex items-center gap-4 px-4 py-3">
                  <Skeleton className="h-5 w-28" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-4 w-32" />
                </div>
              ))}
            </div>
          ) : query.data && query.data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead className="hidden md:table-cell">IP</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.map((entry) => (
                    <TableRow
                      key={entry.id}
                      className="cursor-pointer"
                      onClick={() => setSelected(entry)}
                    >
                      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {formatDateTime(entry.created_at)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={actionVariant(entry.action)}>
                          {entry.action}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className="capitalize">{entry.entity_type}</span>
                        {entry.entity_id ? (
                          <span className="ml-1.5 font-mono text-xs text-muted-foreground">
                            {entry.entity_id.slice(0, 8)}
                          </span>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-sm">
                        {entry.actor_user_id
                          ? (actors.get(entry.actor_user_id) ?? "Unknown")
                          : "System"}
                      </TableCell>
                      <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">
                        {entry.ip ?? "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  {(page - 1) * PAGE_SIZE + 1}–
                  {Math.min(page * PAGE_SIZE, total)} of {total}
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
              title="No audit entries"
              description="Administrative changes will appear here as they happen."
            />
          )}
        </CardContent>
      </Card>

      <Dialog
        open={Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selected?.action}</DialogTitle>
            <DialogDescription>
              {selected ? formatDateTime(selected.created_at) : null}
              {selected?.entity_id ? ` · ${selected.entity_id}` : ""}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <JsonBlock title="Before" value={selected?.before ?? null} />
            <JsonBlock title="After" value={selected?.after ?? null} />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function JsonBlock({
  title,
  value,
}: {
  title: string;
  value: Record<string, unknown> | null;
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <pre className="max-h-64 overflow-auto rounded-lg border bg-muted/40 p-3 font-mono text-xs">
        {value ? JSON.stringify(value, null, 2) : "—"}
      </pre>
    </div>
  );
}

function actionVariant(action: string) {
  if (action.endsWith(".deleted") || action.endsWith(".disabled"))
    return "destructive";
  if (action.endsWith(".created")) return "default";
  return "secondary";
}
