"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Building2, Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import {
  DepartmentDialog,
  type DepartmentValues,
} from "@/components/admin/department-dialog";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
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
import { ApiRequestError, api, queryString } from "@/lib/api";
import type { Department, Page } from "@/lib/types";

export default function DepartmentsPage() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Department | null>(null);

  const query = useQuery({
    queryKey: ["departments", "home"],
    queryFn: () =>
      api.get<Page<Department>>(
        `/api/v1/admin/departments${queryString({ page: 1, page_size: 100 })}`,
      ),
  });

  const createMutation = useMutation({
    mutationFn: (values: DepartmentValues) =>
      api.post<Department>("/api/v1/admin/departments", values),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Department created");
      void queryClient.invalidateQueries({ queryKey: ["departments"] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: DepartmentValues }) =>
      api.patch<Department>(`/api/v1/admin/departments/${id}`, values),
    onSuccess: () => {
      setFormOpen(false);
      toast.success("Department updated");
      void queryClient.invalidateQueries({ queryKey: ["departments"] });
      void queryClient.invalidateQueries({
        queryKey: ["department", editing?.id],
      });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <div>
      <PageHeader
        title="Departments"
        description="Everything in the product is organised around a department: its members, the sources it may use, and the emails it receives."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="size-4" />
            New department
          </Button>
        }
      />

      {query.isError ? (
        <Card>
          <ErrorState
            message={errorMessage(query.error)}
            onRetry={() => void query.refetch()}
          />
        </Card>
      ) : query.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-40 w-full" />
          ))}
        </div>
      ) : query.data && query.data.items.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {query.data.items.map((department) => (
            <Card key={department.id} className="group relative">
              <Link
                href={`/departments/${department.id}`}
                className="absolute inset-0 z-0 rounded-xl"
                aria-label={`Open ${department.name}`}
              />
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{department.name}</CardTitle>
                  <Badge
                    variant={department.is_active ? "outline" : "secondary"}
                    className="shrink-0"
                  >
                    {department.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <CardDescription className="line-clamp-2 min-h-10">
                  {department.description || "No description"}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex items-center justify-between pt-2">
                <span className="text-xs text-muted-foreground">
                  {department.slug}
                </span>
                <div className="relative z-10 flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Edit ${department.name}`}
                    onClick={() => {
                      setEditing(department);
                      setFormOpen(true);
                    }}
                  >
                    <Pencil className="size-4" />
                  </Button>
                  <Button variant="ghost" size="sm" asChild>
                    <Link href={`/departments/${department.id}`}>
                      Open
                      <ArrowRight className="size-4" />
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <EmptyState
            icon={Building2}
            title="No departments yet"
            description="Create the first department to connect data and schedule emails."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                <Plus className="size-4" />
                New department
              </Button>
            }
          />
        </Card>
      )}

      <DepartmentDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        department={editing}
        pending={createMutation.isPending || updateMutation.isPending}
        onSubmit={(values) => {
          if (editing) updateMutation.mutate({ id: editing.id, values });
          else createMutation.mutate(values);
        }}
      />
    </div>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "Something went wrong. Try again.";
}
