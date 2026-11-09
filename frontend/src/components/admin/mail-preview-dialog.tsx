"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertCircle, Loader2, Play, Send, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { SelectionList } from "@/components/admin/selection-list";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, api } from "@/lib/api";
import type {
  DataSource,
  Department,
  MailPreview,
  MailTemplate,
  Page,
} from "@/lib/types";

export function MailPreviewDialog({
  open,
  onOpenChange,
  template,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template: MailTemplate | null;
}) {
  const [departmentId, setDepartmentId] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<MailPreview | null>(null);
  const [testTo, setTestTo] = useState("");

  const departments = useQuery({
    queryKey: ["departments", "mail-preview"],
    queryFn: () =>
      api.get<Page<Department>>(
        "/api/v1/admin/departments?page=1&page_size=100",
      ),
    enabled: open,
  });
  const sources = useQuery({
    queryKey: ["data-sources", "mail-preview"],
    queryFn: () =>
      api.get<Page<DataSource>>(
        "/api/v1/admin/data-sources?page=1&page_size=100&is_active=true",
      ),
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    setPreview(null);
    setTestTo("");
    setSelected(new Set());
    setDepartmentId("");
  }, [open]);

  useEffect(() => {
    if (!departmentId && departments.data?.items.length) {
      setDepartmentId(departments.data.items[0].id);
    }
  }, [departments.data, departmentId]);

  const toggle = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const generate = useMutation({
    mutationFn: () =>
      api.post<MailPreview>(
        `/api/v1/admin/mail/templates/${template?.id}/preview`,
        { department_id: departmentId, source_ids: Array.from(selected) },
      ),
    onSuccess: (result) => setPreview(result),
    onError: (error) => {
      setPreview(null);
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not generate a preview.",
      );
    },
  });

  const testSend = useMutation({
    mutationFn: () =>
      api.post<MailPreview>(
        `/api/v1/admin/mail/templates/${template?.id}/test-send`,
        {
          to: testTo,
          department_id: departmentId,
          source_ids: Array.from(selected),
        },
      ),
    onSuccess: (result) => {
      if (result.ok) {
        toast.success("Test email sent");
      } else {
        toast.error(result.error ?? "Test send failed");
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not send the test email.",
      );
    },
  });

  const canGenerate =
    Boolean(template) &&
    Boolean(departmentId) &&
    selected.size > 0 &&
    !generate.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Preview · {template?.name}</DialogTitle>
          <DialogDescription>
            Uses current snapshots and this department&apos;s real permissions,
            so the preview matches what a recipient would receive.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Department</Label>
              <Select value={departmentId} onValueChange={setDepartmentId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose a department" />
                </SelectTrigger>
                <SelectContent>
                  {(departments.data?.items ?? []).map((department) => (
                    <SelectItem key={department.id} value={department.id}>
                      {department.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Sources</Label>
              {sources.isLoading ? (
                <Skeleton className="h-32 w-full" />
              ) : (
                <SelectionList
                  options={(sources.data?.items ?? []).map((source) => ({
                    id: source.id,
                    label: source.name,
                    hint: source.connector_name,
                  }))}
                  selected={selected}
                  onToggle={toggle}
                  emptyLabel="No active data sources. Add one first."
                  maxHeight="max-h-52"
                />
              )}
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <ShieldCheck className="size-3.5" />
                Sources this department cannot access are excluded
                automatically.
              </p>
            </div>

            <Button
              type="button"
              onClick={() => generate.mutate()}
              disabled={!canGenerate}
              className="w-full"
            >
              {generate.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Play className="size-4" />
              )}
              Generate preview
            </Button>
          </div>

          <div className="space-y-2">
            <Label>Generated email</Label>
            {preview ? (
              <div className="space-y-2">
                <div className="rounded-lg border bg-muted/30 p-3">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">
                    Subject
                  </p>
                  <p className="text-sm font-medium">{preview.subject}</p>
                </div>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border bg-background p-3 text-sm">
                  {preview.body}
                </pre>
                <div className="flex flex-wrap gap-1.5 text-xs">
                  {preview.sources_used.map((name) => (
                    <span
                      key={name}
                      className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-700 dark:text-emerald-400"
                    >
                      Used: {name}
                    </span>
                  ))}
                  {preview.sources_excluded.map((name) => (
                    <span
                      key={name}
                      className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground"
                    >
                      Excluded: {name}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex h-40 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
                Nothing generated yet
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex flex-1 gap-2">
            <Input
              type="email"
              placeholder="test@example.com"
              value={testTo}
              onChange={(event) => setTestTo(event.target.value)}
            />
            <Button
              type="button"
              variant="outline"
              disabled={
                !testTo ||
                !departmentId ||
                selected.size === 0 ||
                testSend.isPending
              }
              onClick={() => testSend.mutate()}
            >
              {testSend.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Send className="size-4" />
              )}
              Test send
            </Button>
          </div>
          <Button type="button" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>

        {!departments.isLoading && !departments.data?.items.length ? (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="size-3.5" />
            Create a department before previewing.
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
