"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, FileText, MoreHorizontal, Plus, Search } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { MailPreviewDialog } from "@/components/admin/mail-preview-dialog";
import {
  MailTemplateDialog,
  type MailTemplateValues,
} from "@/components/admin/mail-template-dialog";
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
import type { MailTemplate, Page } from "@/lib/types";

export default function MailTemplatesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<MailTemplate | null>(null);
  const [previewing, setPreviewing] = useState<MailTemplate | null>(null);
  const [deleting, setDeleting] = useState<MailTemplate | null>(null);

  const query = useQuery({
    queryKey: ["mail-templates", debouncedSearch],
    queryFn: () =>
      api.get<Page<MailTemplate>>(
        `/api/v1/admin/mail/templates${queryString({
          q: debouncedSearch,
          page: 1,
          page_size: 100,
        })}`,
      ),
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["mail-templates"] });
    void queryClient.invalidateQueries({ queryKey: ["audit"] });
  };

  const createMutation = useMutation({
    mutationFn: (values: MailTemplateValues) =>
      api.post<MailTemplate>("/api/v1/admin/mail/templates", values),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Template created");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: MailTemplateValues }) =>
      api.patch<MailTemplate>(`/api/v1/admin/mail/templates/${id}`, values),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Template updated");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const deleteMutation = useMutation({
    mutationFn: (template: MailTemplate) =>
      api.delete(`/api/v1/admin/mail/templates/${template.id}`),
    onSuccess: () => {
      toast.success("Template deleted");
      refresh();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <div>
      <PageHeader
        title="Templates"
        description="Each template is a system prompt. Recipients' departments decide which data can appear in the generated body."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="size-4" />
            New template
          </Button>
        }
      />

      <Card className="mb-4">
        <CardContent className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9"
              placeholder="Search templates"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
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
              {Array.from({ length: 4 }).map((_, index) => (
                <div key={index} className="flex items-center gap-4 px-4 py-4">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 flex-1" />
                  <Skeleton className="h-5 w-16" />
                </div>
              ))}
            </div>
          ) : query.data && query.data.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Template</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((template) => (
                  <TableRow key={template.id}>
                    <TableCell>
                      <p className="text-sm font-medium">{template.name}</p>
                      {template.description ? (
                        <p className="max-w-md truncate text-xs text-muted-foreground">
                          {template.description}
                        </p>
                      ) : null}
                    </TableCell>
                    <TableCell className="max-w-xs truncate font-mono text-xs text-muted-foreground">
                      {template.subject_template}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={template.is_active ? "outline" : "secondary"}
                      >
                        {template.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(template.updated_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Actions for ${template.name}`}
                          >
                            <MoreHorizontal className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-44">
                          <DropdownMenuItem
                            onSelect={() => setPreviewing(template)}
                          >
                            <Eye className="size-4" />
                            Preview
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() => {
                              setEditing(template);
                              setFormOpen(true);
                            }}
                          >
                            Edit template
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant="destructive"
                            onSelect={() => setDeleting(template)}
                          >
                            Delete template
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <EmptyState
              icon={FileText}
              title={
                debouncedSearch ? "No templates match" : "No templates yet"
              }
              description="Create a prompt that describes the email you want generated."
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setEditing(null);
                    setFormOpen(true);
                  }}
                >
                  <Plus className="size-4" />
                  New template
                </Button>
              }
            />
          )}
        </CardContent>
      </Card>

      <MailTemplateDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        template={editing}
        pending={createMutation.isPending || updateMutation.isPending}
        onSubmit={(values) => {
          if (editing) updateMutation.mutate({ id: editing.id, values });
          else createMutation.mutate(values);
        }}
      />

      <MailPreviewDialog
        open={Boolean(previewing)}
        onOpenChange={(open) => {
          if (!open) setPreviewing(null);
        }}
        template={previewing}
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
              Templates used by a schedule cannot be deleted. This cannot be
              undone.
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
              Delete template
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
