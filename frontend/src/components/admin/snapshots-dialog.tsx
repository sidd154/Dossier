"use client";

import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";

import { EmptyState, ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiRequestError, api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { DataSource, Page, Snapshot } from "@/lib/types";

export function SnapshotsDialog({
  open,
  onOpenChange,
  source,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  source: DataSource | null;
}) {
  const query = useQuery({
    queryKey: ["snapshots", source?.id],
    queryFn: () =>
      api.get<Page<Snapshot>>(
        `/api/v1/admin/data-sources/${source?.id}/snapshots?page=1&page_size=25`,
      ),
    enabled: Boolean(open && source),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{source?.name ?? "Snapshots"}</DialogTitle>
          <DialogDescription>
            Immutable captures. The source always reads from the most recent
            one.
          </DialogDescription>
        </DialogHeader>

        {query.isError ? (
          <ErrorState
            message={
              query.error instanceof ApiRequestError
                ? query.error.message
                : "Could not load snapshots."
            }
            onRetry={() => void query.refetch()}
          />
        ) : query.isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </div>
        ) : query.data && query.data.items.length > 0 ? (
          <div className="overflow-hidden rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Captured</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Records</TableHead>
                  <TableHead>Schema</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((snapshot) => (
                  <TableRow key={snapshot.id}>
                    <TableCell className="text-sm">
                      <div className="flex items-center gap-2">
                        {formatDateTime(snapshot.captured_at)}
                        {snapshot.id === source?.current_snapshot?.id ? (
                          <Badge variant="outline">Current</Badge>
                        ) : null}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          snapshot.status === "FAILED"
                            ? "destructive"
                            : "secondary"
                        }
                      >
                        {snapshot.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {snapshot.record_count}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {snapshot.schema_hash?.slice(0, 10) ?? "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState
            icon={History}
            title="No snapshots yet"
            description="Run a sync to create the first capture."
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
