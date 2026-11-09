"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import {
  DepartmentDialog,
  type DepartmentValues,
} from "@/components/admin/department-dialog";
import { AreaTabs } from "@/components/area-tabs";
import { ErrorState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError, api } from "@/lib/api";
import type { Department } from "@/lib/types";

export default function DepartmentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams<{ id: string }>();
  const departmentId = params.id;
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);

  const department = useQuery({
    queryKey: ["department", departmentId],
    queryFn: () =>
      api.get<Department>(`/api/v1/admin/departments/${departmentId}`),
    enabled: Boolean(departmentId),
  });

  const update = useMutation({
    mutationFn: (values: DepartmentValues) =>
      api.patch<Department>(
        `/api/v1/admin/departments/${departmentId}`,
        values,
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(["department", departmentId], updated);
      void queryClient.invalidateQueries({ queryKey: ["departments"] });
      setEditOpen(false);
      toast.success("Department updated");
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiRequestError
          ? error.message
          : "Could not update the department.",
      ),
  });

  if (department.isError) {
    return (
      <Card className="p-6">
        <ErrorState
          message={
            department.error instanceof ApiRequestError
              ? department.error.message
              : "Could not load this department."
          }
          onRetry={() => void department.refetch()}
        />
      </Card>
    );
  }

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1.5">
          <p className="text-xs text-muted-foreground">
            <Link href="/departments" className="hover:text-foreground">
              Departments
            </Link>
            <span className="mx-1.5">/</span>
            {department.data?.name ?? "…"}
          </p>
          {department.isLoading ? (
            <Skeleton className="h-8 w-56" />
          ) : (
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-semibold tracking-tight">
                {department.data?.name}
              </h1>
              <Badge
                variant={department.data?.is_active ? "outline" : "secondary"}
              >
                {department.data?.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          )}
          <p className="max-w-2xl text-sm text-muted-foreground">
            {department.data?.description ||
              "Members, source access, and scheduled emails for this department."}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setEditOpen(true)}
          disabled={!department.data}
        >
          <Pencil className="size-4" />
          Edit department
        </Button>
      </div>

      <AreaTabs
        tabs={[
          {
            href: `/departments/${departmentId}`,
            label: "Overview",
            exact: true,
          },
          { href: `/departments/${departmentId}/sources`, label: "Sources" },
          { href: `/departments/${departmentId}/emails`, label: "Emails" },
          { href: `/departments/${departmentId}/members`, label: "Members" },
        ]}
      />

      {children}

      <DepartmentDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        department={department.data ?? null}
        pending={update.isPending}
        onSubmit={(values) => update.mutate(values)}
      />
    </div>
  );
}
