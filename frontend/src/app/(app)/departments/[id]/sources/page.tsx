"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Database, Loader2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, api } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { DepartmentSources } from "@/lib/types";

export default function DepartmentSourcesPage() {
  const params = useParams<{ id: string }>();
  const departmentId = params.id;
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const query = useQuery({
    queryKey: ["department-sources", departmentId],
    queryFn: () =>
      api.get<DepartmentSources>(
        `/api/v1/admin/departments/${departmentId}/sources`,
      ),
    enabled: Boolean(departmentId),
  });

  useEffect(() => {
    if (!query.data) return;
    setSelected(
      new Set(
        query.data.entries
          .filter((entry) => entry.granted)
          .map((entry) => entry.data_source_id),
      ),
    );
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: () =>
      api.put<DepartmentSources>(
        `/api/v1/admin/departments/${departmentId}/sources`,
        { data_source_ids: Array.from(selected) },
      ),
    onSuccess: (result) => {
      queryClient.setQueryData(["department-sources", departmentId], result);
      toast.success("Source access saved");
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not save source access.",
      ),
  });

  const original = new Set(
    query.data?.entries
      .filter((entry) => entry.granted)
      .map((entry) => entry.data_source_id) ?? [],
  );
  const dirty =
    original.size !== selected.size ||
    Array.from(selected).some((id) => !original.has(id));

  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div>
      <PageHeader
        title="Sources"
        description="What this department may draw from in its emails. A schedule can narrow this further, but never widen it."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" asChild>
              <Link href="/data/sources">
                Manage sources
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button
              onClick={() => mutation.mutate()}
              disabled={!dirty || mutation.isPending}
            >
              {mutation.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : null}
              Save access
            </Button>
          </div>
        }
      />

      {query.isError ? (
        <Card>
          <ErrorState
            message={
              query.error instanceof ApiRequestError
                ? query.error.message
                : "Could not load this department's sources."
            }
            onRetry={() => void query.refetch()}
          />
        </Card>
      ) : query.isLoading ? (
        <Card>
          <CardContent className="space-y-2 p-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : query.data?.entries.length ? (
        <Card>
          <CardContent className="divide-y p-0">
            {query.data.entries.map((entry) => (
              <label
                key={entry.data_source_id}
                className={cn(
                  "flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/40",
                  !entry.is_active && "opacity-60",
                )}
              >
                <input
                  type="checkbox"
                  className="size-4 rounded border-input accent-primary"
                  checked={selected.has(entry.data_source_id)}
                  onChange={() => toggle(entry.data_source_id)}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{entry.name}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {entry.connector_name} · {entry.kind}
                  </p>
                </div>
                <div className="hidden items-center gap-2 text-xs text-muted-foreground sm:flex">
                  {entry.last_sync_at ? (
                    <>
                      <SyncDot status={entry.snapshot_status} />
                      synced {formatRelative(entry.last_sync_at)}
                    </>
                  ) : (
                    "Never synced"
                  )}
                </div>
                <Badge variant={entry.is_active ? "outline" : "secondary"}>
                  {entry.is_active ? "Active" : "Inactive"}
                </Badge>
              </label>
            ))}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={Database}
            title="No sources are registered"
            description="Connect a provider and register at least one source before granting access."
            action={
              <Button variant="outline" asChild>
                <Link href="/data/sources">Go to Data → Sources</Link>
              </Button>
            }
          />
        </Card>
      )}

      <p className="mt-4 flex items-center gap-1.5 text-xs text-muted-foreground">
        <ShieldCheck className="size-3.5" />
        Access applies immediately to the next scheduled run. Inactive sources
        are ignored even when granted.
      </p>
    </div>
  );
}

function SyncDot({
  status,
}: {
  status: "READY" | "PARTIAL" | "FAILED" | null;
}) {
  const colour =
    status === "READY"
      ? "bg-emerald-500"
      : status === "PARTIAL"
        ? "bg-amber-500"
        : status === "FAILED"
          ? "bg-destructive"
          : "bg-muted-foreground";
  return (
    <span className={cn("size-1.5 rounded-full", colour)} aria-hidden="true" />
  );
}
