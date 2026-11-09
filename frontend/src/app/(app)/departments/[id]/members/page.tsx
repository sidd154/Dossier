"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, UserPlus, Users } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState } from "@/components/states";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { formatRelative, initials } from "@/lib/format";
import type { Page, User } from "@/lib/types";

export default function DepartmentMembersPage() {
  const params = useParams<{ id: string }>();
  const departmentId = params.id;

  const query = useQuery({
    queryKey: ["users", "department-members", departmentId],
    queryFn: () =>
      api.get<Page<User>>(
        `/api/v1/admin/users${queryString({
          department_id: departmentId,
          page: 1,
          page_size: 100,
        })}`,
      ),
    enabled: Boolean(departmentId),
  });

  return (
    <div>
      <PageHeader
        title="Members"
        description="Active members receive this department's emails. Disabled accounts are skipped."
        actions={
          <Button variant="outline" asChild>
            <Link href={`/settings/users?department_id=${departmentId}`}>
              <UserPlus className="size-4" />
              Add member
            </Link>
          </Button>
        }
      />

      {query.isError ? (
        <Card>
          <ErrorState
            message={
              query.error instanceof ApiRequestError
                ? query.error.message
                : "Could not load members."
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
      ) : query.data && query.data.items.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last sign-in</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="size-8">
                          <AvatarFallback className="text-xs font-semibold">
                            {initials(user.full_name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">
                            {user.full_name}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {user.email}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          user.role === "ADMIN" ? "default" : "secondary"
                        }
                      >
                        {user.role === "ADMIN" ? "Admin" : "Member"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          user.status === "ACTIVE" ? "outline" : "secondary"
                        }
                      >
                        {user.status === "ACTIVE" ? "Active" : "Disabled"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatRelative(user.last_login_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <EmptyState
            icon={Users}
            title="No members yet"
            description="Add an account to this department so there is someone to email."
            action={
              <Button variant="outline" asChild>
                <Link href={`/settings/users?department_id=${departmentId}`}>
                  Add member
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            }
          />
        </Card>
      )}

      <p className="mt-4 text-xs text-muted-foreground">
        Accounts, roles, and resets are managed in{" "}
        <Link href="/settings/users" className="underline">
          Settings → Users
        </Link>
        .
      </p>
    </div>
  );
}
