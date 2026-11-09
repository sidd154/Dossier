"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Cable,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  ConnectorDialog,
  type ConnectorPayload,
} from "@/components/admin/connector-dialog";
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
import { formatDateTime, formatRelative } from "@/lib/format";
import type { Connector, ConnectorValidationResult, Page } from "@/lib/types";

const PAGE_SIZE = 10;

export default function ConnectorsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [page, setPage] = useState(1);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Connector | null>(null);
  const [deleting, setDeleting] = useState<Connector | null>(null);
  const [validatingId, setValidatingId] = useState<string | null>(null);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, typeFilter]);

  const params = {
    q: debouncedSearch,
    type: typeFilter === "ALL" ? undefined : typeFilter,
    page,
    page_size: PAGE_SIZE,
  };

  const query = useQuery({
    queryKey: ["connectors", params],
    queryFn: () =>
      api.get<Page<Connector>>(
        `/api/v1/admin/connectors${queryString(params)}`,
      ),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["connectors"] });
    void queryClient.invalidateQueries({ queryKey: ["audit"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: ConnectorPayload) =>
      api.post<Connector>("/api/v1/admin/connectors", payload),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Connector created");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ConnectorPayload }) =>
      api.patch<Connector>(`/api/v1/admin/connectors/${id}`, payload),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Connector updated");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (connector: Connector) =>
      api.delete(`/api/v1/admin/connectors/${connector.id}`),
    onSuccess: () => {
      toast.success("Connector deleted");
      refresh();
      void queryClient.invalidateQueries({ queryKey: ["data-sources"] });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const validateMutation = useMutation({
    mutationFn: (connector: Connector) =>
      api.post<ConnectorValidationResult>(
        `/api/v1/admin/connectors/${connector.id}/validate`,
      ),
    onMutate: (connector) => setValidatingId(connector.id),
    onSettled: () => setValidatingId(null),
    onSuccess: (result) => {
      if (result.ok) {
        toast.success("Connection verified");
      } else {
        toast.error(result.error ?? "Validation failed");
      }
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const total = query.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <PageHeader
        title="Connectors"
        description="Credentials for the external systems this workspace reads from."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="size-4" />
            Add connector
          </Button>
        }
      />

      <Card className="mb-4">
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search connectors"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All types</SelectItem>
              <SelectItem value="GOOGLE_SHEETS">Google Sheets</SelectItem>
              <SelectItem value="ZOHO_CRM">Zoho CRM</SelectItem>
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
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="flex items-center gap-4 px-4 py-4">
                  <Skeleton className="h-4 w-40" />
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
                    <TableHead>Connector</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Credentials</TableHead>
                    <TableHead>Last verified</TableHead>
                    <TableHead className="w-10" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.map((connector) => (
                    <TableRow key={connector.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium">
                            {connector.name}
                          </p>
                          {!connector.is_active ? (
                            <Badge variant="secondary">Inactive</Badge>
                          ) : null}
                        </div>
                        {connector.last_validation_error ? (
                          <p className="mt-1 flex items-center gap-1 text-xs text-destructive">
                            <ShieldAlert className="size-3.5" />
                            {connector.last_validation_error}
                          </p>
                        ) : null}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {typeLabel(connector.type)}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            connector.has_credentials
                              ? "outline"
                              : "destructive"
                          }
                        >
                          {connector.has_credentials ? "Stored" : "Missing"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {connector.last_validated_at ? (
                          <span className="flex items-center gap-1.5">
                            <CheckCircle2 className="size-3.5 text-emerald-500" />
                            {formatRelative(connector.last_validated_at)}
                          </span>
                        ) : (
                          "Never"
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              aria-label={`Actions for ${connector.name}`}
                            >
                              <MoreHorizontal className="size-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="w-48">
                            <DropdownMenuItem
                              disabled={validatingId === connector.id}
                              onSelect={() =>
                                validateMutation.mutate(connector)
                              }
                            >
                              <RefreshCw
                                className={
                                  validatingId === connector.id
                                    ? "size-4 animate-spin"
                                    : "size-4"
                                }
                              />
                              Verify connection
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onSelect={() => {
                                setEditing(connector);
                                setFormOpen(true);
                              }}
                            >
                              Edit connector
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              variant="destructive"
                              onSelect={() => setDeleting(connector)}
                            >
                              Delete connector
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between gap-3 border-t px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  {total} connectors
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
              icon={Cable}
              title={
                debouncedSearch ? "No connectors match" : "No connectors yet"
              }
              description={
                debouncedSearch
                  ? "Try a different search term."
                  : "Add Google Sheets or Zoho CRM credentials to start syncing."
              }
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditing(null);
                    setFormOpen(true);
                  }}
                >
                  <Plus className="size-4" />
                  Add connector
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>

      <ConnectorDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        connector={editing}
        pending={createMutation.isPending || updateMutation.isPending}
        onSubmit={(payload) => {
          if (editing) updateMutation.mutate({ id: editing.id, payload });
          else createMutation.mutate(payload);
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
              Every data source from this connector will be removed, along with
              its snapshots and department grants. This cannot be undone.
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
              Delete connector
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function typeLabel(type: Connector["type"]): string {
  return type === "GOOGLE_SHEETS" ? "Google Sheets" : "Zoho CRM";
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
