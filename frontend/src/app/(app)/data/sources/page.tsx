"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  History,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  AddSourceDialog,
  type NewDataSourcePayload,
} from "@/components/admin/add-source-dialog";
import { SnapshotsDialog } from "@/components/admin/snapshots-dialog";
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
import { formatRelative } from "@/lib/format";
import type { Connector, DataSource, Page, SyncJob } from "@/lib/types";

const PAGE_SIZE = 10;

export default function DataSourcesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [connectorFilter, setConnectorFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const [addOpen, setAddOpen] = useState(false);
  const [deleting, setDeleting] = useState<DataSource | null>(null);
  const [historyFor, setHistoryFor] = useState<DataSource | null>(null);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, connectorFilter, statusFilter]);

  const params = {
    q: debouncedSearch,
    connector_id: connectorFilter === "ALL" ? undefined : connectorFilter,
    is_active:
      statusFilter === "ALL"
        ? undefined
        : statusFilter === "ACTIVE"
          ? true
          : false,
    page,
    page_size: PAGE_SIZE,
  };

  const query = useQuery({
    queryKey: ["data-sources", params],
    queryFn: () =>
      api.get<Page<DataSource>>(
        `/api/v1/admin/data-sources${queryString(params)}`,
      ),
  });

  const connectorsQuery = useQuery({
    queryKey: ["connectors", "picker"],
    queryFn: () =>
      api.get<Page<Connector>>(
        "/api/v1/admin/connectors?page=1&page_size=100&is_active=true",
      ),
  });
  const connectors = (connectorsQuery.data?.items ?? []).filter(
    (connector) => connector.has_credentials,
  );

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["data-sources"] });
    void queryClient.invalidateQueries({ queryKey: ["sync-jobs"] });
    void queryClient.invalidateQueries({ queryKey: ["snapshots"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["audit"] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: NewDataSourcePayload) =>
      api.post<DataSource>("/api/v1/admin/data-sources", payload),
    onSuccess: () => {
      setAddOpen(false);
      toast.success("Data source added");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const syncMutation = useMutation({
    mutationFn: (source: DataSource) =>
      api.post<SyncJob>(`/api/v1/admin/data-sources/${source.id}/sync`),
    onMutate: (source) => setSyncingId(source.id),
    onSettled: () => setSyncingId(null),
    onSuccess: (job) => {
      if (job.status === "SUCCEEDED") {
        toast.success(`Synced ${job.record_count ?? 0} records`);
      } else if (job.status === "PARTIAL") {
        toast.warning(
          `Synced ${job.record_count ?? 0} records, but the source returned a partial page`,
        );
      } else {
        toast.error(job.error ?? "Sync failed");
      }
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ source, next }: { source: DataSource; next: boolean }) =>
      api.patch<DataSource>(`/api/v1/admin/data-sources/${source.id}`, {
        is_active: next,
      }),
    onSuccess: () => refresh(),
    onError: (error) => toast.error(errorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (source: DataSource) =>
      api.delete(`/api/v1/admin/data-sources/${source.id}`),
    onSuccess: () => {
      toast.success("Data source removed");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        title="Data sources"
        description="The specific sheets and CRM modules this workspace syncs."
        actions={
          <Button
            onClick={() => setAddOpen(true)}
            disabled={!connectors.length}
          >
            <Plus className="size-4" />
            Add source
          </Button>
        }
      />

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search data sources"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex">
            <Select value={connectorFilter} onValueChange={setConnectorFilter}>
              <SelectTrigger className="w-full sm:w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All connectors</SelectItem>
                {(connectorsQuery.data?.items ?? []).map((connector) => (
                  <SelectItem key={connector.id} value={connector.id}>
                    {connector.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ALL">All statuses</SelectItem>
                <SelectItem value="ACTIVE">Active</SelectItem>
                <SelectItem value="INACTIVE">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
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
              {Array.from({ length: 5 }).map((_, index) => (
                <div key={index} className="flex items-center gap-4 px-4 py-4">
                  <Skeleton className="h-4 w-44" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-5 w-24" />
                </div>
              ))}
            </div>
          ) : query.data && query.data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Source</TableHead>
                    <TableHead>Current snapshot</TableHead>
                    <TableHead>Records</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.map((source) => (
                    <TableRow key={source.id}>
                      <TableCell>
                        <p className="text-sm font-medium">{source.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {source.connector_name} · {source.kind}
                        </p>
                      </TableCell>
                      <TableCell className="text-sm">
                        {source.current_snapshot ? (
                          <div className="flex items-center gap-2">
                            <SnapshotDot
                              status={source.current_snapshot.status}
                            />
                            <span>
                              {formatRelative(
                                source.current_snapshot.captured_at,
                              )}
                            </span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">
                            Never synced
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm tabular-nums">
                        {source.current_snapshot?.record_count ?? "—"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={source.is_active ? "outline" : "secondary"}
                        >
                          {source.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Actions for ${source.name}`}
                            >
                              <MoreHorizontal className="size-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem
                              disabled={
                                !source.is_active || syncingId === source.id
                              }
                              onSelect={() => syncMutation.mutate(source)}
                            >
                              <RefreshCw
                                className={
                                  syncingId === source.id
                                    ? "size-4 animate-spin"
                                    : "size-4"
                                }
                              />
                              Sync now
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => setHistoryFor(source)}
                            >
                              <History className="size-4" />
                              Snapshot history
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              onSelect={() =>
                                toggleMutation.mutate({
                                  source,
                                  next: !source.is_active,
                                })
                              }
                            >
                              {source.is_active ? "Deactivate" : "Activate"}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={() => setDeleting(source)}
                            >
                              Remove source
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
                <p className="text-xs text-muted-foreground">{total} sources</p>
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
              icon={Database}
              title={
                debouncedSearch ? "No sources match" : "No data sources yet"
              }
              description={
                connectors.length
                  ? "Choose a connector and register one of its sheets or modules."
                  : "Add a connector with credentials first, then register its sources."
              }
              action={
                <Button
                  variant="outline"
                  disabled={!connectors.length}
                  onClick={() => setAddOpen(true)}
                >
                  <Plus className="size-4" />
                  Add source
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>

      <AddSourceDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        connectors={connectors}
        pending={createMutation.isPending}
        onSubmit={(payload) => createMutation.mutate(payload)}
      />

      <SnapshotsDialog
        open={Boolean(historyFor)}
        onOpenChange={(open) => {
          if (!open) setHistoryFor(null);
        }}
        source={historyFor}
      />

      <AlertDialog
        open={Boolean(deleting)}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {deleting?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Its snapshots and department grants are deleted with it. Chat and
              mail will stop seeing this data immediately.
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
              Remove source
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SnapshotDot({ status }: { status: "READY" | "PARTIAL" | "FAILED" }) {
  const colour =
    status === "READY"
      ? "bg-emerald-500"
      : status === "PARTIAL"
        ? "bg-amber-500"
        : "bg-destructive";
  return (
    <span className={`size-1.5 rounded-full ${colour}`} aria-hidden="true" />
  );
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
